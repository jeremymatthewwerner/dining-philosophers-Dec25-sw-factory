"""Tests for WebSocket functionality."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.api.websocket import (
    ConnectionManager,
    ConversationRoom,
    SpendLimitExceeded,
    WSMessage,
    WSMessageType,
    get_messages_for_conversation,
    save_thinker_message,
)
from app.core.auth import create_access_token
from app.main import app
from app.models import Conversation, Session, User
from app.models.message import SenderType


def get_test_token(user_id: str = "test-user-id", session_id: str = "test-session-id") -> str:
    """Create a valid JWT token for testing."""
    return create_access_token({"sub": user_id, "session_id": session_id})


class TestConnectionManager:
    """Tests for the ConnectionManager class."""

    def test_manager_initialization(self) -> None:
        """Test that manager initializes correctly."""
        manager = ConnectionManager()
        assert isinstance(manager.rooms, dict)

    def test_is_conversation_active_empty(self) -> None:
        """Test that empty conversation is not active."""
        manager = ConnectionManager()
        assert manager.is_conversation_active("nonexistent") is False


class TestWSMessage:
    """Tests for WSMessage model."""

    def test_message_creation(self) -> None:
        """Test creating a WebSocket message."""
        message = WSMessage(
            type=WSMessageType.MESSAGE,
            conversation_id="conv-123",
            content="Hello!",
            sender_name="Socrates",
            sender_type="thinker",
        )
        assert message.type == WSMessageType.MESSAGE
        assert message.conversation_id == "conv-123"
        assert message.content == "Hello!"

    def test_message_serialization(self) -> None:
        """Test message JSON serialization."""
        message = WSMessage(
            type=WSMessageType.THINKER_TYPING,
            conversation_id="conv-123",
            sender_name="Einstein",
        )
        json_str = message.model_dump_json()
        data = json.loads(json_str)
        assert data["type"] == "thinker_typing"
        assert data["sender_name"] == "Einstein"

    def test_message_types(self) -> None:
        """Test all message types are valid."""
        for msg_type in WSMessageType:
            message = WSMessage(type=msg_type)
            assert message.type == msg_type

    def test_research_status_message_types(self) -> None:
        """Test research status message types are valid."""
        # Test RESEARCH_STARTED
        message = WSMessage(
            type=WSMessageType.RESEARCH_STARTED,
            conversation_id="conv-123",
            thinker_name="Socrates",
        )
        json_str = message.model_dump_json()
        data = json.loads(json_str)
        assert data["type"] == "research_started"
        assert data["thinker_name"] == "Socrates"

        # Test RESEARCH_COMPLETE
        message = WSMessage(
            type=WSMessageType.RESEARCH_COMPLETE,
            conversation_id="conv-123",
            thinker_name="Aristotle",
        )
        json_str = message.model_dump_json()
        data = json.loads(json_str)
        assert data["type"] == "research_complete"
        assert data["thinker_name"] == "Aristotle"

        # Test RESEARCH_FAILED
        message = WSMessage(
            type=WSMessageType.RESEARCH_FAILED,
            conversation_id="conv-123",
            thinker_name="Plato",
            content="Network error",
        )
        json_str = message.model_dump_json()
        data = json.loads(json_str)
        assert data["type"] == "research_failed"
        assert data["thinker_name"] == "Plato"
        assert data["content"] == "Network error"

        # Test CACHE_HIT
        message = WSMessage(
            type=WSMessageType.CACHE_HIT,
            conversation_id="conv-123",
            thinker_name="Confucius",
        )
        json_str = message.model_dump_json()
        data = json.loads(json_str)
        assert data["type"] == "cache_hit"
        assert data["thinker_name"] == "Confucius"


class TestWebSocketEndpoint:
    """Tests for WebSocket endpoint."""

    def test_websocket_connect(self) -> None:
        """Test WebSocket connection."""
        token = get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/test-conversation?token={token}") as websocket,
        ):
            # Should receive user_joined message
            data = websocket.receive_json()
            assert data["type"] == "user_joined"
            assert data["conversation_id"] == "test-conversation"

            # Should receive resumed message (conversation starts unpaused)
            data = websocket.receive_json()
            assert data["type"] == "resumed"
            assert data["conversation_id"] == "test-conversation"

    def test_websocket_send_message(self) -> None:
        """Test sending a message via WebSocket."""
        token = get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/test-conversation?token={token}") as websocket,
        ):
            # Skip the join message
            websocket.receive_json()
            # Skip the initial resumed message (conversation starts unpaused)
            websocket.receive_json()

            # Send a user message
            websocket.send_json(
                {
                    "type": "user_message",
                    "content": "Hello, thinkers!",
                }
            )

            # Should receive the message broadcast back
            data = websocket.receive_json()
            assert data["type"] == "message"
            assert data["content"] == "Hello, thinkers!"
            assert data["sender_type"] == "user"

    def test_websocket_invalid_json(self) -> None:
        """Test handling invalid JSON."""
        token = get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/test-conversation?token={token}") as websocket,
        ):
            # Skip the join message
            websocket.receive_json()
            # Skip the initial resumed message (conversation starts unpaused)
            websocket.receive_json()

            # Send invalid JSON
            websocket.send_text("not valid json")

            # Should receive error message
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "Invalid JSON" in data["content"]

    def test_multiple_clients_receive_messages(self) -> None:
        """Test that multiple clients receive broadcast messages."""
        token1 = get_test_token("user-1")
        token2 = get_test_token("user-2")
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/multi-test?token={token1}") as ws1,
        ):
            # Skip join message for ws1
            ws1.receive_json()
            # Skip the initial resumed message (conversation starts unpaused)
            ws1.receive_json()

            with test_client.websocket_connect(f"/ws/multi-test?token={token2}") as ws2:
                # ws1 should receive user_joined for ws2
                data = ws1.receive_json()
                assert data["type"] == "user_joined"

                # ws2 should receive its own user_joined
                data = ws2.receive_json()
                assert data["type"] == "user_joined"

                # ws2 should also receive the resumed message
                data = ws2.receive_json()
                assert data["type"] == "resumed"

                # ws1 sends a message
                ws1.send_json(
                    {
                        "type": "user_message",
                        "content": "Hello from ws1!",
                    }
                )

                # Both should receive the broadcast
                data1 = ws1.receive_json()
                data2 = ws2.receive_json()

                assert data1["type"] == "message"
                assert data1["content"] == "Hello from ws1!"
                assert data2["type"] == "message"
                assert data2["content"] == "Hello from ws1!"


class TestWebSocketMessageTypes:
    """Tests for different WebSocket message types."""

    def test_typing_start_message(self) -> None:
        """Test typing_start message type."""
        token = get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/typing-test?token={token}") as websocket,
        ):
            # Skip join message
            websocket.receive_json()
            # Skip the initial resumed message (conversation starts unpaused)
            websocket.receive_json()

            # Send typing start
            websocket.send_json({"type": "typing_start"})

            # No response expected for typing_start (it's just a signal)
            # The test passes if no error is raised

    def test_typing_stop_message(self) -> None:
        """Test typing_stop message type."""
        token = get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/typing-test?token={token}") as websocket,
        ):
            # Skip join message
            websocket.receive_json()
            # Skip the initial resumed message (conversation starts unpaused)
            websocket.receive_json()

            # Send typing stop
            websocket.send_json({"type": "typing_stop"})

            # No response expected for typing_stop
            # The test passes if no error is raised

    def test_pause_resume_messages(self) -> None:
        """Test pause and resume message types."""
        token = get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/pause-test?token={token}") as websocket,
        ):
            # Skip join message
            websocket.receive_json()

            # Skip initial resumed message (conversation starts unpaused)
            data = websocket.receive_json()
            assert data["type"] == "resumed"

            # Send pause
            websocket.send_json({"type": "pause"})

            # Should receive paused confirmation
            data = websocket.receive_json()
            assert data["type"] == "paused"
            assert data["conversation_id"] == "pause-test"

            # Send resume
            websocket.send_json({"type": "resume"})

            # Should receive resumed confirmation
            data = websocket.receive_json()
            assert data["type"] == "resumed"
            assert data["conversation_id"] == "pause-test"

    def test_pause_state_preserved_on_reconnect(self) -> None:
        """Test that pause state is preserved when reconnecting to a conversation."""
        from app.services.thinker import thinker_service

        token = get_test_token()
        conversation_id = "pause-reconnect-test"

        with TestClient(app) as test_client:
            # First connection - pause the conversation
            with test_client.websocket_connect(f"/ws/{conversation_id}?token={token}") as ws1:
                # Skip join message
                ws1.receive_json()

                # Skip initial resumed message (conversation starts unpaused)
                data = ws1.receive_json()
                assert data["type"] == "resumed"

                # Pause the conversation
                ws1.send_json({"type": "pause"})

                # Confirm paused
                data = ws1.receive_json()
                assert data["type"] == "paused"

                # Verify backend state is paused
                assert thinker_service.is_paused(conversation_id) is True

            # WebSocket closed - pause state should still be in backend

            # Second connection - should receive pause state immediately
            with test_client.websocket_connect(f"/ws/{conversation_id}?token={token}") as ws2:
                # Should receive join message
                data = ws2.receive_json()
                assert data["type"] == "user_joined"

                # Should receive paused state message
                data = ws2.receive_json()
                assert data["type"] == "paused"
                assert data["conversation_id"] == conversation_id

                # Verify backend still knows it's paused
                assert thinker_service.is_paused(conversation_id) is True

    def test_unpaused_conversation_sends_resumed_on_connect(self) -> None:
        """Test that unpaused conversations send a resumed message on connect.

        This ensures clients always know the correct pause state when switching threads,
        fixing the bug where the UI showed the wrong pause state after thread switching.
        """
        from app.services.thinker import thinker_service

        token = get_test_token()
        conversation_id = "unpause-test"

        # Ensure conversation is not paused
        thinker_service.resume_conversation(conversation_id)

        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/{conversation_id}?token={token}") as websocket,
        ):
            # Should receive join message first
            data = websocket.receive_json()
            assert data["type"] == "user_joined"

            # Should receive resumed message to sync client state
            data = websocket.receive_json()
            assert data["type"] == "resumed"
            assert data["conversation_id"] == conversation_id

            # Verify backend state is not paused
            assert thinker_service.is_paused(conversation_id) is False


class TestCostAccumulation:
    """Tests for cost accumulation to user.total_spend."""

    async def test_save_thinker_message_updates_user_total_spend(
        self, db_session: AsyncSession
    ) -> None:
        """Test that saving a thinker message updates the user's total_spend."""
        from tests.conftest import create_test_user_session_conversation

        user, session, conversation = await create_test_user_session_conversation(db_session)

        # Save a thinker message with cost
        cost_1 = 0.05
        message_1 = await save_thinker_message(
            conversation_id=conversation.id,
            thinker_name="Socrates",
            content="What is the nature of knowledge?",
            cost=cost_1,
            db=db_session,
        )

        # Verify message was saved with cost
        assert message_1.cost == cost_1
        assert message_1.sender_type == SenderType.THINKER
        assert message_1.sender_name == "Socrates"

        # Verify user's total_spend was updated
        result = await db_session.execute(select(User).where(User.id == user.id))
        updated_user = result.scalar_one()
        assert updated_user.total_spend == cost_1

        # Save another message with different cost
        cost_2 = 0.03
        message_2 = await save_thinker_message(
            conversation_id=conversation.id,
            thinker_name="Plato",
            content="I think knowledge is justified true belief.",
            cost=cost_2,
            db=db_session,
        )

        # Verify second message was saved
        assert message_2.cost == cost_2

        # Verify user's total_spend accumulated both costs
        result = await db_session.execute(select(User).where(User.id == user.id))
        updated_user = result.scalar_one()
        assert updated_user.total_spend == pytest.approx(cost_1 + cost_2)

    async def test_save_thinker_message_with_zero_cost(self, db_session: AsyncSession) -> None:
        """Test that saving a message with zero cost still works correctly."""
        from tests.conftest import create_test_user_session_conversation

        user, session, conversation = await create_test_user_session_conversation(db_session)

        # Save a message with zero cost
        message = await save_thinker_message(
            conversation_id=conversation.id,
            thinker_name="Einstein",
            content="E=mc²",
            cost=0.0,
            db=db_session,
        )

        # Verify message was saved
        assert message.cost == 0.0

        # Verify user's total_spend is still 0
        result = await db_session.execute(select(User).where(User.id == user.id))
        updated_user = result.scalar_one()
        assert updated_user.total_spend == 0.0

    async def test_save_thinker_message_multiple_users(self, db_session: AsyncSession) -> None:
        """Test that costs are tracked separately for different users."""
        # Create two users
        user1 = User(
            username="user1",
            password_hash="test_hash",
            total_spend=0.0,
        )
        user2 = User(
            username="user2",
            password_hash="test_hash",
            total_spend=0.0,
        )
        db_session.add_all([user1, user2])
        await db_session.commit()
        await db_session.refresh(user1)
        await db_session.refresh(user2)

        # Create sessions for both users
        session1 = Session(user_id=user1.id)
        session2 = Session(user_id=user2.id)
        db_session.add_all([session1, session2])
        await db_session.commit()
        await db_session.refresh(session1)
        await db_session.refresh(session2)

        # Create conversations for both sessions
        conversation1 = Conversation(
            session_id=session1.id,
            topic="User 1's conversation",
        )
        conversation2 = Conversation(
            session_id=session2.id,
            topic="User 2's conversation",
        )
        db_session.add_all([conversation1, conversation2])
        await db_session.commit()
        await db_session.refresh(conversation1)
        await db_session.refresh(conversation2)

        # Save messages for each user with different costs
        cost1 = 0.10
        cost2 = 0.25
        await save_thinker_message(
            conversation_id=conversation1.id,
            thinker_name="Socrates",
            content="User 1 message",
            cost=cost1,
            db=db_session,
        )
        await save_thinker_message(
            conversation_id=conversation2.id,
            thinker_name="Plato",
            content="User 2 message",
            cost=cost2,
            db=db_session,
        )

        # Verify each user has their own correct total_spend
        result = await db_session.execute(select(User).where(User.id == user1.id))
        updated_user1 = result.scalar_one()
        assert updated_user1.total_spend == cost1

        result = await db_session.execute(select(User).where(User.id == user2.id))
        updated_user2 = result.scalar_one()
        assert updated_user2.total_spend == cost2


class TestWebSocketAuthRejection:
    """Tests for WebSocket authentication rejection paths."""

    def test_websocket_no_token_rejected(self) -> None:
        """Test WebSocket connection without token is rejected with code 4001."""
        from starlette.websockets import WebSocketDisconnect

        with (
            TestClient(app) as test_client,
            pytest.raises(WebSocketDisconnect),
            test_client.websocket_connect("/ws/test-conv-no-token") as websocket,
        ):
            # Connection should be closed immediately
            websocket.receive_json()

    def test_websocket_invalid_token_rejected(self) -> None:
        """Test WebSocket connection with invalid JWT token is rejected with code 4001."""
        from starlette.websockets import WebSocketDisconnect

        with (
            TestClient(app) as test_client,
            pytest.raises(WebSocketDisconnect),
            test_client.websocket_connect(
                "/ws/test-conv-bad-token?token=not.a.valid.jwt"
            ) as websocket,
        ):
            websocket.receive_json()

    def test_websocket_token_without_session_id_rejected(self) -> None:
        """Test that a token lacking session_id is rejected."""
        from starlette.websockets import WebSocketDisconnect

        # Token with user_id but no session_id
        token = create_access_token({"sub": "some-user-id"})
        with (
            TestClient(app) as test_client,
            pytest.raises(WebSocketDisconnect),
            test_client.websocket_connect(f"/ws/test-conv-no-session?token={token}") as websocket,
        ):
            websocket.receive_json()


class TestWebSocketSpeedControl:
    """Tests for WebSocket speed control message."""

    def test_set_speed_message_updates_multiplier(self) -> None:
        """Test that SET_SPEED message updates speed and broadcasts SPEED_CHANGED."""
        token = get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/speed-test?token={token}") as websocket,
        ):
            # Consume the initial join + resumed messages
            websocket.receive_json()
            websocket.receive_json()

            # Send a set_speed message
            websocket.send_json({"type": "set_speed", "speed_multiplier": 2.0})

            # Should receive speed_changed broadcast
            data = websocket.receive_json()
            assert data["type"] == "speed_changed"
            assert data["speed_multiplier"] == 2.0

    def test_set_speed_clamped_to_max(self) -> None:
        """Test that speed is clamped to maximum value of 6.0."""
        token = get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/speed-clamp-max?token={token}") as websocket,
        ):
            websocket.receive_json()
            websocket.receive_json()

            websocket.send_json({"type": "set_speed", "speed_multiplier": 100.0})
            data = websocket.receive_json()
            assert data["type"] == "speed_changed"
            assert data["speed_multiplier"] == 6.0

    def test_set_speed_clamped_to_min(self) -> None:
        """Test that speed is clamped to minimum value of 0.5."""
        token = get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/speed-clamp-min?token={token}") as websocket,
        ):
            websocket.receive_json()
            websocket.receive_json()

            websocket.send_json({"type": "set_speed", "speed_multiplier": 0.0})
            data = websocket.receive_json()
            assert data["type"] == "speed_changed"
            assert data["speed_multiplier"] == 0.5


class TestWebSocketDisconnect:
    """Tests for WebSocket disconnect handling."""

    def test_clean_disconnect_does_not_error(self) -> None:
        """Test that disconnecting cleanly completes without errors."""
        token = get_test_token("disc-user-clean")
        conversation_id = "clean-disconnect-test"

        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/{conversation_id}?token={token}") as websocket,
        ):
            websocket.receive_json()  # user_joined
            websocket.receive_json()  # resumed
        # Context manager exit triggers disconnect; no exception = success

    async def test_conversation_room_inactive_after_remove_all(self) -> None:
        """Test ConversationRoom.is_active becomes False when last connection removed."""
        from unittest.mock import MagicMock

        from app.api.websocket import ConversationRoom

        room = ConversationRoom(conversation_id="test-room")
        mock_ws = MagicMock()

        # Add a connection — room becomes active
        room.add_connection(mock_ws)
        assert room.is_active is True

        # Remove the last connection — room becomes inactive
        room.remove_connection(mock_ws)
        assert room.is_active is False


class TestConnectionManagerBroadcastMethods:
    """Tests for ConnectionManager broadcast/send methods using mock WebSocket connections."""

    async def _setup_manager_with_mock_ws(self) -> tuple[ConnectionManager, MagicMock, str]:
        """Create a ConnectionManager with a mock WebSocket connected."""
        manager = ConnectionManager()
        mock_ws = MagicMock()
        mock_ws.send_text = AsyncMock()
        conv_id = "mock-conv-001"
        # Simulate connect without actually accepting a real WebSocket
        manager.rooms[conv_id] = ConversationRoom(conversation_id=conv_id)
        manager.rooms[conv_id].add_connection(mock_ws)
        return manager, mock_ws, conv_id

    async def test_send_thinker_message_broadcasts_correctly(self) -> None:
        """Test send_thinker_message sends MESSAGE type with correct fields."""
        manager, mock_ws, conv_id = await self._setup_manager_with_mock_ws()

        await manager.send_thinker_message(
            conv_id,
            thinker_name="Socrates",
            content="What is virtue?",
            message_id="msg-1",
            cost=0.01,
        )

        mock_ws.send_text.assert_called_once()
        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "message"
        assert data["sender_name"] == "Socrates"
        assert data["content"] == "What is virtue?"
        assert data["message_id"] == "msg-1"
        assert data["cost"] == 0.01

    async def test_send_thinker_typing_broadcasts_correctly(self) -> None:
        """Test send_thinker_typing sends THINKER_TYPING type."""
        manager, mock_ws, conv_id = await self._setup_manager_with_mock_ws()

        await manager.send_thinker_typing(conv_id, thinker_name="Plato")

        mock_ws.send_text.assert_called_once()
        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "thinker_typing"
        assert data["sender_name"] == "Plato"

    async def test_send_thinker_thinking_broadcasts_correctly(self) -> None:
        """Test send_thinker_thinking sends THINKER_THINKING with content."""
        manager, mock_ws, conv_id = await self._setup_manager_with_mock_ws()

        await manager.send_thinker_thinking(conv_id, "Aristotle", "Considering the nature of form")

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "thinker_thinking"
        assert data["sender_name"] == "Aristotle"
        assert data["content"] == "Considering the nature of form"

    async def test_send_thinker_stopped_typing_broadcasts_correctly(self) -> None:
        """Test send_thinker_stopped_typing sends THINKER_STOPPED_TYPING."""
        manager, mock_ws, conv_id = await self._setup_manager_with_mock_ws()
        # Simulate thinker already typing
        manager.rooms[conv_id].typing_thinkers.add("Kant")

        await manager.send_thinker_stopped_typing(conv_id, "Kant")

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "thinker_stopped_typing"
        assert data["sender_name"] == "Kant"
        assert "Kant" not in manager.rooms[conv_id].typing_thinkers

    async def test_send_research_started_broadcasts_correctly(self) -> None:
        """Test send_research_started sends RESEARCH_STARTED with thinker_name."""
        manager, mock_ws, conv_id = await self._setup_manager_with_mock_ws()

        await manager.send_research_started(conv_id, "Nietzsche")

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "research_started"
        assert data["thinker_name"] == "Nietzsche"

    async def test_send_research_complete_broadcasts_correctly(self) -> None:
        """Test send_research_complete sends RESEARCH_COMPLETE."""
        manager, mock_ws, conv_id = await self._setup_manager_with_mock_ws()

        await manager.send_research_complete(conv_id, "Descartes")

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "research_complete"
        assert data["thinker_name"] == "Descartes"

    async def test_send_research_failed_broadcasts_correctly(self) -> None:
        """Test send_research_failed sends RESEARCH_FAILED with optional error."""
        manager, mock_ws, conv_id = await self._setup_manager_with_mock_ws()

        await manager.send_research_failed(conv_id, "Hume", error="Timeout error")

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "research_failed"
        assert data["thinker_name"] == "Hume"
        assert data["content"] == "Timeout error"

    async def test_send_cache_hit_broadcasts_correctly(self) -> None:
        """Test send_cache_hit sends CACHE_HIT with thinker_name."""
        manager, mock_ws, conv_id = await self._setup_manager_with_mock_ws()

        await manager.send_cache_hit(conv_id, "Locke")

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "cache_hit"
        assert data["thinker_name"] == "Locke"

    async def test_get_speed_multiplier_returns_default(self) -> None:
        """Test get_speed_multiplier returns 1.0 when conversation has no room."""
        manager = ConnectionManager()
        assert manager.get_speed_multiplier("nonexistent-conv") == 1.0

    async def test_get_speed_multiplier_returns_set_value(self) -> None:
        """Test get_speed_multiplier returns the value set via set_speed_multiplier."""
        manager, mock_ws, conv_id = await self._setup_manager_with_mock_ws()

        await manager.set_speed_multiplier(conv_id, 2.5)
        assert manager.get_speed_multiplier(conv_id) == 2.5


class TestSpendLimitExceeded:
    """Tests for SpendLimitExceeded exception."""

    def test_spend_limit_exceeded_message(self) -> None:
        """Test SpendLimitExceeded formats message correctly."""
        exc = SpendLimitExceeded(current_spend=5.50, spend_limit=5.00)
        assert exc.current_spend == 5.50
        assert exc.spend_limit == 5.00
        assert "$5.50" in str(exc)
        assert "$5.00" in str(exc)

    def test_spend_limit_exceeded_is_exception(self) -> None:
        """Test SpendLimitExceeded is an Exception subclass."""
        exc = SpendLimitExceeded(current_spend=1.0, spend_limit=0.5)
        assert isinstance(exc, Exception)


class TestGetMessagesForConversation:
    """Tests for get_messages_for_conversation helper."""

    async def test_returns_empty_for_unknown_conversation(self, db_session: AsyncSession) -> None:
        """Test that an unknown conversation returns an empty message list."""
        messages = await get_messages_for_conversation("nonexistent-conv-id", db_session)
        assert list(messages) == []

    async def test_returns_messages_in_order(self, db_session: AsyncSession) -> None:
        """Test messages are returned in chronological order."""
        from tests.conftest import create_test_user_session_conversation

        _, _, conversation = await create_test_user_session_conversation(db_session)

        # Save two messages
        await save_thinker_message(conversation.id, "Socrates", "First message", 0.01, db_session)
        await save_thinker_message(conversation.id, "Plato", "Second message", 0.01, db_session)

        messages = await get_messages_for_conversation(conversation.id, db_session)
        assert len(messages) == 2
        assert messages[0].content == "First message"
        assert messages[1].content == "Second message"
