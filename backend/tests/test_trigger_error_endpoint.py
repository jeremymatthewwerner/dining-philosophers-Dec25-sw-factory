"""Unit tests for the trigger-error test endpoint."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.websocket import WSMessage, WSMessageType
from app.core.database import get_db
from app.main import app
from app.models import Base


@pytest.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite engine for testing."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database override."""
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_trigger_error_endpoint_forbidden_when_not_in_test_mode(client: AsyncClient) -> None:
    """Test that trigger-error endpoint returns 403 when TEST_MODE is disabled."""
    # Arrange: Ensure test mode is disabled
    with patch("app.api.test_helpers.is_test_mode", return_value=False):
        # Act: Call the trigger-error endpoint
        response = await client.post(
            "/api/test/trigger-error",
            json={
                "conversation_id": "test-conv-123",
                "error_message": "Test error",
            },
        )

        # Assert: Should return 403 Forbidden
        assert response.status_code == 403
        response_json = response.json()
        assert "detail" in response_json
        assert "test mode" in response_json["detail"].lower()


@pytest.mark.asyncio
async def test_trigger_error_endpoint_not_found_when_conversation_not_active(
    client: AsyncClient,
) -> None:
    """Test that trigger-error endpoint returns 404 when conversation has no active connections."""
    # Arrange: Enable test mode and mock inactive conversation
    with (
        patch("app.api.test_helpers.is_test_mode", return_value=True),
        patch("app.api.test_helpers.manager.is_conversation_active", return_value=False),
    ):
        # Act: Call the trigger-error endpoint
        response = await client.post(
            "/api/test/trigger-error",
            json={
                "conversation_id": "test-conv-123",
                "error_message": "Test error",
            },
        )

        # Assert: Should return 404 Not Found
        assert response.status_code == 404
        response_json = response.json()
        assert "detail" in response_json
        assert "no active connections" in response_json["detail"].lower()


@pytest.mark.asyncio
async def test_trigger_error_endpoint_broadcasts_error_message(client: AsyncClient) -> None:
    """Test that trigger-error endpoint successfully broadcasts ERROR message to conversation."""
    # Arrange: Enable test mode and mock active conversation
    mock_broadcast = AsyncMock()
    conversation_id = "test-conv-123"
    error_message = "Test billing error"

    with (
        patch("app.api.test_helpers.is_test_mode", return_value=True),
        patch("app.api.test_helpers.manager.is_conversation_active", return_value=True),
        patch("app.api.test_helpers.manager.broadcast_to_conversation", mock_broadcast),
    ):
        # Act: Call the trigger-error endpoint
        response = await client.post(
            "/api/test/trigger-error",
            json={
                "conversation_id": conversation_id,
                "error_message": error_message,
            },
        )

        # Assert: Should return 200 OK with success message
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["status"] == "success"
        assert conversation_id in response_json["message"]

        # Assert: broadcast_to_conversation was called with correct arguments
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args
        assert call_args[0][0] == conversation_id  # conversation_id argument

        # Verify WSMessage structure
        ws_message = call_args[0][1]  # WSMessage argument
        assert isinstance(ws_message, WSMessage)
        assert ws_message.type == WSMessageType.ERROR
        assert ws_message.conversation_id == conversation_id
        assert ws_message.content == error_message


@pytest.mark.asyncio
async def test_trigger_error_endpoint_validates_request_body(client: AsyncClient) -> None:
    """Test that trigger-error endpoint validates request body fields."""
    # Arrange: Enable test mode
    with patch("app.api.test_helpers.is_test_mode", return_value=True):
        # Act: Call endpoint with missing fields
        response = await client.post(
            "/api/test/trigger-error",
            json={"conversation_id": "test-conv-123"},  # Missing error_message
        )

        # Assert: Should return 422 Unprocessable Entity
        assert response.status_code == 422

        # Act: Call endpoint with empty body
        response = await client.post("/api/test/trigger-error", json={})

        # Assert: Should return 422 Unprocessable Entity
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_trigger_error_endpoint_accepts_custom_error_messages(client: AsyncClient) -> None:
    """Test that trigger-error endpoint accepts custom error messages."""
    # Arrange: Enable test mode and mock active conversation
    mock_broadcast = AsyncMock()
    custom_error = "Custom billing quota exceeded error message"
    conversation_id = "test-conv-456"

    with (
        patch("app.api.test_helpers.is_test_mode", return_value=True),
        patch("app.api.test_helpers.manager.is_conversation_active", return_value=True),
        patch("app.api.test_helpers.manager.broadcast_to_conversation", mock_broadcast),
    ):
        # Act: Call the trigger-error endpoint with custom message
        response = await client.post(
            "/api/test/trigger-error",
            json={
                "conversation_id": conversation_id,
                "error_message": custom_error,
            },
        )

        # Assert: Should succeed
        assert response.status_code == 200

        # Assert: Custom error message is used
        call_args = mock_broadcast.call_args
        ws_message = call_args[0][1]
        assert ws_message.content == custom_error
