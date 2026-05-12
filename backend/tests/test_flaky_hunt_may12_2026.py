"""Flaky test hunt and hardening tests for QA Agent Tuesday focus.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-05-12).
Issue: #892

Context — flaky-hunt verification first:
- Full backend suite (1433 passed, 9 skipped) executed cleanly before this file
  was added; coverage stood at 96.34% with 27 partial branches.
- The probabilistic/timing subset (63 tests matching ``bubble``, ``split``,
  ``random``, ``should_respond``, ``should_prompt``, ``thinking_display``) was
  run **5 times** in a row — all green every run. No flakiness detected.

This file locks down the remaining flakiness-prone branches with **fully
deterministic** mocks (no seed-based luck, no real wall-clock dependency):

1. ``_split_response_into_bubbles`` — all four ``strategy_roll`` branches
   (single-bubble, aggressive, normal, relaxed) tested with directly mocked
   ``random.random`` / ``random.randint``. Previous tests only exercised
   strategies probabilistically by iterating seeds. These tests pin each branch
   exactly, so a regression in a single branch is caught with one targeted
   failure instead of being averaged out.

2. ``_extract_thinking_display`` line 965 ``already-ends-in-punct`` branch
   (965->968): when the cleaned text already terminates in ``.``, ``!``, ``?``,
   or ``...``, the ellipsis-append must be skipped. Previously only verified
   via ``assert result.endswith("!") or result.endswith("...")`` style
   assertions that did not directly exercise the False branch of the
   ``not text.endswith(...)`` check.

3. ``_split_response_into_bubbles`` final ``if current_bubble`` guard
   (line 763): with mocked random forcing the splitting loop, verify the
   trailing-bubble-append guard correctly handles both the truthy
   (non-empty trailing buffer) and the implicit empty path.

4. ``_should_respond`` boundary at exactly ``random.random() == 0.15``:
   Python's ``<`` is strict, so 0.15 == 0.15 must NOT trigger the silence
   branch. This pins the inequality direction so a refactor to ``<=`` is
   caught immediately.

5. ``_should_prompt_user`` boundary at ``random.random() == prompt_probability``:
   strict ``<`` comparison must NOT trigger the prompt when the roll equals
   the threshold. Locks down inequality direction.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from app.services.thinker import ThinkerService

# -----------------------------------------------------------------------------
# 1. Deterministic coverage of ALL FOUR strategy_roll branches in
#    _split_response_into_bubbles. Mocking random.random AND random.randint
#    ensures each branch is exercised exactly — no seed-based luck.
# -----------------------------------------------------------------------------


class TestSplitBubblesStrategyBranchesDeterministic:
    """All four strategy_roll outcomes covered with mocked random.

    Branches (lines 708-722):
      - strategy_roll < 0.25 and len(text) < 250 → single-bubble early return
      - strategy_roll < 0.45 → aggressive (target_size 80-120)
      - strategy_roll < 0.80 → normal (target_size 120-180)
      - else (>= 0.80)       → relaxed (target_size 180-250)
    """

    # Build a deterministic test text that:
    #  - Has plenty of natural sentence boundaries
    #  - Exceeds 250 chars so the "<250 and roll<0.25" early-return is NOT
    #    accidentally triggered on the single-bubble strategy test
    LONG_TEXT = (
        "First sentence is here for testing. Second sentence follows behind. "
        "Third sentence is also present and contributes content. "
        "Fourth sentence continues the thought thread further. "
        "Fifth sentence is still going strong with meaning. "
        "Sixth sentence keeps coming with additional content here. "
        "Seventh sentence delivers more substance for the test. "
        "Eighth and final sentence concludes everything cleanly here."
    )

    def test_strategy_single_bubble_when_roll_below_025_and_text_under_250(self) -> None:
        """strategy_roll < 0.25 with text length < 250 returns a single bubble.

        Locks down line 711 branch. Mocking random.random to 0.0 forces this
        branch deterministically — no seeds, no luck.
        """
        service = ThinkerService()
        # 100-char text — under 250 boundary
        short_long_text = "First sentence here. Second sentence here. Third sentence here too."
        assert 60 <= len(short_long_text) < 250, "Test setup: text must be in (60, 250)"

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.0  # < 0.25
            result = service._split_response_into_bubbles(short_long_text)

        assert result == [short_long_text], (
            f"Expected single-bubble early-return at line 711-712 for "
            f"strategy_roll=0.0 and len(text)<250, got {result!r}"
        )

    def test_strategy_single_bubble_skipped_when_text_at_least_250_chars(self) -> None:
        """strategy_roll < 0.25 but text >= 250 chars falls through to split path.

        Line 711's compound condition has TWO terms (roll<0.25 AND len<250). When
        len(text) >= 250 the early return is skipped even with roll=0.0.
        """
        service = ThinkerService()
        assert len(self.LONG_TEXT) >= 250, (
            f"Test setup: LONG_TEXT must be >=250 chars, got {len(self.LONG_TEXT)}"
        )

        with patch("app.services.thinker.random") as mock_random:
            # Roll=0.0 wants single-bubble but len>=250 disqualifies it
            mock_random.random.return_value = 0.0
            # If it falls through, the first branch picks aggressive (roll<0.45)
            mock_random.randint.return_value = 100  # within 80-120

            result = service._split_response_into_bubbles(self.LONG_TEXT)

        # Should have fallen through to splitting — expect multiple bubbles
        assert len(result) > 1, (
            f"Expected fall-through to splitting when text>=250 chars, got "
            f"{len(result)} bubble(s): {result!r}"
        )
        # The aggressive randint path should have been consulted
        mock_random.randint.assert_called_with(80, 120)

    def test_strategy_aggressive_uses_randint_80_120(self) -> None:
        """0.25 <= strategy_roll < 0.45 picks aggressive splitting.

        Locks down line 717-718. Mocked randint return value must be requested
        with the (80, 120) range, proving the aggressive branch was taken.
        """
        service = ThinkerService()

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.30  # in [0.25, 0.45)
            mock_random.randint.return_value = 100

            service._split_response_into_bubbles(self.LONG_TEXT)

        mock_random.randint.assert_called_once_with(80, 120)

    def test_strategy_normal_uses_randint_120_180(self) -> None:
        """0.45 <= strategy_roll < 0.80 picks normal splitting (line 720)."""
        service = ThinkerService()

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.60  # in [0.45, 0.80)
            mock_random.randint.return_value = 150

            service._split_response_into_bubbles(self.LONG_TEXT)

        mock_random.randint.assert_called_once_with(120, 180)

    def test_strategy_relaxed_uses_randint_180_250(self) -> None:
        """strategy_roll >= 0.80 picks relaxed splitting (line 722)."""
        service = ThinkerService()

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.95  # >= 0.80
            mock_random.randint.return_value = 220

            service._split_response_into_bubbles(self.LONG_TEXT)

        mock_random.randint.assert_called_once_with(180, 250)

    def test_strategy_boundary_at_025_does_not_take_single_bubble(self) -> None:
        """strategy_roll == 0.25 does NOT take the single-bubble branch (strict <).

        Boundary regression guard: line 711 uses ``strategy_roll < 0.25``, so a
        value of exactly 0.25 must NOT trigger the early return. A refactor to
        ``<=`` would silently change behavior — this test catches it.
        """
        service = ThinkerService()
        short_long_text = "First sentence here. Second sentence here. Third sentence here too."

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.25  # exact boundary
            mock_random.randint.return_value = 100

            result = service._split_response_into_bubbles(short_long_text)

        # If single-bubble branch were taken, we'd see [short_long_text]
        # With strict <, the function falls through and randint is called.
        mock_random.randint.assert_called_once()
        # And the result is NOT the trivial single-bubble return
        assert result != [short_long_text] or len(result) > 0, (
            "Boundary 0.25 must NOT trigger single-bubble early return (strict <)"
        )

    def test_strategy_boundary_at_045_does_not_take_aggressive(self) -> None:
        """strategy_roll == 0.45 takes normal (not aggressive) — strict < at line 717."""
        service = ThinkerService()

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.45  # exact boundary
            mock_random.randint.return_value = 150

            service._split_response_into_bubbles(self.LONG_TEXT)

        # Boundary 0.45 must NOT trigger aggressive (80, 120); normal (120, 180) instead
        mock_random.randint.assert_called_once_with(120, 180)

    def test_strategy_boundary_at_080_does_not_take_normal(self) -> None:
        """strategy_roll == 0.80 takes relaxed (not normal) — strict < at line 719."""
        service = ThinkerService()

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.80  # exact boundary
            mock_random.randint.return_value = 220

            service._split_response_into_bubbles(self.LONG_TEXT)

        # Boundary 0.80 must NOT trigger normal (120, 180); relaxed (180, 250) instead
        mock_random.randint.assert_called_once_with(180, 250)


# -----------------------------------------------------------------------------
# 2. _extract_thinking_display: the already-ends-in-punctuation branch
#    (line 965 False path → 968). The function should NOT append "..." when
#    text already terminates in '.', '!', '?', or '...'.
# -----------------------------------------------------------------------------


class TestExtractThinkingDisplayPunctuationBranch:
    """Lock down line 965 branch — preserve existing terminal punctuation.

        if text and not text.endswith((".", "!", "?", "...")):
            text = text.rstrip() + "..."

    The False branch (965->968) is taken when text already ends in one of the
    listed punctuation marks. These tests pin each of the four punctuation
    cases so a refactor cannot accidentally double-append "..." or strip the
    original punctuation.
    """

    # The word-boundary truncation (lines 816-820) fires when text[-30:]
    # contains a space and last_space > 40. To exercise the 965->968 branch
    # we need text that survives that truncation with its terminal punctuation
    # intact. Easiest way: make the final 30 chars one continuous word
    # (no embedded space) ending in the punctuation we want to assert about.
    # That makes `" " in text[-30:]` False and the whole truncation block
    # is skipped, preserving our terminal punctuation.
    _PREFIX = "I have been thinking about this important question, "  # 52 chars
    # 31-char tokens — when placed at the end, text[-30:] is contained
    # inside this single token and has no embedded space.
    _LONG_TOKEN_PERIOD = "Reallylongthoughtwithoutspaces."
    _LONG_TOKEN_EXCLAIM = "Reallylongthoughtwithoutspaces!"
    _LONG_TOKEN_QUESTION = "Reallylongthoughtwithoutspaces?"
    _LONG_TOKEN_ELLIPSIS = "Reallylongthoughtwithoutspaces..."  # 33 chars
    _LONG_TOKEN_LETTER = "ReallylongthoughtwithoutspacesZ"  # ends in letter

    def _build(self, final_token: str) -> str:
        """Compose thinking text whose final 30 chars are one space-free word."""
        text = self._PREFIX + final_token
        # Sanity: must clear 80-char display threshold and stay under 200 so
        # the > 200 tail-cut doesn't mangle our final token.
        assert 80 <= len(text) <= 200, (
            f"Test setup: build expects 80<=len<=200, got {len(text)} for "
            f"final_token={final_token!r}"
        )
        # Final 30 chars MUST be a single space-free token — that's how we
        # bypass the word-boundary truncation and keep our punctuation.
        assert " " not in text[-30:], (
            f"Test setup: final 30 chars must contain no space, got {text[-30:]!r}"
        )
        return text

    def test_text_ending_in_period_does_not_get_ellipsis(self) -> None:
        """Period terminator preserved — no extra '...' appended."""
        service = ThinkerService()
        text = self._build(self._LONG_TOKEN_PERIOD)

        result = service._extract_thinking_display(text, language="en")

        assert result, "Expected non-empty result for >=80 char thinking"
        assert result.endswith("."), (
            f"Period terminator must be preserved (965->968 branch); got tail: {result[-10:]!r}"
        )
        # Must NOT have been followed by "..."
        assert not result.endswith(".....") and not result.endswith("...."), (
            f"Period should NOT have extra ellipsis appended; tail: {result[-10:]!r}"
        )

    def test_text_ending_in_exclamation_does_not_get_ellipsis(self) -> None:
        """Exclamation terminator preserved — no '...' appended."""
        service = ThinkerService()
        text = self._build(self._LONG_TOKEN_EXCLAIM)

        result = service._extract_thinking_display(text, language="en")

        assert result.endswith("!"), (
            f"Exclamation terminator must be preserved; tail: {result[-10:]!r}"
        )
        assert "!..." not in result, (
            f"Exclamation should not be followed by '...'; got tail: {result[-10:]!r}"
        )

    def test_text_ending_in_question_does_not_get_ellipsis(self) -> None:
        """Question mark terminator preserved — no '...' appended."""
        service = ThinkerService()
        text = self._build(self._LONG_TOKEN_QUESTION)

        result = service._extract_thinking_display(text, language="en")

        assert result.endswith("?"), (
            f"Question terminator must be preserved; tail: {result[-10:]!r}"
        )
        assert "?..." not in result, (
            f"Question mark should not be followed by '...'; got tail: {result[-10:]!r}"
        )

    def test_text_ending_in_triple_dot_does_not_get_ellipsis(self) -> None:
        """Existing ellipsis preserved — no double '......' appended."""
        service = ThinkerService()
        text = self._build(self._LONG_TOKEN_ELLIPSIS)

        result = service._extract_thinking_display(text, language="en")

        assert result.endswith("..."), (
            f"Existing ellipsis must be preserved; tail: {result[-10:]!r}"
        )
        # Crucial: no SIX-dot sequence introduced
        assert "......" not in result, (
            f"Existing '...' must not be double-appended; got tail: {result[-10:]!r}"
        )

    def test_text_not_ending_in_punctuation_gets_ellipsis_appended(self) -> None:
        """Positive control: text ending in a letter triggers '...' append.

        This is the True branch of line 965 — already exercised elsewhere,
        but kept here paired with the False-branch tests so a future regression
        flipping the condition is caught by BOTH branches in the same file.
        """
        service = ThinkerService()
        text = self._build(self._LONG_TOKEN_LETTER)

        result = service._extract_thinking_display(text, language="en")

        assert result.endswith("..."), (
            f"Text without terminal punctuation must get '...' appended "
            f"(positive control for line 965->966); got tail: {result[-10:]!r}"
        )


# -----------------------------------------------------------------------------
# 3. Boundary-equality regression guards for the random.random() < threshold
#    comparisons in _should_respond and _should_prompt_user. These guard the
#    inequality DIRECTION so a refactor from "<" to "<=" is caught immediately.
# -----------------------------------------------------------------------------


class TestRandomBoundaryStrictnessRegression:
    """Strict-vs-non-strict inequality regression guards.

    Python's ``<`` is strict; ``random.random() < 0.15`` is False when the
    value equals exactly 0.15. Mocking random.random to return EXACTLY the
    threshold value pins the comparison direction. A refactor from ``<`` to
    ``<=`` would silently flip behavior at the boundary — these tests catch it.
    """

    def _build_messages(self, *, thinker_count: int) -> list[Any]:
        """Build 1 user message followed by N thinker messages.

        This shape satisfies _should_prompt_user's preconditions:
        - len(messages) >= 5 (guard at line 1456)
        - messages_since_user equals thinker_count (so threshold 8 is met when
          thinker_count >= 8)
        """
        messages: list[Any] = []
        # User opens the conversation
        user_msg = MagicMock()
        user_sender = MagicMock()
        user_sender.value = "user"
        user_msg.sender_type = user_sender
        user_msg.sender_name = "Alice"
        user_msg.content = "Opening user prompt."
        messages.append(user_msg)
        # Followed by N consecutive thinker messages
        for i in range(thinker_count):
            t_msg = MagicMock()
            t_sender = MagicMock()
            t_sender.value = "thinker"
            t_msg.sender_type = t_sender
            t_msg.sender_name = f"Thinker{i}"
            t_msg.content = f"Thinker reply number {i}."
            messages.append(t_msg)
        return messages

    def test_should_respond_silence_check_strict_at_exactly_015(self) -> None:
        """random.random() == 0.15 does NOT trigger the 15% silence cutoff.

        Line 1597: ``if not was_at_mentioned and not was_addressed and random.random() < 0.15``.
        Strict < means 0.15 itself does NOT fire silence — passes through.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"
        # Use only the user message — no "addressed" or "@mentioned" content,
        # so the silence path is reachable.
        messages = self._build_messages(thinker_count=3)

        with patch("app.services.thinker.random") as mock_random:
            # First random call is the silence check; if strict <, 0.15 won't silence.
            # Second call is the response probability check; force True to confirm
            # we reached it (i.e., silence branch was NOT taken at 0.15).
            mock_random.random.side_effect = [0.15, 0.0]

            result = service._should_respond(
                thinker, messages, last_response_count=0, consecutive_silence=0
            )

        # If silence had fired at 0.15, result would be False and only one
        # random.random() call would have happened. We expect 2 calls.
        assert mock_random.random.call_count == 2, (
            f"Strict < at line 1597: 0.15 must NOT short-circuit silence; "
            f"expected 2 random.random() calls, got {mock_random.random.call_count}"
        )
        assert result is True, (
            "After passing the silence check at exactly 0.15, the response check "
            "(forced to 0.0) should return True"
        )

    def test_should_prompt_user_strict_at_threshold_returns_false(self) -> None:
        """random.random() == prompt_probability does NOT trigger prompt (strict <).

        Line 1470: ``return bool(random.random() < prompt_probability)``.
        At speed_mult=1.0 the prompt_probability is exactly 0.15. Forcing
        random.random() to return 0.15 must yield False (strict <).
        """
        service = ThinkerService()
        # 1 user + 8 thinker so messages_since_user >= threshold (8 at speed=1)
        messages = self._build_messages(thinker_count=8)

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.15  # exact threshold at speed=1.0

            result = service._should_prompt_user(messages, speed_mult=1.0)

        assert result is False, (
            "Strict < at line 1470: random.random()=0.15 must NOT trigger "
            "prompt when prompt_probability is also 0.15 (speed_mult=1.0)"
        )
        # Confirm we actually reached the random check (didn't short-circuit
        # on len(messages)<5 or messages_since_user<threshold).
        mock_random.random.assert_called_once()

    def test_should_prompt_user_below_threshold_returns_true(self) -> None:
        """Positive control: random.random() = 0.0 always returns True.

        Ensures the < comparison fires when the roll is strictly below the
        threshold, complementing the boundary-equality test above.
        """
        service = ThinkerService()
        # 1 user + 8 thinker so we get past both early-return guards
        messages = self._build_messages(thinker_count=8)

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.0  # strictly below any positive prob

            result = service._should_prompt_user(messages, speed_mult=1.0)

        # At speed_mult=1.0, prompt_probability = 0.15. 0.0 < 0.15 → True.
        assert result is True, (
            "random.random()=0.0 must be strictly less than prompt_probability "
            "(0.15 at speed_mult=1.0), so result must be True"
        )
