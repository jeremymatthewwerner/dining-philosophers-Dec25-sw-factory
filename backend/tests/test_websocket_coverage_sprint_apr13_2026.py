"""Coverage sprint tests for WebSocket module - April 13, 2026.

Focuses on covering the uncovered branches and code paths in app/api/websocket.py:
- ConnectionManager method branches (125->127, 189->191, 212->214)
- websocket_endpoint token validation (lines 351-380)
- websocket_endpoint full connect/disconnect flow
- ConversationRoom broadcast with dead connections
- SpendLimitExceeded exception
- Helper functions

These tests use async unit testing with mock WebSockets so coverage.py
can properly track execution (unlike thread-based TestClient tests).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import (
    ConnectionManager,
    ConversationRoom,
    SpendLimitExceeded,
    WSMessage,
    WSMessageType,
    get_messages_for_conversation,
    websocket_endpoint,
)
from app.core.auth import create_access_token

# ---------------------------------------------------------------------------
# Mock WebSocket for direct endpoint testing
# ---------------------------------------------------------------------------


class MockWebSocket:
    """Minimal mock WebSocket for unit-testing endpoint logic."""

    def __init__(self, messages_to_receive: list[str] | None = None) -> None:
        self.accepted = False
        self.closed = False
        self.close_code: int | None = None
        self.close_reason: str | None = None
        self.sent_messages: list[str] = []
        self._messages: list[str] = list(messages_to_receive or [])
        self._message_index = 0

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason

    async def send_text(self, data: str) -> None:
        self.sent_messages.append(data)

    async def receive_text(self) -> str:
        if self._message_index < len(self._messages):
            msg = self._messages[self._message_index]
            self._message_index += 1
            return msg
        raise WebSocketDisconnect()

# ---------------------------------------------------------------------------
# ConnectionManager unit tests
# ---------------------------------------------------------------------------


class TestConnectionManagerBranches:
    """Tests for ConnectionManager method branches not covered by existing tests."""

    async def test_connect_to_existing_room(self) -> None:
        """Test connecting when room already exists covers branch 125->127.

        The defaultdict creates a room on first access; the explicit `if` check
        in connect() handles the case where the room was pre-created by another
        method (e.g. get_speed_multiplier) before the first connect call.
        """
        mgr = ConnectionManager()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        # First connection — creates the room via the `if not in` branch
        await mgr.connect(ws1, "conv-existing")
        assert "conv-existing" in mgr.rooms

        # Second connection to same room — room already exists, takes else branch
        await mgr.connect(ws2, "conv-existing")
        assert len(mgr.rooms["conv-existing"].connections) == 2

    async def test_send_thinker_typing_with_existing_room(self) -> None:
        """Test send_thinker_typing when room exists covers branch 189->191.

        Branch 189->191: `if conversation_id in self.rooms:` is True, so the
        thinker name is added to typing_thinkers set.
        """
        mgr = ConnectionManager()
        ws = MockWebSocket()
        await mgr.connect(ws, "conv-typing")

        await mgr.send_thinker_typing("conv-typing", "Socrates")

        assert "Socrates" in mgr.rooms["conv-typing"].typing_thinkers
        assert len(ws.sent_messages) == 1
        data = json.loads(ws.sent_messages[0])
        assert data["type"] == "thinker_typing"
        assert data["sender_name"] == "Socrates"

    async def test_send_thinker_stopped_typing_with_existing_room(self) -> None:
        """Test send_thinker_stopped_typing when room exists covers branch 212->214.

        Branch 212->214: `if conversation_id in self.rooms:` is True, so the
        thinker name is removed from typing_thinkers set.
        """
        mgr = ConnectionManager()
        ws = MockWebSocket()
        await mgr.connect(ws, "conv-stop-typing")
        mgr.rooms["conv-stop-typing"].typing_thinkers.add("Socrates")

        await mgr.send_thinker_stopped_typing("conv-stop-typing", "Socrates")

        assert "Socrates" not in mgr.rooms["conv-stop-typing"].typing_thinkers
        assert len(ws.sent_messages) == 1
        data = json.loads(ws.sent_messages[0])
        assert data["type"] == "thinker_stopped_typing"

    async def test_send_thinker_typing_without_room(self) -> None:
        """Test send_thinker_typing when room does not exist (no crash)."""
        mgr = ConnectionManager()
        # Room does not exist — should not crash, nothing added to typing_thinkers
        await mgr.send_thinker_typing("nonexistent-typing", "Socrates")

    async def test_send_thinker_stopped_typing_without_room(self) -> None:
        """Test send_thinker_stopped_typing when room does not exist (no crash)."""
        mgr = ConnectionManager()
        await mgr.send_thinker_stopped_typing("nonexistent-stop", "Socrates")

    async def test_disconnect_nonexistent_conversation(self) -> None:
        """Test that disconnecting from a non-existent conversation doesn't crash."""
        mgr = ConnectionManager()
        ws = MockWebSocket()
        # Should be a no-op without raising
        await mgr.disconnect(ws, "no-such-conv")

    async def test_broadcast_nonexistent_conversation(self) -> None:
        """Test broadcasting to a non-existent conversation is a no-op."""
        mgr = ConnectionManager()
        msg = WSMessage(type=WSMessageType.MESSAGE, conversation_id="no-such")
        # Should not raise
        await mgr.broadcast_to_conversation("no-such", msg)

    async def test_get_speed_multiplier_nonexistent_room(self) -> None:
        """Test get_speed_multiplier returns 1.0 when room doesn't exist."""
        mgr = ConnectionManager()
        speed = mgr.get_speed_multiplier("no-such-room")
        assert speed == 1.0

    async def test_get_speed_multiplier_existing_room(self) -> None:
        """Test get_speed_multiplier returns room value when room exists."""
        mgr = ConnectionManager()
        ws = MockWebSocket()
        await mgr.connect(ws, "conv-speed-get")
        mgr.rooms["conv-speed-get"].speed_multiplier = 2.5

        speed = mgr.get_speed_multiplier("conv-speed-get")
        assert speed == 2.5

    async def test_set_speed_multiplier_clamps_to_minimum(self) -> None:
        """Test set_speed_multiplier clamps value to minimum 0.5."""
        mgr = ConnectionManager()
        ws = MockWebSocket()
        await mgr.connect(ws, "conv-speed-min")

        await mgr.set_speed_multiplier("conv-speed-min", 0.1)  # below min

        assert mgr.rooms["conv-speed-min"].speed_multiplier == 0.5
        # Should broadcast SPEED_CHANGED
        assert len(ws.sent_messages) == 1
        data = json.loads(ws.sent_messages[0])
        assert data["type"] == "speed_changed"
        assert data["speed_multiplier"] == 0.5

    async def test_set_speed_multiplier_clamps_to_maximum(self) -> None:
        """Test set_speed_multiplier clamps value to maximum 6.0."""
        mgr = ConnectionManager()
        ws = MockWebSocket()
        await mgr.connect(ws, "conv-speed-max")

        await mgr.set_speed_multiplier("conv-speed-max", 999.0)  # above max

        assert mgr.rooms["conv-speed-max"].speed_multiplier == 6.0
        data = json.loads(ws.sent_messages[0])
        assert data["speed_multiplier"] == 6.0

    async def test_set_speed_multiplier_accepts_valid_range(self) -> None:
        """Test set_speed_multiplier accepts values within range."""
        mgr = ConnectionManager()
        ws = MockWebSocket()
        await mgr.connect(ws, "conv-speed-valid")

        await mgr.set_speed_multiplier("conv-speed-valid", 2.0)

        assert mgr.rooms["conv-speed-valid"].speed_multiplier == 2.0

    async def test_set_speed_multiplier_nonexistent_room(self) -> None:
        """Test set_speed_multiplier for non-existent room is a no-op."""
        mgr = ConnectionManager()
        # Should not crash when room doesn't exist
        await mgr.set_speed_multiplier("no-such-speed", 2.0)

    async def test_send_thinker_message_broadcasts_correctly(self) -> None:
        """Test send_thinker_message sends well-formed message to connected clients."""
        mgr = ConnectionManager()
        ws = MockWebSocket()
        await mgr.connect(ws, "conv-thinker-msg")

        await mgr.send_thinker_message(
            "conv-thinker-msg", "Socrates", "What is virtue?", "msg-abc", cost=0.005
        )

        assert len(ws.sent_messages) == 1
        data = json.loads(ws.sent_messages[0])
        assert data["type"] == "message"
        assert data["sender_type"] == "thinker"
        assert data["sender_name"] == "Socrates"
        assert data["content"] == "What is virtue?"
        assert data["message_id"] == "msg-abc"
        assert data["cost"] == 0.005

    async def test_send_thinker_message_without_cost(self) -> None:
        """Test send_thinker_message works with no cost provided."""
        mgr = ConnectionManager()
        ws = MockWebSocket()
        await mgr.connect(ws, "conv-thinker-nocost")

        await mgr.send_thinker_message("conv-thinker-nocost", "Plato", "Ideal forms", "msg-xyz")

        data = json.loads(ws.sent_messages[0])
        assert data["cost"] is None

    async def test_send_thinker_thinking_broadcasts_correctly(self) -> None:
        """Test send_thinker_thinking sends THINKER_THINKING message."""
        mgr = ConnectionManager()
        ws = MockWebSocket()
        await mgr.connect(ws, "conv-thinking")

        await mgr.send_thinker_thinking("conv-thinking", "Aristotle", "pondering causality")

        data = json.loads(ws.sent_messages[0])
        assert data["type"] == "thinker_thinking"
        assert data["sender_name"] == "Aristotle"
        assert data["content"] == "pondering causality"

    async def test_send_research_events_all_types(self) -> None:
        """Test all four research event broadcasts."""
        mgr = ConnectionManager()
        ws = MockWebSocket()
        await mgr.connect(ws, "conv-research")

        await mgr.send_research_started("conv-research", "Socrates")
        await mgr.send_research_complete("conv-research", "Socrates")
        await mgr.send_research_failed("conv-research", "Socrates", "Network error")
        await mgr.send_cache_hit("conv-research", "Socrates")

        assert len(ws.sent_messages) == 4
        types = [json.loads(m)["type"] for m in ws.sent_messages]
        assert "research_started" in types
        assert "research_complete" in types
        assert "research_failed" in types
        assert "cache_hit" in types

        # Verify error content on research_failed
        failed_msg = next(
            json.loads(m) for m in ws.sent_messages if json.loads(m)["type"] == "research_failed"
        )
        assert failed_msg["content"] == "Network error"
        assert failed_msg["thinker_name"] == "Socrates"


# ---------------------------------------------------------------------------
# ConversationRoom unit tests
# ---------------------------------------------------------------------------


class TestConversationRoom:
    """Tests for ConversationRoom internal behavior."""

    async def test_broadcast_removes_disconnected_clients(self) -> None:
        """Test that broadcast cleans up dead connections gracefully."""
        room = ConversationRoom(conversation_id="conv-broadcast-dead")

        # A websocket that raises on send (simulates closed connection)
        bad_ws = MockWebSocket()

        async def failing_send(_data: str) -> None:
            raise RuntimeError("Connection closed")

        bad_ws.send_text = failing_send  # type: ignore[method-assign]

        good_ws = MockWebSocket()

        room.add_connection(bad_ws)
        room.add_connection(good_ws)

        msg = WSMessage(type=WSMessageType.MESSAGE, conversation_id="conv-broadcast-dead")
        await room.broadcast(msg)

        # Dead connection removed, good one stays
        assert bad_ws not in room.connections
        assert good_ws in room.connections
        # Good ws received the message
        assert len(good_ws.sent_messages) == 1

    async def test_broadcast_all_dead_deactivates_room(self) -> None:
        """Test that room is marked inactive when all connections die during broadcast."""
        room = ConversationRoom(conversation_id="conv-all-dead")

        bad_ws = MockWebSocket()

        async def failing_send(_data: str) -> None:
            raise RuntimeError("Closed")

        bad_ws.send_text = failing_send  # type: ignore[method-assign]

        room.add_connection(bad_ws)
        assert room.is_active is True

        msg = WSMessage(type=WSMessageType.ERROR)
        await room.broadcast(msg)

        assert len(room.connections) == 0
        assert room.is_active is False

    async def test_remove_last_connection_deactivates_room(self) -> None:
        """Test removing the last connection marks room inactive."""
        room = ConversationRoom(conversation_id="conv-deactivate")
        ws = MockWebSocket()

        room.add_connection(ws)
        assert room.is_active is True

        room.remove_connection(ws)
        assert room.is_active is False
        assert len(room.connections) == 0

    def test_remove_nonexistent_connection_is_safe(self) -> None:
        """Test removing a connection that isn't in the room doesn't crash."""
        room = ConversationRoom(conversation_id="conv-remove-ghost")
        ws = MockWebSocket()
        # Should not raise
        room.remove_connection(ws)

    def test_add_connection_marks_room_active(self) -> None:
        """Test that adding a connection marks the room as active."""
        room = ConversationRoom(conversation_id="conv-activate")
        ws = MockWebSocket()
        assert room.is_active is False

        room.add_connection(ws)
        assert room.is_active is True


# ---------------------------------------------------------------------------
# SpendLimitExceeded tests
# ---------------------------------------------------------------------------


class TestSpendLimitExceeded:
    """Tests for SpendLimitExceeded exception class."""

    def test_exception_message_format(self) -> None:
        """Test exception formats current/limit spend in its message."""
        exc = SpendLimitExceeded(current_spend=5.50, spend_limit=3.00)
        msg = str(exc)
        assert "$5.50" in msg
        assert "$3.00" in msg

    def test_exception_stores_values(self) -> None:
        """Test exception stores current_spend and spend_limit as attributes."""
        exc = SpendLimitExceeded(current_spend=10.0, spend_limit=5.0)
        assert exc.current_spend == 10.0
        assert exc.spend_limit == 5.0

    def test_exception_is_exception(self) -> None:
        """Test SpendLimitExceeded is a proper Exception subclass."""
        exc = SpendLimitExceeded(current_spend=1.0, spend_limit=0.5)
        assert isinstance(exc, Exception)

        with pytest.raises(SpendLimitExceeded):
            raise SpendLimitExceeded(current_spend=1.0, spend_limit=0.5)


# ---------------------------------------------------------------------------
# get_messages_for_conversation tests
# ---------------------------------------------------------------------------


class TestGetMessagesForConversation:
    """Tests for get_messages_for_conversation helper."""

    async def test_returns_empty_for_unknown_conversation(self, db_session: AsyncSession) -> None:
        """Test returns empty list when conversation has no messages."""
        messages = await get_messages_for_conversation("conv-no-messages", db_session)
        assert list(messages) == []

    async def test_returns_messages_for_conversation(self, db_session: AsyncSession) -> None:
        """Test returns messages ordered by created_at."""
        from app.api.websocket import save_thinker_message
        from tests.conftest import create_test_user_session_conversation

        _, _, conversation = await create_test_user_session_conversation(db_session)

        # Save two messages
        msg1 = await save_thinker_message(
            conversation_id=conversation.id,
            thinker_name="Socrates",
            content="First message",
            cost=0.01,
            db=db_session,
        )
        msg2 = await save_thinker_message(
            conversation_id=conversation.id,
            thinker_name="Plato",
            content="Second message",
            cost=0.02,
            db=db_session,
        )

        messages = await get_messages_for_conversation(conversation.id, db_session)
        message_list = list(messages)

        assert len(message_list) == 2
        assert message_list[0].id == msg1.id
        assert message_list[1].id == msg2.id


# ---------------------------------------------------------------------------
# websocket_endpoint direct tests using MockWebSocket
# ---------------------------------------------------------------------------


class TestWebSocketEndpointLogic:
    """Direct async tests for websocket_endpoint with MockWebSocket.

    These run in the pytest asyncio event loop (NOT in a thread), so
    coverage.py properly tracks the executed lines.
    """

    async def test_endpoint_no_token_closes_with_4001(self) -> None:
        """Missing token causes close(4001, 'Authentication required')."""
        mock_ws = MockWebSocket()

        await websocket_endpoint(mock_ws, "conv-no-token", token=None)

        assert mock_ws.closed
        assert mock_ws.close_code == 4001
        assert "Authentication required" in (mock_ws.close_reason or "")
        assert not mock_ws.accepted

    async def test_endpoint_invalid_token_closes_with_4001(self) -> None:
        """An unparseable token string causes close(4001, 'Invalid token')."""
        mock_ws = MockWebSocket()

        await websocket_endpoint(mock_ws, "conv-bad-token", token="not-a-real-jwt")

        assert mock_ws.closed
        assert mock_ws.close_code == 4001
        assert "Invalid token" in (mock_ws.close_reason or "")
        assert not mock_ws.accepted

    async def test_endpoint_token_without_session_id_closes_with_4001(self) -> None:
        """A valid JWT without session_id causes close(4001, 'Invalid token - no session')."""
        mock_ws = MockWebSocket()
        token = create_access_token({"sub": "user-123"})  # no session_id field

        await websocket_endpoint(mock_ws, "conv-no-session", token=token)

        assert mock_ws.closed
        assert mock_ws.close_code == 4001
        assert "no session" in (mock_ws.close_reason or "")
        assert not mock_ws.accepted

    def _make_mock_setup(
        self, paused: bool = False
    ) -> tuple[ConnectionManager, MagicMock, MagicMock, MagicMock]:
        """Helper: create fresh manager, thinker svc mock, db mock, session maker mock."""
        fresh_manager = ConnectionManager()

        mock_thinker_svc = MagicMock()
        mock_thinker_svc.is_paused.return_value = paused
        mock_thinker_svc.stop_conversation_agents = AsyncMock()
        mock_thinker_svc.start_conversation_agents = AsyncMock()
        mock_thinker_svc.pause_conversation = MagicMock()
        mock_thinker_svc.resume_conversation = MagicMock()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker = MagicMock(return_value=mock_db)

        return fresh_manager, mock_thinker_svc, mock_db, mock_session_maker

    async def _run_endpoint(
        self,
        mock_ws: MockWebSocket,
        conv_id: str,
        token: str,
        fresh_manager: ConnectionManager,
        mock_thinker_svc: MagicMock,
        mock_session_maker: MagicMock,
    ) -> None:
        """Helper: run websocket_endpoint with all dependencies patched."""
        # thinker_service and async_session_maker are imported INSIDE the function,
        # so we patch them at their source modules.
        with (
            patch("app.api.websocket.manager", fresh_manager),
            patch("app.services.thinker.thinker_service", mock_thinker_svc),
            patch("app.core.database.async_session_maker", mock_session_maker),
        ):
            await websocket_endpoint(mock_ws, conv_id, token=token)

    async def test_endpoint_valid_token_connects_and_disconnects(self) -> None:
        """Valid token allows connection; empty receive queue triggers disconnect."""
        mock_ws = MockWebSocket(messages_to_receive=[])  # disconnect immediately
        token = create_access_token({"sub": "user-123", "session_id": "session-abc"})

        fresh_manager, mock_thinker_svc, _, mock_session_maker = self._make_mock_setup()

        await self._run_endpoint(
            mock_ws,
            "conv-valid-connect",
            token,
            fresh_manager,
            mock_thinker_svc,
            mock_session_maker,
        )

        # Connection was accepted
        assert mock_ws.accepted

        # Should have received at least: user_joined broadcast + resumed state
        assert len(mock_ws.sent_messages) >= 2
        types = [json.loads(m)["type"] for m in mock_ws.sent_messages]
        assert "user_joined" in types
        assert "resumed" in types

        # On disconnect, stop_conversation_agents is called
        mock_thinker_svc.stop_conversation_agents.assert_called_once_with("conv-valid-connect")

    async def test_endpoint_sends_paused_when_conversation_is_paused(self) -> None:
        """When thinker_service.is_paused returns True, PAUSED message is sent."""
        mock_ws = MockWebSocket(messages_to_receive=[])
        token = create_access_token({"sub": "user-456", "session_id": "session-xyz"})

        fresh_manager, mock_thinker_svc, _, mock_session_maker = self._make_mock_setup(paused=True)

        await self._run_endpoint(
            mock_ws, "conv-paused", token, fresh_manager, mock_thinker_svc, mock_session_maker
        )

        types = [json.loads(m)["type"] for m in mock_ws.sent_messages]
        assert "paused" in types
        assert "resumed" not in types

    async def test_endpoint_handles_pause_message(self) -> None:
        """Sending a pause message triggers PAUSED broadcast."""
        pause_msg = json.dumps({"type": "pause"})
        mock_ws = MockWebSocket(messages_to_receive=[pause_msg])
        token = create_access_token({"sub": "user-789", "session_id": "session-def"})

        fresh_manager, mock_thinker_svc, _, mock_session_maker = self._make_mock_setup()

        await self._run_endpoint(
            mock_ws, "conv-pause-msg", token, fresh_manager, mock_thinker_svc, mock_session_maker
        )

        mock_thinker_svc.pause_conversation.assert_called_once_with("conv-pause-msg")
        types = [json.loads(m)["type"] for m in mock_ws.sent_messages]
        assert "paused" in types

    async def test_endpoint_handles_resume_message(self) -> None:
        """Sending a resume message triggers RESUMED broadcast."""
        resume_msg = json.dumps({"type": "resume"})
        mock_ws = MockWebSocket(messages_to_receive=[resume_msg])
        token = create_access_token({"sub": "user-101", "session_id": "session-ghi"})

        fresh_manager, mock_thinker_svc, _, mock_session_maker = self._make_mock_setup()

        await self._run_endpoint(
            mock_ws, "conv-resume-msg", token, fresh_manager, mock_thinker_svc, mock_session_maker
        )

        mock_thinker_svc.resume_conversation.assert_called_once_with("conv-resume-msg")
        types = [json.loads(m)["type"] for m in mock_ws.sent_messages]
        assert "resumed" in types

    async def test_endpoint_handles_set_speed_message(self) -> None:
        """Sending a set_speed message updates the conversation speed."""
        speed_msg = json.dumps({"type": "set_speed", "speed_multiplier": 2.0})
        mock_ws = MockWebSocket(messages_to_receive=[speed_msg])
        token = create_access_token({"sub": "user-102", "session_id": "session-jkl"})

        fresh_manager, mock_thinker_svc, _, mock_session_maker = self._make_mock_setup()

        await self._run_endpoint(
            mock_ws, "conv-speed-set", token, fresh_manager, mock_thinker_svc, mock_session_maker
        )

        types = [json.loads(m)["type"] for m in mock_ws.sent_messages]
        assert "speed_changed" in types

    async def test_endpoint_handles_invalid_json_message(self) -> None:
        """Sending invalid JSON causes an ERROR response to be sent back."""
        mock_ws = MockWebSocket(messages_to_receive=["not valid json at all"])
        token = create_access_token({"sub": "user-103", "session_id": "session-mno"})

        fresh_manager, mock_thinker_svc, _, mock_session_maker = self._make_mock_setup()

        await self._run_endpoint(
            mock_ws, "conv-invalid-json", token, fresh_manager, mock_thinker_svc, mock_session_maker
        )

        types = [json.loads(m)["type"] for m in mock_ws.sent_messages]
        assert "error" in types
        error_msg = next(
            json.loads(m) for m in mock_ws.sent_messages if json.loads(m)["type"] == "error"
        )
        assert "Invalid JSON" in error_msg["content"]

    async def test_endpoint_handles_user_message(self) -> None:
        """Sending a user_message broadcasts it to the conversation."""
        user_msg = json.dumps({"type": "user_message", "content": "Hello philosophers!"})
        mock_ws = MockWebSocket(messages_to_receive=[user_msg])
        token = create_access_token({"sub": "user-104", "session_id": "session-pqr"})

        fresh_manager, mock_thinker_svc, _, mock_session_maker = self._make_mock_setup()

        await self._run_endpoint(
            mock_ws, "conv-user-msg", token, fresh_manager, mock_thinker_svc, mock_session_maker
        )

        types = [json.loads(m)["type"] for m in mock_ws.sent_messages]
        assert "message" in types
        broadcast_msg = next(
            json.loads(m) for m in mock_ws.sent_messages if json.loads(m)["type"] == "message"
        )
        assert broadcast_msg["content"] == "Hello philosophers!"
        assert broadcast_msg["sender_type"] == "user"

    async def test_endpoint_handles_typing_start_and_stop(self) -> None:
        """Sending typing_start and typing_stop messages are handled without error."""
        typing_start = json.dumps({"type": "typing_start"})
        typing_stop = json.dumps({"type": "typing_stop"})
        mock_ws = MockWebSocket(messages_to_receive=[typing_start, typing_stop])
        token = create_access_token({"sub": "user-105", "session_id": "session-stu"})

        fresh_manager, mock_thinker_svc, _, mock_session_maker = self._make_mock_setup()

        await self._run_endpoint(
            mock_ws,
            "conv-typing-signals",
            token,
            fresh_manager,
            mock_thinker_svc,
            mock_session_maker,
        )

        assert mock_ws.accepted
