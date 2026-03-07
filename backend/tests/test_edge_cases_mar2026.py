"""Edge case tests - Saturday QA focus (Mar 7, 2026).

Tests cover uncovered lines in websocket.py, knowledge_research.py, and thinker.py:
- websocket.py (47%): ConversationRoom.broadcast() exception handling,
  ConnectionManager speed clamping, research event senders, spend limit exceeded,
  SpendLimitExceeded exception, save_thinker_message no-conversation path
- knowledge_research.py (73%): is_stale() with various statuses,
  trigger_research() deduplication, _fetch_wikipedia_data no-result path
- thinker.py (71%): extract_mentions() edge cases, _get_language_instruction() boundaries

Uses `with patch(...)` (not @patch decorator) to ensure coverage is correctly tracked
with pytest-asyncio's auto mode.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import (
    ConnectionManager,
    ConversationRoom,
    SpendLimitExceeded,
    WSMessage,
    WSMessageType,
    save_thinker_message,
)
from app.models import Conversation, ResearchStatus, Session, ThinkerKnowledge, User
from app.services.knowledge_research import KnowledgeResearchService
from app.services.thinker import _get_language_instruction, extract_mentions


class TestConversationRoomBroadcastEdgeCases:
    """Edge cases for ConversationRoom.broadcast() error handling."""

    async def test_broadcast_removes_disconnected_client(self) -> None:
        """Test that broadcast removes a client that raises an exception during send.

        Edge case: Connection that throws during send gets cleaned up (lines 103-107).
        """
        room = ConversationRoom(conversation_id="test-conv")

        # Create two mocks: one that sends OK, one that raises
        healthy_ws = AsyncMock()
        broken_ws = AsyncMock()
        broken_ws.send_text.side_effect = Exception("Connection closed")

        room.connections.add(healthy_ws)
        room.connections.add(broken_ws)
        room.is_active = True

        message = WSMessage(type=WSMessageType.MESSAGE, content="hello")
        await room.broadcast(message)

        # Broken connection should be removed
        assert broken_ws not in room.connections
        # Healthy connection should remain
        assert healthy_ws in room.connections
        # Room stays active since healthy connection remains
        assert room.is_active is True

    async def test_broadcast_sets_inactive_when_all_disconnect(self) -> None:
        """Test that broadcast sets is_active=False when all clients disconnect.

        Edge case: All connections fail, room becomes inactive (lines 108-109).
        """
        room = ConversationRoom(conversation_id="test-conv")

        # One connection that will fail
        broken_ws = AsyncMock()
        broken_ws.send_text.side_effect = Exception("All gone")

        room.connections.add(broken_ws)
        room.is_active = True

        message = WSMessage(type=WSMessageType.MESSAGE, content="hello")
        await room.broadcast(message)

        # All connections removed
        assert len(room.connections) == 0
        # Room becomes inactive
        assert room.is_active is False

    async def test_broadcast_empty_room_is_noop(self) -> None:
        """Test broadcasting to an empty room doesn't fail."""
        room = ConversationRoom(conversation_id="empty-conv")
        message = WSMessage(type=WSMessageType.MESSAGE, content="hello")
        # Should not raise
        await room.broadcast(message)

    def test_add_connection_sets_active(self) -> None:
        """Test that adding a connection sets room as active (lines 87-88)."""
        room = ConversationRoom(conversation_id="test-conv")
        assert room.is_active is False

        mock_ws = MagicMock()
        room.add_connection(mock_ws)

        assert mock_ws in room.connections
        assert room.is_active is True

    def test_remove_connection_sets_inactive_when_empty(self) -> None:
        """Test that removing last connection sets room as inactive (lines 92-94)."""
        room = ConversationRoom(conversation_id="test-conv")
        mock_ws = MagicMock()
        room.add_connection(mock_ws)
        assert room.is_active is True

        room.remove_connection(mock_ws)

        assert mock_ws not in room.connections
        assert room.is_active is False

    def test_remove_connection_stays_active_with_remaining_connections(self) -> None:
        """Test that room stays active after removing one of multiple connections."""
        room = ConversationRoom(conversation_id="test-conv")
        ws1 = MagicMock()
        ws2 = MagicMock()
        room.add_connection(ws1)
        room.add_connection(ws2)

        room.remove_connection(ws1)

        assert ws1 not in room.connections
        assert ws2 in room.connections
        assert room.is_active is True


class TestConnectionManagerEdgeCases:
    """Edge cases for ConnectionManager methods."""

    async def test_set_speed_multiplier_no_room_is_noop(self) -> None:
        """Test set_speed_multiplier does nothing when conversation has no room.

        Edge case: Conversation not in rooms dict (line 149->exit).
        """
        manager = ConnectionManager()
        # Don't add any room for "nonexistent-conv"
        # Should not raise
        await manager.set_speed_multiplier("nonexistent-conv", 2.0)

    async def test_set_speed_multiplier_clamps_below_minimum(self) -> None:
        """Test speed multiplier is clamped to 0.5 minimum."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-1")
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await manager.set_speed_multiplier("conv-1", 0.1)  # Below 0.5 minimum
        assert manager.rooms["conv-1"].speed_multiplier == 0.5

    async def test_set_speed_multiplier_clamps_above_maximum(self) -> None:
        """Test speed multiplier is clamped to 6.0 maximum."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-2")
        mock_ws.send_text = AsyncMock()

        await manager.set_speed_multiplier("conv-2", 10.0)  # Above 6.0 maximum
        assert manager.rooms["conv-2"].speed_multiplier == 6.0

    def test_get_speed_multiplier_nonexistent_room_returns_default(self) -> None:
        """Test get_speed_multiplier returns 1.0 for non-existent conversation."""
        manager = ConnectionManager()
        result = manager.get_speed_multiplier("nonexistent-conv")
        assert result == 1.0

    async def test_send_thinker_typing_adds_to_typing_thinkers(self) -> None:
        """Test send_thinker_typing tracks the thinker in typing_thinkers set.

        Edge case: Typing set membership tracking (lines 189-196).
        """
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-typing")
        mock_ws.send_text = AsyncMock()

        await manager.send_thinker_typing("conv-typing", "Socrates")

        assert "Socrates" in manager.rooms["conv-typing"].typing_thinkers

    async def test_send_thinker_stopped_typing_removes_from_typing_thinkers(self) -> None:
        """Test send_thinker_stopped_typing removes thinker from typing_thinkers set.

        Edge case: Typing set cleanup (lines 212-219).
        """
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-stop")
        mock_ws.send_text = AsyncMock()

        # First mark as typing
        manager.rooms["conv-stop"].typing_thinkers.add("Aristotle")

        await manager.send_thinker_stopped_typing("conv-stop", "Aristotle")

        assert "Aristotle" not in manager.rooms["conv-stop"].typing_thinkers

    async def test_send_thinker_thinking_broadcasts_message(self) -> None:
        """Test send_thinker_thinking broadcasts thinking content to room.

        Edge case: Research/thinking event broadcast (lines 202-208).
        """
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-think")
        mock_ws.send_text = AsyncMock()

        await manager.send_thinker_thinking("conv-think", "Plato", "Contemplating justice...")

        mock_ws.send_text.assert_called_once()
        call_arg = mock_ws.send_text.call_args[0][0]
        import json

        data = json.loads(call_arg)
        assert data["type"] == "thinker_thinking"
        assert data["sender_name"] == "Plato"
        assert data["content"] == "Contemplating justice..."

    async def test_send_research_started_broadcasts_to_room(self) -> None:
        """Test send_research_started broadcasts research start event.

        Edge case: Research status event (lines 223-229).
        """
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-research")
        mock_ws.send_text = AsyncMock()

        await manager.send_research_started("conv-research", "Nietzsche")

        mock_ws.send_text.assert_called_once()
        call_arg = mock_ws.send_text.call_args[0][0]
        import json

        data = json.loads(call_arg)
        assert data["type"] == "research_started"
        assert data["thinker_name"] == "Nietzsche"
        assert data["timestamp"] is not None

    async def test_send_research_complete_broadcasts_to_room(self) -> None:
        """Test send_research_complete broadcasts research completion event.

        Edge case: Research status event (lines 233-239).
        """
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-research2")
        mock_ws.send_text = AsyncMock()

        await manager.send_research_complete("conv-research2", "Kant")

        mock_ws.send_text.assert_called_once()
        call_arg = mock_ws.send_text.call_args[0][0]
        import json

        data = json.loads(call_arg)
        assert data["type"] == "research_complete"
        assert data["thinker_name"] == "Kant"

    async def test_send_research_failed_with_error_message(self) -> None:
        """Test send_research_failed broadcasts failure with error content.

        Edge case: Research failure with error detail (lines 245-252).
        """
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-fail")
        mock_ws.send_text = AsyncMock()

        await manager.send_research_failed("conv-fail", "Hegel", "Wikipedia timeout")

        mock_ws.send_text.assert_called_once()
        call_arg = mock_ws.send_text.call_args[0][0]
        import json

        data = json.loads(call_arg)
        assert data["type"] == "research_failed"
        assert data["thinker_name"] == "Hegel"
        assert data["content"] == "Wikipedia timeout"

    async def test_send_research_failed_without_error_message(self) -> None:
        """Test send_research_failed broadcasts failure without error (None content)."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-fail2")
        mock_ws.send_text = AsyncMock()

        await manager.send_research_failed("conv-fail2", "Marx")  # No error message

        mock_ws.send_text.assert_called_once()
        call_arg = mock_ws.send_text.call_args[0][0]
        import json

        data = json.loads(call_arg)
        assert data["type"] == "research_failed"
        assert data["content"] is None

    async def test_send_cache_hit_broadcasts_to_room(self) -> None:
        """Test send_cache_hit broadcasts cache hit event.

        Edge case: Cache hit event (lines 256-262).
        """
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-cache")
        mock_ws.send_text = AsyncMock()

        await manager.send_cache_hit("conv-cache", "Descartes")

        mock_ws.send_text.assert_called_once()
        call_arg = mock_ws.send_text.call_args[0][0]
        import json

        data = json.loads(call_arg)
        assert data["type"] == "cache_hit"
        assert data["thinker_name"] == "Descartes"

    async def test_send_thinker_message_with_cost(self) -> None:
        """Test send_thinker_message includes cost in broadcast (lines 175-185)."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-msg")
        mock_ws.send_text = AsyncMock()

        await manager.send_thinker_message(
            "conv-msg", "Spinoza", "God is everything.", "msg-id-1", cost=0.005
        )

        mock_ws.send_text.assert_called_once()
        call_arg = mock_ws.send_text.call_args[0][0]
        import json

        data = json.loads(call_arg)
        assert data["type"] == "message"
        assert data["sender_name"] == "Spinoza"
        assert data["content"] == "God is everything."
        assert data["message_id"] == "msg-id-1"
        assert data["cost"] == pytest.approx(0.005)

    async def test_send_thinker_message_without_cost(self) -> None:
        """Test send_thinker_message with no cost (None)."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-nocost")
        mock_ws.send_text = AsyncMock()

        await manager.send_thinker_message(
            "conv-nocost", "Locke", "Life and liberty.", "msg-id-2", cost=None
        )

        mock_ws.send_text.assert_called_once()
        call_arg = mock_ws.send_text.call_args[0][0]
        import json

        data = json.loads(call_arg)
        assert data["cost"] is None


class TestSpendLimitExceededException:
    """Edge cases for SpendLimitExceeded exception."""

    def test_spend_limit_exceeded_attributes(self) -> None:
        """Test SpendLimitExceeded stores spend amounts correctly (lines 285-287)."""
        exc = SpendLimitExceeded(current_spend=10.50, spend_limit=10.00)
        assert exc.current_spend == 10.50
        assert exc.spend_limit == 10.00

    def test_spend_limit_exceeded_message_format(self) -> None:
        """Test SpendLimitExceeded has human-readable error message."""
        exc = SpendLimitExceeded(current_spend=5.25, spend_limit=5.00)
        assert "5.25" in str(exc)
        assert "5.00" in str(exc)

    def test_spend_limit_exceeded_is_exception(self) -> None:
        """Test SpendLimitExceeded is a proper Exception subclass."""
        exc = SpendLimitExceeded(current_spend=1.0, spend_limit=1.0)
        assert isinstance(exc, Exception)


class TestSaveThinkerMessageEdgeCases:
    """Edge cases for save_thinker_message spend limit tracking."""

    async def test_save_message_raises_when_spend_limit_exceeded(
        self, db_session: AsyncSession
    ) -> None:
        """Test that save_thinker_message raises SpendLimitExceeded when user is at limit.

        Edge case: Spend limit enforcement (lines 308->317, 314).
        """
        # Create user AT their spend limit
        user = User(
            username="at_limit_user",
            password_hash="hash",
            total_spend=5.00,
            spend_limit=5.00,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        session = Session(user_id=user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        conversation = Conversation(session_id=session.id, topic="Philosophy debate")
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        with pytest.raises(SpendLimitExceeded) as exc_info:
            await save_thinker_message(
                conversation.id, "Aristotle", "Logic is key.", 0.01, db_session
            )

        assert exc_info.value.current_spend == 5.00
        assert exc_info.value.spend_limit == 5.00

    async def test_save_message_updates_user_spend(self, db_session: AsyncSession) -> None:
        """Test that save_thinker_message increments user.total_spend (lines 327-330).

        Edge case: Spend tracking update after message is saved.
        """
        user = User(
            username="spender_user",
            password_hash="hash",
            total_spend=1.00,
            spend_limit=100.00,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        session = Session(user_id=user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        conversation = Conversation(session_id=session.id, topic="Science discussion")
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        message = await save_thinker_message(
            conversation.id, "Einstein", "E=mc2.", 0.05, db_session
        )

        assert message.content == "E=mc2."
        # User spend should be updated
        await db_session.refresh(user)
        assert user.total_spend == pytest.approx(1.05)

    async def test_save_message_no_conversation_still_saves(self, db_session: AsyncSession) -> None:
        """Test save_thinker_message with non-existent conversation still creates message.

        Edge case: conversation not found path - message is still created.
        """
        fake_conv_id = "00000000-0000-0000-0000-000000000000"
        message = await save_thinker_message(
            fake_conv_id, "Plato", "The ideal form.", 0.01, db_session
        )
        # Message gets created even if conversation not found (no user spend tracked)
        assert message.content == "The ideal form."
        assert message.sender_name == "Plato"


class TestKnowledgeResearchIsStale:
    """Edge cases for KnowledgeResearchService.is_stale()."""

    def test_is_stale_pending_returns_true(self) -> None:
        """Test that PENDING status is always considered stale."""
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Socrates",
            status=ResearchStatus.PENDING,
            research_data={},
        )
        assert service.is_stale(knowledge) is True

    def test_is_stale_failed_returns_true(self) -> None:
        """Test that FAILED status is always considered stale."""
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Plato",
            status=ResearchStatus.FAILED,
            research_data={},
        )
        assert service.is_stale(knowledge) is True

    def test_is_stale_in_progress_returns_true(self) -> None:
        """Test that IN_PROGRESS status is always considered stale."""
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Aristotle",
            status=ResearchStatus.IN_PROGRESS,
            research_data={},
        )
        assert service.is_stale(knowledge) is True

    def test_is_stale_complete_old_returns_true(self) -> None:
        """Test that COMPLETE status with old timestamp is stale."""
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Kant",
            status=ResearchStatus.COMPLETE,
            research_data={},
        )
        # Set updated_at to 60 days ago (beyond 30-day threshold)
        knowledge.updated_at = datetime.now(UTC) - timedelta(days=60)
        assert service.is_stale(knowledge) is True

    def test_is_stale_complete_recent_returns_false(self) -> None:
        """Test that COMPLETE status with recent timestamp is not stale."""
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Hume",
            status=ResearchStatus.COMPLETE,
            research_data={},
        )
        # Set updated_at to 1 day ago (within 30-day threshold)
        knowledge.updated_at = datetime.now(UTC) - timedelta(days=1)
        assert service.is_stale(knowledge) is False


class TestKnowledgeResearchTriggerDeduplication:
    """Edge cases for trigger_research() deduplication."""

    def test_trigger_research_deduplicates_in_progress(self) -> None:
        """Test that trigger_research doesn't start a new task if one is already running.

        Edge case: Deduplication logic (lines 97-99).
        """
        service = KnowledgeResearchService()

        # Create a mock task that's not done yet
        mock_task = MagicMock()
        mock_task.done.return_value = False
        service._active_tasks["Nietzsche"] = mock_task

        with patch("asyncio.create_task") as mock_create:
            service.trigger_research("Nietzsche")
            # Should NOT create a new task
            mock_create.assert_not_called()

    def test_trigger_research_restarts_completed_task(self) -> None:
        """Test that trigger_research starts a new task if the previous one is done."""
        service = KnowledgeResearchService()

        # Create a mock task that IS done
        mock_task = MagicMock()
        mock_task.done.return_value = True
        service._active_tasks["Marx"] = mock_task

        with (
            patch("asyncio.create_task") as mock_create,
            patch.object(service, "_research_thinker"),
        ):
            mock_new_task = MagicMock()
            mock_create.return_value = mock_new_task
            service.trigger_research("Marx")
            # Should create a new task
            mock_create.assert_called_once()


class TestKnowledgeResearchFetchWikipedia:
    """Edge cases for Wikipedia fetching."""

    async def test_fetch_wikipedia_no_results_returns_none(self) -> None:
        """Test that _fetch_wikipedia_data returns None when no results found."""
        service = KnowledgeResearchService()

        mock_response = MagicMock()
        mock_response.json.return_value = {"query": {"search": []}}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_async_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service._fetch_wikipedia_data("NonExistentThinker12345")

        assert result is None

    async def test_fetch_wikipedia_http_error_returns_none(self) -> None:
        """Test that _fetch_wikipedia_data returns None on HTTP error."""
        service = KnowledgeResearchService()

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Network error")
            )
            mock_async_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service._fetch_wikipedia_data("Aristotle")

        assert result is None


class TestExtractMentionsEdgeCases:
    """Edge cases for extract_mentions() function."""

    def test_extract_mentions_empty_text(self) -> None:
        """Test extract_mentions returns empty list for empty input."""
        result = extract_mentions("")
        assert result == []

    def test_extract_mentions_no_mentions(self) -> None:
        """Test extract_mentions returns empty list when no @mentions."""
        result = extract_mentions("This is a normal sentence without mentions.")
        assert result == []

    def test_extract_mentions_quoted_name_with_spaces(self) -> None:
        """Test extract_mentions handles @\"Name With Spaces\" format."""
        result = extract_mentions('@"Marie Curie" what do you think?')
        assert "Marie Curie" in result

    def test_extract_mentions_simple_name(self) -> None:
        """Test extract_mentions handles @SingleName format."""
        result = extract_mentions("@Socrates please respond")
        assert "Socrates" in result

    def test_extract_mentions_multiple_thinkers(self) -> None:
        """Test extract_mentions handles multiple @mentions in one text."""
        result = extract_mentions("@Socrates and @Plato both agree")
        assert "Socrates" in result
        assert "Plato" in result

    def test_extract_mentions_quoted_prevents_duplicate(self) -> None:
        """Test that quoted @mentions don't cause duplicate simple @mention extraction."""
        result = extract_mentions('@"Marie Curie" is brilliant')
        # "Marie Curie" should appear once, not as "Marie" and also "Marie Curie"
        assert result.count("Marie Curie") == 1


class TestGetLanguageInstructionEdgeCases:
    """Edge cases for _get_language_instruction()."""

    def test_english_returns_empty_string(self) -> None:
        """Test that English (default) returns empty string (no instruction needed)."""
        result = _get_language_instruction("en")
        assert result == ""

    def test_spanish_returns_instruction(self) -> None:
        """Test that Spanish returns correct language instruction."""
        result = _get_language_instruction("es")
        assert "Spanish" in result
        assert "Respond in" in result

    def test_french_returns_instruction(self) -> None:
        """Test that French returns correct language instruction."""
        result = _get_language_instruction("fr")
        assert "French" in result

    def test_unknown_language_code_uses_code_as_name(self) -> None:
        """Test that unknown language code uses the code itself as language name.

        Edge case: Language code not in LANGUAGE_NAMES dict.
        """
        result = _get_language_instruction("zh")
        assert "zh" in result
        assert "Respond in" in result

    def test_german_returns_instruction(self) -> None:
        """Test that German returns correct language instruction."""
        result = _get_language_instruction("de")
        assert "German" in result

    def test_hindi_returns_instruction(self) -> None:
        """Test that Hindi returns correct language instruction."""
        result = _get_language_instruction("hi")
        assert "Hindi" in result
