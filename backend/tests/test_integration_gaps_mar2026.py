"""Integration tests for Wednesday Mar 4 2026 - filling WebSocket coverage gaps.

Focus: ConnectionManager, ConversationRoom, and helper function coverage.

Key gaps identified:
- app/api/websocket.py: 47% coverage - class methods and helpers not tested
- app/main.py: 60% - health/ready degraded path

Strategy: Test the building blocks directly (ConnectionManager, ConversationRoom,
helper functions) using AsyncMock for WebSocket objects. This avoids the Starlette
TestClient thread-isolation issue that prevents coverage of the endpoint itself.
"""

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from httpx import AsyncClient

from app.api.websocket import (
    ConnectionManager,
    ConversationRoom,
    SpendLimitExceeded,
    WSMessage,
    WSMessageType,
    get_messages_for_conversation,
    save_thinker_message,
)
from app.models import Conversation, Message
from app.models.message import SenderType
from tests.conftest import create_test_user_session_conversation


def make_mock_ws() -> AsyncMock:
    """Create a mock WebSocket for testing (async accept + send_text)."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# ConversationRoom - add_connection / remove_connection / broadcast
# ---------------------------------------------------------------------------


class TestConversationRoomMethods:
    """Tests for ConversationRoom methods that were uncovered (lines 87-109)."""

    def test_add_connection_adds_websocket_and_sets_active(self) -> None:
        """add_connection() stores the WS and marks room active (lines 87-88)."""
        room = ConversationRoom(conversation_id="conv-1")
        ws = make_mock_ws()

        room.add_connection(ws)

        assert ws in room.connections
        assert room.is_active is True

    def test_add_connection_multiple_websockets(self) -> None:
        """add_connection() can hold multiple WebSocket connections."""
        room = ConversationRoom(conversation_id="conv-1")
        ws1, ws2, ws3 = make_mock_ws(), make_mock_ws(), make_mock_ws()

        room.add_connection(ws1)
        room.add_connection(ws2)
        room.add_connection(ws3)

        assert len(room.connections) == 3
        assert room.is_active is True

    def test_remove_connection_clears_active_when_no_connections_remain(self) -> None:
        """remove_connection() sets is_active=False when all connections removed (lines 92-94)."""
        room = ConversationRoom(conversation_id="conv-1")
        ws = make_mock_ws()
        room.add_connection(ws)

        room.remove_connection(ws)

        assert ws not in room.connections
        assert room.is_active is False

    def test_remove_connection_stays_active_when_others_remain(self) -> None:
        """remove_connection() keeps is_active=True if other connections remain (lines 92-93)."""
        room = ConversationRoom(conversation_id="conv-1")
        ws1, ws2 = make_mock_ws(), make_mock_ws()
        room.add_connection(ws1)
        room.add_connection(ws2)

        room.remove_connection(ws1)

        assert ws1 not in room.connections
        assert ws2 in room.connections
        assert room.is_active is True  # still has ws2

    async def test_broadcast_sends_to_all_connected_clients(self) -> None:
        """broadcast() calls send_text on every active connection (lines 101-104)."""
        room = ConversationRoom(conversation_id="conv-1")
        ws1, ws2 = make_mock_ws(), make_mock_ws()
        room.connections = {ws1, ws2}
        msg = WSMessage(type=WSMessageType.MESSAGE, conversation_id="conv-1", content="hello")

        await room.broadcast(msg)

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()
        sent_data = json.loads(ws1.send_text.call_args[0][0])
        assert sent_data["type"] == "message"
        assert sent_data["content"] == "hello"

    async def test_broadcast_removes_failed_connections(self) -> None:
        """broadcast() removes connections that raise exceptions (lines 103-107)."""
        room = ConversationRoom(conversation_id="conv-1")
        ws_good = make_mock_ws()
        ws_bad = make_mock_ws()
        ws_bad.send_text.side_effect = Exception("Connection closed")
        room.connections = {ws_good, ws_bad}
        msg = WSMessage(type=WSMessageType.PAUSED, conversation_id="conv-1")

        await room.broadcast(msg)

        assert ws_bad not in room.connections
        assert ws_good in room.connections

    async def test_broadcast_sets_inactive_when_all_clients_disconnect(self) -> None:
        """broadcast() sets is_active=False when all connections fail (lines 107-109)."""
        room = ConversationRoom(conversation_id="conv-1")
        ws_bad = make_mock_ws()
        ws_bad.send_text.side_effect = Exception("All gone")
        room.add_connection(ws_bad)
        msg = WSMessage(type=WSMessageType.ERROR, content="test")

        await room.broadcast(msg)

        assert room.is_active is False
        assert len(room.connections) == 0


# ---------------------------------------------------------------------------
# ConnectionManager - connect / disconnect / set_speed_multiplier
# ---------------------------------------------------------------------------


class TestConnectionManagerConnect:
    """Tests for ConnectionManager.connect() and disconnect() (lines 122-133)."""

    async def test_connect_accepts_websocket_and_creates_room(self) -> None:
        """connect() calls accept() and creates a new ConversationRoom (lines 123-127)."""
        manager = ConnectionManager()
        ws = make_mock_ws()

        await manager.connect(ws, "conv-new")

        ws.accept.assert_called_once()
        assert "conv-new" in manager.rooms
        assert ws in manager.rooms["conv-new"].connections
        assert manager.rooms["conv-new"].is_active is True

    async def test_connect_adds_to_existing_room(self) -> None:
        """connect() adds to an existing room without creating a duplicate (lines 124-127)."""
        manager = ConnectionManager()
        ws1, ws2 = make_mock_ws(), make_mock_ws()

        await manager.connect(ws1, "conv-shared")
        await manager.connect(ws2, "conv-shared")

        assert len(manager.rooms["conv-shared"].connections) == 2
        assert ws1 in manager.rooms["conv-shared"].connections
        assert ws2 in manager.rooms["conv-shared"].connections

    async def test_disconnect_removes_websocket_from_room(self) -> None:
        """disconnect() removes the WS from the room (lines 131-133)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")

        await manager.disconnect(ws, "conv-1")

        assert ws not in manager.rooms["conv-1"].connections

    async def test_disconnect_no_op_for_unknown_conversation(self) -> None:
        """disconnect() is a no-op for a conversation that doesn't exist (line 131-132)."""
        manager = ConnectionManager()
        ws = make_mock_ws()

        # Should not raise
        await manager.disconnect(ws, "nonexistent-conv")

    async def test_disconnect_sets_room_inactive_when_last_client(self) -> None:
        """disconnect() sets room to inactive when last client leaves."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")
        assert manager.is_conversation_active("conv-1") is True

        await manager.disconnect(ws, "conv-1")

        assert manager.is_conversation_active("conv-1") is False


# ---------------------------------------------------------------------------
# ConnectionManager - set_speed_multiplier
# ---------------------------------------------------------------------------


class TestConnectionManagerSetSpeed:
    """Tests for set_speed_multiplier clamping and broadcast (lines 148-159)."""

    async def test_set_speed_multiplier_below_minimum_clamps_to_half(self) -> None:
        """set_speed_multiplier clamps values below 0.5 to 0.5 (line 149)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")

        await manager.set_speed_multiplier("conv-1", 0.1)

        assert manager.rooms["conv-1"].speed_multiplier == 0.5

    async def test_set_speed_multiplier_above_maximum_clamps_to_six(self) -> None:
        """set_speed_multiplier clamps values above 6.0 to 6.0 (line 149)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")

        await manager.set_speed_multiplier("conv-1", 100.0)

        assert manager.rooms["conv-1"].speed_multiplier == 6.0

    async def test_set_speed_multiplier_broadcasts_speed_changed(self) -> None:
        """set_speed_multiplier sends SPEED_CHANGED to all clients (lines 150-158)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")
        ws.send_text.reset_mock()  # clear the initial setup calls if any

        await manager.set_speed_multiplier("conv-1", 2.0)

        ws.send_text.assert_called_once()
        data = json.loads(ws.send_text.call_args[0][0])
        assert data["type"] == "speed_changed"
        assert data["speed_multiplier"] == 2.0
        assert data["conversation_id"] == "conv-1"

    async def test_set_speed_multiplier_no_op_for_unknown_conversation(self) -> None:
        """set_speed_multiplier does nothing for a conversation with no room."""
        manager = ConnectionManager()

        # Should not raise, just silently skip
        await manager.set_speed_multiplier("no-room", 1.5)


# ---------------------------------------------------------------------------
# ConnectionManager - send_thinker_message
# ---------------------------------------------------------------------------


class TestConnectionManagerSendThinkerMessage:
    """Tests for send_thinker_message (lines 175-185)."""

    async def test_send_thinker_message_broadcasts_message_type(self) -> None:
        """send_thinker_message sends a MESSAGE with correct fields (lines 175-185)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")
        ws.send_text.reset_mock()

        await manager.send_thinker_message("conv-1", "Socrates", "Know thyself.", "msg-id-1", 0.02)

        ws.send_text.assert_called_once()
        data = json.loads(ws.send_text.call_args[0][0])
        assert data["type"] == "message"
        assert data["sender_type"] == "thinker"
        assert data["sender_name"] == "Socrates"
        assert data["content"] == "Know thyself."
        assert data["message_id"] == "msg-id-1"
        assert data["cost"] == pytest.approx(0.02)
        assert data["timestamp"] is not None

    async def test_send_thinker_message_without_cost(self) -> None:
        """send_thinker_message works with cost=None."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")
        ws.send_text.reset_mock()

        await manager.send_thinker_message("conv-1", "Plato", "Ideas are real.", "msg-id-2")

        data = json.loads(ws.send_text.call_args[0][0])
        assert data["cost"] is None


# ---------------------------------------------------------------------------
# ConnectionManager - send_thinker_typing / thinking / stopped_typing
# ---------------------------------------------------------------------------


class TestConnectionManagerTypingMethods:
    """Tests for thinker typing indicator methods (lines 189-219)."""

    async def test_send_thinker_typing_tracks_thinker_and_broadcasts(self) -> None:
        """send_thinker_typing adds thinker to typing set and sends THINKER_TYPING (lines 189-196)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")
        ws.send_text.reset_mock()

        await manager.send_thinker_typing("conv-1", "Aristotle")

        assert "Aristotle" in manager.rooms["conv-1"].typing_thinkers
        ws.send_text.assert_called_once()
        data = json.loads(ws.send_text.call_args[0][0])
        assert data["type"] == "thinker_typing"
        assert data["sender_name"] == "Aristotle"

    async def test_send_thinker_thinking_broadcasts_with_content(self) -> None:
        """send_thinker_thinking sends THINKER_THINKING with thinking content (lines 202-208)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")
        ws.send_text.reset_mock()

        await manager.send_thinker_thinking("conv-1", "Kant", "Categorical imperatives...")

        ws.send_text.assert_called_once()
        data = json.loads(ws.send_text.call_args[0][0])
        assert data["type"] == "thinker_thinking"
        assert data["sender_name"] == "Kant"
        assert data["content"] == "Categorical imperatives..."

    async def test_send_thinker_stopped_typing_removes_from_set_and_broadcasts(self) -> None:
        """send_thinker_stopped_typing removes from typing set and sends (lines 212-219)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")
        # Add thinker to typing set first
        manager.rooms["conv-1"].typing_thinkers.add("Hegel")
        ws.send_text.reset_mock()

        await manager.send_thinker_stopped_typing("conv-1", "Hegel")

        assert "Hegel" not in manager.rooms["conv-1"].typing_thinkers
        ws.send_text.assert_called_once()
        data = json.loads(ws.send_text.call_args[0][0])
        assert data["type"] == "thinker_stopped_typing"
        assert data["sender_name"] == "Hegel"

    async def test_send_thinker_typing_for_unknown_conversation_does_not_track(self) -> None:
        """send_thinker_typing for unknown conversation doesn't crash, just broadcasts."""
        manager = ConnectionManager()

        # No room for this conversation - should not raise
        await manager.send_thinker_typing("no-room", "Nietzsche")

    async def test_send_thinker_stopped_typing_for_unknown_conversation_no_crash(self) -> None:
        """send_thinker_stopped_typing for unknown conversation doesn't crash (branch 212->214).

        When conversation_id is not in rooms, the discard step is skipped
        but the broadcast still proceeds (to an empty room, which is a no-op).
        """
        manager = ConnectionManager()

        # No room for this conversation - should not raise
        await manager.send_thinker_stopped_typing("no-room-conv", "Schopenhauer")


# ---------------------------------------------------------------------------
# ConnectionManager - research status methods
# ---------------------------------------------------------------------------


class TestConnectionManagerResearchMethods:
    """Tests for research status notification methods (lines 223-262)."""

    async def test_send_research_started_broadcasts_with_timestamp(self) -> None:
        """send_research_started sends RESEARCH_STARTED with thinker name (lines 223-229)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")
        ws.send_text.reset_mock()

        await manager.send_research_started("conv-1", "Darwin")

        ws.send_text.assert_called_once()
        data = json.loads(ws.send_text.call_args[0][0])
        assert data["type"] == "research_started"
        assert data["thinker_name"] == "Darwin"
        assert data["timestamp"] is not None

    async def test_send_research_complete_broadcasts(self) -> None:
        """send_research_complete sends RESEARCH_COMPLETE (lines 233-239)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")
        ws.send_text.reset_mock()

        await manager.send_research_complete("conv-1", "Newton")

        ws.send_text.assert_called_once()
        data = json.loads(ws.send_text.call_args[0][0])
        assert data["type"] == "research_complete"
        assert data["thinker_name"] == "Newton"

    async def test_send_research_failed_broadcasts_with_error(self) -> None:
        """send_research_failed sends RESEARCH_FAILED with error content (lines 245-252)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")
        ws.send_text.reset_mock()

        await manager.send_research_failed("conv-1", "Galileo", "Network timeout")

        ws.send_text.assert_called_once()
        data = json.loads(ws.send_text.call_args[0][0])
        assert data["type"] == "research_failed"
        assert data["thinker_name"] == "Galileo"
        assert data["content"] == "Network timeout"

    async def test_send_research_failed_without_error_message(self) -> None:
        """send_research_failed works with error=None (lines 245-252)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")
        ws.send_text.reset_mock()

        await manager.send_research_failed("conv-1", "Copernicus")

        data = json.loads(ws.send_text.call_args[0][0])
        assert data["type"] == "research_failed"
        assert data["content"] is None

    async def test_send_cache_hit_broadcasts_with_thinker_name(self) -> None:
        """send_cache_hit sends CACHE_HIT with thinker name and timestamp (lines 256-262)."""
        manager = ConnectionManager()
        ws = make_mock_ws()
        await manager.connect(ws, "conv-1")
        ws.send_text.reset_mock()

        await manager.send_cache_hit("conv-1", "Confucius")

        ws.send_text.assert_called_once()
        data = json.loads(ws.send_text.call_args[0][0])
        assert data["type"] == "cache_hit"
        assert data["thinker_name"] == "Confucius"
        assert data["timestamp"] is not None


# ---------------------------------------------------------------------------
# get_messages_for_conversation
# ---------------------------------------------------------------------------


class TestGetMessagesForConversation:
    """Tests for get_messages_for_conversation helper (lines 273-278)."""

    async def test_returns_messages_in_creation_order(self, db_session: AsyncSession) -> None:
        """get_messages_for_conversation returns messages ordered by created_at (lines 273-278)."""
        _, _, conversation = await create_test_user_session_conversation(db_session)

        # Add messages
        msg1 = Message(
            conversation_id=conversation.id,
            sender_type=SenderType.THINKER,
            sender_name="Socrates",
            content="First message",
        )
        msg2 = Message(
            conversation_id=conversation.id,
            sender_type=SenderType.USER,
            sender_name="User",
            content="Second message",
        )
        db_session.add(msg1)
        db_session.add(msg2)
        await db_session.commit()

        messages = await get_messages_for_conversation(conversation.id, db_session)

        assert len(messages) == 2
        assert messages[0].content == "First message"
        assert messages[1].content == "Second message"

    async def test_returns_empty_for_nonexistent_conversation(
        self, db_session: AsyncSession
    ) -> None:
        """get_messages_for_conversation returns empty list for unknown conversation."""
        messages = await get_messages_for_conversation("nonexistent-id", db_session)

        assert len(messages) == 0

    async def test_returns_only_messages_for_given_conversation(
        self, db_session: AsyncSession
    ) -> None:
        """get_messages_for_conversation filters by conversation_id."""
        _, session_obj, conv1 = await create_test_user_session_conversation(db_session)

        # Create a second conversation
        conv2 = Conversation(session_id=session_obj.id, topic="Another topic")
        db_session.add(conv2)
        await db_session.commit()
        await db_session.refresh(conv2)

        # Add message to conv1 only
        msg = Message(
            conversation_id=conv1.id,
            sender_type=SenderType.THINKER,
            sender_name="Plato",
            content="For conv1 only",
        )
        db_session.add(msg)
        await db_session.commit()

        # conv2 should have no messages
        messages = await get_messages_for_conversation(conv2.id, db_session)
        assert len(messages) == 0

        # conv1 should have one message
        messages = await get_messages_for_conversation(conv1.id, db_session)
        assert len(messages) == 1


# ---------------------------------------------------------------------------
# SpendLimitExceeded exception
# ---------------------------------------------------------------------------


class TestSpendLimitExceededException:
    """Tests for SpendLimitExceeded exception class (lines 285-287)."""

    def test_spend_limit_exceeded_stores_current_and_limit(self) -> None:
        """SpendLimitExceeded stores current_spend and spend_limit (lines 285-287)."""
        exc = SpendLimitExceeded(current_spend=5.50, spend_limit=5.00)

        assert exc.current_spend == 5.50
        assert exc.spend_limit == 5.00

    def test_spend_limit_exceeded_message_includes_amounts(self) -> None:
        """SpendLimitExceeded message includes both dollar amounts (lines 285-287)."""
        exc = SpendLimitExceeded(current_spend=10.75, spend_limit=10.00)

        msg = str(exc)
        assert "10.75" in msg
        assert "10.00" in msg

    def test_spend_limit_exceeded_is_exception(self) -> None:
        """SpendLimitExceeded is a proper Exception subclass."""
        exc = SpendLimitExceeded(current_spend=1.0, spend_limit=0.5)

        assert isinstance(exc, Exception)
        with pytest.raises(SpendLimitExceeded):
            raise exc


# ---------------------------------------------------------------------------
# save_thinker_message - spend limit path
# ---------------------------------------------------------------------------


class TestSaveThinkerMessageSpendLimit:
    """Tests for save_thinker_message spend limit enforcement (lines 308-330)."""

    async def test_raises_spend_limit_exceeded_when_at_limit(
        self, db_session: AsyncSession
    ) -> None:
        """save_thinker_message raises SpendLimitExceeded when spend >= limit (lines 308-317)."""
        user, _, conversation = await create_test_user_session_conversation(db_session)

        # Set user's spend to exactly their limit
        user.spend_limit = 1.0
        user.total_spend = 1.0
        await db_session.commit()

        with pytest.raises(SpendLimitExceeded) as exc_info:
            await save_thinker_message(
                conversation_id=conversation.id,
                thinker_name="Socrates",
                content="This should fail.",
                cost=0.01,
                db=db_session,
            )

        assert exc_info.value.current_spend == 1.0
        assert exc_info.value.spend_limit == 1.0

    async def test_raises_spend_limit_exceeded_when_above_limit(
        self, db_session: AsyncSession
    ) -> None:
        """save_thinker_message raises when total_spend exceeds spend_limit (line 314)."""
        user, _, conversation = await create_test_user_session_conversation(db_session)

        # Set user's spend above their limit
        user.spend_limit = 2.0
        user.total_spend = 5.0  # already exceeded
        await db_session.commit()

        with pytest.raises(SpendLimitExceeded) as exc_info:
            await save_thinker_message(
                conversation_id=conversation.id,
                thinker_name="Plato",
                content="This should also fail.",
                cost=0.01,
                db=db_session,
            )

        assert exc_info.value.current_spend == 5.0
        assert exc_info.value.spend_limit == 2.0

    async def test_updates_spend_when_under_limit(self, db_session: AsyncSession) -> None:
        """save_thinker_message updates user.total_spend when under limit (lines 327-330)."""
        user, _, conversation = await create_test_user_session_conversation(db_session)

        user.spend_limit = 10.0
        user.total_spend = 0.0
        await db_session.commit()

        await save_thinker_message(
            conversation_id=conversation.id,
            thinker_name="Aristotle",
            content="The good life.",
            cost=0.05,
            db=db_session,
        )

        # Reload user to verify spend was updated
        await db_session.refresh(user)
        assert user.total_spend == pytest.approx(0.05)

    async def test_saves_message_for_nonexistent_conversation_without_spend_update(
        self, db_session: AsyncSession
    ) -> None:
        """save_thinker_message saves message when conversation_id doesn't exist (branch 308->317).

        When conversation is None, user spend check is skipped entirely and
        the message is saved without updating any user's total_spend.
        """
        # Pass a nonexistent conversation_id - SQLite FK is not enforced by default
        message = await save_thinker_message(
            conversation_id="nonexistent-conv-id",
            thinker_name="Descartes",
            content="I think therefore I am.",
            cost=0.03,
            db=db_session,
        )

        assert message.sender_name == "Descartes"
        assert message.content == "I think therefore I am."
        assert message.cost == pytest.approx(0.03)
        assert message.sender_type == SenderType.THINKER


# ---------------------------------------------------------------------------
# health/ready degraded path (app/main.py lines 155-157)
# ---------------------------------------------------------------------------


class TestHealthReadyDegradedPath:
    """Tests for the /health/ready endpoint degraded path (app/main.py lines 155-157)."""

    async def test_health_ready_returns_503_when_database_fails(
        self,
        client: "AsyncClient",  # type: ignore[name-defined]
    ) -> None:
        """health/ready returns 503 with degraded status when DB execute fails (lines 155-157)."""
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.core.database import get_db
        from app.main import app

        async def override_get_db_failing():  # type: ignore[return]
            """Provide a DB session whose execute() raises an exception."""
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(side_effect=Exception("DB connection refused"))

            async def _gen():
                yield mock_session

            async for session in _gen():
                yield session

        app.dependency_overrides[get_db] = override_get_db_failing

        try:
            response = await client.get("/health/ready")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert "database" in body["checks"]
        assert "error" in body["checks"]["database"]

    async def test_health_ready_returns_200_when_database_ok(self, client: "AsyncClient") -> None:  # type: ignore[name-defined]
        """health/ready returns 200 with ready status when DB is healthy."""
        response = await client.get("/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["checks"]["database"] == "ok"
