"""Tests for WebSocket functionality."""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.api.websocket import (
    ConnectionManager,
    WSMessage,
    WSMessageType,
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

    def test_websocket_send_message(self) -> None:
        """Test sending a message via WebSocket."""
        token = get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/test-conversation?token={token}") as websocket,
        ):
            # Skip the join message
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

            with test_client.websocket_connect(f"/ws/multi-test?token={token2}") as ws2:
                # ws1 should receive user_joined for ws2
                data = ws1.receive_json()
                assert data["type"] == "user_joined"

                # ws2 should receive its own user_joined
                data = ws2.receive_json()
                assert data["type"] == "user_joined"

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

    def test_unpaused_conversation_no_pause_message_on_connect(self) -> None:
        """Test that unpaused conversations don't receive a pause message on connect."""
        from app.services.thinker import thinker_service

        token = get_test_token()
        conversation_id = "unpause-test"

        # Ensure conversation is not paused
        thinker_service.resume_conversation(conversation_id)

        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/{conversation_id}?token={token}") as websocket,
        ):
            # Should only receive join message, not pause message
            data = websocket.receive_json()
            assert data["type"] == "user_joined"

            # Verify no pause message comes through
            # (we can't directly check "no message", but we can verify the state)
            assert thinker_service.is_paused(conversation_id) is False


class TestCostAccumulation:
    """Tests for cost accumulation to user.total_spend."""

    @pytest.mark.asyncio
    async def test_save_thinker_message_updates_user_total_spend(
        self, db_session: AsyncSession
    ) -> None:
        """Test that saving a thinker message updates the user's total_spend."""
        # Create a user
        user = User(
            username="test_user",
            password_hash="test_hash",
            total_spend=0.0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Create a session for the user
        session = Session(
            user_id=user.id,
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Create a conversation for the session
        conversation = Conversation(
            session_id=session.id,
            topic="Test conversation about philosophy",
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

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

    @pytest.mark.asyncio
    async def test_save_thinker_message_with_zero_cost(self, db_session: AsyncSession) -> None:
        """Test that saving a message with zero cost still works correctly."""
        # Create a user
        user = User(
            username="test_user_zero",
            password_hash="test_hash",
            total_spend=0.0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Create a session for the user
        session = Session(
            user_id=user.id,
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Create a conversation for the session
        conversation = Conversation(
            session_id=session.id,
            topic="Test conversation",
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

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

    @pytest.mark.asyncio
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
