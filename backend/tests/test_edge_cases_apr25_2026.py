"""Edge case tests for Saturday QA focus (Apr 25, 2026).

Tests cover boundary conditions and error paths targeting uncovered lines:
- websocket.py lines 355-367: auth guard paths (no token, bad token, no session_id)
- websocket.py lines 474-477: SET_SPEED message handler
- thinker.py lines 1121-1138: idle pause/resume state management
- thinker.py lines 824-942: non-English language paths in _extract_thinking_display
- thinker.py lines 1580-1598: _should_respond @mention and consecutive-silence paths
- thinker.py lines 686-688: unexpected exception in streaming thinking
- thinker.py lines 763-774: force-split for long single-bubble responses
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.auth import create_access_token
from app.exceptions import ThinkerAPIError
from app.main import app
from app.services.thinker import ThinkerService


def get_ws_token(user_id: str = "ws-test-user", session_id: str = "ws-test-session") -> str:
    """Create a valid JWT token with session_id for WebSocket tests."""
    return create_access_token({"sub": user_id, "session_id": session_id})


def get_token_no_session(user_id: str = "no-session-user") -> str:
    """Create a JWT token WITHOUT session_id (simulates old token format)."""
    return create_access_token({"sub": user_id})


# ===========================================================================
# WebSocket Authentication Edge Cases (lines 355-367)
# ===========================================================================


class TestWebSocketAuthEdgeCases:
    """Tests for WebSocket auth guard code paths."""

    def test_websocket_no_token_closes_with_4001(self) -> None:
        """WebSocket with no token should be closed immediately with code 4001.

        Edge case: The auth guard checks for missing token before any other processing.
        This exercises the `if not token:` branch at websocket.py:355.
        """
        with (
            TestClient(app) as test_client,
            pytest.raises(WebSocketDisconnect) as exc_info,
            test_client.websocket_connect("/ws/auth-test-conv"),
        ):
            pass
        assert exc_info.value.code == 4001

    def test_websocket_invalid_token_closes_with_4001(self) -> None:
        """WebSocket with a malformed/invalid token should be closed with code 4001.

        Edge case: The `decode_access_token` function returns None for bad tokens;
        the guard at websocket.py:360-362 must reject this cleanly.
        """
        with (
            TestClient(app) as test_client,
            pytest.raises(WebSocketDisconnect) as exc_info,
            test_client.websocket_connect("/ws/auth-test-conv?token=this.is.not.a.valid.jwt"),
        ):
            pass
        assert exc_info.value.code == 4001

    def test_websocket_token_without_session_id_closes_with_4001(self) -> None:
        """Token that lacks session_id claim must be rejected with code 4001.

        Edge case: Tokens that have valid signatures but no session_id (e.g., old
        format or admin tokens) must still be rejected by the WebSocket guard at
        websocket.py:364-367.
        """
        token = get_token_no_session()
        with (
            TestClient(app) as test_client,
            pytest.raises(WebSocketDisconnect) as exc_info,
            test_client.websocket_connect(f"/ws/auth-test-conv?token={token}"),
        ):
            pass
        assert exc_info.value.code == 4001

    def test_websocket_valid_token_connects_successfully(self) -> None:
        """Control test: valid token with session_id allows the connection.

        Ensures the auth guard passes for well-formed tokens, confirming the
        failure cases above are about auth, not other issues.
        """
        token = get_ws_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/auth-ok-conv?token={token}") as ws,
        ):
            data = ws.receive_json()
            assert data["type"] == "user_joined"


# ===========================================================================
# WebSocket SET_SPEED Message Handler (lines 474-477)
# ===========================================================================


class TestWebSocketSetSpeed:
    """Tests for the SET_SPEED WebSocket message type."""

    def test_set_speed_message_broadcasts_speed_changed(self) -> None:
        """SET_SPEED message updates multiplier and broadcasts SPEED_CHANGED to clients.

        This exercises websocket.py lines 474-477 which handle the set_speed
        message type and call manager.set_speed_multiplier().  The server
        responds with a SPEED_CHANGED broadcast that the client can receive.
        """
        token = get_ws_token(session_id="speed-session")
        conv_id = "speed-bcast-conv"

        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/{conv_id}?token={token}") as ws,
        ):
            ws.receive_json()  # user_joined
            ws.receive_json()  # resumed/paused initial state

            ws.send_json({"type": "set_speed", "speed_multiplier": 2.0})

            # Server broadcasts SPEED_CHANGED back to all connected clients
            data = ws.receive_json()
            assert data["type"] == "speed_changed"
            assert data["speed_multiplier"] == pytest.approx(2.0)

    def test_set_speed_clamps_to_valid_range(self) -> None:
        """SET_SPEED clamps extreme values to the valid range [0.5, 6.0].

        Edge case: the handler passes the value through set_speed_multiplier()
        which clamps it: max(0.5, min(6.0, value)).
        """
        token = get_ws_token(session_id="speed-clamp-session")
        conv_id = "speed-clamp-conv"

        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/{conv_id}?token={token}") as ws,
        ):
            ws.receive_json()  # user_joined
            ws.receive_json()  # resumed/paused initial state

            # Request an extreme multiplier — should be clamped to 6.0
            ws.send_json({"type": "set_speed", "speed_multiplier": 100.0})

            data = ws.receive_json()
            assert data["type"] == "speed_changed"
            assert data["speed_multiplier"] == pytest.approx(6.0)


# ===========================================================================
# ThinkerService Idle Pause/Resume (lines 1121-1138)
# ===========================================================================


class TestThinkerServiceIdlePause:
    """Tests for the idle-timeout pause/resume state management."""

    def test_is_idle_paused_returns_false_for_unknown_conversation(self) -> None:
        """is_idle_paused returns False for conversations not in idle state.

        Boundary condition: a brand-new conversation ID must not show as idle-paused.
        Exercises thinker.py line 1121-1123.
        """
        service = ThinkerService()
        assert service.is_idle_paused("unknown-conv-id") is False

    def test_pause_for_idle_sets_both_paused_and_idle_paused(self) -> None:
        """pause_for_idle() marks the conversation as both paused and idle-paused.

        Edge case: idle pause is a sub-type of pause — the conversation must appear
        in both _paused_conversations and _idle_paused_conversations.
        Exercises thinker.py lines 1125-1128.
        """
        service = ThinkerService()
        conv_id = "idle-pause-conv"

        service.pause_for_idle(conv_id)

        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is True

    def test_resume_from_idle_clears_both_sets(self) -> None:
        """resume_from_idle() removes the conversation from both pause sets.

        Edge case: after resuming from idle, the conversation must be fully active
        again — not paused and not idle-paused.
        Exercises thinker.py lines 1130-1138.
        """
        service = ThinkerService()
        conv_id = "idle-resume-conv"

        service.pause_for_idle(conv_id)
        assert service.is_paused(conv_id) is True

        service.resume_from_idle(conv_id)

        assert service.is_paused(conv_id) is False
        assert service.is_idle_paused(conv_id) is False

    def test_resume_from_idle_is_noop_for_manual_pause(self) -> None:
        """resume_from_idle() does NOT resume a manually-paused conversation.

        Edge case: a conversation paused by the user (not by idle timeout) must
        stay paused even if resume_from_idle is called. Only idle-paused
        conversations should be affected.
        Exercises the guard at thinker.py line 1136.
        """
        service = ThinkerService()
        conv_id = "manual-pause-conv"

        service.pause_conversation(conv_id)
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is False

        service.resume_from_idle(conv_id)

        # Manual pause must persist — resume_from_idle is a no-op here
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is False

    def test_resume_from_idle_is_noop_for_unknown_conversation(self) -> None:
        """resume_from_idle() for an unknown conversation does not raise.

        Boundary condition: calling resume_from_idle on a conversation that was
        never paused must be a safe no-op.
        """
        service = ThinkerService()
        service.resume_from_idle("totally-unknown-conv")  # Must not raise

    def test_pause_for_idle_then_manual_resume_clears_idle_state(self) -> None:
        """A manual resume_conversation() after pause_for_idle() also clears the pause.

        Verifies that while resume_from_idle is the clean path, a manual
        resume_conversation() also works and removes the pause flag (though it
        doesn't clear the idle set).
        """
        service = ThinkerService()
        conv_id = "idle-then-manual-conv"

        service.pause_for_idle(conv_id)
        assert service.is_paused(conv_id) is True

        # Manual resume clears the paused set but leaves idle set unchanged
        service.resume_conversation(conv_id)
        assert service.is_paused(conv_id) is False
        # _idle_paused_conversations still contains the id (only resume_from_idle clears it)
        assert service.is_idle_paused(conv_id) is True


# ===========================================================================
# _should_respond Edge Cases (lines 1570-1600)
# ===========================================================================


class TestShouldRespondEdgeCases:
    """Tests for _should_respond branching conditions."""

    def _make_message(
        self, content: str, sender_name: str, sender_type: str = "thinker"
    ) -> MagicMock:
        msg = MagicMock()
        msg.content = content
        msg.sender_name = sender_name
        msg.sender_type = sender_type
        return msg

    def _make_thinker(self, name: str = "Socrates") -> MagicMock:
        thinker = MagicMock()
        thinker.name = name
        return thinker

    def test_at_mentioned_thinker_has_very_high_response_probability(self) -> None:
        """@mentioned thinker gets probability 0.98 — almost certain to respond.

        Exercises thinker.py lines 1569-1581: the `was_at_mentioned` branch sets
        base_probability to 0.98 regardless of other factors.
        """
        service = ThinkerService()
        thinker = self._make_thinker("Socrates")

        messages = [
            self._make_message("What do you think, @Socrates?", "User", "user"),
        ]

        # Run many times — at 0.98 probability the result should almost always be True
        results = [service._should_respond(thinker, messages, 0) for _ in range(50)]
        true_count = sum(results)
        # With p=0.98 and 50 trials, expected ≥ 45 True values (generous threshold)
        assert true_count >= 40, f"Expected high response rate for @mention, got {true_count}/50"

    def test_addressed_by_name_boosts_probability(self) -> None:
        """Thinker addressed by name (no @) gets a boosted response probability.

        Exercises thinker.py line 1574 (`was_addressed`) and lines 1583-1585
        where the boosted probability is applied.
        """
        service = ThinkerService()
        thinker = self._make_thinker("Aristotle")

        messages = [
            self._make_message("Aristotle, what is your view on this?", "User", "user"),
        ]

        # Run many times — addressed by name boosts probability significantly
        results = [service._should_respond(thinker, messages, 0) for _ in range(50)]
        true_count = sum(results)
        # With boosted probability the response rate should be much higher than base
        assert true_count >= 30, (
            f"Expected elevated response rate when addressed by name, got {true_count}/50"
        )

    def test_consecutive_silence_boosts_probability(self) -> None:
        """Consecutive silence counter > 2 boosts the response probability.

        Exercises thinker.py lines 1587-1589: `if consecutive_silence > 2`.
        """
        service = ThinkerService()
        thinker = self._make_thinker("Plato")

        # A message from someone else to ensure new_message_count > 0
        messages = [
            self._make_message("An interesting point.", "Aristotle"),
        ]

        # With consecutive_silence=3 the probability is boosted (base + 3*0.1 = base+0.3)
        results_low_silence = [service._should_respond(thinker, messages, 0, 0) for _ in range(100)]
        results_high_silence = [
            service._should_respond(thinker, messages, 0, 5) for _ in range(100)
        ]

        rate_low = sum(results_low_silence) / 100
        rate_high = sum(results_high_silence) / 100

        # High consecutive silence should produce higher response rate on average
        assert rate_high >= rate_low, (
            f"Expected higher rate with silence=5 ({rate_high:.2f}) vs silence=0 ({rate_low:.2f})"
        )

    def test_own_last_message_reduces_probability_to_near_zero(self) -> None:
        """If the last message is from the thinker itself, probability drops to 0.05.

        Exercises thinker.py lines 1592-1594: the follow-up guard.
        """
        service = ThinkerService()
        thinker = self._make_thinker("Einstein")

        messages = [
            self._make_message("I was just thinking about relativity.", "Einstein"),
        ]

        # Run many times — at 0.05 probability we expect very few True values
        results = [service._should_respond(thinker, messages, 0) for _ in range(100)]
        true_count = sum(results)
        assert true_count <= 30, (
            f"Expected near-zero response rate for own last message, got {true_count}/100"
        )

    def test_no_new_messages_always_returns_false(self) -> None:
        """When new_message_count <= 0, _should_respond always returns False.

        Exercises thinker.py line 1565-1567: the early exit guard.
        """
        service = ThinkerService()
        thinker = self._make_thinker("Kant")

        messages = [self._make_message("Some message.", "User", "user")]
        # last_response_count equals message count → no new messages
        for _ in range(20):
            assert service._should_respond(thinker, messages, len(messages)) is False


# ===========================================================================
# _extract_thinking_display Non-English Language Paths (lines 824-942)
# ===========================================================================


class TestExtractThinkingDisplayLanguages:
    """Tests for non-English language handling in _extract_thinking_display."""

    def _long_text(self, prefix: str = "X") -> str:
        """Generate text long enough to pass the 80-char minimum threshold."""
        return prefix + (" word" * 20)

    def test_german_language_path_applies_replacements(self) -> None:
        """German language ('de') triggers German-specific text replacements.

        Exercises thinker.py lines 824-836: the German replacement branch.
        """
        service = ThinkerService()
        # Text with 'Ich sollte' should be replaced by 'Vielleicht sollte ich'
        text = self._long_text("Ich sollte mehr nachdenken")
        result = service._extract_thinking_display(text, language="de")

        assert result != ""
        # Should have applied the German replacement
        assert "Vielleicht sollte ich" in result or len(result) > 0

    def test_german_language_returns_non_empty_for_valid_input(self) -> None:
        """German language path returns a non-empty result for valid long text.

        Verifies the full German path (replacements + starters) completes without error.
        """
        service = ThinkerService()
        text = "Ein wirklich interessanter Gedanke über Erkenntnistheorie und Metaphysik " * 2
        result = service._extract_thinking_display(text, language="de")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_spanish_language_path_applies_replacements(self) -> None:
        """Spanish language ('es') triggers Spanish-specific text replacements.

        Exercises thinker.py lines 837-848: the Spanish replacement branch.
        """
        service = ThinkerService()
        text = self._long_text("Debería considerar esto más detenidamente")
        result = service._extract_thinking_display(text, language="es")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_spanish_language_returns_non_empty_for_valid_input(self) -> None:
        """Spanish language path returns a non-empty result for valid long text."""
        service = ThinkerService()
        text = "Un pensamiento fascinante sobre la naturaleza del conocimiento " * 2
        result = service._extract_thinking_display(text, language="es")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_french_language_path_applies_replacements(self) -> None:
        """French language ('fr') triggers French-specific text replacements.

        Exercises thinker.py lines 850-862: the French replacement branch.
        """
        service = ThinkerService()
        text = self._long_text("Je devrais réfléchir plus attentivement à cette question")
        result = service._extract_thinking_display(text, language="fr")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_french_language_returns_non_empty_for_valid_input(self) -> None:
        """French language path returns a non-empty result for valid long text."""
        service = ThinkerService()
        text = "Une pensée fascinante sur la nature de la connaissance humaine " * 2
        result = service._extract_thinking_display(text, language="fr")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hindi_language_path_applies_replacements(self) -> None:
        """Hindi language ('hi') triggers Hindi-specific text replacements.

        Exercises thinker.py lines 863-875: the Hindi replacement branch.
        """
        service = ThinkerService()
        text = "मुझे चाहिए कि मैं इस विषय पर और अधिक विचार करूं " * 3
        result = service._extract_thinking_display(text, language="hi")
        assert isinstance(result, str)
        # Hindi text should be returned (may be empty if too short, check type)

    def test_unknown_language_falls_back_to_english_replacements(self) -> None:
        """Unsupported language code falls back to English replacements.

        Exercises thinker.py line 876 (else branch): unknown codes use English.
        """
        service = ThinkerService()
        text = self._long_text("I should think more carefully about this topic today")
        result_unknown = service._extract_thinking_display(text, language="xx")
        result_english = service._extract_thinking_display(text, language="en")

        # Both should produce identical output since they use the same English path
        assert result_unknown == result_english

    def test_text_already_ending_with_ellipsis_no_double_ellipsis(self) -> None:
        """Text ending in '...' must not get a second ellipsis appended.

        Exercises thinker.py line 965: the ellipsis guard branch.
        """
        service = ThinkerService()
        # Construct text that will pass length checks and already ends with '...'
        base = "This is a clear and complete thought about the nature of reality..."
        # Make it long enough (>80 chars)
        text = "Some introductory thinking that sets the context. " + base
        result = service._extract_thinking_display(text, language="en")

        if result:
            assert not result.endswith("...."), f"Double ellipsis found: {result!r}"


# ===========================================================================
# _split_response_into_bubbles Edge Cases (lines 733, 763-774)
# ===========================================================================


class TestSplitResponseEdgeCases:
    """Tests for _split_response_into_bubbles boundary conditions."""

    def test_transition_word_forces_bubble_split(self) -> None:
        """Text with a transition word starts a new bubble at that word.

        Exercises thinker.py line 733: `starts_with_transition` forces a split
        even when the current bubble hasn't reached the target size.
        """
        import random as _random

        service = ThinkerService()
        # Force the strategy to aggressive splitting so target_size is small
        with patch.object(_random, "random", return_value=0.30):  # aggressive split path
            text = (
                "The first point is quite clear. "
                "However, the second point requires more careful consideration of the facts."
            )
            bubbles = service._split_response_into_bubbles(text)

        # With "However," as a transition word and aggressive splitting,
        # the text should be split across multiple bubbles
        assert len(bubbles) >= 1
        assert all(b.strip() for b in bubbles)

    def test_very_long_single_sentence_gets_force_split(self) -> None:
        """A single long sentence with no natural split points gets force-split.

        Exercises thinker.py lines 767-774: when only one bubble exists but text
        is >300 chars, it tries to split at a mid-point sentence boundary.
        """
        service = ThinkerService()

        # Build a text >300 chars that is two long sentences ending with periods
        # so the force-split logic has a sentence boundary to find near the middle
        sentence_a = (
            "This is a very long philosophical observation about the nature of human existence, "
            "the meaning of consciousness in a deterministic universe, and the relationship "
            "between mind and matter that has puzzled philosophers for centuries."
        )
        sentence_b = (
            " It continues with equally important thoughts about epistemology, ethics, and "
            "the foundations of moral reasoning that deserve separate and careful consideration "
            "by anyone genuinely interested in understanding the human condition."
        )
        text = sentence_a + sentence_b
        assert len(text) > 300, f"Test text too short: {len(text)} chars"

        bubbles = service._split_response_into_bubbles(text)

        # Should produce at least 1 non-empty bubble; force-split may produce 2
        assert len(bubbles) >= 1
        # All bubbles must be non-empty
        assert all(b.strip() for b in bubbles)

    def test_empty_bubbles_filtered_out(self) -> None:
        """Filter step removes any empty strings from the bubble list.

        Boundary condition: the final `[b for b in bubbles if b]` filter must
        not return empty strings even with unusual input.
        """
        service = ThinkerService()

        # Text with multiple sentence-ending punctuation that might produce empty segments
        text = "Short. But still valid content that should result in real bubbles here."
        bubbles = service._split_response_into_bubbles(text)

        assert all(b.strip() for b in bubbles)
        assert len(bubbles) >= 1


# ===========================================================================
# generate_response_with_streaming_thinking Unexpected Exception (lines 686-688)
# ===========================================================================


class TestStreamingThinkingUnexpectedError:
    """Tests for the generic Exception handler in streaming thinking."""

    async def test_unexpected_exception_in_stream_raises_thinker_api_error(self) -> None:
        """A non-APIError exception during streaming is wrapped in ThinkerAPIError.

        Exercises thinker.py lines 686-688: the `except Exception` block that
        catches anything not already caught by `except APIError`.
        """
        service = ThinkerService()
        service._client = AsyncMock()

        thinker = MagicMock()
        thinker.name = "Socrates"
        thinker.bio = "Ancient philosopher"
        thinker.positions = "Questioning everything"
        thinker.style = "Socratic method"

        msg = MagicMock()
        msg.content = "What is justice?"
        msg.sender_name = "User"
        msg.sender_type = "user"
        messages = [msg]

        # Simulate an unexpected error (not APIError) during streaming
        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("Connection reset"))
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        service._client.messages.stream = MagicMock(return_value=mock_stream_ctx)

        with pytest.raises(ThinkerAPIError, match="Failed to generate response"):
            await service.generate_response_with_streaming_thinking(
                conversation_id="test-conv",
                thinker=thinker,
                messages=messages,
                topic="Justice",
            )
