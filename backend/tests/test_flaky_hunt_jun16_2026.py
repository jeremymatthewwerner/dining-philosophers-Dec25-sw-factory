"""Flaky-hunt deterministic regression tests — QA Agent Tuesday session.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-06-16).
Issue: #967

Context — flaky-hunt verification first:
- The full backend suite (1794 passed, 10 skipped) ran clean.
- The random/timing-prone subset (380 tests matching ``flaky``, ``random``,
  ``bubble``, ``split``, ``should_respond``, ``should_prompt``,
  ``thinking_display``, ``choose_response``, ``choose_style``, ``strategy``,
  ``randint``, ``mention``, ``speed``) was run **5× back-to-back** plus under
  ``PYTHONHASHSEED`` 0/1/12345 before adding this file — 379 passed every run
  (~26s). No flakiness detected.

Prior flaky-hunt / edge-case sessions have exhaustively pinned the random-roll
BOUNDARIES of every probabilistic *decision* function:
- ``_should_respond`` (base-prob cap transition, @mention 0.98, addressed +0.5
  cap 0.95, consecutive_silence ``> 2`` boundary + 0.9 cap, the two-draw
  noise-floor/decision ordering),
- ``_choose_response_style`` (every cascading roll boundary + max_tokens),
- ``_should_prompt_user`` (threshold + probability, and the ``speed_mult**0.3``
  scaling),
- ``_split_response_into_bubbles`` strategy-roll boundaries (0.25 / 0.45 / 0.80)
  and the ``randint`` target-size ranges (80-120 / 120-180 / 180-250).

This file pins the **remaining gap**: the transition-word list in
``_split_response_into_bubbles`` (thinker.py:736-748). When a sentence *starts*
with one of these words, it is forced into a fresh bubble even if it would
otherwise fit under ``target_size``::

    transition_words = [
        "But ", "However,", "Although ", "On the other hand,", "That said,",
        "Nevertheless,", "Yet ", "Still,", "Though ", "Conversely,",
    ]
    starts_with_transition = any(sentence.startswith(tw) for tw in transition_words)

Prior sessions only ever exercised ``However,`` (test_edge_cases_apr25_2026,
test_flaky_hunt_apr28_2026, test_edge_cases_saturday_may30_2026). The other
**nine** words — and the exact casing / trailing-space of each entry — were
never guarded. A regression that dropped ``Conversely,``, lowercased ``But ``
to ``but ``, or stripped the trailing space from ``Yet `` would silently change
how thinker responses are split into chat bubbles and slip past the entire
suite.

Isolation strategy: mock ``random.random`` → 0.5 (normal-split branch, line
719) and ``random.randint`` → 500 (a target_size far larger than the test text)
so that **size never forces a split**. The transition word then becomes the
*sole* possible cause of a second bubble — fully deterministic, no seed search.
The negative controls prove this: with the same huge target_size, a neutral
leading word (``Indeed ``) and a lowercase ``but `` both stay a single bubble.
"""

from unittest.mock import patch

import pytest

from app.services.thinker import ThinkerService

# The exact list mirrored from thinker.py:736-747. Order/spelling/casing here
# is deliberate — it must match the production list character-for-character.
TRANSITION_WORDS = [
    "But ",
    "However,",
    "Although ",
    "On the other hand,",
    "That said,",
    "Nevertheless,",
    "Yet ",
    "Still,",
    "Though ",
    "Conversely,",
]

# A first sentence long enough (with the second) to clear the 60-char
# single-bubble short-circuit, but short enough that the whole text stays well
# under both the 250-char keep-single window and the 300-char force-split path —
# so neither confounds the transition-word behaviour under test.
_LEAD = "Justice is a topic worth careful and patient thought today."
_TAIL = "mercy deserves equal weight in our considered judgment."


def _two_sentence_text(transition: str) -> str:
    """Build ``<lead>. <transition><tail>`` where sentence 2 starts with the word.

    Words ending in a space (e.g. ``"But "``) need no extra separator; words
    ending in a comma (e.g. ``"However,"``) get a single space before the tail.
    """
    sep = "" if transition.endswith(" ") else " "
    return f"{_LEAD} {transition}{sep}{_TAIL}"


class TestTransitionWordBubbleSplit:
    """Pin every transition word that forces a new bubble in
    ``_split_response_into_bubbles`` (thinker.py:736-760).

    With ``random.random`` pinned to 0.5 the normal-split branch runs, and with
    ``random.randint`` pinned to 500 the running bubble never exceeds
    ``target_size`` — so the *only* thing that can produce a second bubble is the
    ``starts_with_transition`` check. Each test therefore proves the word's
    presence (and exact form) in the production list.
    """

    @pytest.mark.parametrize("transition", TRANSITION_WORDS)
    def test_transition_word_forces_new_bubble(self, transition: str) -> None:
        """Each listed transition word splits sentence 2 into its own bubble.

        Regression guard: dropping the word from the list, or changing its
        casing/trailing-space so ``startswith`` no longer matches, would merge
        the two sentences into a single bubble and fail this test.
        """
        service = ThinkerService()
        text = _two_sentence_text(transition)
        # Guards on the fixture itself so a future edit can't silently move the
        # text out of the size window we rely on.
        assert len(text) >= 60, "text must clear the 60-char short-circuit"
        assert len(text) < 250, "text must stay under the keep-single window"

        with (
            patch("app.services.thinker.random.random", return_value=0.5),
            patch("app.services.thinker.random.randint", return_value=500),
        ):
            result = service._split_response_into_bubbles(text)

        assert len(result) == 2, (
            f"Transition word {transition!r} must force a 2nd bubble even though "
            f"target_size=500 leaves room for both sentences; got {result!r}"
        )
        assert result[0].startswith("Justice"), (
            f"First bubble should be the lead sentence; got {result[0]!r}"
        )
        assert result[1].startswith(transition), (
            f"Second bubble must start with the transition word {transition!r}; got {result[1]!r}"
        )

    def test_neutral_leading_word_stays_single_bubble(self) -> None:
        """A non-transition leading word keeps both sentences in one bubble.

        Negative control: proves the splits in the parametrized tests above are
        caused by the transition word and NOT by size — with the same
        target_size=500 a neutral word (``Indeed ``) produces a single bubble.
        """
        service = ThinkerService()
        text = f"{_LEAD} Indeed {_TAIL}"
        assert len(text) < 300, "must stay under the force-split path"

        with (
            patch("app.services.thinker.random.random", return_value=0.5),
            patch("app.services.thinker.random.randint", return_value=500),
        ):
            result = service._split_response_into_bubbles(text)

        assert len(result) == 1, (
            f"Neutral leading word must NOT split (size leaves room); got {result!r}"
        )

    def test_transition_match_is_case_sensitive(self) -> None:
        """Lowercase ``but `` must NOT trigger a split — the list is case-sensitive.

        The production list stores ``"But "`` (capitalised). ``startswith`` is
        case-sensitive, so a lowercase ``but `` at a sentence start is NOT a
        transition. This pins that exact casing: if someone ``.lower()``-ed the
        comparison the two sentences would wrongly split and this test would
        fail.
        """
        service = ThinkerService()
        text = f"{_LEAD} but {_TAIL}"
        assert len(text) < 300

        with (
            patch("app.services.thinker.random.random", return_value=0.5),
            patch("app.services.thinker.random.randint", return_value=500),
        ):
            result = service._split_response_into_bubbles(text)

        assert len(result) == 1, (
            f"Lowercase 'but ' must NOT be treated as a transition word; got {result!r}"
        )
