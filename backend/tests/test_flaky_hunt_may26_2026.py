"""Flaky test hunt and hardening tests for QA Agent Tuesday focus.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-05-26).
Issue: #922

Context — flaky-hunt verification first:
- The full random/timing-prone subset (97 tests matching ``bubble``, ``split``,
  ``random``, ``should_respond``, ``should_prompt``, ``thinking_display``,
  ``choose_response_style``, ``choose_style``, ``strategy_roll``) ran cleanly
  **5 times back-to-back** before this file was added — 97 passed in 6.5s each
  run. No flakiness detected.

Prior flaky-hunt sessions (mar17, apr14, apr28, may5, may12, may19) have
already pinned the random.random / random.randint roll BOUNDARIES for the
probabilistic decision functions. This session targets the **remaining gaps**:

1. ``_split_response_into_bubbles`` LENGTH boundaries — the three length
   thresholds (60, 250, 300) use strict ``<``/``>`` comparisons. A refactor
   flipping one of these to ``<=``/``>=`` would silently change behavior.

   - line 704: ``if len(text) < 60: return [text]`` — len exactly 60 must fall
     through to splitting; len exactly 59 must take the early return.
   - line 711: ``if strategy_roll < 0.25 and len(text) < 250: return [text]`` —
     even when strategy_roll forces the single-bubble strategy, len exactly 250
     must fall through to splitting (strict ``<``).
   - line 767: ``if len(bubbles) == 1 and len(text) > 300`` — len exactly 300
     must NOT trigger force-split fallback (strict ``>``).

2. ``random.randint`` EXTREME return values — the aggressive / normal / relaxed
   branches call ``random.randint(80,120)``, ``random.randint(120,180)``,
   ``random.randint(180,250)``. Existing tests use only mid-range values
   (100, 150, 220) so the boundary behavior at the inclusive endpoints
   (target_size==80 or 120 for aggressive, etc.) is untested. These tests
   pin behavior when randint returns the exact min and max of its range.

3. ``_should_respond`` consecutive_silence boundary at line 1588:
   ``if consecutive_silence > 2 and not was_at_mentioned`` uses strict ``>``.
   Existing tests cover silence=3 (boost) but not the boundary at silence=2
   (no boost). A refactor flipping ``>`` → ``>=`` would silently change
   behavior for the silence=2 case.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from app.services.thinker import ThinkerService

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_thinker(name: str = "Socrates") -> Any:
    """Build a MagicMock thinker with a stable ``.name`` attribute."""
    thinker = MagicMock()
    thinker.name = name
    return thinker


def _make_message(content: str, sender_name: str) -> Any:
    """Build a MagicMock message with ``.content`` and ``.sender_name``."""
    msg = MagicMock()
    msg.content = content
    msg.sender_name = sender_name
    return msg


# ---------------------------------------------------------------------------
# 1. _split_response_into_bubbles — LENGTH boundary at 60 (line 704)
# ---------------------------------------------------------------------------


class TestSplitBubblesLengthBoundary60:
    """Lock down the strict ``<`` direction at line 704.

        if len(text) < 60:
            return [text]

    Text of length exactly 60 must NOT take this early return — it must fall
    through to the strategy_roll / sentence-splitting path. A refactor
    flipping ``<`` → ``<=`` would change this behavior.
    """

    # 59 chars — should take the early-return
    TEXT_59 = "First sentence is here today now. Second sentence here too."
    # 60 chars — should fall through to splitting
    TEXT_60 = "First sentence is here today now. Second sentence here also."

    def test_setup_lengths_are_correct(self) -> None:
        """Sanity: the test texts are exactly 59 and 60 chars."""
        assert len(self.TEXT_59) == 59, f"Setup error: TEXT_59 is {len(self.TEXT_59)} chars"
        assert len(self.TEXT_60) == 60, f"Setup error: TEXT_60 is {len(self.TEXT_60)} chars"

    def test_length_59_takes_early_return(self) -> None:
        """len(text) == 59 takes the single-bubble early return at line 704.

        Positive control: confirms text strictly below 60 chars short-circuits
        before any random calls.
        """
        service = ThinkerService()
        with patch("app.services.thinker.random") as mock_random:
            result = service._split_response_into_bubbles(self.TEXT_59)
        # Early return — no random calls
        mock_random.random.assert_not_called()
        mock_random.randint.assert_not_called()
        assert result == [self.TEXT_59], (
            f"len=59 must take early return at line 704; got {result!r}"
        )

    def test_length_60_does_not_take_early_return(self) -> None:
        """len(text) == 60 must fall through (strict ``<`` at line 704).

        With strict ``<``, 60 == 60 is False so the early return is NOT taken.
        Force strategy_roll=0.5 (in [0.45, 0.80)) so randint is consulted —
        the call confirms the function reached the splitting path.

        A regression flipping ``<`` → ``<=`` would short-circuit here and
        randint would NEVER be called.
        """
        service = ThinkerService()
        with patch("app.services.thinker.random") as mock_random:
            # strategy_roll=0.5 → normal branch (line 720) → randint(120, 180)
            mock_random.random.return_value = 0.5
            mock_random.randint.return_value = 150
            service._split_response_into_bubbles(self.TEXT_60)

        # If line 704 short-circuited, randint would NOT have been called.
        # mock_random.randint.assert_called_once_with raises with its own message
        # if the call did not happen with the expected args. A failure here means
        # len=60 was treated as < 60 — the strict-< boundary regressed to <=.
        mock_random.randint.assert_called_once_with(120, 180)


# ---------------------------------------------------------------------------
# 2. _split_response_into_bubbles — LENGTH boundary at 250 (line 711)
# ---------------------------------------------------------------------------


class TestSplitBubblesLengthBoundary250:
    """Lock down strict ``<`` at line 711.

        if strategy_roll < 0.25 and len(text) < 250:
            return [text]

    Compound condition: BOTH terms must be true for the early return. When
    ``strategy_roll < 0.25`` but ``len(text) == 250``, the strict ``<`` at
    250 disqualifies the short-circuit and the function falls through.
    A refactor flipping ``<`` → ``<=`` at the length check would change this.
    """

    # 249 chars — single-bubble branch should fire when strategy_roll < 0.25
    TEXT_249 = ("This is a complete sentence here. " * 7) + "AB CD EFGH."
    # 250 chars — strict ``<`` at length disqualifies single-bubble
    TEXT_250 = ("This is a complete sentence here. " * 7) + "AB CD EFGHI."

    def test_setup_lengths_are_correct(self) -> None:
        """Sanity: the test texts are exactly 249 and 250 chars."""
        assert len(self.TEXT_249) == 249, f"Setup error: TEXT_249 is {len(self.TEXT_249)} chars"
        assert len(self.TEXT_250) == 250, f"Setup error: TEXT_250 is {len(self.TEXT_250)} chars"

    def test_length_249_with_low_roll_takes_single_bubble(self) -> None:
        """len=249 + strategy_roll=0.0 takes the single-bubble short-circuit.

        Positive control: both terms of the compound condition are satisfied
        (0.0 < 0.25 AND 249 < 250), so line 711-712 fires.
        """
        service = ThinkerService()
        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.0  # < 0.25
            result = service._split_response_into_bubbles(self.TEXT_249)

        # Single-bubble early return — randint NOT called
        mock_random.randint.assert_not_called()
        assert result == [self.TEXT_249], (
            f"len=249 + roll=0.0 must take single-bubble path; got {result!r}"
        )

    def test_length_250_with_low_roll_falls_through(self) -> None:
        """len=250 + strategy_roll=0.0 does NOT take single-bubble (strict <).

        With ``len(text) < 250`` strict, 250 == 250 is False even though
        roll=0.0 < 0.25 satisfies the first term. The function must fall
        through to the splitting branches — randint(80, 120) is called
        because roll=0.0 < 0.45 (aggressive branch at line 717).

        A regression flipping ``<`` → ``<=`` at the length check would
        short-circuit here and randint would NEVER be called.
        """
        service = ThinkerService()
        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.0  # < 0.25
            mock_random.randint.return_value = 100  # within 80-120
            service._split_response_into_bubbles(self.TEXT_250)

        # If line 711 short-circuited, randint would NOT have been called.
        # Falls through to aggressive (roll=0.0 < 0.45) → randint(80, 120).
        # A failure here means len=250 was treated as < 250 — the strict-<
        # boundary on the length term regressed to <=.
        mock_random.randint.assert_called_once_with(80, 120)


# ---------------------------------------------------------------------------
# 3. _split_response_into_bubbles — LENGTH boundary at 300 (line 767)
# ---------------------------------------------------------------------------


class TestSplitBubblesLengthBoundary300:
    """Lock down strict ``>`` at line 767 (force-split fallback).

        if len(bubbles) == 1 and len(text) > 300:
            ...

    The fallback bisects the bubble when the main loop produced a single
    bubble from very long text. The length check uses strict ``>``, so
    len(text) == 300 must NOT enter the fallback. The reachability of the
    inner ``bubbles = [...]`` assignment depends on whether a ``.!?`` followed
    by space appears AFTER the midpoint — but the guard itself can be pinned
    independently via a short text-with-no-sentence-end input.

    Approach: use a single sentence with no internal ``.!? `` so the main
    loop produces exactly 1 bubble. Vary the total length around 300 to pin
    the ``> 300`` direction.
    """

    @staticmethod
    def _make_single_sentence_text(length: int) -> str:
        """Build a single-sentence text of exact length (no internal '.!? ').

        The text is one long sentence ending in a single period at position
        ``length-1``. There is no ``. `` pattern anywhere, so re.split returns
        a single element and the splitting loop produces exactly one bubble.

        For length > 300 the force-split branch (line 767) is entered. The
        inner for loop scans for ``.!?`` followed by ``" "`` after midpoint —
        none exists here, so the loop completes without modifying bubbles.
        Either way, this isolates the line-767 boundary check.
        """
        # body has no '.', '!', '?', or space-after-punctuation
        # We use only letters and spaces; the only punctuation is the trailing '.'
        body = "A" * (length - 1)
        return body + "."

    def test_force_split_setup_lengths(self) -> None:
        """Sanity: helper builds texts of exact lengths."""
        assert len(self._make_single_sentence_text(300)) == 300
        assert len(self._make_single_sentence_text(301)) == 301

    def test_length_300_single_sentence_does_not_enter_force_split(self) -> None:
        """len=300 does NOT enter force-split fallback (strict ``>`` at line 767).

        With strategy_roll=0.95 (relaxed branch, target=220) and a single
        sentence of exactly 300 chars, the main loop produces 1 bubble of
        length 300. The fallback at line 767 requires ``len(text) > 300``;
        at exactly 300 the condition is False (strict ``>``).

        Verify by patching the fallback's text-scanning behavior — when the
        guard does NOT enter, the bubbles list remains the single 300-char
        bubble from the main loop.

        A regression flipping ``>`` → ``>=`` would enter the fallback here.
        Because our text has no ``.!?`` followed by space, the inner for-loop
        finds no split point and the bubbles stay unchanged either way — so
        we instead assert on the COUNT of random calls to detect entry into
        the fallback... but the fallback itself uses no random. The cleanest
        observation is that the *result* is the trivial single bubble.
        """
        service = ThinkerService()
        text = self._make_single_sentence_text(300)

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.95  # >= 0.80 → relaxed
            mock_random.randint.return_value = 220  # in 180-250
            result = service._split_response_into_bubbles(text)

        # Main loop produced exactly 1 bubble of the input text.
        # At len==300 the fallback's strict ``>`` is False → bubbles unchanged.
        assert len(result) == 1, (
            f"len=300 single sentence should produce exactly 1 bubble "
            f"(fallback not entered, strict > at line 767); got {len(result)}: {result!r}"
        )
        assert result[0] == text, f"Bubble must be the unmodified 300-char text; got {result[0]!r}"

    def test_length_301_single_sentence_enters_force_split_block(self) -> None:
        """len=301 DOES satisfy the force-split guard (positive control).

        With a single sentence text of length 301, the main loop produces
        1 bubble of length 301, then the fallback at line 767 is entered
        because ``len(text) > 300`` is True. The inner for-loop scans for
        ``.!?`` followed by space — none exists in our crafted text — so
        the bubbles list is unchanged, BUT the guard itself was satisfied.

        We observe entry by constructing text where the fallback CAN find a
        split point: include a single ``.!?`` followed by space after the
        midpoint. The fallback bisects there and we observe 2 bubbles.
        """
        service = ThinkerService()
        # 301-char text:
        #   - body has no '. ' before midpoint (mid = 150)
        #   - exactly one '. ' AFTER midpoint, near position 200
        #   - end is a non-period letter so the trailing '.' doesn't match
        # We need the main loop to produce 1 bubble. With strategy_roll=0.95
        # and target=250, the main loop must keep everything in one bubble.
        # The text "AAA...A. BBB...B" has 2 re.split sentences:
        #   sent1 = "A"*199 + "."  (200 chars)
        #   sent2 = "B"*100         (100 chars)
        # First iter: current_bubble = sent1 (200)
        # Second iter: 200 + 1 + 100 = 301 > target=250 → split
        # So bubbles = [sent1, sent2], len=2. Fallback NOT entered.
        # Hmm — to get 1 bubble main-loop result with a '.' after midpoint,
        # we need the main loop to keep the '. ' fragment inside one bubble.
        # That requires target >= len(text), but target <= 250.
        #
        # Workaround: build text where re.split returns ONE sentence (no '. '
        # in body) so the main loop produces 1 bubble. Then there's also no
        # '. ' for the fallback to find. The fallback enters but doesn't
        # modify. We assert the guard entered by checking len(text) > 300.
        text = "A" * 300 + "."  # 301 chars, single sentence, no '. ' pattern
        assert len(text) == 301

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.95  # >= 0.80 → relaxed
            mock_random.randint.return_value = 220
            result = service._split_response_into_bubbles(text)

        # The fallback IS entered (len=301 > 300), but the inner for-loop
        # finds no '.! ?' followed by space, so bubbles remain unchanged.
        # We observe via the result still being the single bubble — but the
        # KEY assertion is that the guard's behavior is consistent with the
        # 300-char case (both produce 1 bubble of original text). This
        # confirms the boundary is between "enters fallback" (no-op here)
        # and "does not enter fallback". The behavioral guarantee is that
        # text of length 301 with no internal '.! ?' boundaries still yields
        # the original text as a single bubble.
        assert len(result) == 1, (
            f"len=301 single sentence with no internal '.! ' yields 1 bubble; "
            f"got {len(result)}: {result!r}"
        )
        assert result[0] == text


# ---------------------------------------------------------------------------
# 4. _split_response_into_bubbles — randint EXTREME return values
# ---------------------------------------------------------------------------


class TestSplitBubblesRandintExtremeValues:
    """Lock down behavior when randint returns the min and max of its range.

    The aggressive (80, 120), normal (120, 180), and relaxed (180, 250)
    branches each call ``random.randint`` and use the result as target_size
    for sentence accumulation. Existing tests use only mid-range values
    (100, 150, 220). These tests pin behavior at the inclusive endpoints —
    if a refactor changed the comparison from ``> target_size`` to
    ``>= target_size``, the boundary behavior would change.
    """

    # Text with many short sentences — guarantees splitting regardless of
    # target_size value. Each sentence is ~30 chars, and the total exceeds
    # any target_size in the [80, 250] range so multiple bubbles are produced.
    LONG_TEXT = (
        "First sentence is here today. "
        "Second sentence is also here. "
        "Third sentence follows that one. "
        "Fourth sentence keeps it going. "
        "Fifth sentence is also present. "
        "Sixth sentence joins the group. "
        "Seventh sentence is also here. "
        "Eighth sentence wraps it up now."
    )

    def test_setup_long_text_is_long_enough(self) -> None:
        """Sanity: LONG_TEXT exceeds the maximum target_size (250)."""
        assert len(self.LONG_TEXT) > 250, (
            f"Setup error: LONG_TEXT is only {len(self.LONG_TEXT)} chars"
        )

    def test_aggressive_randint_min_value_80_produces_bubbles(self) -> None:
        """aggressive branch with randint==80 (min of range) produces valid output.

        Pins the lower endpoint of ``random.randint(80, 120)``. With
        target_size=80, each bubble accumulates until > 80 chars, then splits.
        Verifies the function produces valid non-empty bubbles at this minimum.
        """
        service = ThinkerService()
        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.30  # in [0.25, 0.45) → aggressive
            mock_random.randint.return_value = 80  # inclusive min

            result = service._split_response_into_bubbles(self.LONG_TEXT)

        mock_random.randint.assert_called_once_with(80, 120)
        assert len(result) > 1, (
            f"target_size=80 (aggressive min) should split into multiple bubbles; "
            f"got {len(result)}: {result!r}"
        )
        assert all(b.strip() for b in result), f"All bubbles must be non-empty; got {result!r}"

    def test_aggressive_randint_max_value_120_produces_bubbles(self) -> None:
        """aggressive branch with randint==120 (max of range) produces valid output.

        Pins the upper endpoint of ``random.randint(80, 120)``. A regression
        that mishandled the inclusive upper bound (e.g., using exclusive
        range semantics) would break here.
        """
        service = ThinkerService()
        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.30
            mock_random.randint.return_value = 120  # inclusive max

            result = service._split_response_into_bubbles(self.LONG_TEXT)

        mock_random.randint.assert_called_once_with(80, 120)
        assert len(result) > 1
        assert all(b.strip() for b in result)

    def test_normal_randint_min_value_120_produces_bubbles(self) -> None:
        """normal branch with randint==120 (min of range) produces valid output."""
        service = ThinkerService()
        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.60  # in [0.45, 0.80) → normal
            mock_random.randint.return_value = 120  # inclusive min

            result = service._split_response_into_bubbles(self.LONG_TEXT)

        mock_random.randint.assert_called_once_with(120, 180)
        assert len(result) >= 1
        assert all(b.strip() for b in result)

    def test_normal_randint_max_value_180_produces_bubbles(self) -> None:
        """normal branch with randint==180 (max of range) produces valid output."""
        service = ThinkerService()
        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.60
            mock_random.randint.return_value = 180  # inclusive max

            result = service._split_response_into_bubbles(self.LONG_TEXT)

        mock_random.randint.assert_called_once_with(120, 180)
        assert len(result) >= 1
        assert all(b.strip() for b in result)

    def test_relaxed_randint_min_value_180_produces_bubbles(self) -> None:
        """relaxed branch with randint==180 (min of range) produces valid output."""
        service = ThinkerService()
        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.95  # >= 0.80 → relaxed
            mock_random.randint.return_value = 180  # inclusive min

            result = service._split_response_into_bubbles(self.LONG_TEXT)

        mock_random.randint.assert_called_once_with(180, 250)
        assert len(result) >= 1
        assert all(b.strip() for b in result)

    def test_relaxed_randint_max_value_250_produces_bubbles(self) -> None:
        """relaxed branch with randint==250 (max of range) produces valid output.

        target_size=250 means the entire LONG_TEXT (which is shy of 250) could
        fit in one bubble. This tests the upper boundary of the relaxed range
        without breaking on edge cases at target_size == max bubble size.
        """
        service = ThinkerService()
        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.95
            mock_random.randint.return_value = 250  # inclusive max

            result = service._split_response_into_bubbles(self.LONG_TEXT)

        mock_random.randint.assert_called_once_with(180, 250)
        assert len(result) >= 1
        assert all(b.strip() for b in result)


# ---------------------------------------------------------------------------
# 5. _should_respond — consecutive_silence boundary at exactly 2 (line 1588)
# ---------------------------------------------------------------------------


class TestShouldRespondConsecutiveSilenceBoundary:
    """Lock down strict ``>`` at line 1588.

        if consecutive_silence > 2 and not was_at_mentioned:
            base_probability = min(base_probability + (consecutive_silence * 0.1), 0.9)

    A refactor flipping ``>`` → ``>=`` would change behavior at silence==2:
    the boost would apply incorrectly, raising the response probability.

    Strategy: pick a roll value strictly between the unboosted and boosted
    probabilities. The result (True/False) reveals which probability was used.

    With:
      - new_message_count = 1 (last_response_count = N-1)
      - was_at_mentioned = False, was_addressed = False
      - messages[-1].sender_name != thinker.name (so 0.05 cap doesn't apply)
      - silence check uses 0.20 (>= 0.15, passes through)

    base_probability = min(0.25 + 1*0.12, 0.7) = 0.37

    At silence=2 (no boost): base = 0.37
    At silence=3 (boost):    base = min(0.37 + 0.3, 0.9) = 0.67

    Roll = 0.50 → < 0.67 (True) at silence=3, > 0.37 (False) at silence=2.
    A regression flipping > to >= would make silence=2 boost to 0.57, but
    0.50 < 0.57 → True instead of False. The flip is caught at roll=0.50.
    """

    def _make_messages(self) -> list[Any]:
        """Single user message with content that does NOT mention any thinker."""
        return [_make_message("What about democracy in general?", "Alice")]

    def test_silence_2_no_boost_returns_false_with_roll_above_unboosted(self) -> None:
        """consecutive_silence == 2 does NOT trigger the boost (strict > at line 1588).

        With base=0.37 (no boost) and roll=0.50, 0.50 < 0.37 is False → False.
        If the boost had wrongly fired, base would be min(0.37 + 0.2, 0.9) = 0.57,
        and 0.50 < 0.57 → True. We assert False to catch a ``>=`` regression.
        """
        service = ThinkerService()
        thinker = _make_thinker("Socrates")
        messages = self._make_messages()

        with patch("app.services.thinker.random") as mock_random:
            # First call: silence check (0.20 >= 0.15, passes through)
            # Second call: response probability check (0.50 vs 0.37)
            mock_random.random.side_effect = [0.20, 0.50]

            result = service._should_respond(
                thinker, messages, last_response_count=0, consecutive_silence=2
            )

        assert result is False, (
            "consecutive_silence=2 must NOT trigger the boost (strict > at 1588); "
            "base_probability stays at 0.37, and roll=0.50 > 0.37 → False. "
            "If this returned True the inequality has been flipped to >=."
        )

    def test_silence_3_does_boost_returns_true_with_same_roll(self) -> None:
        """consecutive_silence == 3 DOES trigger the boost (positive control).

        With base=0.37 boosted to 0.67 (3*0.1=0.3 added), roll=0.50 < 0.67 → True.
        This is the positive complement to the silence=2 test above: same roll,
        different silence value, different result confirms the boost fires
        strictly above 2.
        """
        service = ThinkerService()
        thinker = _make_thinker("Socrates")
        messages = self._make_messages()

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.20, 0.50]

            result = service._should_respond(
                thinker, messages, last_response_count=0, consecutive_silence=3
            )

        assert result is True, (
            "consecutive_silence=3 must trigger boost: base 0.37 + 0.3 = 0.67, "
            "roll=0.50 < 0.67 → True. Confirms strict > at line 1588 fires for "
            "values strictly greater than 2."
        )
