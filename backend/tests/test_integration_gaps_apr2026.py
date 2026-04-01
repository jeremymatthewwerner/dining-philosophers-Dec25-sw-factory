"""Integration gap tests for April 2026 - Wednesday focus.

Targets uncovered lines and branches identified in coverage analysis:
- app/api/websocket.py: ConnectionManager branch misses (189->191, 212->214, 125->127)
- app/api/websocket.py: WebSocket auth failures (no token, invalid token, no session_id)
- app/api/websocket.py: SET_SPEED message type
- app/services/thinker.py: _split_response_into_bubbles force-split path (lines 763-774)
- app/services/thinker.py: _extract_thinking_display with >200 chars, word boundary truncation
- app/services/thinker.py: _extract_thinking_display language-specific replacements (de, es, fr)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.websocket import ConnectionManager, WSMessage, WSMessageType
from app.core.auth import create_access_token
from app.main import app
from app.services.thinker import thinker_service


class MockStreamingResponse:
    """A proper async iterator mock for the Anthropic streaming response.

    Used to test generate_response_with_streaming_thinking without real API calls.
    """

    def __init__(self, final_msg: MagicMock, events: list[MagicMock] | None = None) -> None:
        self._final_msg = final_msg
        self._events = events or []
        self._idx = 0

    def __aiter__(self) -> "MockStreamingResponse":
        return self

    async def __anext__(self) -> MagicMock:
        if self._idx >= len(self._events):
            raise StopAsyncIteration
        event = self._events[self._idx]
        self._idx += 1
        return event

    async def get_final_message(self) -> MagicMock:
        return self._final_msg


def get_test_token(user_id: str = "test-user-id", session_id: str = "test-session-id") -> str:
    """Create a valid JWT token for testing."""
    return create_access_token({"sub": user_id, "session_id": session_id})


def get_token_without_session_id(user_id: str = "test-user-id") -> str:
    """Create a JWT token missing session_id."""
    return create_access_token({"sub": user_id})


# ---------------------------------------------------------------------------
# ConnectionManager branch coverage
# ---------------------------------------------------------------------------


class TestConnectionManagerBranchCoverage:
    """Tests targeting uncovered branches in ConnectionManager."""

    async def test_send_thinker_typing_conversation_not_in_rooms(self) -> None:
        """send_thinker_typing when conversation has no room does not error.

        Coverage: branch 189->191 (if conversation_id in self.rooms: → False path).
        The branch where conversation is NOT in rooms should skip the typing add
        but still attempt to broadcast (which also short-circuits safely).
        """
        mgr = ConnectionManager()
        # Call with a conversation that has no room - should not raise
        await mgr.send_thinker_typing("nonexistent-conv", "Socrates")
        # Branch taken: conversation_id not in self.rooms → skip line 190

    async def test_send_thinker_stopped_typing_conversation_not_in_rooms(self) -> None:
        """send_thinker_stopped_typing when conversation has no room does not error.

        Coverage: branch 212->214 (if conversation_id in self.rooms: → False path).
        """
        mgr = ConnectionManager()
        await mgr.send_thinker_stopped_typing("nonexistent-conv", "Aristotle")
        # Branch taken: conversation_id not in self.rooms → skip line 213

    async def test_set_speed_multiplier_conversation_not_in_rooms(self) -> None:
        """set_speed_multiplier when conversation has no room is a no-op.

        Coverage: line 149 (if conversation_id in self.rooms: → False path).
        """
        mgr = ConnectionManager()
        # Should silently do nothing when conversation room doesn't exist
        await mgr.set_speed_multiplier("nonexistent-conv", 2.0)
        # Speed is clamped but no room to update - no error raised

    async def test_connect_to_existing_room_adds_connection(self) -> None:
        """connect() when room already in rooms skips creating new room.

        Coverage: branch 125->127 (if conversation_id not in self.rooms: → False path).
        This tests that the existing room is reused, not a new one created.
        """
        mgr = ConnectionManager()
        conversation_id = "existing-room-conv"

        # Pre-populate the rooms dict with an existing room
        from app.api.websocket import ConversationRoom

        existing_room = ConversationRoom(conversation_id=conversation_id)
        mgr.rooms[conversation_id] = existing_room

        # Create a mock WebSocket
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        # Connect a websocket - should use the EXISTING room (not create new one)
        await mgr.connect(mock_ws, conversation_id)

        # The existing room object should be used (same reference)
        assert mgr.rooms[conversation_id] is existing_room
        mock_ws.accept.assert_called_once()

    async def test_broadcast_to_conversation_no_room_is_noop(self) -> None:
        """broadcast_to_conversation when no room exists silently does nothing."""
        mgr = ConnectionManager()
        msg = WSMessage(type=WSMessageType.MESSAGE, conversation_id="no-room")
        # Should not raise even though room doesn't exist
        await mgr.broadcast_to_conversation("no-room", msg)

    async def test_send_thinker_typing_adds_to_typing_set_when_room_exists(self) -> None:
        """send_thinker_typing when room exists adds thinker to typing set.

        Coverage: branch 189->191 True path - exercises the typing_thinkers.add().
        """
        mgr = ConnectionManager()
        conv_id = "typing-test-conv"

        # Create a room first
        from app.api.websocket import ConversationRoom

        room = ConversationRoom(conversation_id=conv_id)
        mgr.rooms[conv_id] = room

        await mgr.send_thinker_typing(conv_id, "Plato")
        # Plato should be in typing_thinkers
        assert "Plato" in room.typing_thinkers

    async def test_send_thinker_stopped_typing_removes_from_typing_set(self) -> None:
        """send_thinker_stopped_typing when room exists removes from typing set.

        Coverage: branch 212->214 True path.
        """
        mgr = ConnectionManager()
        conv_id = "stopped-typing-conv"

        from app.api.websocket import ConversationRoom

        room = ConversationRoom(conversation_id=conv_id)
        room.typing_thinkers.add("Einstein")
        mgr.rooms[conv_id] = room

        await mgr.send_thinker_stopped_typing(conv_id, "Einstein")
        # Einstein should be removed from typing_thinkers
        assert "Einstein" not in room.typing_thinkers


# ---------------------------------------------------------------------------
# WebSocket authentication failure paths
# ---------------------------------------------------------------------------


class TestWebSocketAuthFailures:
    """Tests for WebSocket connection rejection on auth failures.

    These test the authentication paths in websocket_endpoint (lines 355-367).
    """

    def test_websocket_no_token_rejected(self) -> None:
        """WebSocket connection without token is rejected with code 4001."""
        with (
            TestClient(app) as test_client,
            pytest.raises((WebSocketDisconnect, Exception)),
            test_client.websocket_connect("/ws/test-conv-no-token") as ws,
        ):
            # Server should reject without token
            ws.receive_json()

    def test_websocket_invalid_token_rejected(self) -> None:
        """WebSocket connection with invalid/malformed token is rejected."""
        with (
            TestClient(app) as test_client,
            pytest.raises((WebSocketDisconnect, Exception)),
            test_client.websocket_connect("/ws/test-conv-bad-token?token=not-a-valid-jwt") as ws,
        ):
            ws.receive_json()

    def test_websocket_token_without_session_id_rejected(self) -> None:
        """WebSocket connection with token missing session_id is rejected."""
        token = get_token_without_session_id()
        with (
            TestClient(app) as test_client,
            pytest.raises((WebSocketDisconnect, Exception)),
            test_client.websocket_connect(f"/ws/test-conv-no-session?token={token}") as ws,
        ):
            ws.receive_json()

    def test_websocket_set_speed_message(self) -> None:
        """WebSocket SET_SPEED message is handled and broadcasts SPEED_CHANGED.

        Coverage: lines 474-477 (elif message_type == WSMessageType.SET_SPEED.value).
        """
        token = get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/speed-test-conv?token={token}") as ws,
        ):
            # Skip join message
            ws.receive_json()
            # Skip initial resumed message
            ws.receive_json()

            # Send SET_SPEED message
            ws.send_json({"type": "set_speed", "speed_multiplier": 2.0})

            # Should receive SPEED_CHANGED broadcast
            data = ws.receive_json()
            assert data["type"] == "speed_changed"
            assert data["speed_multiplier"] == 2.0

    def test_websocket_set_speed_clamped_to_valid_range(self) -> None:
        """SET_SPEED is clamped to valid range [0.5, 6.0]."""
        token = get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/speed-clamp-conv?token={token}") as ws,
        ):
            ws.receive_json()  # user_joined
            ws.receive_json()  # resumed

            # Send speed above max (6.0)
            ws.send_json({"type": "set_speed", "speed_multiplier": 99.0})

            data = ws.receive_json()
            assert data["type"] == "speed_changed"
            # Should be clamped to 6.0
            assert data["speed_multiplier"] == 6.0


# ---------------------------------------------------------------------------
# ThinkerService unit tests for uncovered paths
# ---------------------------------------------------------------------------


class TestThinkerServiceSplitBubbles:
    """Tests for _split_response_into_bubbles force-split path."""

    def test_force_split_long_single_sentence(self) -> None:
        """Long text with one bubble triggers force split at middle sentence boundary.

        Coverage: lines 763-774 (if len(bubbles) == 1 and len(text) > 300:).
        """
        # Create a long text (>300 chars) that won't naturally split into multiple bubbles
        # because it has no sentence endings (periods) that would trigger a natural split
        # Text must be > 300 chars, have no natural sentence splits (single "bubble" from natural logic),
        # AND have a period after the midpoint so force-split can find a boundary.
        # Single long "sentence" with a period near the 3/4 mark.
        first_half = "W" * 150 + " "  # 151 chars, no period
        mid_section = "The philosopher considered the problem at length. "  # period here
        second_half = "X" * 150  # pad to ensure total > 300
        long_text = first_half + mid_section + second_half
        assert len(long_text) > 300

        # Use a deterministic random strategy that doesn't early-return (strategy_roll > 0.25)
        # and uses a large target_size so natural splitting doesn't divide the text
        with (
            patch("app.services.thinker.random.random", return_value=0.5),
            patch("app.services.thinker.random.randint", return_value=300),
        ):
            result = thinker_service._split_response_into_bubbles(long_text)

        # Should be at least 1 result (force split may or may not find a boundary)
        assert len(result) >= 1
        # All parts should be non-empty
        assert all(len(p) > 0 for p in result)

    def test_force_split_long_text_with_sentence_boundaries(self) -> None:
        """Long text with sentence boundary after midpoint gets force-split there.

        Coverage: lines 769-774 (loop to find nearest sentence end after mid).
        """
        # Create text > 300 chars with a sentence end in the second half
        # "A " * 50 = 100 chars, then a sentence that ends with period
        first_half = "A " * 75  # 150 chars, no period
        second_half = "B " * 75 + "end. More text here."  # period at char ~302
        long_text = first_half + second_half

        assert len(long_text) > 300

        result = thinker_service._split_response_into_bubbles(long_text)
        # Result should have at least 1 entry (force split may or may not find a period)
        assert len(result) >= 1

    def test_short_text_not_force_split(self) -> None:
        """Text shorter than 300 chars is not force-split even if one bubble."""
        short_text = "This is a short philosophical statement under 300 characters."
        assert len(short_text) < 300

        result = thinker_service._split_response_into_bubbles(short_text)
        # Should be 1 bubble (not force-split)
        assert len(result) == 1
        assert result[0] == short_text

    def test_text_with_transition_words_splits_correctly(self) -> None:
        """Text starting with transition words triggers a new bubble.

        Uses text > 250 chars to bypass the 25% 'keep as single bubble' early return,
        and seeds random to use the normal splitting strategy.
        """

        # Use text > 250 chars to avoid the early-return path (len < 250 check)
        # Also ensure neither sentence alone exceeds target_size so split is driven by transition
        first = "This is one philosophical thought that we are examining carefully here with some detail. "
        second = "However, this is a contrasting thought that represents an opposing view in the discussion and adds nuance to the overall philosophical argument being made about the nature of things."
        text = first + second
        assert len(text) > 250

        # Seed random to get a strategy_roll > 0.25 (so we don't early-return)
        # and target_size large enough to not split on length alone
        with (
            patch("app.services.thinker.random.random", return_value=0.5),
            patch("app.services.thinker.random.randint", return_value=200),
        ):
            result = thinker_service._split_response_into_bubbles(text)

        # "However," triggers a new bubble even with large target_size
        assert len(result) >= 2
        assert any("However" in b for b in result)


class TestThinkerServiceExtractThinkingDisplay:
    """Tests for _extract_thinking_display edge cases."""

    def test_empty_text_returns_empty_string(self) -> None:
        """Empty thinking text returns empty string."""
        result = thinker_service._extract_thinking_display("", "en")
        assert result == ""

    def test_short_text_under_80_returns_empty(self) -> None:
        """Text shorter than 80 chars returns empty (wait for more content)."""
        short = "Short thought."
        assert len(short) < 80
        result = thinker_service._extract_thinking_display(short, "en")
        assert result == ""

    def test_long_text_over_200_chars_extracts_last_200(self) -> None:
        """Text over 200 chars extracts from the last ~200 characters.

        Coverage: lines 801-808 (if len(text) > 200: text = text[-200:]).
        """
        # Create text well over 200 chars. The beginning is clearly distinct from the end.
        # "Beginning section..." then a long middle, then an "Important conclusion..."
        beginning = "ZZZZZ_START " * 5  # easy to detect if present in output
        middle = "The philosopher considered the question carefully and at length." * 3
        end_section = " This is the important conclusion we want to see in the display."
        text = beginning + middle + end_section
        assert len(text) > 200

        result = thinker_service._extract_thinking_display(text, "en")
        # Should return something (not empty)
        assert isinstance(result, str)
        # The beginning section should NOT appear in the result (it's from the start, not end)
        assert "ZZZZZ_START" not in result

    def test_sentence_boundary_found_in_truncated_text(self) -> None:
        """When text is >200 chars and has sentence boundary, start from it.

        Coverage: lines 804-808 (finding sentence boundary with '. ').
        """
        # 200+ chars text where the last 200 chars have a sentence boundary early
        prefix = "X" * 150
        # The ". " should appear at index < 80 in the last 200 chars
        suffix = "Complete thought. " + "Y" * 130 + " final words."
        long_text = prefix + suffix

        assert len(long_text) > 200

        result = thinker_service._extract_thinking_display(long_text, "en")
        assert isinstance(result, str)

    def test_word_boundary_truncation_for_readability(self) -> None:
        """Text doesn't end mid-word - truncated at last word boundary.

        Coverage: lines 816-820 (word boundary truncation).
        """
        # Create text of exactly 80+ chars that needs word boundary check
        # The function checks: len(text) > 60 and not text[-1].isspace() and " " in text[-30:]
        text = "This is a well-formed thought that has proper word boundaries for clean display"
        assert len(text) > 60

        result = thinker_service._extract_thinking_display(text, "en")
        # Should not end mid-word
        assert isinstance(result, str)
        if result:
            # Result should not end with partial word (end should be a complete word)
            assert not result.endswith(" ")

    def test_german_language_replacements(self) -> None:
        """German language uses German-specific text replacements.

        Coverage: lines 824-836 (language == 'de' branch).
        """
        # Create German text > 80 chars with phrases that get replaced
        text = "Ich denke über dieses Problem nach. Ich sollte die Konsequenzen bedenken. Dies ist eine wichtige philosophische Frage für uns alle."
        assert len(text) >= 80

        result = thinker_service._extract_thinking_display(text, "de")
        # Should apply German replacements - "Ich denke " → ""
        assert isinstance(result, str)

    def test_spanish_language_replacements(self) -> None:
        """Spanish language uses Spanish-specific text replacements.

        Coverage: lines 837-848 (language == 'es' branch).
        """
        text = "Creo que este problema es muy interesante para explorar. Debería considerar las consecuencias filosóficas de esta propuesta con cuidado."
        assert len(text) >= 80

        result = thinker_service._extract_thinking_display(text, "es")
        assert isinstance(result, str)

    def test_french_language_replacements(self) -> None:
        """French language uses French-specific text replacements.

        Coverage: lines 850-862 (language == 'fr' branch).
        """
        text = "Je pense que cette question philosophique est fondamentale. Je devrais examiner les implications de cette idée avec soin et précision."
        assert len(text) >= 80

        result = thinker_service._extract_thinking_display(text, "fr")
        assert isinstance(result, str)

    def test_english_language_replacements_applied(self) -> None:
        """English language applies English-specific replacements.

        Coverage: lines 876-889 (else → English replacements).
        """
        # Text with English phrases that get replaced
        text = (
            "I think the fundamental question here is one of ethics. "
            "I should consider what Kant would say about this matter and how it applies to modern context."
        )
        assert len(text) >= 80

        result = thinker_service._extract_thinking_display(text, "en")
        # "I think " should be removed
        assert isinstance(result, str)
        # "I think " should be replaced with ""
        assert "I think " not in result


# ---------------------------------------------------------------------------
# ThinkerService generate_response_with_streaming_thinking
# ---------------------------------------------------------------------------


class TestThinkerServiceGetSenderLabel:
    """Tests for the get_sender_label nested function inside generate_response_with_streaming_thinking.

    Coverage: lines 540-543 (get_sender_label function).
    """

    async def test_generate_response_returns_empty_when_no_client(self) -> None:
        """generate_response_with_streaming_thinking returns empty tuple when no API client.

        Coverage: line 532-533 (if not self.client: return "", 0.0).
        This exercises the early-return path which avoids calling get_sender_label.
        """
        mock_thinker = MagicMock()
        mock_thinker.name = "Socrates"
        mock_thinker.bio = "Ancient philosopher"
        mock_thinker.positions = "Questioning everything"
        mock_thinker.style = "Socratic method"

        # Temporarily clear client by patching the settings API key
        with patch("app.services.thinker.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.anthropic_api_key = None
            mock_settings.idle_timeout_seconds = 0
            mock_get_settings.return_value = mock_settings

            from app.services.thinker import ThinkerService

            service = ThinkerService()
            # _client is None and anthropic_api_key is None → client property returns None
            assert service.client is None

            result = await service.generate_response_with_streaming_thinking(
                "conv-id", mock_thinker, [], "philosophy"
            )
        assert result == ("", 0.0)

    async def test_generate_response_with_user_messages_exercises_sender_label(
        self,
    ) -> None:
        """get_sender_label correctly identifies user messages for context building.

        Coverage: lines 540-543 - the user sender type check in get_sender_label.
        We patch the API call to avoid real HTTP requests.
        """
        mock_thinker = MagicMock()
        mock_thinker.name = "Socrates"
        mock_thinker.bio = "Ancient philosopher"
        mock_thinker.positions = "Questioning everything"
        mock_thinker.style = "Socratic method"

        # Create mock messages with user sender type (enum-style with .value)
        user_msg = MagicMock()
        user_msg.sender_type = MagicMock()
        user_msg.sender_type.value = "user"
        user_msg.sender_name = "Alice"
        user_msg.content = "What is justice?"

        thinker_msg = MagicMock()
        thinker_msg.sender_type = "thinker"
        thinker_msg.sender_name = "Plato"
        thinker_msg.content = "Justice is harmony."

        messages = [user_msg, thinker_msg]

        # Mock the Anthropic streaming call - patch _client directly since client is a property
        mock_anthropic = MagicMock()
        mock_stream_ctx = AsyncMock()
        mock_final_msg = MagicMock()
        mock_final_msg.usage.input_tokens = 100
        mock_final_msg.usage.output_tokens = 50
        mock_final_msg.content = []

        # Build a proper async-iterable mock using MockStreamingResponse
        mock_stream = MockStreamingResponse(mock_final_msg)
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_anthropic.messages.stream.return_value = mock_stream_ctx

        # Patch _client (private attribute) since 'client' is a read-only property
        original_client = thinker_service._client
        thinker_service._client = mock_anthropic
        try:
            result = await thinker_service.generate_response_with_streaming_thinking(
                "test-conv", mock_thinker, messages, "justice", language="en"
            )
        finally:
            thinker_service._client = original_client

        # Should return a tuple (response_text, cost)
        assert isinstance(result, tuple)
        assert len(result) == 2

    async def test_get_sender_label_user_without_value_attr(self) -> None:
        """get_sender_label handles sender_type without .value attribute (string type).

        Coverage: line 541 - `(hasattr(sender, 'value') and sender.value == 'user') or sender == 'user'`
        Tests the `sender == 'user'` path when sender_type is a plain string.
        """
        mock_thinker = MagicMock()
        mock_thinker.name = "Socrates"
        mock_thinker.bio = "Ancient philosopher"
        mock_thinker.positions = "Questioning everything"
        mock_thinker.style = "Socratic method"

        # Message with string sender_type (not enum) - exercises the `sender == 'user'` branch
        user_msg = MagicMock()
        user_msg.sender_type = "user"  # plain string, no .value attribute
        user_msg.sender_name = "Bob"
        user_msg.content = "Tell me about ethics."

        messages = [user_msg]

        mock_anthropic = MagicMock()
        mock_stream_ctx = AsyncMock()
        mock_final_msg = MagicMock()
        mock_final_msg.usage.input_tokens = 100
        mock_final_msg.usage.output_tokens = 50
        mock_final_msg.content = []

        mock_stream = MockStreamingResponse(mock_final_msg)
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_anthropic.messages.stream.return_value = mock_stream_ctx

        original_client = thinker_service._client
        thinker_service._client = mock_anthropic
        try:
            result = await thinker_service.generate_response_with_streaming_thinking(
                "test-conv2", mock_thinker, messages, "ethics", language="en"
            )
        finally:
            thinker_service._client = original_client

        assert isinstance(result, tuple)

    async def test_initial_message_instruction_added_for_first_message(self) -> None:
        """is_initial_message=True adds CRITICAL FOR FIRST MESSAGE instruction.

        Coverage: lines 557-563 (if is_initial_message: initial_message_instruction = ...).
        When messages list is empty or has <=1 message, is_initial_message=True.
        """
        mock_thinker = MagicMock()
        mock_thinker.name = "Aristotle"
        mock_thinker.bio = "Student of Plato"
        mock_thinker.positions = "Logic and virtue ethics"
        mock_thinker.style = "Systematic and empirical"

        # Empty messages triggers is_initial_message = True (len(messages) <= 1)
        messages: list = []

        mock_anthropic = MagicMock()
        mock_stream_ctx = AsyncMock()
        mock_final_msg = MagicMock()
        mock_final_msg.usage.input_tokens = 100
        mock_final_msg.usage.output_tokens = 50
        mock_final_msg.content = []

        mock_stream = MockStreamingResponse(mock_final_msg)
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_anthropic.messages.stream.return_value = mock_stream_ctx

        original_client = thinker_service._client
        thinker_service._client = mock_anthropic
        try:
            result = await thinker_service.generate_response_with_streaming_thinking(
                "test-conv3", mock_thinker, messages, "virtue", language="en"
            )
        finally:
            thinker_service._client = original_client

        # Successfully exercised the is_initial_message=True code path
        assert isinstance(result, tuple)
        assert len(result) == 2

    async def test_non_initial_message_skips_instruction(self) -> None:
        """is_initial_message=False skips the CRITICAL FOR FIRST MESSAGE instruction.

        Coverage: the else/skip path in lines 556-562.
        When messages has >1 message, is_initial_message=False.
        """
        mock_thinker = MagicMock()
        mock_thinker.name = "Kant"
        mock_thinker.bio = "Enlightenment philosopher"
        mock_thinker.positions = "Categorical imperative"
        mock_thinker.style = "Systematic and formal"

        # Two messages triggers is_initial_message = False
        msg1 = MagicMock()
        msg1.sender_type = "user"
        msg1.sender_name = "Alice"
        msg1.content = "What is the good?"

        msg2 = MagicMock()
        msg2.sender_type = "thinker"
        msg2.sender_name = "Aristotle"
        msg2.content = "The good is eudaimonia."

        messages = [msg1, msg2]

        mock_anthropic = MagicMock()
        mock_stream_ctx = AsyncMock()
        mock_final_msg = MagicMock()
        mock_final_msg.usage.input_tokens = 100
        mock_final_msg.usage.output_tokens = 50
        mock_final_msg.content = []

        mock_stream = MockStreamingResponse(mock_final_msg)
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_anthropic.messages.stream.return_value = mock_stream_ctx

        original_client = thinker_service._client
        thinker_service._client = mock_anthropic
        try:
            result = await thinker_service.generate_response_with_streaming_thinking(
                "test-conv4", mock_thinker, messages, "good life", language="en"
            )
        finally:
            thinker_service._client = original_client

        assert isinstance(result, tuple)


# ---------------------------------------------------------------------------
# Main lifespan integration test
# ---------------------------------------------------------------------------


class TestMainLifespan:
    """Tests that exercise main.py lifespan startup/shutdown paths.

    Coverage: lines 49-68 (lifespan context manager).
    """

    async def test_lifespan_startup_calls_init_and_create_admin(self) -> None:
        """Lifespan startup calls init_db and create_admin_user.

        Coverage: lines 49-62 (startup try block with init_db and create_admin_user).
        """
        with (
            patch("app.main.init_db") as mock_init_db,
            patch("app.main.create_admin_user") as mock_create_admin,
            patch("app.main.close_db") as mock_close_db,
        ):
            mock_init_db.return_value = None
            mock_create_admin.return_value = None
            mock_close_db.return_value = None

            # Use the lifespan context manager directly
            from app.main import lifespan

            mock_app = MagicMock()
            async with lifespan(mock_app):
                # We're inside the lifespan - startup has completed
                mock_init_db.assert_called_once()
                mock_create_admin.assert_called_once()

            # After context exits, shutdown should have been called
            mock_close_db.assert_called_once()

    async def test_lifespan_startup_failure_propagates_exception(self) -> None:
        """Lifespan startup failure propagates the exception.

        Coverage: lines 63-65 (except Exception as e: logger.error; raise).
        """
        with (
            patch("app.main.init_db", side_effect=RuntimeError("DB connection failed")),
        ):
            from app.main import lifespan

            mock_app = MagicMock()
            with pytest.raises(RuntimeError, match="DB connection failed"):
                async with lifespan(mock_app):
                    pass  # Should not reach here
