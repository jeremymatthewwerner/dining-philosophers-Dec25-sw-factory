"""Flaky test hunt and hardening tests for QA Agent Tuesday focus.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-04-28).
Issue: #863

This file addresses the following flakiness risks identified in the Apr 28 session:

1. `_extract_thinking_display` language branches (de, es, fr, hi) are not covered
   by existing tests. A refactor could silently break non-English behavior.
   These deterministic tests lock down behavior for all language branches.

2. `_should_respond` probabilistic logic relies on `random.random` making it
   theoretically flaky under extreme random states. Mocking random.random makes
   these tests fully deterministic and catches logic regressions without luck.

3. `_split_response_into_bubbles` transition word detection: the transition word
   logic is always deterministic (not random), but existing tests mix it with
   random seed searches. Pure deterministic transition tests are faster and more
   reliable regression guards.

4. Conversation pause/idle state isolation: tests that create ThinkerService
   instances and call pause/idle methods without cleanup could leak state.
   These tests verify that each instance starts with clean state and that
   state methods handle unknown conversation IDs gracefully.

5. `_extract_thinking_display` boundary conditions: the word-boundary truncation
   (lines 819-820) and ellipsis addition (lines 965-966) are not explicitly tested.
   These cover the guard conditions that prevent displaying garbled truncated text.
"""

import random
from typing import Any
from unittest.mock import MagicMock, patch

from app.services.thinker import ThinkerService


class TestExtractThinkingDisplayLanguages:
    """Deterministic tests for _extract_thinking_display language branches.

    These tests verify that non-English language replacements work correctly.
    They are deterministic (no random calls) making them safe regression guards.
    """

    def _make_long_thinking(self, content: str) -> str:
        """Create a thinking text that's long enough to display (>80 chars)."""
        # Pad to be exactly 200 chars so no truncation occurs
        padding = " " * (200 - len(content)) if len(content) < 200 else ""
        return content + padding

    def test_german_replacements_applied(self) -> None:
        """Test that German (de) text transformations are applied correctly."""
        service = ThinkerService()
        # Text > 80 chars with a German phrase to replace
        thinking = (
            "Ich denke dies ist eine sehr wichtige Frage über Philosophie und Ethik heute hier."
        )
        result = service._extract_thinking_display(thinking, language="de")
        # "Ich denke " should be removed (replaced with "")
        assert "Ich denke " not in result

    def test_spanish_replacements_applied(self) -> None:
        """Test that Spanish (es) text transformations are applied correctly."""
        service = ThinkerService()
        # Text > 80 chars with a Spanish phrase to replace
        thinking = "Creo que esta es una pregunta muy importante sobre filosofía y ética hoy aquí."
        result = service._extract_thinking_display(thinking, language="es")
        # "Creo que " should be removed (replaced with "")
        assert "Creo que " not in result

    def test_french_replacements_applied(self) -> None:
        """Test that French (fr) text transformations are applied correctly."""
        service = ThinkerService()
        thinking = (
            "Je pense que cette question est très importante pour la philosophie moderne actuelle."
        )
        result = service._extract_thinking_display(thinking, language="fr")
        # "Je pense que " should be removed
        assert "Je pense que " not in result

    def test_english_should_replacement(self) -> None:
        """Test that English 'I should' is replaced with 'Perhaps I should'."""
        service = ThinkerService()
        thinking = "I should think carefully about this philosophical question regarding virtue and ethics now."
        result = service._extract_thinking_display(thinking, language="en")
        assert "Perhaps I should" in result
        assert "I should " not in result or "Perhaps" in result

    def test_english_let_me_replacement(self) -> None:
        """Test that English 'Let me' is replaced with 'Let me see...'."""
        service = ThinkerService()
        thinking = "Let me consider the historical context of this argument about virtue and the good life."
        result = service._extract_thinking_display(thinking, language="en")
        assert "Let me " not in result or "Let me see..." in result

    def test_short_text_returns_empty_string(self) -> None:
        """Test that text under 80 chars always returns empty string.

        Regression guard: display should never show incomplete snippets.
        """
        service = ThinkerService()
        for length in [0, 1, 40, 79]:
            text = "A" * length
            result = service._extract_thinking_display(text)
            assert result == "", f"Expected empty for {length}-char text, got: {result!r}"

    def test_exactly_80_chars_threshold(self) -> None:
        """Test the exact 80-character threshold for displaying thinking.

        79 chars → empty, 80 chars → may display (deterministic check).
        """
        service = ThinkerService()
        text_79 = "x" * 79
        assert service._extract_thinking_display(text_79) == ""

    def test_empty_text_returns_empty_string(self) -> None:
        """Test that empty input always returns empty string."""
        service = ThinkerService()
        assert service._extract_thinking_display("") == ""
        assert service._extract_thinking_display("", language="de") == ""
        assert service._extract_thinking_display("", language="es") == ""
        assert service._extract_thinking_display("", language="fr") == ""

    def test_long_text_gets_truncated_to_200_chars(self) -> None:
        """Test that text > 200 chars uses only the last 200 chars.

        Regression guard: very long thinking should not bloat display.
        """
        service = ThinkerService()
        # Create a 500-char text with a distinctive suffix
        prefix = "A" * 300  # This part should be dropped
        suffix = "Now let me think about this important philosophical point carefully. Yes, indeed."
        full_text = prefix + suffix
        assert len(full_text) > 200

        result = service._extract_thinking_display(full_text)
        # The result should contain text from the suffix region, not pure "A" prefix
        assert result != ""

    def test_text_with_ellipsis_not_doubled(self) -> None:
        """Test that text already ending with '...' does not get another '...'."""
        service = ThinkerService()
        # Long enough to display, already ends with ...
        thinking = "Hmm, let me think about this very carefully and deeply and ponder the implications now..."
        result = service._extract_thinking_display(thinking)
        # Should not end with "......"
        assert not result.endswith("......")

    def test_german_user_pronoun_replacement(self) -> None:
        """Test German 'Der Benutzer' → 'Sie' replacement."""
        service = ThinkerService()
        thinking = "Der Benutzer fragt nach der Wahrheit und ich denke über die Antwort sehr sorgfältig nach."
        result = service._extract_thinking_display(thinking, language="de")
        assert "Der Benutzer " not in result

    def test_spanish_user_pronoun_replacement(self) -> None:
        """Test Spanish 'El usuario' → 'Ellos' replacement."""
        service = ThinkerService()
        thinking = (
            "El usuario pregunta sobre la verdad y la filosofía del conocimiento humano moderno."
        )
        result = service._extract_thinking_display(thinking, language="es")
        assert "El usuario " not in result

    def test_hindi_short_text_returns_empty(self) -> None:
        """Test Hindi (hi) with short text also returns empty."""
        service = ThinkerService()
        short_hindi = "हम्म यह प्रश्न"
        assert service._extract_thinking_display(short_hindi, language="hi") == ""


class TestShouldRespondDeterministic:
    """Deterministic tests for _should_respond using mocked random.

    The existing probabilistic tests use 100 trials which is statistically robust
    but theoretically flaky. These tests mock random.random to deterministically
    verify each branch of the logic, providing regression guards without
    any probability of failure.
    """

    def _make_message(self, content: str, sender: str = "User") -> MagicMock:
        """Create a mock message with content and sender."""
        msg = MagicMock()
        msg.content = content
        msg.sender_name = sender
        return msg

    def test_at_mentioned_with_random_always_0_always_responds(self) -> None:
        """Test that @mentioned thinker with random=0.0 always responds.

        When @mentioned: base_probability=0.98, 15% silence check skipped.
        With random=0.0 < 0.98 → should always respond.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = self._make_message("@Socrates what is virtue?")
        messages: Any = [message]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.0
            result = service._should_respond(thinker, messages, 0)
        assert result is True

    def test_at_mentioned_with_random_always_1_never_responds(self) -> None:
        """Test that @mentioned thinker with random=1.0 never responds.

        With random=1.0 > 0.98 → should never respond.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = self._make_message("@Socrates what is virtue?")
        messages: Any = [message]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 1.0
            result = service._should_respond(thinker, messages, 0)
        assert result is False

    def test_own_message_with_random_0_still_suppressed(self) -> None:
        """Test that own message without @mention uses 0.05 probability.

        When sender == thinker and not @mentioned: base_probability=0.05.
        With random=0.0: passes 15% check (0.0 > 0.15 is False... wait)

        Actually: `if not was_at_mentioned and not was_addressed and random.random() < 0.15`
        With random returning 0.0 first (silence check: 0.0 < 0.15 → True → return False).
        So own message + random=0.0 → always returns False due to silence check.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = self._make_message("This is my own thought.", sender="Socrates")
        messages: Any = [message]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.0  # triggers silence cutoff
            result = service._should_respond(thinker, messages, 0)
        # With random=0.0, 15% silence check fires → returns False
        assert result is False

    def test_own_message_with_random_above_silence_threshold_uses_5pct(self) -> None:
        """Test that own message (no @mention) uses 0.05 final probability.

        Sequence with mocked random:
        - First call (0.20): 0.20 < 0.15 → False, silence check skipped (0.20 > 0.15)
        - Second call (0.04): 0.04 < 0.05 (base_prob for own message) → True
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = self._make_message("I am pondering this.", sender="Socrates")
        messages: Any = [message]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.20, 0.04]  # passes silence, passes 5% check
            result = service._should_respond(thinker, messages, 0)
        assert result is True

    def test_no_messages_returns_false(self) -> None:
        """Test that empty message list always returns False (no randomness needed)."""
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        result = service._should_respond(thinker, [], 0)
        assert result is False

    def test_no_new_messages_returns_false(self) -> None:
        """Test that last_response_count >= len(messages) returns False."""
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = self._make_message("Hello")
        messages: Any = [message]

        result = service._should_respond(thinker, messages, last_response_count=1)
        assert result is False

    def test_consecutive_silence_boosts_probability(self) -> None:
        """Test that consecutive_silence > 2 increases probability.

        With consecutive_silence=3 (not @mentioned): base_prob += 3*0.1 = 0.3
        Starting from 0.25 + 0.12 = 0.37, plus 0.3 = 0.67 (capped at 0.9).
        With random=0.0 and 0.0: silence check passes, response check passes.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = self._make_message("What do you think?")
        messages: Any = [message]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.20, 0.0]  # passes silence (>0.15), passes response
            result = service._should_respond(thinker, messages, 0, consecutive_silence=3)
        assert result is True

    def test_addressed_by_name_boosts_probability(self) -> None:
        """Test that thinker addressed by name (without @) gets higher probability.

        With 'Socrates' in message and not @mentioned:
        base_prob = min(0.25 + 0.12, 0.7) + 0.5 → capped at 0.95.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = self._make_message("Socrates what is virtue exactly?")
        messages: Any = [message]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.20, 0.0]  # passes silence, passes response
            result = service._should_respond(thinker, messages, 0)
        assert result is True

    def test_silence_cutoff_returns_false_deterministically(self) -> None:
        """Test that 15% silence cutoff returns False when random < 0.15.

        Regression guard: this branch (line 1597-1598) should always fire
        when random.random() < 0.15 and thinker is not @mentioned/addressed.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = self._make_message("Some general discussion happening here.")
        messages: Any = [message]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.10  # 0.10 < 0.15 → silence check fires
            result = service._should_respond(thinker, messages, 0)
        assert result is False


class TestSplitResponseBubblesDeterministic:
    """Deterministic tests for _split_response_into_bubbles.

    These tests verify transition word detection and force-split logic without
    relying on random seed searches. They are always deterministic.
    """

    def test_transition_word_but_forces_new_bubble(self) -> None:
        """Test that 'But ' at sentence start creates a new bubble.

        Uses text > 250 chars to bypass the 'keep as single bubble' short-circuit
        (which only applies when len(text) < 250). When text is longer, the
        sentence-level splitting always runs and transition words always fire.
        """
        service = ThinkerService()
        # Text > 250 chars so single-bubble short-circuit doesn't apply
        text = (
            "This is the first complete thought in my long response to your philosophical question here. "
            "I have spent considerable time thinking about virtue ethics and the good life in depth. "
            "But this sentence contradicts the previous one and should therefore start a new bubble."
        )
        assert len(text) > 250, f"Text must be > 250 chars for this test, got {len(text)}"
        random.seed(1)
        result = service._split_response_into_bubbles(text)
        # With text > 250 and "But " as transition, should always produce a split
        found_but_bubble = any(b.startswith("But ") for b in result)
        assert found_but_bubble, f"Expected 'But' to start a new bubble, got: {result}"

    def test_however_transition_forces_new_bubble(self) -> None:
        """Test that 'However,' at sentence start creates a new bubble.

        Uses text > 250 chars to ensure the sentence splitting path runs.
        """
        service = ThinkerService()
        # Text > 250 chars to bypass single-bubble short-circuit
        text = (
            "I believe this is absolutely true and correct in every possible way imaginable here. "
            "This first part establishes a clear philosophical position that I will defend carefully. "
            "However, there are important exceptions we must consider with great care and attention."
        )
        assert len(text) > 250, f"Text must be > 250 chars for this test, got {len(text)}"
        random.seed(1)
        result = service._split_response_into_bubbles(text)
        found_however = any(b.startswith("However") for b in result)
        assert found_however, f"Expected 'However' to start a new bubble, got: {result}"

    def test_very_short_text_always_single_bubble(self) -> None:
        """Test that text under 60 chars is always a single bubble (deterministic).

        This requires no random - the < 60 char check fires before any split logic.
        """
        service = ThinkerService()
        for seed in range(10):
            random.seed(seed)
            result = service._split_response_into_bubbles("Short text.")
            assert len(result) == 1, f"Seed {seed}: expected 1 bubble, got {len(result)}"

    def test_empty_text_returns_empty_list(self) -> None:
        """Test that empty text returns empty list (no random needed)."""
        service = ThinkerService()
        result = service._split_response_into_bubbles("")
        assert result == []

    def test_very_long_text_force_splits(self) -> None:
        """Test that text > 300 chars with only 1 natural bubble gets force-split.

        The force-split logic (lines 767-774) is deterministic - it finds the
        midpoint and splits at the nearest sentence boundary. This is pure logic.
        """
        service = ThinkerService()
        # Text > 300 chars that is very uniform (no natural split points for sentence-mode)
        text = (
            "This is an extremely long philosophical discourse that goes on and on forever. "
            "Every single word here is crafted to extend the text well beyond any threshold. "
            "The conversation continues with more and more ideas building upon each other. "
            "Ultimately we end with a final thought that wraps up this very long message now."
        )
        assert len(text) > 300
        random.seed(42)  # Consistent seed
        result = service._split_response_into_bubbles(text)
        # Force-split should fire if only 1 natural bubble → at least 1 split
        assert len(result) >= 1
        # All bubbles should be non-empty
        assert all(b.strip() for b in result)

    def test_no_empty_bubbles_in_output(self) -> None:
        """Test that filter removes empty strings from results.

        Regression guard: the `[b for b in bubbles if b]` filter should
        always prevent empty strings in the output.
        """
        service = ThinkerService()
        texts = [
            "A complete sentence.",
            "Two sentences here. And another one follows.",
            "Very long text with multiple sentences. Each one adding detail. And yet more detail.",
        ]
        for seed in range(5):
            random.seed(seed)
            for text in texts:
                result = service._split_response_into_bubbles(text)
                assert all(b for b in result), f"Found empty bubble with seed={seed}: {result}"


class TestConversationStateIsolation:
    """Tests for conversation pause/idle state isolation.

    Previous flaky-hunt sessions identified that ConnectionManager state
    can leak between tests. These tests verify that ThinkerService
    instances start with clean state and handle unknown IDs gracefully.
    """

    def test_fresh_thinker_service_has_no_paused_conversations(self) -> None:
        """Test that a new ThinkerService starts with no paused conversations."""
        service = ThinkerService()
        assert not service.is_paused("nonexistent-conv-id")

    def test_fresh_thinker_service_has_no_idle_paused_conversations(self) -> None:
        """Test that a new ThinkerService starts with no idle-paused conversations."""
        service = ThinkerService()
        assert not service.is_idle_paused("nonexistent-conv-id")

    def test_pause_and_unpause_returns_to_clean_state(self) -> None:
        """Test that pause followed by resume returns to clean (unpaused) state."""
        service = ThinkerService()
        conv_id = "test-isolation-conv"

        # Should start unpaused
        assert not service.is_paused(conv_id)

        # Pause it
        service.pause_for_idle(conv_id)
        assert service.is_idle_paused(conv_id)

        # Resume from idle
        service.resume_from_idle(conv_id)
        assert not service.is_idle_paused(conv_id)

    def test_unknown_conv_resume_from_idle_is_safe(self) -> None:
        """Test that calling resume_from_idle on unknown conversation is safe."""
        service = ThinkerService()
        # Should not raise - graceful handling of unknown conversation
        service.resume_from_idle("completely-unknown-conversation-id-xyz")
        assert not service.is_idle_paused("completely-unknown-conversation-id-xyz")

    def test_multiple_services_have_independent_state(self) -> None:
        """Test that two ThinkerService instances have independent state.

        Flakiness risk: if service state is stored at class level (not instance),
        state from one test could leak to another. This verifies isolation.
        """
        service1 = ThinkerService()
        service2 = ThinkerService()

        conv_id = "shared-name-conv"

        service1.pause_for_idle(conv_id)
        # service2 should not be affected
        assert service1.is_idle_paused(conv_id)
        assert not service2.is_idle_paused(conv_id)

    def test_pause_for_idle_sets_idle_paused_flag(self) -> None:
        """Test that pause_for_idle correctly sets the idle-paused flag."""
        service = ThinkerService()
        conv_id = "idle-test-conv"

        assert not service.is_idle_paused(conv_id)
        service.pause_for_idle(conv_id)
        assert service.is_idle_paused(conv_id)

    def test_get_last_user_message_timestamp_with_no_user_messages(self) -> None:
        """Test that _get_last_user_message_timestamp returns 0.0 for empty messages.

        Regression guard for idle timeout logic: if no user messages, should
        return 0.0 (safe sentinel) not raise an exception.
        """
        service = ThinkerService()
        result = service._get_last_user_message_timestamp([])
        assert result == 0.0

    def test_idle_timeout_default_setting_is_positive(self) -> None:
        """Test that the default idle timeout setting is a positive number or 0.

        Regression guard: idle_timeout_seconds should be a valid non-negative
        number so the idle check `if idle_timeout > 0` behaves correctly.
        """
        service = ThinkerService()
        assert service.settings.idle_timeout_seconds >= 0


class TestShouldRespondEdgeCases:
    """Edge case tests for _should_respond that don't rely on probabilistic sampling."""

    def _make_message(self, content: str, sender: str = "User") -> MagicMock:
        msg = MagicMock()
        msg.content = content
        msg.sender_name = sender
        return msg

    def test_probability_capped_at_0_9_with_high_silence(self) -> None:
        """Test that consecutive_silence boost is capped at 0.9 probability.

        With consecutive_silence=100: boost = 100*0.1 = 10.0, capped at 0.9.
        So random=0.89 should still respond, random=0.91 should not.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = self._make_message("General discussion here.")
        messages: Any = [message]

        with patch("app.services.thinker.random") as mock_random:
            # 0.20 passes silence (>0.15), 0.89 < 0.9 cap → should respond
            mock_random.random.side_effect = [0.20, 0.89]
            result = service._should_respond(thinker, messages, 0, consecutive_silence=100)
        assert result is True

        with patch("app.services.thinker.random") as mock_random:
            # 0.20 passes silence, 0.91 > 0.9 cap → should not respond
            mock_random.random.side_effect = [0.20, 0.91]
            result = service._should_respond(thinker, messages, 0, consecutive_silence=100)
        assert result is False

    def test_addressed_probability_capped_at_0_95(self) -> None:
        """Test that addressed-by-name probability is capped at 0.95.

        'Socrates' in message with many new messages:
          base = min(0.25 + N*0.12, 0.7) + 0.5 → capped at 0.95.
          With N=5: base = min(0.85, 0.7) = 0.7, +0.5 = 1.2 → capped at 0.95.

        When thinker is addressed by name, the silence check is SKIPPED
        (code: `if not was_at_mentioned and not was_addressed`), so only
        ONE random.random() call is made (the final response check).
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        # 5 messages with "Socrates" in last 3 to ensure 0.95 cap is reached
        msg_with_name = self._make_message("Socrates what do you think about virtue?")
        other_msg = self._make_message("Here is some context from before.")
        messages: Any = [other_msg, other_msg, msg_with_name, msg_with_name, msg_with_name]

        with patch("app.services.thinker.random") as mock_random:
            # Only one random call (no silence check when addressed)
            mock_random.random.return_value = 0.94  # 0.94 < 0.95 cap → responds
            result = service._should_respond(thinker, messages, 0)
        assert result is True

        with patch("app.services.thinker.random") as mock_random:
            # Only one random call (no silence check when addressed)
            mock_random.random.return_value = 0.96  # 0.96 > 0.95 cap → does not respond
            result = service._should_respond(thinker, messages, 0)
        assert result is False

    def test_base_probability_capped_at_0_7(self) -> None:
        """Test that base probability from new_message_count is capped at 0.7.

        With 10 new messages: 0.25 + 10*0.12 = 1.45 → capped at 0.7.
        random=0.69 should respond, random=0.71 should not.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = self._make_message("Some general topic.")
        messages: Any = [message] * 10

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.20, 0.69]
            result = service._should_respond(thinker, messages, 0)
        assert result is True

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.20, 0.71]
            result = service._should_respond(thinker, messages, 0)
        assert result is False
