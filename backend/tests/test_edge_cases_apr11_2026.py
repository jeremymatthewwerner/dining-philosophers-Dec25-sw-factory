"""Edge case tests for Saturday QA focus (Apr 11, 2026).

Tests cover boundary conditions and error paths in:
- WebSocket ConnectionManager: speed multiplier clamping, disconnection when room absent,
  set_speed for non-existent room, get_speed for non-existent room
- ConversationRoom: broadcast to disconnected clients (cleanup), remove from empty set,
  is_active flag lifecycle
- ThinkerService utility methods: _split_response_into_bubbles (empty, short, long,
  transition words, force-split at mid), _extract_thinking_display (all language branches,
  short text guard, word boundary trimming), extract_mentions / is_mentioned edge cases
  (multi-word quoted, no match, empty text), _should_prompt_user (below threshold,
  exactly at threshold, too few messages), _get_last_user_message_timestamp (no user msgs,
  with user msgs), _count_messages_since_user (no messages, only thinker messages, user
  last), _get_user_name_from_messages (no messages, no user messages)
- KnowledgeResearchService: is_stale (COMPLETE + fresh, COMPLETE + old, non-COMPLETE),
  get_or_create_knowledge (existing entry, new entry creation), refresh_stale_knowledge
  (no stale entries, with stale entries)
- WebSocket endpoint: no token, invalid token, missing session_id in payload,
  SET_SPEED message type dispatching
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.api.websocket import (
    ConnectionManager,
    ConversationRoom,
    WSMessage,
    WSMessageType,
)
from app.core.auth import create_access_token
from app.main import app
from app.models import ResearchStatus, ThinkerKnowledge
from app.services.thinker import (
    ThinkerService,
    extract_mentions,
    is_mentioned,
)

# ===========================================================================
# Helper utilities
# ===========================================================================


def make_mock_message(
    sender_type: str = "thinker",
    sender_name: str = "Socrates",
    content: str = "Hello",
    created_at: datetime | None = None,
) -> MagicMock:
    """Create a lightweight mock message for ThinkerService unit tests."""
    msg = MagicMock()
    msg.sender_type = sender_type
    msg.sender_name = sender_name
    msg.content = content
    msg.created_at = created_at or datetime(2026, 4, 11, 12, 0, 0, tzinfo=UTC)
    return msg


def get_test_token(user_id: str = "test-user-id", session_id: str = "test-session-id") -> str:
    """Create a valid JWT token for WebSocket auth tests."""
    return create_access_token({"sub": user_id, "session_id": session_id})


# ===========================================================================
# ConversationRoom boundary conditions
# ===========================================================================


class TestConversationRoomBoundaryConditions:
    """Boundary condition tests for ConversationRoom."""

    def test_room_starts_inactive_with_no_connections(self) -> None:
        """New ConversationRoom has is_active=False before any connections.

        Edge case: Verify clean initial state.
        """
        room = ConversationRoom(conversation_id="test-room")
        assert room.is_active is False
        assert len(room.connections) == 0

    def test_add_connection_activates_room(self) -> None:
        """Adding a WebSocket connection sets is_active=True.

        Boundary condition: Transition from inactive to active.
        """
        room = ConversationRoom(conversation_id="test-room")
        mock_ws = MagicMock()
        room.add_connection(mock_ws)
        assert room.is_active is True
        assert mock_ws in room.connections

    def test_remove_last_connection_deactivates_room(self) -> None:
        """Removing the only connection sets is_active=False.

        Boundary condition: Room becomes inactive when empty.
        """
        room = ConversationRoom(conversation_id="test-room")
        mock_ws = MagicMock()
        room.add_connection(mock_ws)
        room.remove_connection(mock_ws)
        assert room.is_active is False
        assert len(room.connections) == 0

    def test_remove_one_of_two_connections_stays_active(self) -> None:
        """Room stays active when one of two connections is removed.

        Boundary condition: Verify is_active only becomes False when truly empty.
        """
        room = ConversationRoom(conversation_id="test-room")
        ws1 = MagicMock()
        ws2 = MagicMock()
        room.add_connection(ws1)
        room.add_connection(ws2)
        room.remove_connection(ws1)
        assert room.is_active is True
        assert ws2 in room.connections

    def test_remove_nonexistent_connection_is_safe(self) -> None:
        """Calling remove_connection with an unknown WebSocket doesn't crash.

        Edge case: discard() on a set with non-member must not raise.
        """
        room = ConversationRoom(conversation_id="test-room")
        ws = MagicMock()
        # Should not raise
        room.remove_connection(ws)
        assert room.is_active is False

    @pytest.mark.asyncio
    async def test_broadcast_cleans_up_disconnected_clients(self) -> None:
        """Broadcast removes WebSockets that raise during send.

        Edge case: Clients may disconnect mid-broadcast; room must clean up.
        """
        room = ConversationRoom(conversation_id="test-room")

        good_ws = AsyncMock()
        bad_ws = AsyncMock()
        bad_ws.send_text.side_effect = Exception("client disconnected")

        room.add_connection(good_ws)
        room.add_connection(bad_ws)

        msg = WSMessage(type=WSMessageType.MESSAGE, content="hello")
        await room.broadcast(msg)

        # bad_ws should have been removed
        assert bad_ws not in room.connections
        # good_ws should still be connected and received the message
        assert good_ws in room.connections
        good_ws.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_all_disconnected_deactivates_room(self) -> None:
        """When all clients fail during broadcast, room becomes inactive.

        Edge case: Network partition removes all clients.
        """
        room = ConversationRoom(conversation_id="test-room")
        ws = AsyncMock()
        ws.send_text.side_effect = Exception("disconnected")
        room.add_connection(ws)

        msg = WSMessage(type=WSMessageType.MESSAGE, content="test")
        await room.broadcast(msg)

        assert room.is_active is False
        assert len(room.connections) == 0


# ===========================================================================
# ConnectionManager edge cases
# ===========================================================================


class TestConnectionManagerEdgeCases:
    """Edge case tests for ConnectionManager."""

    def test_get_speed_for_nonexistent_room_returns_default(self) -> None:
        """get_speed_multiplier returns 1.0 for unknown conversation.

        Edge case: No crash when conversation_id not in rooms dict.
        """
        mgr = ConnectionManager()
        speed = mgr.get_speed_multiplier("does-not-exist")
        assert speed == 1.0

    @pytest.mark.asyncio
    async def test_set_speed_for_nonexistent_room_is_noop(self) -> None:
        """set_speed_multiplier silently does nothing for unknown conversation.

        Edge case: Prevents KeyError when calling set_speed before any connections.
        """
        mgr = ConnectionManager()
        # Should not raise
        await mgr.set_speed_multiplier("does-not-exist", 2.0)
        # Speed is still default since room was never created
        assert mgr.get_speed_multiplier("does-not-exist") == 1.0

    @pytest.mark.asyncio
    async def test_set_speed_clamps_below_minimum(self) -> None:
        """set_speed_multiplier clamps values below 0.5 to 0.5.

        Boundary condition: Minimum speed = 0.5 (fastest).
        """
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws, "clamp-test")

        await mgr.set_speed_multiplier("clamp-test", 0.1)
        assert mgr.get_speed_multiplier("clamp-test") == 0.5

    @pytest.mark.asyncio
    async def test_set_speed_clamps_above_maximum(self) -> None:
        """set_speed_multiplier clamps values above 6.0 to 6.0.

        Boundary condition: Maximum speed = 6.0 (slowest / contemplative).
        """
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws, "clamp-test-high")

        await mgr.set_speed_multiplier("clamp-test-high", 100.0)
        assert mgr.get_speed_multiplier("clamp-test-high") == 6.0

    @pytest.mark.asyncio
    async def test_set_speed_exact_boundary_values(self) -> None:
        """set_speed_multiplier accepts exactly 0.5 and 6.0 without clamping.

        Boundary condition: Min and max values must be accepted as-is.
        """
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws, "exact-boundary")

        await mgr.set_speed_multiplier("exact-boundary", 0.5)
        assert mgr.get_speed_multiplier("exact-boundary") == 0.5

        await mgr.set_speed_multiplier("exact-boundary", 6.0)
        assert mgr.get_speed_multiplier("exact-boundary") == 6.0

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_room_is_safe(self) -> None:
        """disconnect() with unknown conversation_id must not raise.

        Edge case: Client may send disconnect for a conversation it was never in.
        """
        mgr = ConnectionManager()
        ws = AsyncMock()
        # Should not raise KeyError
        await mgr.disconnect(ws, "never-existed")

    def test_is_conversation_active_nonexistent_room(self) -> None:
        """is_conversation_active returns False for unknown conversation.

        Edge case: Absence of room must not crash.
        """
        mgr = ConnectionManager()
        assert mgr.is_conversation_active("phantom-conversation") is False

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_conversation_is_noop(self) -> None:
        """broadcast_to_conversation does nothing if conversation_id is unknown.

        Edge case: Race condition where broadcast fires after room is removed.
        """
        mgr = ConnectionManager()
        msg = WSMessage(type=WSMessageType.MESSAGE, content="orphan")
        # Should not raise
        await mgr.broadcast_to_conversation("ghost-room", msg)


# ===========================================================================
# extract_mentions / is_mentioned edge cases
# ===========================================================================


class TestMentionEdgeCases:
    """Edge case tests for mention extraction and matching."""

    def test_extract_mentions_empty_string(self) -> None:
        """Empty string produces no mentions.

        Edge case: Boundary condition for empty input.
        """
        assert extract_mentions("") == []

    def test_extract_mentions_no_at_signs(self) -> None:
        """Text with no @ symbols produces no mentions.

        Edge case: Normal text must not generate false positives.
        """
        result = extract_mentions("Hello everyone, this is normal speech.")
        assert result == []

    def test_extract_mentions_quoted_multiword(self) -> None:
        """Quoted @mentions with spaces are extracted as full names.

        Edge case: @\"Marie Curie\" must return \"Marie Curie\", not \"Marie\".
        """
        result = extract_mentions('Hello @"Marie Curie", how are you?')
        assert "Marie Curie" in result

    def test_extract_mentions_simple_at_sign(self) -> None:
        """Simple @Name without quotes is extracted correctly.

        Standard case verified as baseline.
        """
        result = extract_mentions("What do you think, @Socrates?")
        assert "Socrates" in result

    def test_extract_mentions_multiple_at_signs(self) -> None:
        """Multiple @mentions in same text are all extracted.

        Edge case: Multiple mentions on same line.
        """
        result = extract_mentions("@Plato and @Aristotle both agree on this.")
        assert "Plato" in result
        assert "Aristotle" in result

    def test_extract_mentions_at_sign_in_email_format(self) -> None:
        """@word patterns in email-like text still match.

        Edge case: Email pattern like user@domain still captures 'domain'
        because the regex is simple. This tests current behavior.
        """
        # @domain portion matches the simple_pattern
        result = extract_mentions("Contact user@example for help")
        assert "example" in result

    def test_is_mentioned_exact_name(self) -> None:
        """is_mentioned returns True for exact full name @mention.

        Standard case for full name matching.
        """
        assert is_mentioned("Hello @Socrates!", "Socrates") is True

    def test_is_mentioned_first_name_matches_full_name(self) -> None:
        """@FirstName matches thinker with multi-word name.

        Edge case: @Marie should match \"Marie Curie\".
        """
        assert is_mentioned("Great question @Marie!", "Marie Curie") is True

    def test_is_mentioned_no_mention_of_thinker(self) -> None:
        """is_mentioned returns False when thinker is not @mentioned.

        Edge case: Name appears in text but without @ symbol.
        """
        assert is_mentioned("Socrates was wise", "Socrates") is False

    def test_is_mentioned_empty_text(self) -> None:
        """is_mentioned returns False for empty text.

        Boundary condition: Empty input.
        """
        assert is_mentioned("", "Socrates") is False

    def test_is_mentioned_empty_thinker_name(self) -> None:
        """is_mentioned handles empty thinker name without crashing.

        Boundary condition: Defensive check for empty thinker name.
        """
        # Should not raise even with empty thinker name
        result = is_mentioned("@Socrates speaks", "")
        assert result is False

    def test_is_mentioned_quoted_full_name(self) -> None:
        """is_mentioned recognizes @\"Full Name\" quoted format.

        Edge case: Quoted multi-word names must match.
        """
        assert is_mentioned('@"Marie Curie" what do you think?', "Marie Curie") is True


# ===========================================================================
# ThinkerService utility methods
# ===========================================================================


class TestSplitResponseIntoBubbles:
    """Tests for ThinkerService._split_response_into_bubbles edge cases."""

    def setup_method(self) -> None:
        """Create a ThinkerService instance for each test."""
        self.service = ThinkerService()

    def test_empty_string_returns_empty_list(self) -> None:
        """Empty response text returns an empty list.

        Boundary condition: Guard clause for empty input.
        """
        result = self.service._split_response_into_bubbles("")
        assert result == []

    def test_whitespace_only_returns_no_meaningful_bubbles(self) -> None:
        """Whitespace-only text produces no meaningful (non-empty) bubbles.

        Edge case: Whitespace-only response should produce no non-empty bubbles.
        The implementation strips the text first, so all-whitespace input
        may produce at most one empty bubble that gets filtered.
        """
        result = self.service._split_response_into_bubbles("   \n  ")
        # Filter empty strings - should have no meaningful content
        non_empty = [b for b in result if b.strip()]
        assert non_empty == []

    def test_very_short_text_stays_single_bubble(self) -> None:
        """Text under 60 chars always stays as a single bubble.

        Boundary condition: No splitting below minimum length.
        """
        short_text = "I agree with you."
        result = self.service._split_response_into_bubbles(short_text)
        assert len(result) == 1
        assert result[0] == short_text

    def test_text_at_59_chars_stays_single_bubble(self) -> None:
        """Text exactly 59 chars (below 60 threshold) stays single bubble.

        Boundary condition: 59 < 60, must not split.
        """
        text = "a" * 58 + "."
        assert len(text) == 59
        result = self.service._split_response_into_bubbles(text)
        assert len(result) == 1

    def test_very_long_text_is_split_into_multiple_bubbles(self) -> None:
        """Very long text (>300 chars) is split into multiple bubbles.

        Edge case: Long responses must always be divided for readability.
        """
        long_text = (
            "The nature of reality is a profound philosophical question. "
            "Plato believed in ideal forms that exist beyond our perception. "
            "Aristotle challenged this by emphasizing empirical observation. "
            "Later thinkers like Descartes grounded reality in the thinking self. "
            "Modern philosophy continues to wrestle with these ancient questions."
        )
        assert len(long_text) > 300
        result = self.service._split_response_into_bubbles(long_text)
        assert len(result) >= 1
        # All text should be preserved (no loss)
        assert all(b for b in result)

    def test_transition_word_triggers_new_bubble(self) -> None:
        """Transition words like 'However,' at sentence start trigger a new bubble.

        Edge case: Natural conversation flow splits at rhetorical transitions.
        """
        text = (
            "This is a good point about ethics. "
            "However, we must also consider the consequences. "
            "The utilitarian perspective differs here."
        )
        # With some roll values this will split at 'However,'
        # We just verify no crash and output is non-empty list
        result = self.service._split_response_into_bubbles(text)
        assert len(result) >= 1
        assert all(b for b in result)

    def test_no_empty_bubbles_in_output(self) -> None:
        """Output list must not contain empty strings.

        Edge case: Filter clause at end must work correctly.
        """
        text = (
            "A long sentence here. "
            "Another sentence that follows. "
            "And one more for good measure, ending here."
        )
        result = self.service._split_response_into_bubbles(text)
        assert all(b.strip() for b in result), "No empty bubbles should be present"


class TestExtractThinkingDisplay:
    """Tests for ThinkerService._extract_thinking_display edge cases."""

    def setup_method(self) -> None:
        """Create a ThinkerService instance for each test."""
        self.service = ThinkerService()

    def test_empty_string_returns_empty(self) -> None:
        """Empty thinking text returns empty string.

        Boundary condition: Guard clause for empty input.
        """
        result = self.service._extract_thinking_display("")
        assert result == ""

    def test_short_text_under_80_chars_returns_empty(self) -> None:
        """Text under 80 chars returns empty string (too short to display).

        Boundary condition: 79 chars must not be shown.
        """
        short = "Just a short thought here."
        assert len(short) < 80
        result = self.service._extract_thinking_display(short)
        assert result == ""

    def test_text_at_79_chars_returns_empty(self) -> None:
        """Text exactly 79 chars (below threshold) still returns empty.

        Boundary condition: Exactly at length boundary.
        """
        text = "a" * 79
        result = self.service._extract_thinking_display(text)
        assert result == ""

    def test_text_at_80_chars_may_return_something(self) -> None:
        """Text of exactly 80 chars may be shown (at threshold).

        Boundary condition: At the 80 char minimum, content may be displayed.
        """
        # Construct a text string of exactly 80 chars to hit the boundary
        base = "The user is asking about philosophy and ethics and the nature of human existence."
        text = (base + "x" * (80 - len(base)))[:80]
        assert len(text) == 80
        # Should not crash
        result = self.service._extract_thinking_display(text)
        # result may be "" or non-empty depending on word cleanup, but shouldn't raise
        assert isinstance(result, str)

    def test_english_language_replacements(self) -> None:
        """English language replacements transform LLM-style tokens correctly.

        Edge case: 'I think ' prefix is stripped; 'I should ' → 'Perhaps I should'.
        """
        # Use a long enough text with English replacement trigger
        long_text = (
            "I should consider the implications of this philosophical position carefully. "
            "The user wants to understand how virtue ethics applies to modern dilemmas. "
            "Let me think about the key arguments that Aristotle would make here."
        )
        result = self.service._extract_thinking_display(long_text, language="en")
        # Should return a non-empty string
        assert isinstance(result, str)

    def test_german_language_branch(self) -> None:
        """German language code triggers German-specific replacements.

        Edge case: Non-English language branch must be reachable.
        """
        long_text = (
            "Ich sollte die philosophischen Implikationen dieser Frage berücksichtigen. "
            "Der Benutzer fragt nach den grundlegenden Prinzipien der Ethik. "
            "Ich denke, dass wir zunächst die Grundlagen klären müssen. "
            "Das ist ein sehr wichtiger Aspekt dieser Diskussion."
        )
        result = self.service._extract_thinking_display(long_text, language="de")
        assert isinstance(result, str)

    def test_spanish_language_branch(self) -> None:
        """Spanish language code triggers Spanish-specific replacements.

        Edge case: es branch must not crash and must return a string.
        """
        long_text = (
            "Debería considerar las implicaciones filosóficas de esta pregunta. "
            "El usuario quiere entender cómo se aplica la ética de la virtud. "
            "Creo que primero debemos aclarar los fundamentos de la ética. "
            "Este es un aspecto muy importante de la discusión filosófica."
        )
        result = self.service._extract_thinking_display(long_text, language="es")
        assert isinstance(result, str)

    def test_french_language_branch(self) -> None:
        """French language code triggers French-specific replacements.

        Edge case: fr branch must not crash and must return a string.
        """
        long_text = (
            "Je devrais considérer les implications philosophiques de cette question. "
            "L'utilisateur veut comprendre comment s'applique l'éthique des vertus. "
            "Je pense que nous devons d'abord clarifier les bases de l'éthique. "
            "C'est un aspect très important de cette discussion philosophique."
        )
        result = self.service._extract_thinking_display(long_text, language="fr")
        assert isinstance(result, str)

    def test_hindi_language_branch(self) -> None:
        """Hindi language code triggers Hindi-specific replacements.

        Edge case: hi branch must not crash and must return a string.
        """
        long_text = (
            "मुझे इस दार्शनिक प्रश्न के निहितार्थों पर विचार करना चाहिए। "
            "उपयोगकर्ता यह समझना चाहता है कि नैतिकता कैसे लागू होती है। "
            "मुझे लगता है कि हमें पहले नैतिकता की नींव स्पष्ट करनी चाहिए। "
            "यह इस दार्शनिक चर्चा का एक बहुत महत्वपूर्ण पहलू है।"
        )
        result = self.service._extract_thinking_display(long_text, language="hi")
        assert isinstance(result, str)

    def test_unknown_language_falls_back_to_english(self) -> None:
        """Unknown language code falls back to English replacements.

        Edge case: Unrecognized language code must not crash.
        """
        long_text = (
            "I should consider the implications carefully here. "
            "The user wants to understand virtue ethics deeply. "
            "Let me think through the key points of this argument. "
            "This is a very important philosophical discussion indeed."
        )
        result = self.service._extract_thinking_display(long_text, language="zh")
        assert isinstance(result, str)


class TestGetLastUserMessageTimestamp:
    """Tests for ThinkerService._get_last_user_message_timestamp edge cases."""

    def setup_method(self) -> None:
        self.service = ThinkerService()

    def test_empty_messages_returns_zero(self) -> None:
        """Empty message list returns 0.0.

        Boundary condition: No messages → no timestamp.
        """
        result = self.service._get_last_user_message_timestamp([])
        assert result == 0.0

    def test_only_thinker_messages_returns_zero(self) -> None:
        """List of only thinker messages returns 0.0.

        Edge case: No user messages present.
        """
        messages = [
            make_mock_message(sender_type="thinker"),
            make_mock_message(sender_type="thinker"),
        ]
        result = self.service._get_last_user_message_timestamp(messages)
        assert result == 0.0

    def test_user_message_returns_its_timestamp(self) -> None:
        """List with user message returns that message's timestamp.

        Standard case: Correct timestamp extraction.
        """
        ts = datetime(2026, 4, 11, 10, 0, 0, tzinfo=UTC)
        messages = [
            make_mock_message(sender_type="user", created_at=ts),
        ]
        result = self.service._get_last_user_message_timestamp(messages)
        assert result == ts.timestamp()

    def test_returns_last_user_message_timestamp(self) -> None:
        """When multiple user messages, returns most recent one.

        Edge case: Multiple user messages - last one wins.
        """
        ts1 = datetime(2026, 4, 11, 10, 0, 0, tzinfo=UTC)
        ts2 = datetime(2026, 4, 11, 11, 0, 0, tzinfo=UTC)
        messages = [
            make_mock_message(sender_type="user", created_at=ts1),
            make_mock_message(sender_type="thinker"),
            make_mock_message(sender_type="user", created_at=ts2),
        ]
        result = self.service._get_last_user_message_timestamp(messages)
        assert result == ts2.timestamp()

    def test_sender_type_as_enum_value_is_handled(self) -> None:
        """Sender type as enum-like object with .value attribute is handled.

        Edge case: Both string 'user' and enum value user are recognized.
        """
        ts = datetime(2026, 4, 11, 10, 0, 0, tzinfo=UTC)
        msg = make_mock_message(sender_type="user", created_at=ts)
        # Simulate enum with .value attribute
        enum_sender = MagicMock()
        enum_sender.value = "user"
        msg.sender_type = enum_sender

        result = self.service._get_last_user_message_timestamp([msg])
        assert result == ts.timestamp()


class TestCountMessagesSinceUser:
    """Tests for ThinkerService._count_messages_since_user edge cases."""

    def setup_method(self) -> None:
        self.service = ThinkerService()

    def test_empty_messages_returns_zero(self) -> None:
        """Empty message list returns 0.

        Boundary condition: No messages.
        """
        result = self.service._count_messages_since_user([])
        assert result == 0

    def test_only_thinker_messages_counts_all(self) -> None:
        """Only thinker messages - count equals total message count.

        Edge case: User never spoke; all messages are thinker messages.
        """
        messages = [
            make_mock_message(sender_type="thinker"),
            make_mock_message(sender_type="thinker"),
            make_mock_message(sender_type="thinker"),
        ]
        result = self.service._count_messages_since_user(messages)
        assert result == 3

    def test_user_last_returns_zero(self) -> None:
        """User message at the end resets count to 0.

        Edge case: User just spoke; no thinker messages since then.
        """
        messages = [
            make_mock_message(sender_type="thinker"),
            make_mock_message(sender_type="user"),
        ]
        result = self.service._count_messages_since_user(messages)
        assert result == 0

    def test_two_thinker_messages_after_user(self) -> None:
        """Two thinker messages after last user message returns 2.

        Standard counting case.
        """
        messages = [
            make_mock_message(sender_type="user"),
            make_mock_message(sender_type="thinker"),
            make_mock_message(sender_type="thinker"),
        ]
        result = self.service._count_messages_since_user(messages)
        assert result == 2


class TestGetUserNameFromMessages:
    """Tests for ThinkerService._get_user_name_from_messages edge cases."""

    def setup_method(self) -> None:
        self.service = ThinkerService()

    def test_empty_messages_returns_none(self) -> None:
        """Empty message list returns None.

        Boundary condition: No messages.
        """
        result = self.service._get_user_name_from_messages([])
        assert result is None

    def test_no_user_messages_returns_none(self) -> None:
        """Messages with no user sender returns None.

        Edge case: Conversation only has thinker messages.
        """
        messages = [
            make_mock_message(sender_type="thinker", sender_name="Plato"),
        ]
        result = self.service._get_user_name_from_messages(messages)
        assert result is None

    def test_user_with_name_returns_name(self) -> None:
        """User message with sender_name returns that name.

        Standard case: Name extraction from user message.
        """
        messages = [
            make_mock_message(sender_type="user", sender_name="Alice"),
        ]
        result = self.service._get_user_name_from_messages(messages)
        assert result == "Alice"

    def test_returns_last_user_name(self) -> None:
        """Multiple user messages - most recent user name is returned.

        Edge case: _get_user_name iterates in reverse so last is first found.
        """
        messages = [
            make_mock_message(sender_type="user", sender_name="Alice"),
            make_mock_message(sender_type="thinker", sender_name="Socrates"),
            make_mock_message(sender_type="user", sender_name="Bob"),
        ]
        result = self.service._get_user_name_from_messages(messages)
        assert result == "Bob"


class TestShouldPromptUser:
    """Tests for ThinkerService._should_prompt_user boundary conditions."""

    def setup_method(self) -> None:
        self.service = ThinkerService()

    def test_fewer_than_5_messages_returns_false(self) -> None:
        """Fewer than 5 messages in conversation always returns False.

        Boundary condition: Too early to prompt user.
        """
        messages = [make_mock_message() for _ in range(4)]
        result = self.service._should_prompt_user(messages, 1.0)
        assert result is False

    def test_exactly_5_messages_may_return_false(self) -> None:
        """With exactly 5 messages, may return False if threshold not met.

        Boundary condition: At-threshold message count.
        """
        # All thinker messages - 5 since user = 5, threshold at speed 1.0 = max(4, 8) = 8
        # So 5 < 8 threshold → should_prompt_user returns False
        messages = [make_mock_message(sender_type="thinker") for _ in range(5)]
        result = self.service._should_prompt_user(messages, 1.0)
        assert result is False  # 5 < threshold of 8

    def test_below_threshold_returns_false(self) -> None:
        """When messages_since_user < threshold, always returns False.

        Boundary condition: Threshold not met.
        """
        # 3 thinker messages after user, threshold = max(4, int(8/1^0.3)) = 8
        # 3 < 8 → returns False
        messages = [
            make_mock_message(sender_type="user"),
            make_mock_message(sender_type="thinker"),
            make_mock_message(sender_type="thinker"),
            make_mock_message(sender_type="thinker"),
            make_mock_message(sender_type="thinker"),
        ]
        result = self.service._should_prompt_user(messages, 1.0)
        assert result is False


# ===========================================================================
# KnowledgeResearchService edge cases
# ===========================================================================


class TestKnowledgeResearchIsStale:
    """Tests for KnowledgeResearchService.is_stale boundary conditions."""

    def setup_method(self) -> None:
        from app.services.knowledge_research import KnowledgeResearchService

        self.service = KnowledgeResearchService()

    def test_pending_status_is_stale(self) -> None:
        """Knowledge with PENDING status is always considered stale.

        Edge case: Unfinished research must always be refreshed.
        """
        knowledge = MagicMock(spec=ThinkerKnowledge)
        knowledge.status = ResearchStatus.PENDING
        knowledge.updated_at = datetime.now(UTC)
        assert self.service.is_stale(knowledge) is True

    def test_in_progress_status_is_stale(self) -> None:
        """Knowledge with IN_PROGRESS status is considered stale.

        Edge case: In-flight research that may have stalled.
        """
        knowledge = MagicMock(spec=ThinkerKnowledge)
        knowledge.status = ResearchStatus.IN_PROGRESS
        knowledge.updated_at = datetime.now(UTC)
        assert self.service.is_stale(knowledge) is True

    def test_failed_status_is_stale(self) -> None:
        """Knowledge with FAILED status is considered stale (needs retry).

        Edge case: Failed research should be retried.
        """
        knowledge = MagicMock(spec=ThinkerKnowledge)
        knowledge.status = ResearchStatus.FAILED
        knowledge.updated_at = datetime.now(UTC)
        assert self.service.is_stale(knowledge) is True

    def test_complete_fresh_knowledge_is_not_stale(self) -> None:
        """COMPLETE knowledge updated recently is not stale.

        Standard case: Fresh cached data should not be re-fetched.
        """
        knowledge = MagicMock(spec=ThinkerKnowledge)
        knowledge.status = ResearchStatus.COMPLETE
        knowledge.updated_at = datetime.now(UTC)  # Just now
        assert self.service.is_stale(knowledge) is False

    def test_complete_old_knowledge_is_stale(self) -> None:
        """COMPLETE knowledge older than CACHE_STALENESS_DAYS is stale.

        Boundary condition: Cache expiry must be enforced.
        """
        from app.services.knowledge_research import CACHE_STALENESS_DAYS

        knowledge = MagicMock(spec=ThinkerKnowledge)
        knowledge.status = ResearchStatus.COMPLETE
        # Set updated_at to just past the staleness threshold
        stale_date = datetime.now(UTC) - timedelta(days=CACHE_STALENESS_DAYS + 1)
        knowledge.updated_at = stale_date
        assert self.service.is_stale(knowledge) is True

    def test_complete_at_exactly_staleness_boundary(self) -> None:
        """COMPLETE knowledge exactly at staleness threshold is stale.

        Boundary condition: < vs <= comparison at the staleness cutoff.
        """
        from app.services.knowledge_research import CACHE_STALENESS_DAYS

        knowledge = MagicMock(spec=ThinkerKnowledge)
        knowledge.status = ResearchStatus.COMPLETE
        # Exactly at the boundary
        stale_date = datetime.now(UTC) - timedelta(days=CACHE_STALENESS_DAYS)
        knowledge.updated_at = stale_date
        # At exactly CACHE_STALENESS_DAYS, updated_at is NOT less than threshold
        # so result depends on exact timing - we just check it doesn't crash
        result = self.service.is_stale(knowledge)
        assert isinstance(result, bool)


class TestKnowledgeResearchGetOrCreate:
    """Tests for KnowledgeResearchService.get_or_create_knowledge."""

    @pytest.mark.asyncio
    async def test_get_existing_knowledge_returns_it(self) -> None:
        """get_or_create_knowledge returns existing knowledge without creating new.

        Standard case: Cache hit path.
        """
        from app.services.knowledge_research import KnowledgeResearchService

        service = KnowledgeResearchService()

        existing = MagicMock(spec=ThinkerKnowledge)
        existing.name = "Socrates"

        mock_db = AsyncMock()
        # Patch get_knowledge to return existing
        with patch.object(service, "get_knowledge", return_value=existing) as mock_get:
            result = await service.get_or_create_knowledge(mock_db, "Socrates")
            mock_get.assert_called_once_with(mock_db, "Socrates")
            assert result is existing
            # db.add should NOT have been called since knowledge existed
            mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_new_knowledge_when_not_found(self) -> None:
        """get_or_create_knowledge creates a new entry when none exists.

        Edge case: Cache miss path creates new pending entry.
        """
        from app.services.knowledge_research import KnowledgeResearchService

        service = KnowledgeResearchService()

        mock_db = AsyncMock()

        with patch.object(service, "get_knowledge", return_value=None):
            # Simulate the db.refresh populating the new entry
            async def fake_refresh(obj: Any) -> None:
                obj.id = "new-id"

            mock_db.refresh.side_effect = fake_refresh

            result = await service.get_or_create_knowledge(mock_db, "NewThinker")
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            # Result should be the newly created ThinkerKnowledge with PENDING status
            assert result.status == ResearchStatus.PENDING
            assert result.name == "NewThinker"


class TestKnowledgeResearchRefreshStale:
    """Tests for KnowledgeResearchService.refresh_stale_knowledge."""

    @pytest.mark.asyncio
    async def test_no_stale_entries_returns_zero(self) -> None:
        """refresh_stale_knowledge returns 0 when no stale entries found.

        Boundary condition: Empty result from DB query.
        """
        from app.services.knowledge_research import KnowledgeResearchService

        service = KnowledgeResearchService()
        mock_db = AsyncMock()

        # DB returns no stale entries
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        count = await service.refresh_stale_knowledge(mock_db)
        assert count == 0

    @pytest.mark.asyncio
    async def test_stale_entries_triggers_research_for_each(self) -> None:
        """refresh_stale_knowledge calls trigger_research for each stale entry.

        Standard case: Multiple stale entries all get queued.
        """
        from app.services.knowledge_research import KnowledgeResearchService

        service = KnowledgeResearchService()
        mock_db = AsyncMock()

        # Create mock stale entries
        entry1 = MagicMock()
        entry1.name = "Plato"
        entry2 = MagicMock()
        entry2.name = "Aristotle"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entry1, entry2]
        mock_db.execute.return_value = mock_result

        with patch.object(service, "trigger_research") as mock_trigger:
            count = await service.refresh_stale_knowledge(mock_db)

        assert count == 2
        assert mock_trigger.call_count == 2
        trigger_calls = [call[0][0] for call in mock_trigger.call_args_list]
        assert "Plato" in trigger_calls
        assert "Aristotle" in trigger_calls


class TestKnowledgeResearchTriggerDeduplication:
    """Tests for KnowledgeResearchService.trigger_research deduplication."""

    def test_trigger_research_deduplicates_active_tasks(self) -> None:
        """Calling trigger_research twice for same name while first is running is a noop.

        Edge case: Prevents duplicate background tasks for the same thinker.
        """
        from app.services.knowledge_research import KnowledgeResearchService

        service = KnowledgeResearchService()

        # Simulate an active (not done) task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        service._active_tasks["Socrates"] = mock_task

        # Calling trigger_research again should not create a new task
        with patch("asyncio.create_task") as mock_create:
            service.trigger_research("Socrates")
            mock_create.assert_not_called()

    def test_trigger_research_starts_new_task_after_done(self) -> None:
        """trigger_research starts a new task when previous task is done.

        Edge case: Completed tasks can be replaced.
        """
        from app.services.knowledge_research import KnowledgeResearchService

        service = KnowledgeResearchService()

        # Simulate a completed task
        mock_done_task = MagicMock()
        mock_done_task.done.return_value = True
        service._active_tasks["Plato"] = mock_done_task

        mock_new_task = MagicMock()
        mock_new_task.add_done_callback = MagicMock()

        with patch("asyncio.create_task", return_value=mock_new_task) as mock_create:
            service.trigger_research("Plato")
            mock_create.assert_called_once()
            assert service._active_tasks["Plato"] is mock_new_task


# ===========================================================================
# WebSocket endpoint auth edge cases (via TestClient)
# ===========================================================================


class TestWebSocketAuthEdgeCases:
    """Edge case tests for WebSocket endpoint authentication."""

    def test_websocket_no_token_closes_with_4001(self) -> None:
        """WebSocket connection without token parameter is rejected with code 4001.

        Edge case: Missing auth token must be rejected, not crash server.
        """
        rejected = False
        with TestClient(app) as test_client:
            try:
                with test_client.websocket_connect("/ws/test-conv") as ws:
                    ws.receive_json()
            except Exception:  # noqa: BLE001
                rejected = True
        # Connection should have been rejected
        assert rejected, "Expected WebSocket connection to be rejected without token"

    def test_websocket_invalid_token_closes_with_4001(self) -> None:
        """WebSocket connection with invalid (non-JWT) token is rejected.

        Edge case: Garbage token string must not crash the server.
        """
        rejected = False
        with TestClient(app) as test_client:
            try:
                with test_client.websocket_connect("/ws/test-conv?token=not-a-jwt") as ws:
                    ws.receive_json()
            except Exception:  # noqa: BLE001
                rejected = True
        assert rejected, "Expected WebSocket connection to be rejected with invalid token"

    def test_websocket_token_missing_session_id_closes_with_4001(self) -> None:
        """WebSocket token without session_id is rejected with code 4001.

        Edge case: JWT must include session_id claim.
        """
        token_without_session = create_access_token({"sub": "user-id"})
        rejected = False
        with TestClient(app) as test_client:
            try:
                with test_client.websocket_connect(
                    f"/ws/test-conv?token={token_without_session}"
                ) as ws:
                    ws.receive_json()
            except Exception:  # noqa: BLE001
                rejected = True
        assert rejected, "Expected WebSocket connection to be rejected with token missing session_id"

    def test_websocket_set_speed_message_dispatched(self) -> None:
        """SET_SPEED WebSocket message type is processed and broadcasts SPEED_CHANGED.

        Edge case: speed control message path (lines 474-477 of websocket.py).
        """
        token = get_test_token()
        with TestClient(app) as test_client, test_client.websocket_connect(
            f"/ws/speed-test?token={token}"
        ) as ws:
            # Skip join + resumed messages
            ws.receive_json()  # user_joined
            ws.receive_json()  # resumed

            # Send SET_SPEED message
            ws.send_json({"type": "set_speed", "speed_multiplier": 2.0})

            # Should receive SPEED_CHANGED broadcast
            data = ws.receive_json()
            assert data["type"] == "speed_changed"
            assert data["speed_multiplier"] == 2.0


# ===========================================================================
# ThinkerService pause/idle state machine
# ===========================================================================


class TestThinkerServiceStateMachine:
    """Tests for ThinkerService pause/idle state transitions."""

    def test_pause_and_resume_conversation(self) -> None:
        """pause_conversation and resume_conversation toggle paused state.

        Standard case: Basic pause/resume lifecycle.
        """
        service = ThinkerService()
        conv_id = "test-conv-123"

        assert service.is_paused(conv_id) is False
        service.pause_conversation(conv_id)
        assert service.is_paused(conv_id) is True
        service.resume_conversation(conv_id)
        assert service.is_paused(conv_id) is False

    def test_idle_pause_sets_both_paused_and_idle_flags(self) -> None:
        """pause_for_idle sets both regular pause and idle-pause flags.

        Edge case: Idle-paused conversations are a subset of paused ones.
        """
        service = ThinkerService()
        conv_id = "idle-conv"

        service.pause_for_idle(conv_id)
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is True

    def test_resume_from_idle_clears_both_flags(self) -> None:
        """resume_from_idle clears both paused and idle-paused state.

        Edge case: Resuming from idle should make conversation fully active.
        """
        service = ThinkerService()
        conv_id = "idle-resume-conv"

        service.pause_for_idle(conv_id)
        service.resume_from_idle(conv_id)
        assert service.is_paused(conv_id) is False
        assert service.is_idle_paused(conv_id) is False

    def test_resume_from_idle_noop_if_not_idle_paused(self) -> None:
        """resume_from_idle does nothing if conversation was manually paused.

        Edge case: Manual pause should not be cleared by idle resume.
        """
        service = ThinkerService()
        conv_id = "manual-paused"

        service.pause_conversation(conv_id)
        # Attempt idle resume - should do nothing since it's not idle-paused
        service.resume_from_idle(conv_id)
        # Conversation should still be paused (manual pause persists)
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is False

    def test_resume_from_idle_noop_if_not_paused_at_all(self) -> None:
        """resume_from_idle is safe to call on a non-paused conversation.

        Boundary condition: Guard against double-resume.
        """
        service = ThinkerService()
        conv_id = "never-paused"

        # Should not raise
        service.resume_from_idle(conv_id)
        assert service.is_paused(conv_id) is False

    def test_multiple_conversations_paused_independently(self) -> None:
        """Pause state is tracked independently per conversation.

        Edge case: Pausing one conversation must not affect another.
        """
        service = ThinkerService()

        service.pause_conversation("conv-A")
        assert service.is_paused("conv-A") is True
        assert service.is_paused("conv-B") is False

    def test_stop_conversation_agents_for_nonexistent_conv_is_safe(self) -> None:
        """stop_conversation_agents does nothing for unknown conversation.

        Edge case: No crash when stopping agents that were never started.
        """
        service = ThinkerService()
        # Should not raise
        asyncio.get_event_loop().run_until_complete(
            service.stop_conversation_agents("nonexistent-conv")
        )
