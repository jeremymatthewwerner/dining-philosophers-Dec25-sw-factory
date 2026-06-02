"""Flaky-hunt deterministic regression tests — QA Agent Tuesday session.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-06-02).
Issue: #937

Context — flaky-hunt verification first:
- The full random/timing-prone subset (241 tests matching ``flaky``, ``random``,
  ``bubble``, ``split``, ``should_respond``, ``should_prompt``,
  ``thinking_display``, ``choose_response_style``, ``choose_style``,
  ``strategy_roll``, ``randint``) was run **5× back-to-back** before adding
  this file — 241 passed in 18s each run. No flakiness detected.

Prior flaky-hunt sessions (mar17, apr14, apr28, may5, may12, may19, may26) have
already pinned the random.random / random.randint roll BOUNDARIES for the
probabilistic decision functions and their length thresholds. This file pins
the **remaining gaps** identified in the issue analysis:

1. ``_should_respond`` base_probability cap **transition** — prior PRs pinned
   the cap behavior with N=10 (deep in cap region). The cap actually engages
   at N=4: ``0.25 + 4*0.12 = 0.73 → min(_, 0.7) = 0.7``. A regression flipping
   ``0.12`` → ``0.10`` or ``0.25`` → ``0.30`` would shift the transition but
   still pass N=10. We pin N=3 (uncapped, 0.61) and N=4 (first-capped, 0.7).

2. ``_should_respond`` two-call ``random.random()`` ordering invariant —
   the function calls ``random.random()`` TWICE in the not-addressed /
   not-@mentioned path: line 1597 for the 15% silence check, line 1600
   for the base-probability response check. A refactor that swapped these
   or collapsed them into one call would silently change behavior.

3. ``_should_respond`` consecutive_silence cap at 0.9 — silence=3 keeps
   the result below the cap (0.37 + 0.3 = 0.67). Silence=6 forces the cap
   (0.37 + 0.6 = 0.97 → 0.9). Pin both directions.

4. ``_should_respond`` was_addressed cap at 0.95 — N=1: 0.37 + 0.5 = 0.87
   (uncapped). N=2: 0.49 + 0.5 = 0.99 → capped at 0.95. Pin the transition.

5. ``is_mentioned`` boundaries — full-name match, first-name match,
   case-insensitivity, no-match (no @), wrong @mention. Used by both
   ``_should_respond`` and ``_choose_response_style``.

6. ``_split_response_into_bubbles`` transition-word at sentence-0 — the
   split guard at line 751 is ``if current_bubble and (... or
   starts_with_transition)``. The leading ``current_bubble and`` prevents
   the transition word from producing a spurious empty bubble when it
   appears at index 0. Pin this boundary.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from app.services.thinker import ThinkerService, is_mentioned

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_thinker(name: str = "Socrates") -> Any:
    """Build a MagicMock thinker with a stable ``.name`` attribute."""
    thinker = MagicMock()
    thinker.name = name
    return thinker


def _make_message(content: str, sender_name: str = "User") -> Any:
    """Build a MagicMock message with ``.content`` and ``.sender_name``."""
    msg = MagicMock()
    msg.content = content
    msg.sender_name = sender_name
    return msg


# ---------------------------------------------------------------------------
# 1. _should_respond — base_probability cap TRANSITION at N=4
# ---------------------------------------------------------------------------


class TestShouldRespondBaseProbabilityCapTransition:
    """Pin the exact N where ``min(0.25 + N*0.12, 0.7)`` engages the cap.

    Existing tests verify N=10 (deep cap region) and the strict-< response
    boundary. They do NOT pin the *transition* — a regression changing
    ``0.12`` → ``0.10`` (transition shifts to N=5) or ``0.25`` → ``0.30``
    (transition shifts to N=4 → N=3) would still pass N=10. These tests
    use the smallest N that is uncapped (N=3 → 0.61) and the smallest N
    that is capped (N=4 → 0.7) to pin the formula coefficients.

    Note: takes the not-addressed / not-@mentioned path, so TWO random.random()
    calls are made. First call passes the silence check (must be >= 0.15).
    Second call is the actual response check against base_probability.
    """

    def test_n3_base_probability_is_0_61_uncapped(self) -> None:
        """N=3 → base_probability = 0.61 (formula uncapped).

        random=0.60 < 0.61 → True (response). A regression that shifted
        the formula would change this exact boundary.
        """
        service = ThinkerService()
        thinker = _make_thinker()
        # 3 generic messages (no name mention, no @mention) → new_message_count=3
        # All from "User", so messages[-1].sender_name != thinker.name.
        messages: Any = [_make_message(f"Comment number {i}.") for i in range(3)]

        with patch("app.services.thinker.random") as mock_random:
            # First call: silence check (0.50 >= 0.15 → passes through)
            # Second call: response check (0.60 < 0.61 → True)
            mock_random.random.side_effect = [0.50, 0.60]
            result = service._should_respond(thinker, messages, last_response_count=0)

        assert result is True, (
            "N=3 → base_probability=0.61; random=0.60 < 0.61 must return True. "
            "A failure here means the formula 0.25 + N*0.12 was changed."
        )

    def test_n3_response_strict_lt_boundary(self) -> None:
        """N=3 → base_probability = 0.61; random=0.61 is NOT < 0.61 → False.

        Pins the strict ``<`` direction at the formula-computed value (not
        just at the 0.7 cap). A regression flipping ``<`` to ``<=`` would
        return True here.
        """
        service = ThinkerService()
        thinker = _make_thinker()
        messages: Any = [_make_message(f"Comment number {i}.") for i in range(3)]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.50, 0.61]
            result = service._should_respond(thinker, messages, last_response_count=0)

        assert result is False, (
            "N=3 → base_probability=0.61; random=0.61 NOT < 0.61 → must return False. "
            "Strict-< boundary at the formula-computed value."
        )

    def test_n4_base_probability_engages_cap_at_0_7(self) -> None:
        """N=4 → 0.25 + 4*0.12 = 0.73 → capped at 0.7.

        random=0.69 < 0.7 → True. If the cap was raised to 0.75, this would
        still pass. If the formula coefficient changed so N=4 became uncapped
        (e.g. 0.10 step → 0.65), random=0.69 would no longer be < base.
        """
        service = ThinkerService()
        thinker = _make_thinker()
        messages: Any = [_make_message(f"Comment number {i}.") for i in range(4)]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.50, 0.69]
            result = service._should_respond(thinker, messages, last_response_count=0)

        assert result is True, (
            "N=4 → base = min(0.73, 0.7) = 0.7; random=0.69 < 0.7 must return True. "
            "Verifies cap engages at N=4, not later."
        )

    def test_n4_cap_strict_lt_at_0_70(self) -> None:
        """N=4 → base_probability capped at 0.7; random=0.70 NOT < 0.70 → False.

        Pins the cap VALUE itself (0.7, not 0.71 or 0.69). Combined with
        N=4 cap engagement, locks the cap exactly.
        """
        service = ThinkerService()
        thinker = _make_thinker()
        messages: Any = [_make_message(f"Comment number {i}.") for i in range(4)]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.50, 0.70]
            result = service._should_respond(thinker, messages, last_response_count=0)

        assert result is False, (
            "N=4 cap at 0.7; random=0.70 NOT < 0.70 → must return False. "
            "Pins the cap VALUE (0.7) exactly."
        )


# ---------------------------------------------------------------------------
# 2. _should_respond — random.random() call ORDERING invariant
# ---------------------------------------------------------------------------


class TestShouldRespondRandomCallOrdering:
    """Lock down the two-call ordering in the not-addressed / not-@mentioned path.

    Source lines 1597 and 1600 both call ``random.random()``:
        if not was_at_mentioned and not was_addressed and random.random() < 0.15:
            return False
        return random.random() < base_probability

    A refactor that collapsed these into one call, swapped them, or added
    a third call would change observable behavior. We pin the call count
    AND the value-to-decision mapping with ``side_effect``.
    """

    def test_exactly_two_random_calls_made_in_unaddressed_path(self) -> None:
        """Two random.random() calls are made in the not-addressed path.

        Use side_effect with exactly TWO values. If only one call happens,
        the second value is never consumed (silent). If three calls happen,
        side_effect raises StopIteration. We verify the call count directly.
        """
        service = ThinkerService()
        thinker = _make_thinker()
        messages: Any = [_make_message("Generic discussion happening here.")]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.50, 0.30]
            service._should_respond(thinker, messages, last_response_count=0)

        assert mock_random.random.call_count == 2, (
            f"Expected exactly 2 random.random() calls in not-addressed path, "
            f"got {mock_random.random.call_count}. A refactor collapsing or "
            f"adding calls would silently change response probability."
        )

    def test_first_call_is_silence_check_second_is_response(self) -> None:
        """First random call is silence-check (< 0.15), second is response-check.

        Set side_effect=[0.14, 0.99]: first triggers silence early-return.
        The second value (0.99) is NOT consumed because we return early.
        Verify by checking only 1 call was made — a swapped order would
        make 2 calls (silence-check with 0.99 passes, then 0.14 < base).
        """
        service = ThinkerService()
        thinker = _make_thinker()
        messages: Any = [_make_message("Generic discussion happening here.")]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.14, 0.99]
            result = service._should_respond(thinker, messages, last_response_count=0)

        assert result is False, "0.14 < 0.15 must trigger silence early-return"
        assert mock_random.random.call_count == 1, (
            f"Silence early-return must short-circuit before the response call. "
            f"Expected 1 call, got {mock_random.random.call_count}. "
            f"A swapped call order would make 2 calls here."
        )


# ---------------------------------------------------------------------------
# 3. _should_respond — consecutive_silence cap TRANSITION at 0.9
# ---------------------------------------------------------------------------


class TestShouldRespondConsecutiveSilenceCap:
    """Pin the silence-boost cap at 0.9.

    Line 1589: ``base_probability = min(base_probability + (consecutive_silence
    * 0.1), 0.9)``. With N=1 (base=0.37):
      - silence=3:  0.37 + 0.3  = 0.67  → uncapped
      - silence=5:  0.37 + 0.5  = 0.87  → uncapped (just under cap)
      - silence=6:  0.37 + 0.6  = 0.97  → capped at 0.9

    Note: line 1588 has strict ``>``, so silence=2 is NOT boosted; that
    boundary is pinned in test_flaky_hunt_may26_2026.py. Here we pin the
    UPPER cap, not the entry threshold.
    """

    def test_silence_3_gives_uncapped_0_67(self) -> None:
        """N=1, silence=3 → base = 0.37 + 0.3 = 0.67 (uncapped).

        random=0.66 < 0.67 → True; random=0.67 → False (strict <).
        Two-call path: silence-check passes first.
        """
        service = ThinkerService()
        thinker = _make_thinker()
        messages: Any = [_make_message("Generic topic.")]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.50, 0.66]
            result_true = service._should_respond(
                thinker, messages, last_response_count=0, consecutive_silence=3
            )
        assert result_true is True, "0.66 < 0.67 → True"

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.50, 0.67]
            result_false = service._should_respond(
                thinker, messages, last_response_count=0, consecutive_silence=3
            )
        assert result_false is False, (
            "N=1 silence=3 base=0.67 uncapped; random=0.67 NOT < 0.67 → False. "
            "Pins silence-boost formula (silence * 0.1) exactly."
        )

    def test_silence_6_engages_cap_at_0_9(self) -> None:
        """N=1, silence=6 → 0.37 + 0.6 = 0.97 → capped at 0.9.

        random=0.89 < 0.9 → True; random=0.90 → False (strict < at cap).
        If the cap was changed to 0.95 (or removed), random=0.90 would
        incorrectly return True (0.90 < 0.97).
        """
        service = ThinkerService()
        thinker = _make_thinker()
        messages: Any = [_make_message("Generic topic.")]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.50, 0.89]
            result_true = service._should_respond(
                thinker, messages, last_response_count=0, consecutive_silence=6
            )
        assert result_true is True, "silence=6 capped at 0.9; 0.89 < 0.9 → True"

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.side_effect = [0.50, 0.90]
            result_false = service._should_respond(
                thinker, messages, last_response_count=0, consecutive_silence=6
            )
        assert result_false is False, (
            "silence=6 capped at 0.9; random=0.90 NOT < 0.9 → False. "
            "Pins the cap VALUE (0.9) exactly — a regression raising the cap "
            "to 0.95 would incorrectly return True here."
        )


# ---------------------------------------------------------------------------
# 4. _should_respond — was_addressed (+0.5) cap TRANSITION at 0.95
# ---------------------------------------------------------------------------


class TestShouldRespondWasAddressedCap:
    """Pin the addressed-by-name (no @) boost cap at 0.95.

    Line 1585: ``base_probability = min(base_probability + 0.5, 0.95)``.
    With name "Socrates" in the message (but no @), the boost applies:
      - N=1: 0.37 + 0.5 = 0.87 → uncapped
      - N=2: 0.49 + 0.5 = 0.99 → capped at 0.95

    Note: was_addressed=True SKIPS the line-1597 silence check (because
    ``not was_addressed`` is False), so only ONE random.random() call
    is made for the response check.
    """

    def test_n1_addressed_no_cap_at_0_87(self) -> None:
        """N=1 with name in message → base = 0.37 + 0.5 = 0.87 (uncapped).

        Only one random call (silence check skipped because was_addressed=True).
        random=0.86 < 0.87 → True; random=0.87 → False.
        """
        service = ThinkerService()
        thinker = _make_thinker("Socrates")
        # Name "Socrates" appears in the message → was_addressed=True
        messages: Any = [_make_message("Socrates what is virtue?")]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.86
            result_true = service._should_respond(thinker, messages, last_response_count=0)
        assert result_true is True, "N=1 addressed base=0.87; 0.86 < 0.87 → True"

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.87
            mock_random.random.side_effect = None  # use return_value
            result_false = service._should_respond(thinker, messages, last_response_count=0)
        assert result_false is False, (
            "N=1 addressed base=0.87; 0.87 NOT < 0.87 → False. "
            "Pins addressed-boost (+0.5) at the uncapped value."
        )

    def test_n1_addressed_skips_silence_check(self) -> None:
        """was_addressed=True short-circuits line 1597 → only 1 random call.

        If a refactor removed the ``not was_addressed`` guard, two calls
        would be made and our return_value=0.86 would be reused — but
        silence-check at 0.86 < 0.15 is False, so the silence wouldn't fire
        and the response check would still see 0.86 → True. The observable
        change is the CALL COUNT.
        """
        service = ThinkerService()
        thinker = _make_thinker("Socrates")
        messages: Any = [_make_message("Socrates what is virtue?")]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.86
            service._should_respond(thinker, messages, last_response_count=0)

        assert mock_random.random.call_count == 1, (
            f"was_addressed=True must skip silence-check (line 1597). "
            f"Expected 1 random call, got {mock_random.random.call_count}."
        )

    def test_n2_addressed_engages_cap_at_0_95(self) -> None:
        """N=2 with name in message → 0.49 + 0.5 = 0.99 → capped at 0.95.

        random=0.94 < 0.95 → True; random=0.95 → False (strict < at cap).
        """
        service = ThinkerService()
        thinker = _make_thinker("Socrates")
        # 2 messages, name in first → was_addressed=True, N=2
        messages: Any = [
            _make_message("Socrates I have a question."),
            _make_message("Following up on that point."),
        ]

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.94
            result_true = service._should_respond(thinker, messages, last_response_count=0)
        assert result_true is True, "N=2 addressed capped at 0.95; 0.94 < 0.95 → True"

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.95
            result_false = service._should_respond(thinker, messages, last_response_count=0)
        assert result_false is False, (
            "N=2 addressed capped at 0.95; 0.95 NOT < 0.95 → False. "
            "Pins the addressed-boost cap VALUE (0.95) exactly."
        )


# ---------------------------------------------------------------------------
# 5. is_mentioned — boundary cases
# ---------------------------------------------------------------------------


class TestIsMentionedBoundaries:
    """Pin boundary behavior of ``is_mentioned``.

    Used by both ``_should_respond`` (line 1571) and ``_choose_response_style``
    (line 465). A regression here would silently change WHEN thinkers
    perceive themselves as @mentioned, which cascades into base_probability
    (0.98 vs formula) and follow-up routing.
    """

    def test_full_name_at_mention_matches(self) -> None:
        """``@Socrates`` matches thinker named ``Socrates``."""
        assert is_mentioned("Hey @Socrates what say you?", "Socrates") is True

    def test_first_name_at_mention_matches_multi_word(self) -> None:
        """``@Marie`` matches thinker named ``Marie Curie`` (first-name path)."""
        assert is_mentioned("Hey @Marie what about radiation?", "Marie Curie") is True

    def test_full_quoted_at_mention_matches_multi_word(self) -> None:
        """``@"Marie Curie"`` matches thinker named ``Marie Curie`` (quoted path).

        The extract_mentions function has a separate quoted_pattern that
        captures the full name including spaces.
        """
        assert is_mentioned('@"Marie Curie" what about radiation?', "Marie Curie") is True

    def test_case_insensitive_match(self) -> None:
        """``@socrates`` matches ``Socrates`` (lowercased comparison)."""
        assert is_mentioned("Hey @socrates over here", "Socrates") is True

    def test_no_at_symbol_does_not_match(self) -> None:
        """Mention of the name WITHOUT ``@`` returns False.

        ``_should_respond`` distinguishes ``was_at_mentioned`` (@ prefix,
        base=0.98) from ``was_addressed`` (name appears, base=base+0.5).
        is_mentioned must return False for non-@ name appearances.
        """
        assert is_mentioned("Socrates is wise", "Socrates") is False

    def test_wrong_at_mention_does_not_match(self) -> None:
        """``@Plato`` does NOT match thinker named ``Socrates``."""
        assert is_mentioned("Hey @Plato what say you?", "Socrates") is False

    def test_empty_text_does_not_match(self) -> None:
        """Empty text → no mentions → False."""
        assert is_mentioned("", "Socrates") is False


# ---------------------------------------------------------------------------
# 6. _split_response_into_bubbles — transition word at sentence index 0
# ---------------------------------------------------------------------------


class TestSplitBubblesTransitionAtIndexZero:
    """Pin the ``current_bubble and ...`` guard at line 751.

    The split guard is::

        if current_bubble and (
            len(current_bubble) + len(sentence) > target_size or starts_with_transition
        ):
            bubbles.append(current_bubble.strip())
            current_bubble = sentence

    The leading ``current_bubble and`` term ensures the FIRST sentence
    (when current_bubble is empty) does NOT trigger a split — preventing
    a spurious empty bubble at the start.

    A regression flipping ``and`` to ``or`` would mean a leading transition
    word like "But ..." causes an empty bubble to be appended on the first
    iteration, then "But ..." starts the second bubble. The empty bubble
    would be filtered out by the final ``if b`` filter, but the second
    bubble would NEVER accumulate further sentences (because each subsequent
    sentence would also trigger the split). We pin this by checking that
    "But ..." as the leading transition produces a clean first bubble
    containing both the transition sentence AND the next non-transition
    sentence (provided length is under target_size).
    """

    def test_leading_but_combines_with_next_sentence_under_target(self) -> None:
        """Text starting with ``But ...`` followed by a non-transition sentence,
        with total length under target_size, must produce a SINGLE bubble.

        If the guard regressed to ``or starts_with_transition``, the first
        iteration would split on the empty current_bubble, leaving the
        "But ..." sentence alone — and then the next iteration (no transition)
        would just append the second sentence as a separate bubble. So we
        would observe 2 bubbles instead of 1.
        """
        service = ThinkerService()
        # Text starts with "But " — transition at sentence index 0
        # Must be > 60 chars to bypass the early-return, AND we set
        # strategy_roll to fall through to the normal branch (0.5 → 120-180)
        # with target_size large enough that BOTH sentences fit in one bubble.
        text = (
            "But this is the leading sentence with a transition word starting."
            " And this is the second sentence following close behind here."
        )
        # Length is ~127 chars — fits in normal target_size 150
        assert len(text) >= 60, f"Test text must be >= 60 chars, got {len(text)}"
        assert len(text) <= 180, f"Test text must fit in normal target, got {len(text)}"

        with patch("app.services.thinker.random") as mock_random:
            # strategy_roll = 0.5 → normal branch (line 720) → randint(120, 180)
            mock_random.random.return_value = 0.5
            mock_random.randint.return_value = 180  # generous target
            result = service._split_response_into_bubbles(text)

        # With the guard ``current_bubble and ...``, sentence-0 ("But ...")
        # has current_bubble="" and is just assigned (else branch at line 757).
        # Sentence-1 fits under target_size, so it's appended. Result: 1 bubble.
        assert len(result) == 1, (
            f"Leading transition word at sentence-0 must NOT cause a split "
            f"(current_bubble is empty — the ``current_bubble and ...`` guard "
            f"short-circuits). Expected 1 bubble, got {len(result)}: {result!r}"
        )
        # The single bubble should contain BOTH sentences
        assert "But " in result[0], f"First sentence with 'But ' must be in result: {result!r}"
        assert "And " in result[0], f"Second sentence with 'And ' must be in result: {result!r}"

    def test_leading_however_combines_with_next_sentence_under_target(self) -> None:
        """Same guard but with ``However,`` transition at index 0.

        Confirms the guard short-circuits for ALL transition words, not
        just "But ". A regression would split here too.
        """
        service = ThinkerService()
        text = (
            "However, this is a careful response to the prior question here."
            " Then this second sentence adds more context in a small way."
        )
        assert 60 <= len(text) <= 180

        with patch("app.services.thinker.random") as mock_random:
            mock_random.random.return_value = 0.5
            mock_random.randint.return_value = 180
            result = service._split_response_into_bubbles(text)

        assert len(result) == 1, (
            f"Leading 'However,' transition must NOT split on empty current_bubble. "
            f"Expected 1 bubble, got {len(result)}: {result!r}"
        )
        assert result[0].startswith("However,"), (
            f"Bubble must start with the leading transition: {result[0]!r}"
        )
