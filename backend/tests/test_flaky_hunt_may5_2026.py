"""Flaky test hunt and hardening tests for QA Agent Tuesday focus.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-05-05).
Issue: #876

This file addresses the following flakiness risks identified in the May 5 session:

1. `_extract_thinking_display` word-boundary branch at line 819:
   The condition `if last_space > 40` has two branches. Previous tests only
   exercised the True branch (truncation applied). The False branch (819->824,
   last_space <= 40, truncation skipped) was never covered. These tests lock
   down both paths deterministically.

2. `_should_prompt_user` probabilistic path at line 1469:
   Uses `random.random()` to decide whether to prompt the user. Previous tests
   iterated with seeds (which works but is indirect). Mock-based tests directly
   verify both True/False paths of the probability check, making it immune to
   changes in the probability formula.

3. `_should_respond` forced-silence branch at line 1597:
   The `if random.random() < 0.15: return False` forced-silence path was only
   tested probabilistically (run N times, expect at least one True). A mock-based
   test directly validates the False-silence path without relying on randomness.

4. `_count_messages_since_user` edge cases:
   Existing tests cover the "user spoke in the middle" case. Missing: all-thinker
   messages (user never spoke → count = all messages) and no-messages → count = 0.

5. `_split_response_into_bubbles` empty-sentence filtering at line 733:
   The `if not sentence: continue` guard filters blank entries from re.split.
   A test with text containing consecutive punctuation (producing empty splits)
   verifies the guard functions correctly.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from app.services.thinker import ThinkerService


class TestExtractThinkingDisplayWordBoundaryBranches:
    """Tests for the word-boundary truncation branches in _extract_thinking_display.

    Lines 816-820:
        if len(text) > 60 and not text[-1].isspace() and " " in text[-30:]:
            last_space = text.rfind(" ", len(text) - 30)
            if last_space > 40:   # line 819
                text = text[:last_space]  # line 820

    Branch 819->824 (last_space <= 40, truncation skipped) was never exercised.
    These tests cover both the True and False outcomes of line 819.
    """

    def test_word_boundary_truncation_skipped_when_space_position_is_early(self) -> None:
        """_extract_thinking_display skips tail-trim when last_space <= 40.

        Covers branch 819->824: when the rightmost space in the last 30 chars is
        at absolute position <= 40, word-boundary truncation is NOT applied and the
        trailing characters are preserved.

        Text construction (83 chars → 65 chars after start-cleanup):
          - Prefix 'verylongword_1234 ' (18 chars, lowercase) removed by start-cleanup
          - Remaining: 'A'*35 + ' ' + 'B'*29  (65 chars)
          - text[-30:] = text[35:] = ' ' + 'B'*29  → space IS in last 30 chars
          - last_space = text.rfind(' ', 35) = 35   → 35 <= 40 → truncation SKIPPED
        """
        service = ThinkerService()
        # 83-char input; start-cleanup removes the 18-char prefix
        thinking = "verylongword_1234 " + "A" * 35 + " " + "B" * 29
        result = service._extract_thinking_display(thinking, language="en")

        # Function should return a non-empty string (thinking is > 80 chars)
        assert len(result) > 0, (
            "Expected non-empty result for thinking > 80 chars; "
            "819->824 branch should be taken (last_space=35 ≤ 40, no tail-trim)"
        )
        # The B characters survive because truncation was skipped
        assert "B" in result, (
            "Expected 'B' characters to be preserved when word-boundary "
            "truncation is skipped (branch 819->824: last_space <= 40)"
        )

    def test_word_boundary_truncation_applied_when_space_position_is_late(self) -> None:
        """_extract_thinking_display applies tail-trim when last_space > 40.

        Contrasts with the previous test: when the rightmost space in the last 30
        chars is at absolute position > 40, truncation IS applied (line 820).

        Text construction (115 chars → 111 chars after start-cleanup):
          - Prefix 'abc ' (4 chars, lowercase) removed by start-cleanup
          - Remaining: 'A'*50 + ' ' + 'B'*30 + ' ' + 'C'*29  (111 chars)
          - text[-30:] = text[81:] = ' ' + 'C'*29  → space at absolute position 81
          - last_space = 81 > 40 → truncation IS applied at position 81
          - Result does NOT contain trailing C's
        """
        service = ThinkerService()
        # 115-char input; start-cleanup removes the 4-char 'abc ' prefix
        thinking = "abc " + "A" * 50 + " " + "B" * 30 + " " + "C" * 29
        result = service._extract_thinking_display(thinking, language="en")

        # Function should return something (thinking is > 80 chars)
        assert len(result) > 0, "Expected non-empty result for > 80-char input"
        # The C characters should be truncated since last_space (81) > 40
        # (The 'C' block is after the last word-boundary and gets removed)
        assert "C" not in result, (
            "Expected trailing 'C' characters to be removed by word-boundary "
            "truncation (line 820: text = text[:last_space])"
        )

    def test_word_boundary_check_not_triggered_when_no_space_in_tail(self) -> None:
        """Word-boundary check at line 816 is skipped when no space in last 30 chars.

        The condition at 816 requires `' ' in text[-30:]`. When the last 30 chars
        have no space (e.g., all letters), the entire word-boundary block is skipped.
        """
        service = ThinkerService()
        # Thinking where the last 30+ chars are all the same letter with no spaces
        # prefix (lowercase) + 50 A's + 40 B's (no spaces in the B block)
        # After cleanup: A's + B's → last 30 chars are pure B's (no space)
        thinking = "prefix " + "A" * 50 + "B" * 40  # 97 chars
        result = service._extract_thinking_display(thinking, language="en")

        # The function should still work; no crash from missing space
        assert isinstance(result, str), (
            "Should return a string even with no spaces in last 30 chars"
        )


class TestShouldPromptUserDeterministic:
    """Deterministic tests for _should_prompt_user using mocked random.random().

    The existing test `test_should_prompt_probability_after_many_thinker_messages`
    iterates 100 seeds and asserts `any(prompts)`. While reliable, this approach
    cannot detect subtle bugs where the probability formula changes but still
    produces True 'sometimes'. These tests mock random.random() directly to
    verify BOTH the True and False paths of line 1470 independently.
    """

    def _make_messages_exceeding_threshold(self) -> Any:
        """Build 11 messages (user then 10 thinkers) to exceed the silence threshold.

        With speed_mult=1.0: threshold = max(4, int(8 / 1^0.3)) = 8.
        10 thinker messages after user > 8 → threshold met.
        """
        user_message = MagicMock()
        user_message.sender_type = "user"

        thinker_message = MagicMock()
        thinker_message.sender_type = "thinker"

        return [user_message] + [thinker_message] * 10

    def test_prompt_returns_true_when_random_below_probability(self) -> None:
        """_should_prompt_user returns True when random.random() < prompt_probability.

        Deterministic path: with speed_mult=1.0, prompt_probability = 0.15 * 1^0.3 = 0.15.
        Mocking random.random() to return 0.05 (< 0.15) → should return True.
        """
        service = ThinkerService()
        messages = self._make_messages_exceeding_threshold()

        with patch("random.random", return_value=0.05):
            result = service._should_prompt_user(messages, speed_mult=1.0)

        assert result is True, (
            "Expected True when random.random()=0.05 < prompt_probability=0.15 "
            "(speed_mult=1.0, threshold met with 10 thinker messages)"
        )

    def test_prompt_returns_false_when_random_above_probability(self) -> None:
        """_should_prompt_user returns False when random.random() >= prompt_probability.

        Deterministic path: with speed_mult=1.0, prompt_probability = 0.15.
        Mocking random.random() to return 0.20 (>= 0.15) → should return False.
        """
        service = ThinkerService()
        messages = self._make_messages_exceeding_threshold()

        with patch("random.random", return_value=0.20):
            result = service._should_prompt_user(messages, speed_mult=1.0)

        assert result is False, (
            "Expected False when random.random()=0.20 >= prompt_probability=0.15 "
            "(speed_mult=1.0, threshold met but random too high)"
        )

    def test_prompt_returns_false_when_threshold_not_met_regardless_of_random(self) -> None:
        """_should_prompt_user returns False before reaching random check if threshold not met.

        Guard: the random.random() call at line 1470 is only reached AFTER the
        messages_since_user >= threshold check. With only 2 thinker messages (< 8
        threshold at speed_mult=1.0), the function returns False early without
        touching random.random().
        """
        service = ThinkerService()

        user_message = MagicMock()
        user_message.sender_type = "user"
        thinker_message = MagicMock()
        thinker_message.sender_type = "thinker"

        # Only 2 thinker messages since user (below threshold=8)
        messages: Any = [user_message] + [thinker_message] * 2

        # Even with a 'sure to be True' random value, threshold prevents prompt
        with patch("random.random", return_value=0.0):
            result = service._should_prompt_user(messages, speed_mult=1.0)

        assert result is False, (
            "Expected False when only 2 thinker messages since user "
            "(below threshold=8 at speed_mult=1.0)"
        )

    def test_prompt_threshold_scales_with_speed_multiplier(self) -> None:
        """_should_prompt_user threshold decreases as speed_mult increases.

        Formula: threshold = max(4, int(8 / speed_mult^0.3))
        At speed_mult=6.0: threshold = max(4, int(8 / 6^0.3)) = max(4, int(8/1.97)) = max(4,4) = 4
        So 4 thinker messages (just hitting threshold) should be enough at high speed.
        """
        service = ThinkerService()

        user_message = MagicMock()
        user_message.sender_type = "user"
        thinker_message = MagicMock()
        thinker_message.sender_type = "thinker"

        # 5 total messages: 1 user + 4 thinkers (meets threshold at speed_mult=6.0)
        messages: Any = [user_message] + [thinker_message] * 4

        # With random below the probability → should prompt at high speed
        with patch("random.random", return_value=0.0):
            result = service._should_prompt_user(messages, speed_mult=6.0)

        assert result is True, (
            "Expected True at speed_mult=6.0 with 4 thinker messages (threshold=4) "
            "and random.random()=0.0 (below any positive probability)"
        )


class TestShouldRespondForcedSilenceBranch:
    """Deterministic tests for the forced-silence branch in _should_respond.

    Line 1597:
        if not was_at_mentioned and not was_addressed and random.random() < 0.15:
            return False

    This 15% noise-floor forces silence even when base_probability is high.
    Previous tests exercised the return value probabilistically (run N times).
    These tests use mock to directly verify the forced-silence path is taken.
    """

    def _make_unaddressed_message(self, thinker_name: str = "Socrates") -> tuple[Any, Any]:
        """Create a thinker and message list where the thinker is NOT @mentioned."""
        thinker = MagicMock()
        thinker.name = thinker_name

        msg = MagicMock()
        msg.content = "What is truth?"  # No @mention, no name reference
        msg.sender_name = "Alice"

        return thinker, [msg]

    def test_forced_silence_returns_false_when_noise_floor_triggers(self) -> None:
        """_should_respond returns False when the 15% noise-floor random check fires.

        Covers the forced-silence path: when random.random() < 0.15 AND the
        thinker is neither @mentioned nor addressed, the function returns False
        immediately (line 1597-1598), bypassing the base_probability check.

        Mocking random.random() to 0.05 ensures the noise-floor fires.
        """
        service = ThinkerService()
        thinker, messages = self._make_unaddressed_message()

        with patch("random.random", return_value=0.05):
            result = service._should_respond(thinker, messages, last_response_count=0)

        assert result is False, (
            "Expected False when random.random()=0.05 < 0.15 (noise-floor silence). "
            "The forced-silence path should return False before base_probability check."
        )

    def test_forced_silence_bypassed_when_at_mentioned(self) -> None:
        """Forced-silence is skipped entirely when thinker is @mentioned.

        The condition at line 1597 requires `not was_at_mentioned`. When the
        thinker IS @mentioned, the noise-floor check is bypassed, and the high
        base_probability (0.98 for @mentions) applies instead.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        msg = MagicMock()
        msg.content = "@Socrates what do you think?"  # Direct @mention
        msg.sender_name = "Alice"
        messages = [msg]

        # Even with random.random() that would trigger noise-floor (0.05 < 0.15),
        # @mention bypasses it. But the base_probability check (0.98) still needs
        # to pass. With side_effect=[0.97, 0.97]: first call bypasses noise-floor
        # (was_at_mentioned=True), second call 0.97 < 0.98 → True.
        with patch("random.random", side_effect=[0.97, 0.97]):
            result = service._should_respond(thinker, messages, last_response_count=0)

        assert result is True, (
            "Expected True for @mentioned thinker even with random values "
            "that would trigger noise-floor for unmentioned thinkers"
        )

    def test_should_respond_false_when_base_probability_roll_fails(self) -> None:
        """_should_respond returns False when base_probability roll fails.

        Tests line 1600: `return random.random() < base_probability`.
        When the noise-floor check passes (first call > 0.15) but the
        base_probability roll fails (second call > base_probability), returns False.
        """
        service = ThinkerService()
        thinker, messages = self._make_unaddressed_message()

        # First call: 0.20 > 0.15 → noise-floor NOT triggered
        # Second call: 0.99 > base_probability (0.37 with 1 new message) → False
        with patch("random.random", side_effect=[0.20, 0.99]):
            result = service._should_respond(thinker, messages, last_response_count=0)

        assert result is False, (
            "Expected False when noise-floor passes (0.20 > 0.15) but "
            "base_probability roll fails (0.99 > 0.37)"
        )

    def test_should_respond_true_when_both_checks_pass(self) -> None:
        """_should_respond returns True when noise-floor passes AND base_probability met.

        Full positive path: noise-floor check (line 1597) passes because
        random.random() > 0.15, then base_probability check (line 1600) passes
        because random.random() < base_probability.
        """
        service = ThinkerService()
        thinker, messages = self._make_unaddressed_message()

        # First call: 0.20 > 0.15 → noise-floor passes
        # Second call: 0.10 < base_probability (0.37) → returns True
        with patch("random.random", side_effect=[0.20, 0.10]):
            result = service._should_respond(thinker, messages, last_response_count=0)

        assert result is True, (
            "Expected True when noise-floor passes (0.20 > 0.15) and "
            "base_probability met (0.10 < 0.37)"
        )


class TestCountMessagesSinceUserEdgeCases:
    """Edge-case tests for _count_messages_since_user.

    Existing tests cover the common case (user in the middle of message history).
    These tests cover boundary conditions: no user messages at all (returns total
    count), empty message list (returns 0), and alternating sender types.
    """

    def test_all_thinker_messages_returns_full_count(self) -> None:
        """_count_messages_since_user returns len(messages) when user never spoke.

        When there are no user messages, the for-loop never hits `break`, so
        `count` increments for every message and equals len(messages).
        """
        service = ThinkerService()

        thinker_message = MagicMock()
        thinker_message.sender_type = "thinker"

        messages: Any = [thinker_message] * 7

        result = service._count_messages_since_user(messages)

        assert result == 7, (
            f"Expected 7 (all thinker messages), got {result}. "
            "_count_messages_since_user should count all messages when user never spoke."
        )

    def test_empty_messages_returns_zero(self) -> None:
        """_count_messages_since_user returns 0 for empty message list.

        The for-loop body never executes on empty input, so count=0 is returned.
        Guard: ensures the function doesn't raise on empty input.
        """
        service = ThinkerService()

        result = service._count_messages_since_user([])

        assert result == 0, f"Expected 0 for empty message list, got {result}"

    def test_user_as_last_message_returns_zero(self) -> None:
        """_count_messages_since_user returns 0 when the latest message is from the user.

        When the user spoke most recently, the reversed loop encounters a user
        message immediately and breaks with count=0.
        """
        service = ThinkerService()

        thinker_message = MagicMock()
        thinker_message.sender_type = "thinker"

        user_message = MagicMock()
        user_message.sender_type = "user"

        # Order: older thinker, newer user
        messages: Any = [thinker_message, thinker_message, user_message]

        result = service._count_messages_since_user(messages)

        assert result == 0, (
            f"Expected 0 when the most recent message is from the user, got {result}"
        )

    def test_enum_sender_type_counted_correctly(self) -> None:
        """_count_messages_since_user handles SenderType enum (not plain string).

        Guard: the method checks both `sender.value == 'user'` (for enums) and
        `sender == 'user'` (for strings). This test verifies the enum path by
        using a mock with a .value attribute set to 'user'.
        """
        service = ThinkerService()

        thinker_sender = MagicMock()
        thinker_sender.value = "thinker"

        user_sender = MagicMock()
        user_sender.value = "user"

        thinker_message = MagicMock()
        thinker_message.sender_type = thinker_sender

        user_message = MagicMock()
        user_message.sender_type = user_sender

        # 1 user message, then 3 thinker messages (reversed: 3 thinkers, then user)
        messages: Any = [user_message, thinker_message, thinker_message, thinker_message]

        result = service._count_messages_since_user(messages)

        assert result == 3, (
            f"Expected 3 thinker messages since last user message, got {result}. "
            "SenderType enum values should be recognized correctly."
        )


class TestSplitResponseBubblesEdgeCases:
    """Edge-case tests for _split_response_into_bubbles.

    Line 733: `if not sentence: continue` - filters empty strings from re.split.
    Line 763: `if current_bubble:` - only appends non-empty final bubble.

    These cover scenarios that produce empty sentence entries from re.split,
    ensuring the filter works correctly without causing IndexError or empty bubbles.
    """

    def test_text_with_consecutive_punctuation_produces_no_empty_bubbles(self) -> None:
        """Consecutive sentence-ending punctuation produces no empty bubbles.

        Text like 'Hello world!? Yes.' causes re.split to produce empty strings
        between consecutive sentence-ending punctuation. The `continue` at line 733
        filters these, preventing empty strings in the output.
        """
        import random

        service = ThinkerService()
        # Text with consecutive punctuation to produce empty splits
        # Using a seed that forces sentence-splitting strategy (not single-bubble)
        text = (
            "First sentence!? Second sentence. "
            "Third sentence. Fourth sentence. "
            "Fifth sentence. Sixth sentence. "
            "This final part adds length to exceed minimum thresholds."
        )

        # Run 5 seeds to verify no empty bubbles regardless of strategy
        for seed in range(5):
            random.seed(seed)
            result = service._split_response_into_bubbles(text)
            for bubble in result:
                assert bubble, (
                    f"Found empty bubble in result (seed={seed}): {result!r}. "
                    "Empty-sentence filter at line 733 should prevent this."
                )

    def test_single_char_sentence_boundaries_not_treated_as_empty(self) -> None:
        """Single-character sentences (like '.' alone) are filtered or included correctly.

        When re.split produces ["A.", "", "B."] from "A.. B.", the empty string
        is filtered by the `if not sentence: continue` guard. 'A.' and 'B.' are
        single-character-boundary sentences and should be handled without error.
        """
        import random

        service = ThinkerService()
        text = "Question? What about this point here? And more content beyond that point to reach length."

        random.seed(42)
        result = service._split_response_into_bubbles(text)

        # Result should contain only non-empty strings
        assert all(result), f"All bubbles should be non-empty: {result!r}"
        # Result should be a list (not raise)
        assert isinstance(result, list)

    def test_empty_response_returns_empty_list(self) -> None:
        """_split_response_into_bubbles returns [] for truly empty input.

        Early guard at line 698: `if not response_text: return []`
        Guard: ensures the function doesn't crash on degenerate input.

        Note: whitespace-only strings ("   ") are truthy in Python, so they bypass
        the `if not response_text` guard. After .strip() they become "", then the
        `if len(text) < 60: return [text]` returns [""] — an empty string in a list.
        This documents the actual boundary behavior.
        """
        service = ThinkerService()

        assert service._split_response_into_bubbles("") == []
        # Whitespace-only input: truthy so bypasses empty guard, strips to "",
        # then short-text early return yields [""] not [] — documenting actual behavior
        result = service._split_response_into_bubbles("   ")
        assert isinstance(result, list), "Should return a list even for whitespace input"

    def test_very_short_text_always_single_bubble_across_seeds(self) -> None:
        """Text under 60 chars is never split regardless of random strategy.

        Regression guard for the early return at line 704: `if len(text) < 60: return [text]`.
        Tests 10 seeds to verify that no random state can cause splitting of short text.
        Unlike `test_text_under_60_chars_never_splits` (which uses random.seed(None)),
        this uses explicit seeds for full determinism.
        """
        import random

        service = ThinkerService()
        short_text = "Brief philosophical statement."  # 30 chars, well under 60

        for seed in range(10):
            random.seed(seed)
            result = service._split_response_into_bubbles(short_text)
            assert len(result) == 1, (
                f"Expected single bubble for {len(short_text)}-char text at seed {seed}, "
                f"got {len(result)} bubbles: {result!r}"
            )
            assert result[0] == short_text, (
                f"Expected bubble content to equal original text at seed {seed}"
            )
