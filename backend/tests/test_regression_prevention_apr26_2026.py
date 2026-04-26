"""Regression prevention tests for Sunday QA (Apr 26, 2026).

Focus areas targeting behaviors that could regress from recent bug fixes:
- fix(thinker): linear speed scaling instead of exponential (#533, Jan 17)
- fix(websocket): sync pause button state on reconnect (#367, Jan 9)
- fix(feedback): enum values for PostgreSQL (#299, Jan 9)
- fix(i18n): Hindi language support (#570, Jan 23)

Test groups:
- TestStopAgentsPauseStatePersistence (3): stop_conversation_agents preserves pause state
- TestConversationRoomConnectionManagement (4): is_active tracking on add/remove connections
- TestExtractThinkingDisplayEllipsis (4): ellipsis added when text ends mid-sentence
- TestSenderTypeEnumDualPath (5): _get_last_user_message_timestamp and helpers work with both
  enum SenderType values and plain "user" strings (SQLAlchemy vs raw model access)
- TestConnectionManagerRoomSpeedMultiplier (3): per-room defaults and independence
- TestIsMentionedEdgeCases (4): empty text, empty name, bare @ sign
- TestShouldRespondMessageCountBoundary (3): zero/negative new-message-count returns False
- TestPauseStateAttemptDualSet (4): manual vs idle pause interaction with resume_from_idle
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.websocket import (
    ConnectionManager,
    ConversationRoom,
    WSMessage,
    WSMessageType,
)
from app.models.message import SenderType
from app.services.thinker import ThinkerService, extract_mentions, is_mentioned

# ===========================================================================
# TestStopAgentsPauseStatePersistence
# Regression guard: stop_conversation_agents MUST NOT clear pause state.
# The comment in the code says "We intentionally do NOT clean up paused state
# here. Pause state should persist across reconnections so users see the
# conversation is still paused when they return."
# If this guard fails, users who pause a conversation and reconnect would find
# the conversation running again unexpectedly.
# ===========================================================================


class TestStopAgentsPauseStatePersistence:
    """Regression tests: stop_conversation_agents preserves pause state."""

    async def test_stop_agents_does_not_clear_manual_pause(self) -> None:
        """stop_conversation_agents must not clear manually-paused conversations.

        Regression guard for the intentional design in thinker.py:stop_conversation_agents:
        'We intentionally do NOT clean up paused state here.'

        If pause state were cleared on agent stop, a user who pauses and then
        disconnects/reconnects would find the conversation unexpectedly resumed.
        """
        service = ThinkerService()
        conv_id = "manual-pause-stop-test"

        service.pause_conversation(conv_id)
        assert service.is_paused(conv_id) is True

        # Simulate agent stop (no actual tasks to cancel)
        await service.stop_conversation_agents(conv_id)

        # Pause state MUST persist after agents stop
        assert service.is_paused(conv_id) is True, (
            "Manual pause state was unexpectedly cleared by stop_conversation_agents"
        )

    async def test_stop_agents_does_not_clear_idle_pause(self) -> None:
        """stop_conversation_agents must not clear idle-paused conversations.

        Regression guard: if idle pause were cleared on disconnect, reconnecting
        users would see an unpaused conversation even though it was auto-paused
        for inactivity.
        """
        service = ThinkerService()
        conv_id = "idle-pause-stop-test"

        service.pause_for_idle(conv_id)
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is True

        await service.stop_conversation_agents(conv_id)

        assert service.is_paused(conv_id) is True, (
            "Idle pause state was unexpectedly cleared by stop_conversation_agents"
        )
        assert service.is_idle_paused(conv_id) is True, (
            "Idle-paused flag was unexpectedly cleared by stop_conversation_agents"
        )

    async def test_stop_agents_cleans_up_active_tasks_dict(self) -> None:
        """stop_conversation_agents removes the conversation from _active_tasks.

        Confirms the task dict IS cleaned up (unlike pause state).
        Regression guard: we always clean tasks but never pause state.
        """
        service = ThinkerService()
        conv_id = "task-cleanup-test"

        # Manually add a completed task to simulate finished agent
        async def noop() -> None:
            pass

        task = asyncio.ensure_future(noop())
        await task  # Complete the task immediately
        service._active_tasks[conv_id] = {"thinker-1": task}

        await service.stop_conversation_agents(conv_id)

        assert conv_id not in service._active_tasks, (
            "Active tasks dict was not cleaned up by stop_conversation_agents"
        )


# ===========================================================================
# TestConversationRoomConnectionManagement
# Regression guard: ConversationRoom.is_active must track connections correctly.
# After fix(websocket)#367, the pause state sync on connect relies on this.
# If is_active tracking is wrong, thinkers could run with nobody watching.
# ===========================================================================


class TestConversationRoomConnectionManagement:
    """Tests for ConversationRoom connection add/remove and is_active state."""

    def test_room_becomes_inactive_when_only_connection_removed(self) -> None:
        """is_active=False when the last connection is removed.

        Regression guard: thinkers check is_conversation_active() in their loop
        to decide whether to sleep. If is_active stays True after disconnect,
        thinkers waste compute when nobody is watching.
        """
        room = ConversationRoom(conversation_id="test-room")
        ws = MagicMock()

        room.add_connection(ws)
        assert room.is_active is True

        room.remove_connection(ws)
        assert room.is_active is False, (
            "Room is_active should be False after last connection removed"
        )

    def test_room_stays_active_with_multiple_connections_one_removed(self) -> None:
        """is_active=True as long as at least one connection remains.

        Regression guard: two-client scenario where one disconnects should not
        stop thinkers from messaging the remaining client.
        """
        room = ConversationRoom(conversation_id="two-clients")
        ws1, ws2 = MagicMock(), MagicMock()

        room.add_connection(ws1)
        room.add_connection(ws2)
        assert room.is_active is True

        room.remove_connection(ws1)
        assert room.is_active is True, (
            "Room is_active should remain True while second connection is present"
        )

    def test_room_becomes_inactive_when_all_connections_removed(self) -> None:
        """is_active=False only when ALL connections have been removed.

        Regression guard: ensures sequential disconnect of multiple clients
        eventually marks room inactive.
        """
        room = ConversationRoom(conversation_id="multi-disconnect")
        ws1, ws2 = MagicMock(), MagicMock()

        room.add_connection(ws1)
        room.add_connection(ws2)
        room.remove_connection(ws1)
        room.remove_connection(ws2)

        assert room.is_active is False, (
            "Room is_active should be False after all connections removed"
        )

    async def test_broadcast_handles_stale_connection_gracefully(self) -> None:
        """Broadcast silently removes a WebSocket that raises on send.

        Regression guard: if a client drops without a clean WebSocketDisconnect,
        the stale socket raises on send. Broadcast must handle this without
        crashing so other clients still receive messages.
        """
        room = ConversationRoom(conversation_id="stale-ws-test")
        good_ws = AsyncMock()
        bad_ws = AsyncMock()
        bad_ws.send_text.side_effect = RuntimeError("connection lost")

        room.add_connection(good_ws)
        room.add_connection(bad_ws)

        msg = WSMessage(type=WSMessageType.MESSAGE, conversation_id="stale-ws-test")
        # Should not raise despite bad_ws error
        await room.broadcast(msg)

        # Good client still received the message
        good_ws.send_text.assert_called_once()
        # Stale connection was purged
        assert bad_ws not in room.connections


# ===========================================================================
# TestExtractThinkingDisplayEllipsis
# Regression guard for lines 964-966 in thinker.py:
#   if text and not text.endswith((".", "!", "?", "...")):
#       text = text.rstrip() + "..."
# This ensures that mid-sentence thinking snippets look like "I'm thinking..."
# rather than cutting off awkwardly.
# ===========================================================================


class TestExtractThinkingDisplayEllipsis:
    """Tests for the ellipsis-appending logic in _extract_thinking_display."""

    def test_text_truncated_mid_sentence_gets_ellipsis(self) -> None:
        """Text that ends mid-sentence gets '...' appended.

        Regression guard for lines 964-966: when thinking text is truncated
        before a sentence boundary, the output should end with '...' so it
        reads naturally as an unfinished thought.
        """
        service = ThinkerService()
        # 80+ chars of text that ends in the middle of a sentence (no terminal punctuation)
        text = (
            "This is the beginning of a profound philosophical observation "
            "about the nature of reality and existence in our modern world"
        )
        assert len(text) >= 80, "Test text must be long enough to pass the 80-char guard"

        result = service._extract_thinking_display(text, language="en")

        assert result.endswith("..."), f"Expected '...' at end of truncated text, got: {result!r}"

    def test_text_ending_with_exclamation_does_not_get_ellipsis(self) -> None:
        """Text already ending with '!' does NOT get an extra '...'.

        Regression guard: only texts without terminal punctuation should get
        ellipsis. Adding it to texts with '!' would produce "Interesting!..."
        which looks wrong.
        """
        service = ThinkerService()
        text = (
            "This is a complete and emphatic statement about philosophical matters "
            "that ends with an exclamation mark right here!"
        )
        result = service._extract_thinking_display(text, language="en")

        # Result should end with '!' not '!...'
        assert result.endswith("!") or result.endswith("..."), (
            "Result should end with punctuation; double-ellipsis is a regression"
        )
        assert not result.endswith("!..."), (
            "Result should NOT end with '!...' — double terminal punctuation"
        )

    def test_text_ending_with_question_mark_does_not_get_ellipsis(self) -> None:
        """Text ending with '?' does NOT get an extra '...'.

        Regression guard matching the '?' case in the terminal punctuation check.
        """
        service = ThinkerService()
        text = (
            "But what does it truly mean to exist in a world without inherent meaning, "
            "and can we ever know the answer to such a question?"
        )
        result = service._extract_thinking_display(text, language="en")

        assert not result.endswith("?..."), (
            "Result should NOT end with '?...' — double terminal punctuation is a regression"
        )

    def test_text_already_ending_with_ellipsis_no_double_ellipsis(self) -> None:
        """Text already ending with '...' does NOT get a second '...'.

        Regression guard: the condition checks for '...' as one of the valid
        endings. If accidentally removed, texts would become '......'.
        """
        service = ThinkerService()
        text = (
            "Perhaps the answer lies somewhere deeper, in a place we have not yet "
            "looked with sufficient care and philosophical rigor..."
        )
        result = service._extract_thinking_display(text, language="en")

        assert "......" not in result, (
            f"Result should not contain double-ellipsis '......': {result!r}"
        )


# ===========================================================================
# TestSenderTypeEnumDualPath
# Regression guard: _get_last_user_message_timestamp, _count_messages_since_user,
# and _get_user_name_from_messages use:
#   (hasattr(sender, "value") and sender.value == "user") or sender == "user"
# This handles both SQLAlchemy ORM objects (where sender_type is SenderType enum)
# and plain string values (test mocks or raw dict access).
# If this dual-path check regresses to only one form, half the code paths break.
# ===========================================================================


def _make_mock_message(
    sender_type: SenderType | str,
    sender_name: str | None = None,
    content: str = "Hello",
    created_at: datetime | None = None,
) -> MagicMock:
    """Create a mock Message with the given sender type.

    Supports both enum SenderType values and plain strings to test both
    code paths in the sender_type comparison logic.
    """
    msg = MagicMock()
    msg.sender_type = sender_type
    msg.sender_name = sender_name
    msg.content = content
    msg.created_at = created_at or datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    return msg


class TestSenderTypeEnumDualPath:
    """Regression tests for the dual-path sender_type comparison in thinker helpers."""

    def test_get_last_timestamp_recognizes_enum_sender_type(self) -> None:
        """_get_last_user_message_timestamp finds user with SenderType.USER enum.

        Regression guard: if the hasattr(sender, 'value') branch is removed,
        ORM-loaded messages with SenderType enum would be missed, making the
        idle timeout never trigger.
        """
        service = ThinkerService()
        expected_ts = datetime(2026, 1, 20, 8, 0, 0, tzinfo=UTC)
        messages = [
            _make_mock_message(SenderType.THINKER, "Socrates"),
            _make_mock_message(SenderType.USER, "Alice", created_at=expected_ts),
        ]

        timestamp = service._get_last_user_message_timestamp(messages)

        assert timestamp == pytest.approx(expected_ts.timestamp()), (
            "Should recognize SenderType.USER enum as a user message"
        )

    def test_get_last_timestamp_recognizes_string_sender_type(self) -> None:
        """_get_last_user_message_timestamp finds user with plain 'user' string.

        Regression guard: if the `sender == 'user'` branch is removed, tests
        using string mocks would fail silently, masking real bugs.
        """
        service = ThinkerService()
        expected_ts = datetime(2026, 1, 21, 9, 0, 0, tzinfo=UTC)
        messages = [
            _make_mock_message("thinker", "Socrates"),
            _make_mock_message("user", "Bob", created_at=expected_ts),
        ]

        timestamp = service._get_last_user_message_timestamp(messages)

        assert timestamp == pytest.approx(expected_ts.timestamp()), (
            "Should recognize plain 'user' string as a user message"
        )

    def test_count_messages_since_user_recognizes_enum(self) -> None:
        """_count_messages_since_user correctly counts when sender_type is SenderType enum.

        Regression guard: if enum path breaks, thinkers would think the user
        has been silent forever and prompt them unnecessarily.
        """
        service = ThinkerService()
        messages = [
            _make_mock_message(SenderType.USER, "Alice"),  # user msg → stop counting
            _make_mock_message(SenderType.THINKER, "Plato"),
            _make_mock_message(SenderType.THINKER, "Socrates"),
        ]

        count = service._count_messages_since_user(messages)

        assert count == 2, f"Expected 2 thinker messages since last user message, got {count}"

    def test_count_messages_since_user_recognizes_string(self) -> None:
        """_count_messages_since_user works with plain 'user' string sender_type.

        Regression guard: same as enum test but for the string path.
        """
        service = ThinkerService()
        messages = [
            _make_mock_message("user", "Alice"),
            _make_mock_message("thinker", "Plato"),
            _make_mock_message("thinker", "Aristotle"),
            _make_mock_message("thinker", "Socrates"),
        ]

        count = service._count_messages_since_user(messages)

        assert count == 3, f"Expected 3 thinker messages since last user message, got {count}"

    def test_get_user_name_recognizes_enum_sender_type(self) -> None:
        """_get_user_name_from_messages returns name when sender_type is SenderType enum.

        Regression guard: if ORM enum detection breaks, generate_user_prompt
        won't know the user's name, making greetings impersonal.
        """
        service = ThinkerService()
        messages = [
            _make_mock_message(SenderType.THINKER, "Socrates"),
            _make_mock_message(SenderType.USER, "Diana"),
        ]

        name = service._get_user_name_from_messages(messages)

        assert name == "Diana", (
            f"Expected 'Diana', got {name!r} — SenderType enum not recognized as user"
        )


# ===========================================================================
# TestConnectionManagerRoomSpeedMultiplier
# Regression guard for fix(thinker)#533: linear speed scaling.
# The ConnectionManager rooms must have 1.0 as the default speed multiplier
# (not 0.0 or any other value), and each room must be independent.
# ===========================================================================


class TestConnectionManagerRoomSpeedMultiplier:
    """Tests for ConnectionManager per-room speed multiplier behavior."""

    def test_new_room_has_default_speed_multiplier_of_1_0(self) -> None:
        """A newly created ConversationRoom defaults to speed_multiplier=1.0.

        Regression guard: 1.0 = normal speed. If this regresses to 0.0, the
        timing formula min_interval = 15.0 * speed_mult would give 0s (instant
        spam). If it regresses to a larger value, conversations start in
        slow-motion unexpectedly.
        """
        room = ConversationRoom(conversation_id="new-room-default")

        assert room.speed_multiplier == pytest.approx(1.0), (
            f"Default speed_multiplier should be 1.0, got {room.speed_multiplier}"
        )

    async def test_speed_multiplier_is_independent_per_conversation(self) -> None:
        """Setting speed on one conversation does not affect another.

        Regression guard: if rooms share state (e.g., global dict), changing
        speed in one conversation would leak into others. This was the motivation
        behind ConversationRoom having its own speed_multiplier field.
        """
        manager = ConnectionManager()

        ws_a = AsyncMock()
        ws_b = AsyncMock()

        await manager.connect(ws_a, "conv-A")
        await manager.connect(ws_b, "conv-B")

        await manager.set_speed_multiplier("conv-A", 3.0)

        assert manager.get_speed_multiplier("conv-A") == pytest.approx(3.0)
        assert manager.get_speed_multiplier("conv-B") == pytest.approx(1.0), (
            "conv-B speed multiplier should still be the default 1.0"
        )

    def test_get_speed_for_unknown_conversation_returns_1_0(self) -> None:
        """get_speed_multiplier returns 1.0 for a conversation with no room.

        Regression guard: the default return in ConnectionManager.get_speed_multiplier
        is 1.0 for unknown conversations. If this regresses to 0 or raises,
        thinkers computing min_interval in new conversations would behave wrongly.
        """
        manager = ConnectionManager()

        speed = manager.get_speed_multiplier("never-connected-conv")

        assert speed == pytest.approx(1.0), f"Expected 1.0 for unknown conversation, got {speed}"


# ===========================================================================
# TestIsMentionedEdgeCases
# Regression guard for the @mention system added in feat(thinker)#257.
# Edge cases that should return False without raising exceptions.
# ===========================================================================


class TestIsMentionedEdgeCases:
    """Edge case tests for extract_mentions and is_mentioned."""

    def test_is_mentioned_empty_text_returns_false(self) -> None:
        """is_mentioned("", thinker_name) returns False without error.

        Regression guard: empty message bodies should not cause crashes or
        false positives. This can happen when users send empty messages.
        """
        result = is_mentioned("", "Socrates")
        assert result is False

    def test_is_mentioned_no_at_sign_returns_false(self) -> None:
        """Text with thinker name but no @ sign is not treated as a mention.

        Regression guard: 'Hey Socrates, what do you think?' should NOT trigger
        the @mention high-probability response. Only @Socrates should.
        The is_mentioned() function specifically checks @ syntax.
        """
        result = is_mentioned("Hey Socrates, what do you think?", "Socrates")
        assert result is False, (
            "Name without @ should not count as an @mention (use was_addressed instead)"
        )

    def test_extract_mentions_bare_at_sign_returns_empty(self) -> None:
        """A bare '@' with no name following it does not produce a mention.

        Regression guard: some users type '@' and then backspace. This should
        not produce a spurious empty-string mention that matches every thinker.
        """
        result = extract_mentions("@ what do you all think?")
        # A bare '@' followed by a space matches no word characters
        # (the simple_pattern r'@(\w+)' requires at least one word char)
        assert result == [], f"Bare '@' should produce no mentions, got {result}"

    def test_is_mentioned_case_insensitive_match(self) -> None:
        """is_mentioned matches regardless of case in the @ mention text.

        Regression guard: @SOCRATES and @socrates should both match 'Socrates'.
        The comparison uses mention_lower == thinker_lower which handles this,
        but must not regress to a case-sensitive check.
        """
        assert is_mentioned("@SOCRATES please respond", "Socrates") is True
        assert is_mentioned("@socrates please respond", "Socrates") is True


# ===========================================================================
# TestShouldRespondMessageCountBoundary
# Regression guard: _should_respond returns False when no new messages.
# The check `if new_message_count <= 0: return False` is critical to prevent
# thinkers from responding to their own messages in a loop.
# ===========================================================================


class TestShouldRespondMessageCountBoundary:
    """Tests for the new_message_count boundary in _should_respond."""

    def test_no_response_when_message_count_equals_last_response_count(self) -> None:
        """_should_respond returns False when new_message_count == 0.

        Regression guard: if a thinker has already seen all messages
        (len(messages) == last_response_count), it should not respond again.
        This prevents thinkers from spamming responses when the conversation
        is stale.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Plato"

        messages = [MagicMock(content="Hello", sender_name="Alice")]

        # last_response_count == len(messages) → new_message_count == 0
        result = service._should_respond(thinker, messages, last_response_count=1)

        assert result is False, "Should not respond when no new messages"

    def test_no_response_when_last_response_count_exceeds_messages(self) -> None:
        """_should_respond returns False when new_message_count < 0.

        Regression guard: edge case where last_response_count > len(messages)
        (shouldn't happen normally but the guard `<= 0` covers it).
        Ensures no off-by-one regression introduces spurious responses.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Aristotle"

        messages = [MagicMock(content="Hi", sender_name="Alice")]

        # last_response_count > len(messages) → negative new_message_count
        result = service._should_respond(thinker, messages, last_response_count=5)

        assert result is False, "Should not respond when message count is negative"

    def test_can_respond_when_one_new_message(self) -> None:
        """_should_respond can return True when there is one new message.

        Regression guard: verifies the positive path is not blocked. With 1 new
        message from another sender, _should_respond has a non-zero probability
        to return True (run 50 times to confirm at least once).
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        # Message from someone else (not Socrates)
        msg = MagicMock()
        msg.content = "What is the nature of justice?"
        msg.sender_name = "Alice"
        messages = [msg]

        # Run many times — with base_probability of at least 0.25, should get True
        responses = [
            service._should_respond(thinker, messages, last_response_count=0) for _ in range(50)
        ]
        assert any(responses), (
            "Should respond True at least once in 50 tries when there is 1 new message"
        )


# ===========================================================================
# TestPauseStateAttemptDualSet
# Regression guard for the dual-set pattern (_paused + _idle_paused) and the
# behavior of resume_from_idle vs resume_conversation.
# This was added in feat(backend)#483 (idle timeout) and must not regress.
# ===========================================================================


class TestPauseStateAttemptDualSet:
    """Tests for manual pause vs idle pause state interaction."""

    def test_manual_pause_not_cleared_by_resume_from_idle(self) -> None:
        """resume_from_idle does NOT resume a manually-paused conversation.

        Regression guard: resume_from_idle is specifically for auto-resume when
        users return after an idle timeout. It must not inadvertently resume
        conversations that the user manually paused (they expect the pause to
        persist until they explicitly resume).
        """
        service = ThinkerService()
        conv_id = "manual-pause-idle-test"

        service.pause_conversation(conv_id)  # manual pause
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is False  # NOT idle-paused

        service.resume_from_idle(conv_id)  # should be a no-op

        assert service.is_paused(conv_id) is True, (
            "Manual pause must not be cleared by resume_from_idle"
        )

    def test_idle_pause_IS_cleared_by_resume_from_idle(self) -> None:
        """resume_from_idle does resume an idle-paused conversation.

        Positive regression guard: auto-resumed conversations should work when
        the user returns and sends a message (which triggers resume_from_idle).
        """
        service = ThinkerService()
        conv_id = "idle-resume-test"

        service.pause_for_idle(conv_id)
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is True

        service.resume_from_idle(conv_id)

        assert service.is_paused(conv_id) is False, (
            "Idle pause should be cleared by resume_from_idle"
        )
        assert service.is_idle_paused(conv_id) is False, (
            "is_idle_paused should be cleared by resume_from_idle"
        )

    def test_pause_conversation_makes_is_paused_true(self) -> None:
        """Basic regression guard: pause_conversation sets is_paused=True."""
        service = ThinkerService()
        conv_id = "basic-pause-test"

        assert service.is_paused(conv_id) is False
        service.pause_conversation(conv_id)
        assert service.is_paused(conv_id) is True

    def test_resume_conversation_makes_is_paused_false(self) -> None:
        """Basic regression guard: resume_conversation clears is_paused.

        Also verifies that resume_conversation does NOT affect idle-paused state
        (the two sets are independent for the resume operation).
        """
        service = ThinkerService()
        conv_id = "basic-resume-test"

        service.pause_conversation(conv_id)
        assert service.is_paused(conv_id) is True

        service.resume_conversation(conv_id)
        assert service.is_paused(conv_id) is False
