"""Test helper endpoints for integration testing.

These endpoints are only used in test environments to trigger specific error conditions.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.websocket import WSMessage, WSMessageType, manager
from app.core.config import is_test_mode
from app.exceptions import BillingError

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
