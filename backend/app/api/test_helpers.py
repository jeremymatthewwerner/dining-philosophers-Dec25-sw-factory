"""Test helper endpoints for integration testing.

These endpoints are only used in test environments to trigger specific error conditions.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import WSMessage, WSMessageType, manager
from app.core.config import get_settings, is_test_mode
from app.core.database import get_db
from app.exceptions import BillingError
from app.models import User

router = APIRouter(prefix="/test")


class TriggerErrorRequest(BaseModel):
    """Request body for trigger-error endpoint.

    Attributes:
        conversation_id: UUID of the conversation to send the error message to.
                        Must have active WebSocket connections.
        error_message: The error message content to display in the frontend.
                      Example: "API billing error: API credit limit reached."
    """

    conversation_id: str
    error_message: str


@router.get("/billing-error")
async def trigger_billing_error() -> None:
    """Test endpoint that raises BillingError for integration testing.

    This endpoint is used by integration tests to verify that:
    1. BillingError exception is properly caught by the exception handler
    2. HTTP 503 response is returned
    3. GitHub issue filing is triggered in background
    """
    raise BillingError("Test billing error for integration testing")


@router.post("/trigger-error")
async def trigger_error(request: TriggerErrorRequest) -> dict[str, str]:
    """Test endpoint that sends ERROR type WebSocket messages to a conversation.

    **SECURITY**: This endpoint is only available when TEST_MODE=true and is used
    by E2E tests to verify error handling in the frontend. In production
    (TEST_MODE=false), requests to this endpoint return 403 Forbidden.

    **Purpose**: Allows E2E tests to simulate billing errors and other error
    conditions that would normally be triggered by the backend, without needing
    to actually cause those errors to occur (which may be difficult or impossible
    to reliably reproduce in test environments).

    **Usage Example** (from E2E test):
    ```typescript
    // 1. Create a conversation via API
    const { id: conversationId } = await createConversationViaAPI(
      page,
      'Test error handling',
      ['Aristotle']
    );

    // 2. Navigate to the conversation and wait for WebSocket connection
    await page.goto(`/conversation/${conversationId}`);
    await page.waitForSelector('[data-testid="chat-area"]');
    await page.waitForTimeout(1500); // Wait for WebSocket connection

    // 3. Trigger error via backend endpoint
    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    await page.request.post('http://localhost:8000/api/test/trigger-error', {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        conversation_id: conversationId,
        error_message: 'API billing error: API credit limit reached.'
      }
    });

    // 4. Verify error banner appears in UI
    await expect(page.getByTestId('error-banner')).toBeVisible();
    ```

    **Request Body**:
    ```json
    {
      "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
      "error_message": "API billing error: API credit limit reached."
    }
    ```

    **Success Response** (200 OK):
    ```json
    {
      "status": "success",
      "message": "Error message broadcast to conversation 550e8400-e29b-41d4-a716-446655440000"
    }
    ```

    **Error Responses**:
    - 403 Forbidden: TEST_MODE is not enabled
    - 404 Not Found: No active WebSocket connections for the conversation
    - 422 Unprocessable Entity: Invalid request body (missing fields)

    Args:
        request: Contains conversation_id and error_message

    Returns:
        Success message confirming the error was broadcast

    Raises:
        HTTPException: 403 if not in test mode, 404 if conversation not found
    """
    if not is_test_mode():
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available in test mode",
        )

    # Check if conversation has active connections
    if not manager.is_conversation_active(request.conversation_id):
        raise HTTPException(
            status_code=404,
            detail=f"No active connections for conversation {request.conversation_id}",
        )

    # Broadcast ERROR message to all connections in the conversation
    error_ws_message = WSMessage(
        type=WSMessageType.ERROR,
        conversation_id=request.conversation_id,
        content=request.error_message,
    )

    await manager.broadcast_to_conversation(request.conversation_id, error_ws_message)

    return {
        "status": "success",
        "message": f"Error message broadcast to conversation {request.conversation_id}",
    }


# Test user prefixes that can be cleaned up
TEST_USER_PREFIXES = ("smoketest_", "canary_")


class CleanupResponse(BaseModel):
    """Response schema for test user cleanup."""

    deleted_count: int
    deleted_users: list[str]


@router.delete("/cleanup-test-users", response_model=CleanupResponse)
async def cleanup_test_users(
    secret: str,
    db: AsyncSession = Depends(get_db),
) -> CleanupResponse:
    """Delete test users created by smoke/canary tests.

    **SECURITY**: This endpoint is protected by TEST_CLEANUP_SECRET and only
    deletes users whose usernames start with known test prefixes (smoketest_,
    canary_). This ensures that only automated test accounts are removed.

    **Purpose**: CI workflows create test users to verify the auth flow works
    in production. These users accumulate over time and clutter the database.
    This endpoint allows workflows to clean up after themselves.

    **Usage Example** (from CI workflow):
    ```bash
    curl -X DELETE "$BACKEND_URL/api/test/cleanup-test-users?secret=$TEST_CLEANUP_SECRET"
    ```

    **Query Parameters**:
    - secret: The TEST_CLEANUP_SECRET value (required)

    **Success Response** (200 OK):
    ```json
    {
      "deleted_count": 3,
      "deleted_users": ["smoketest_1704412800", "canary_1704412900_12345", ...]
    }
    ```

    **Error Responses**:
    - 403 Forbidden: Invalid or missing secret
    - 500 Internal Server Error: Database error

    Args:
        secret: The cleanup secret to authenticate the request

    Returns:
        Count and usernames of deleted test users
    """
    settings = get_settings()

    # Verify secret is configured
    if not settings.test_cleanup_secret:
        raise HTTPException(
            status_code=403,
            detail="Test cleanup secret not configured",
        )

    # Verify provided secret matches
    if secret != settings.test_cleanup_secret:
        raise HTTPException(
            status_code=403,
            detail="Invalid cleanup secret",
        )

    # Find all test users
    deleted_users: list[str] = []
    for prefix in TEST_USER_PREFIXES:
        result = await db.execute(select(User).where(User.username.startswith(prefix)))
        users = result.scalars().all()
        for user in users:
            deleted_users.append(user.username)

    if not deleted_users:
        return CleanupResponse(deleted_count=0, deleted_users=[])

    # Delete all test users
    for prefix in TEST_USER_PREFIXES:
        await db.execute(delete(User).where(User.username.startswith(prefix)))

    await db.commit()

    return CleanupResponse(
        deleted_count=len(deleted_users),
        deleted_users=deleted_users,
    )
