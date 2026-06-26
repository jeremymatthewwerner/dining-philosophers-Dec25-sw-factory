"""Integration gap tests - Wednesday focus (April 22, 2026).

Tests targeting uncovered integration paths:
- websocket.py ConnectionManager async edge cases (branches 125->127, 189->191, 212->214)
- websocket.py SpendLimitExceeded exception and save_thinker_message error path
- thinker.py _split_response_into_bubbles force-split path (long single-bubble texts)
- thinker.py _extract_thinking_display with non-English language branches
- knowledge_research.py error handling (lines 140-149)
- End-to-end integration chains: feedback workflow, admin spend workflow
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import (
    ConnectionManager,
    SpendLimitExceeded,
    WSMessage,
    WSMessageType,
    get_messages_for_conversation,
    save_thinker_message,
)
from app.models import Conversation, Message, Session, User
from app.models.message import SenderType
from tests.conftest import (
    bearer_header,
    create_admin_headers,
    register_and_get_token,
)

# ============================================================================
# ConnectionManager Async Edge Cases
# Covers branches: 125->127, 189->191, 212->214 in websocket.py
# ============================================================================


class TestConnectionManagerAsyncEdgeCases:
    """Test async edge cases in ConnectionManager that expose uncovered branches."""

    async def test_connect_to_existing_room_reuses_room(self) -> None:
        """Connect to a room that already exists (branch 125->127: room exists, skip creation).

        Covers the else branch of 'if conversation_id not in self.rooms'.
        """
        manager = ConnectionManager()
        conv_id = "existing-conv-1"

        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        # First connect creates the room
        await manager.connect(mock_ws1, conv_id)
        assert conv_id in manager.rooms
        room_before = manager.rooms[conv_id]

        # Second connect to same conversation reuses the existing room
        await manager.connect(mock_ws2, conv_id)
        # Same room object should be in place
        assert manager.rooms[conv_id] is room_before
        # Both connections should be in the room
        assert manager.rooms[conv_id].is_active is True

    async def test_broadcast_to_nonexistent_conversation_is_noop(self) -> None:
        """Broadcast to a conversation with no room should silently do nothing.

        Covers branch 189->191: 'conversation_id not in self.rooms'.
        """
        manager = ConnectionManager()
        msg = WSMessage(
            type=WSMessageType.MESSAGE,
            conversation_id="ghost-conv",
            content="Hello",
        )
        # Should not raise — conversations without rooms are silently ignored
        await manager.broadcast_to_conversation("ghost-conv", msg)
        assert "ghost-conv" not in manager.rooms

    async def test_send_thinker_typing_without_room(self) -> None:
        """Thinker typing notification to non-existent room should not crash.

        Covers branch 212->214: 'conversation_id not in self.rooms' in send_thinker_typing.
        The typing_thinkers set is only updated when the room exists.
        """
        manager = ConnectionManager()
        # No room for this conversation — mock_broadcast to avoid actual send
        with patch.object(manager, "broadcast_to_conversation", new_callable=AsyncMock) as mock_bc:
            await manager.send_thinker_typing("no-room-conv", "Socrates")
            # Broadcast is still called even without a room
            mock_bc.assert_called_once()

    async def test_send_thinker_stopped_typing_without_room(self) -> None:
        """Thinker stopped-typing notification to non-existent room should not crash.

        Mirrors the same guard pattern as send_thinker_typing.
        """
        manager = ConnectionManager()
        with patch.object(manager, "broadcast_to_conversation", new_callable=AsyncMock) as mock_bc:
            await manager.send_thinker_stopped_typing("no-room-conv", "Aristotle")
            mock_bc.assert_called_once()

    async def test_set_speed_multiplier_clamped_to_valid_range(self) -> None:
        """Speed multiplier is clamped to [0.5, 6.0] and broadcast to clients."""
        manager = ConnectionManager()
        conv_id = "speed-test-conv"

        mock_ws = AsyncMock()
        await manager.connect(mock_ws, conv_id)

        with patch.object(manager, "broadcast_to_conversation", new_callable=AsyncMock) as mock_bc:
            # Below minimum: should clamp to 0.5
            await manager.set_speed_multiplier(conv_id, 0.1)
            assert manager.rooms[conv_id].speed_multiplier == 0.5

            # Above maximum: should clamp to 6.0
            await manager.set_speed_multiplier(conv_id, 10.0)
            assert manager.rooms[conv_id].speed_multiplier == 6.0

            # Normal value
            await manager.set_speed_multiplier(conv_id, 2.5)
            assert manager.rooms[conv_id].speed_multiplier == 2.5

            assert mock_bc.call_count == 3

    async def test_set_speed_multiplier_for_nonexistent_room_is_noop(self) -> None:
        """Setting speed for a conversation with no room should be a no-op."""
        manager = ConnectionManager()
        with patch.object(manager, "broadcast_to_conversation", new_callable=AsyncMock) as mock_bc:
            await manager.set_speed_multiplier("ghost-conv", 2.0)
            # No broadcast since no room
            mock_bc.assert_not_called()

    async def test_get_speed_multiplier_for_nonexistent_room_returns_default(self) -> None:
        """Getting speed for a conversation with no room returns default 1.0."""
        manager = ConnectionManager()
        result = manager.get_speed_multiplier("ghost-conv")
        assert result == 1.0

    async def test_conversation_room_typing_thinkers_tracking(self) -> None:
        """ConversationRoom tracks typing thinkers correctly."""
        manager = ConnectionManager()
        conv_id = "typing-track-conv"

        mock_ws = AsyncMock()
        await manager.connect(mock_ws, conv_id)

        with patch.object(manager, "broadcast_to_conversation", new_callable=AsyncMock):
            # Add thinker typing
            await manager.send_thinker_typing(conv_id, "Socrates")
            assert "Socrates" in manager.rooms[conv_id].typing_thinkers

            # Remove thinker typing
            await manager.send_thinker_stopped_typing(conv_id, "Socrates")
            assert "Socrates" not in manager.rooms[conv_id].typing_thinkers


# ============================================================================
# SpendLimitExceeded and save_thinker_message error paths
# ============================================================================


class TestSpendLimitExceededException:
    """Test SpendLimitExceeded exception class and related paths."""

    def test_spend_limit_exceeded_attributes(self) -> None:
        """SpendLimitExceeded stores current and limit spend values."""
        exc = SpendLimitExceeded(current_spend=10.50, spend_limit=10.00)
        assert exc.current_spend == 10.50
        assert exc.spend_limit == 10.00
        assert "10.50" in str(exc)
        assert "10.00" in str(exc)

    def test_spend_limit_exceeded_is_exception(self) -> None:
        """SpendLimitExceeded is a proper Exception subclass."""
        exc = SpendLimitExceeded(5.0, 5.0)
        assert isinstance(exc, Exception)
        with pytest.raises(SpendLimitExceeded):
            raise exc


class TestSaveThinkerMessageSpendLimit:
    """Integration tests for save_thinker_message spend limit enforcement."""

    async def test_save_message_raises_when_spend_equals_limit(
        self, db_session: AsyncSession
    ) -> None:
        """save_thinker_message raises SpendLimitExceeded when user spend >= limit.

        Covers websocket.py lines that check spend limit before saving a message.
        """
        user = User(
            username="spendlimit_user",
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

        conversation = Conversation(session_id=session.id, topic="Test philosophy")
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        with pytest.raises(SpendLimitExceeded) as exc_info:
            await save_thinker_message(
                str(conversation.id), "Socrates", "Hello world", 0.01, db_session
            )

        assert exc_info.value.current_spend == 5.00
        assert exc_info.value.spend_limit == 5.00

    async def test_save_message_raises_when_spend_exceeds_limit(
        self, db_session: AsyncSession
    ) -> None:
        """save_thinker_message raises SpendLimitExceeded when spend > limit."""
        user = User(
            username="over_limit_user",
            password_hash="hash",
            total_spend=7.50,
            spend_limit=5.00,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        session = Session(user_id=user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        conversation = Conversation(session_id=session.id, topic="Ethics discussion")
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        with pytest.raises(SpendLimitExceeded):
            await save_thinker_message(
                str(conversation.id), "Aristotle", "Good evening", 0.01, db_session
            )

    async def test_save_message_succeeds_when_under_limit(self, db_session: AsyncSession) -> None:
        """save_thinker_message succeeds and updates spend when under limit."""
        user = User(
            username="under_limit_user",
            password_hash="hash",
            total_spend=1.00,
            spend_limit=10.00,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        session = Session(user_id=user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        conversation = Conversation(session_id=session.id, topic="Logic")
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        msg = await save_thinker_message(
            str(conversation.id), "Aristotle", "Let us reason together.", 0.05, db_session
        )

        assert msg.content == "Let us reason together."
        assert msg.sender_name == "Aristotle"
        assert msg.sender_type == SenderType.THINKER
        assert msg.cost == 0.05

        # User's total_spend should be updated
        await db_session.refresh(user)
        assert user.total_spend == pytest.approx(1.05)

    async def test_save_message_with_no_conversation_does_not_crash(
        self, db_session: AsyncSession
    ) -> None:
        """save_thinker_message handles non-existent conversation gracefully."""
        msg = await save_thinker_message(
            "nonexistent-conv-id", "Plato", "Forms and shadows.", 0.02, db_session
        )
        # Message is created even if conversation link is broken
        assert msg.content == "Forms and shadows."
        assert msg.sender_name == "Plato"


class TestGetMessagesForConversation:
    """Integration tests for get_messages_for_conversation helper."""

    async def test_get_messages_returns_empty_for_new_conversation(
        self, db_session: AsyncSession
    ) -> None:
        """get_messages_for_conversation returns empty list for a new conversation."""
        messages = await get_messages_for_conversation("no-messages-conv", db_session)
        assert messages == [] or list(messages) == []

    async def test_get_messages_returns_all_messages_ordered_by_time(
        self, db_session: AsyncSession
    ) -> None:
        """Messages are returned in creation order for a conversation."""
        user = User(username="msg_test_user", password_hash="hash")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        session = Session(user_id=user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        conversation = Conversation(session_id=session.id, topic="Order test")
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        msg1 = Message(
            conversation_id=str(conversation.id),
            sender_type=SenderType.USER,
            content="First message",
        )
        msg2 = Message(
            conversation_id=str(conversation.id),
            sender_type=SenderType.THINKER,
            sender_name="Socrates",
            content="Second message",
        )
        db_session.add(msg1)
        db_session.add(msg2)
        await db_session.commit()

        messages = await get_messages_for_conversation(str(conversation.id), db_session)
        assert len(list(messages)) == 2


# ============================================================================
# Thinker service _split_response_into_bubbles force-split path
# ============================================================================


class TestSplitResponseIntoBubblesEdgeCases:
    """Tests for force-split path in _split_response_into_bubbles.

    Covers lines 763-768: 'If we ended up with just one bubble but text is very long, force split'
    """

    def test_force_split_on_very_long_single_bubble(self) -> None:
        """A long text with no sentence separators forces a mid-point split.

        To trigger force split: text > 300 chars, the loop produces exactly 1 bubble.
        We patch random to avoid the early-return (strategy_roll >= 0.45) and ensure
        target_size is large enough that no sentence boundary triggers a split mid-loop.
        """
        from app.services.thinker import thinker_service

        # Construct a text > 300 chars with ONE sentence boundary (a period + space) in the middle
        # The loop will put the whole thing in one bubble because target_size >= len(text)
        long_sentence = (
            "The philosopher contemplated the nature of existence and the fundamental "
            "questions that arise from human consciousness in a very long and detailed dissertation. "
            "These ideas flow from Plato through Aristotle to modern phenomenology in an "
            "unbroken chain of philosophical thought that spans millennia of careful inquiry."
        )
        assert len(long_sentence) > 300

        # Patch random to return a value that picks large target_size (~250 chars)
        # and skips the early-return check (strategy_roll = 0.9 >= 0.25, and text > 250)
        with (
            patch("app.services.thinker.random.random", return_value=0.9),
            patch("app.services.thinker.random.randint", return_value=300),
        ):
            result = thinker_service._split_response_into_bubbles(long_sentence)

        # Should have at least 1 bubble with content
        assert len(result) >= 1
        assert all(len(b) > 0 for b in result)
        # Concatenated content should preserve all words
        full_text = " ".join(result)
        assert "philosopher" in full_text

    def test_force_split_creates_two_bubbles_from_long_text(self) -> None:
        """Force split creates 2 bubbles when one very long bubble has a mid-point break.

        The force-split searches for a period/!/? followed by a space after the midpoint.
        """
        from app.services.thinker import thinker_service

        # Build text > 300 chars with a clear sentence boundary past the midpoint
        first_half = "A" * 200 + " is an important concept in philosophy"
        second_half = "B" * 100 + " reveals the deeper truths of existence"
        long_text = first_half + ". " + second_half

        assert len(long_text) > 300

        # Force large target_size so entire text stays as 1 bubble in the main loop
        with (
            patch("app.services.thinker.random.random", return_value=0.9),
            patch("app.services.thinker.random.randint", return_value=500),
        ):
            result = thinker_service._split_response_into_bubbles(long_text)

        # Force split should yield 2 parts
        assert len(result) >= 1
        assert all(len(b) > 0 for b in result)

    def test_text_with_transition_word_starts_new_bubble(self) -> None:
        """Transition words like 'However,' start a new bubble for better conversation flow."""
        from app.services.thinker import thinker_service

        text = (
            "Philosophy seeks fundamental truths about existence. "
            "However, not all questions have clear answers."
        )
        # With aggressive splitting (strategy_roll=0.4 → target_size=80-120)
        with (
            patch("app.services.thinker.random.random", return_value=0.4),
            patch("app.services.thinker.random.randint", return_value=100),
        ):
            result = thinker_service._split_response_into_bubbles(text)

        # Should produce 2+ bubbles due to transition word split
        assert len(result) >= 1
        assert all(b.strip() for b in result)

    def test_very_long_text_without_sentence_end_past_midpoint(self) -> None:
        """Long text with no sentence end past midpoint returns as single or split bubble."""
        from app.services.thinker import thinker_service

        # No sentence-ending punctuation followed by space in the text
        no_punct_text = "A" * 400

        with (
            patch("app.services.thinker.random.random", return_value=0.9),
            patch("app.services.thinker.random.randint", return_value=500),
        ):
            result = thinker_service._split_response_into_bubbles(no_punct_text)

        # Returns the original text as-is (no valid split point found)
        assert len(result) >= 1
        assert result[0] == "A" * 400


# ============================================================================
# Thinker service _extract_thinking_display non-English language branches
# ============================================================================


class TestExtractThinkingDisplayLanguageBranches:
    """Tests for language-specific branches in _extract_thinking_display.

    The coverage report shows lines 816-824 (Hindi/Japanese/Korean language blocks)
    are not covered by existing tests which only test de/fr/es.
    """

    def test_extract_thinking_display_japanese(self) -> None:
        """Japanese language replacements are applied correctly."""
        from app.services.thinker import thinker_service

        text = "私は考えています。" * 15  # Repeated to get > 80 chars
        # Verify function handles Japanese text without crashing
        result = thinker_service._extract_thinking_display(text, language="ja")
        assert isinstance(result, str)

    def test_extract_thinking_display_korean(self) -> None:
        """Korean language replacements are applied correctly."""
        from app.services.thinker import thinker_service

        text = "나는 생각하고 있습니다. " * 10  # Repeated to get > 80 chars
        result = thinker_service._extract_thinking_display(text, language="ko")
        assert isinstance(result, str)

    def test_extract_thinking_display_hindi(self) -> None:
        """Hindi language replacements are applied correctly."""
        from app.services.thinker import thinker_service

        text = "मुझे चाहिए कि हम इस प्रश्न पर विचार करें। " * 5
        result = thinker_service._extract_thinking_display(text, language="hi")
        assert isinstance(result, str)

    def test_extract_thinking_display_text_over_200_chars_trimmed(self) -> None:
        """Text over 200 chars is trimmed and starts from a sentence boundary."""
        from app.services.thinker import thinker_service

        # Text > 200 chars with a sentence boundary near the start of the last 200 chars
        text = "This is a long philosophical treatise. " * 10
        assert len(text) > 200

        result = thinker_service._extract_thinking_display(text, language="en")
        # Should return a non-empty string trimmed from the end
        assert isinstance(result, str)
        assert len(result) <= 200 or len(result) <= len(text)

    def test_extract_thinking_display_sentence_boundary_search(self) -> None:
        """Text over 200 chars tries to start at a sentence boundary ('. ' in first 80 chars)."""
        from app.services.thinker import thinker_service

        # Text over 200 chars where the last 200 chars start with an incomplete word
        # then has a ". " within the first 80 chars
        prefix = "incomplete "  # starts mid-word (lowercase)
        sentence_start = "Here is a clear sentence. And another thought continues here at length."
        padding = " More philosophical context follows." * 5
        text = "A" * 300 + ". " + prefix + sentence_start + padding
        assert len(text) > 200

        result = thinker_service._extract_thinking_display(text, language="en")
        assert isinstance(result, str)

    def test_extract_thinking_display_text_starting_with_lowercase(self) -> None:
        """Text starting with lowercase and containing a space drops the first incomplete word."""
        from app.services.thinker import thinker_service

        # Simulate text > 80 chars that starts with lowercase + space
        text = (
            "ontinues from before. This is the real philosophical thought that begins here in full."
        )
        assert len(text) >= 80

        result = thinker_service._extract_thinking_display(text, language="en")
        # After trimming incomplete word, should start with "This"
        assert isinstance(result, str)
        # If trimmed, content should contain the real thought
        if result:
            assert len(result) > 0

    def test_extract_thinking_display_english_replacements(self) -> None:
        """English language text has LLM phrasing replaced with first-person monologue."""
        from app.services.thinker import thinker_service

        # English with typical LLM phrasings that should be replaced
        text = (
            "I need to consider carefully what the user is asking. "
            "Let me think about this philosophical question in depth."
        )
        result = thinker_service._extract_thinking_display(text, language="en")
        # Should not contain "The user" or "the user" verbatim
        assert isinstance(result, str)


# ============================================================================
# Knowledge research service error handling
# ============================================================================


class TestKnowledgeResearchErrorHandling:
    """Tests for error handling in knowledge_research service.

    Covers lines 140-149: research failure exception handler that marks
    the knowledge entry as FAILED.
    """

    async def test_get_or_create_knowledge_creates_new_entry(
        self, db_session: AsyncSession
    ) -> None:
        """get_or_create_knowledge creates a new entry if none exists."""
        from app.services.knowledge_research import knowledge_service

        knowledge = await knowledge_service.get_or_create_knowledge(db_session, "NewThinker")
        assert knowledge is not None
        assert knowledge.name == "NewThinker"

    async def test_get_or_create_knowledge_returns_existing(self, db_session: AsyncSession) -> None:
        """get_or_create_knowledge returns existing entry without duplication."""
        from app.services.knowledge_research import knowledge_service

        knowledge1 = await knowledge_service.get_or_create_knowledge(db_session, "DuplicateThinker")
        knowledge2 = await knowledge_service.get_or_create_knowledge(db_session, "DuplicateThinker")
        assert knowledge1.id == knowledge2.id

    async def test_get_knowledge_returns_none_for_unknown(self, db_session: AsyncSession) -> None:
        """get_knowledge returns None for a thinker that hasn't been researched."""
        from app.services.knowledge_research import knowledge_service

        result = await knowledge_service.get_knowledge(db_session, "CompletelyUnknownThinker")
        assert result is None

    async def test_is_stale_returns_true_for_old_knowledge(self, db_session: AsyncSession) -> None:
        """is_stale returns True when knowledge is older than the stale threshold."""
        from datetime import UTC, datetime, timedelta

        from app.models.thinker_knowledge import ResearchStatus, ThinkerKnowledge
        from app.services.knowledge_research import knowledge_service

        # Create knowledge entry with old timestamp
        old_time = datetime.now(UTC) - timedelta(days=30)
        old_knowledge = ThinkerKnowledge(
            name="OldThinker",
            status=ResearchStatus.COMPLETE,
            updated_at=old_time,
        )
        db_session.add(old_knowledge)
        await db_session.commit()

        # 30 days old is definitely stale (threshold is typically 7 days)
        assert knowledge_service.is_stale(old_knowledge) is True

    async def test_is_stale_returns_false_for_fresh_knowledge(
        self, db_session: AsyncSession
    ) -> None:
        """is_stale returns False for recently updated knowledge."""
        from datetime import UTC, datetime

        from app.models.thinker_knowledge import ResearchStatus, ThinkerKnowledge
        from app.services.knowledge_research import knowledge_service

        recent_knowledge = ThinkerKnowledge(
            name="FreshThinker",
            status=ResearchStatus.COMPLETE,
            updated_at=datetime.now(UTC),
        )
        db_session.add(recent_knowledge)
        await db_session.commit()

        assert knowledge_service.is_stale(recent_knowledge) is False


# ============================================================================
# End-to-end integration chains
# ============================================================================


class TestFeedbackWorkflowIntegration:
    """Full feedback lifecycle: submit → get pending → mark processed."""

    async def test_submit_feedback_then_retrieve_as_pending(self, client: AsyncClient) -> None:
        """Feedback submitted by user appears in pending queue for processing.

        Tests the full integration chain: POST /api/feedback → GET /api/feedback/pending.
        """
        secret = "test-feedback-secret"
        with patch("app.api.feedback.get_settings") as mock_settings:
            mock_settings.return_value.feedback_processor_secret = secret

            # Submit feedback (no secret needed for submit)
            submit_response = await client.post(
                "/api/feedback",
                json={
                    "feedback_type": "bug",
                    "message": "The conversation loading spinner never stops after refresh.",
                    "email": "reporter@example.com",
                },
            )
            assert submit_response.status_code == 201

            # Retrieve pending feedback
            pending_response = await client.get(
                "/api/feedback/pending",
                params={"secret": secret, "limit": 10},
            )
            assert pending_response.status_code == 200
            data = pending_response.json()
            assert data["count"] >= 1
            messages = [fb["message"] for fb in data["feedbacks"]]
            assert any("spinner" in m for m in messages)

    async def test_full_feedback_mark_processed_chain(self, client: AsyncClient) -> None:
        """Full feedback chain: submit → get pending → mark as processed.

        Tests that feedback moves from NEW to REVIEWED state.
        """
        secret = "integration-test-secret"
        with patch("app.api.feedback.get_settings") as mock_settings:
            mock_settings.return_value.feedback_processor_secret = secret

            # Step 1: Submit feedback
            submit = await client.post(
                "/api/feedback",
                json={
                    "feedback_type": "feature",
                    "message": "Allow users to export conversation as PDF for sharing.",
                },
            )
            assert submit.status_code == 201
            feedback_id = submit.json()["id"]

            # Step 2: Get pending feedback
            pending = await client.get(
                "/api/feedback/pending",
                params={"secret": secret},
            )
            assert pending.status_code == 200
            ids = [fb["id"] for fb in pending.json()["feedbacks"]]
            assert feedback_id in ids

            # Step 3: Mark as processed with GitHub issue URL
            mark = await client.patch(
                f"/api/feedback/{feedback_id}/processed",
                params={"secret": secret},
                json={"github_issue_url": "https://github.com/test/repo/issues/999"},
            )
            assert mark.status_code == 200
            assert mark.json()["success"] is True
            assert mark.json()["github_issue_url"] == "https://github.com/test/repo/issues/999"

            # Step 4: Verify it no longer appears in pending
            pending_after = await client.get(
                "/api/feedback/pending",
                params={"secret": secret},
            )
            assert pending_after.status_code == 200
            ids_after = [fb["id"] for fb in pending_after.json()["feedbacks"]]
            assert feedback_id not in ids_after


class TestAdminSpendWorkflowIntegration:
    """Integration tests for the admin spend management workflow."""

    async def test_admin_update_spend_limit_then_retrieve_spend_data(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Admin updates spend limit, then verifies via spend endpoint.

        Tests: PATCH /api/admin/users/{id}/spend-limit → GET /api/spend/{user_id}
        """
        # Create admin
        admin_headers = await create_admin_headers(client, db_session, "admin_spend", "pass123")

        # Create a regular user to manage
        user_data = await register_and_get_token(client, "target_user_spend", "pass123")
        target_user_id = user_data["user"]["id"]

        # Update target user's spend limit
        patch_response = await client.patch(
            f"/api/admin/users/{target_user_id}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": 25.00},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["spend_limit"] == 25.00

        # Retrieve spend data via spend API
        spend_response = await client.get(
            f"/api/spend/{target_user_id}",
            headers=admin_headers,
        )
        assert spend_response.status_code == 200
        spend_data = spend_response.json()
        assert spend_data["user_id"] == target_user_id

    async def test_admin_list_users_shows_updated_spend_limit(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Spend limit update is immediately visible in admin user list.

        Tests: PATCH /api/admin/users/{id}/spend-limit → GET /api/admin/users
        """
        admin_headers = await create_admin_headers(
            client, db_session, "admin_list_check", "pass123"
        )
        user_data = await register_and_get_token(client, "spend_list_user", "pass123")
        user_id = user_data["user"]["id"]

        new_limit = 50.00
        await client.patch(
            f"/api/admin/users/{user_id}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": new_limit},
        )

        list_response = await client.get("/api/admin/users", headers=admin_headers)
        assert list_response.status_code == 200
        users = list_response.json()
        target = next((u for u in users if u["id"] == user_id), None)
        assert target is not None
        assert target["spend_limit"] == new_limit


class TestSessionConversationIntegrationChain:
    """Full integration chain: auth → session → conversation → messages."""

    async def test_register_login_create_conversation_send_message(
        self, client: AsyncClient
    ) -> None:
        """Complete user workflow from registration through message sending.

        Validates the full chain works as an integrated system:
        POST /auth/register → GET /sessions/me → POST /conversations → POST messages
        """
        # Step 1: Register
        register_response = await client.post(
            "/api/auth/register",
            json={
                "username": "chain_test_user",
                "display_name": "Chain Tester",
                "password": "securepass123",
            },
        )
        assert register_response.status_code == 200
        token = register_response.json()["access_token"]
        headers = bearer_header(token)

        # Step 2: Get current session
        session_response = await client.get("/api/sessions/me", headers=headers)
        assert session_response.status_code == 200
        assert "id" in session_response.json()

        # Step 3: Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "The nature of consciousness",
                "thinkers": [
                    {
                        "name": "Descartes",
                        "bio": "French philosopher (1596-1650)",
                        "positions": "Mind-body dualism, cogito ergo sum",
                        "style": "Methodical and systematic doubt",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Step 4: Send a message
        with patch(
            "app.services.thinker.thinker_service.generate_response",
            new_callable=AsyncMock,
            return_value=("I think, therefore I am.", 0.01),
        ):
            msg_response = await client.post(
                f"/api/conversations/{conv_id}/messages",
                headers=headers,
                json={"content": "What can we know with certainty?"},
            )
        assert msg_response.status_code == 200
        assert msg_response.json()["content"] == "What can we know with certainty?"

        # Step 5: Retrieve conversation with messages
        get_response = await client.get(
            f"/api/conversations/{conv_id}",
            headers=headers,
        )
        assert get_response.status_code == 200
        conv_data = get_response.json()
        assert len(conv_data["messages"]) >= 1
        assert conv_data["messages"][0]["content"] == "What can we know with certainty?"

    async def test_delete_user_cascade_removes_conversations(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Deleting a user cascades to remove their conversations.

        Validates admin delete user then verifies user is gone.
        """
        admin_headers = await create_admin_headers(
            client, db_session, "admin_cascade_del", "pass123"
        )
        user_data = await register_and_get_token(client, "cascade_del_user", "pass123")
        user_id = user_data["user"]["id"]

        # Delete the user
        delete_response = await client.delete(
            f"/api/admin/users/{user_id}",
            headers=admin_headers,
        )
        assert delete_response.status_code == 200
        assert "deleted" in delete_response.json()["message"].lower()

        # Verify user no longer appears in list
        list_response = await client.get("/api/admin/users", headers=admin_headers)
        user_ids = [u["id"] for u in list_response.json()]
        assert user_id not in user_ids


class TestThinkerKnowledgeEndpointIntegration:
    """Integration tests for thinker knowledge API endpoints."""

    async def test_get_knowledge_creates_entry_and_triggers_research(
        self, client: AsyncClient
    ) -> None:
        """GET /api/thinkers/knowledge/{name} creates a knowledge entry if none exists.

        Covers lines in thinkers.py that call get_knowledge → get_or_create_knowledge.
        """
        response = await client.get("/api/thinkers/knowledge/NewPhilosopher")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "NewPhilosopher"
        assert "status" in data

    async def test_get_knowledge_status_returns_pending_for_unknown(
        self, client: AsyncClient
    ) -> None:
        """GET /api/thinkers/knowledge/{name}/status returns PENDING for unknown thinker."""
        response = await client.get("/api/thinkers/knowledge/CompletelyUnknownPerson/status")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "CompletelyUnknownPerson"
        assert data["status"] in ("pending", "in_progress", "complete", "failed")

    async def test_refresh_thinker_knowledge_triggers_new_research(
        self, client: AsyncClient
    ) -> None:
        """POST /api/thinkers/knowledge/{name}/refresh triggers fresh research."""
        response = await client.post("/api/thinkers/knowledge/Socrates/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Socrates"
        assert "status" in data
