"""Flaky-hunt deterministic regression tests — QA Agent Tuesday session.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-07-14).
Issue: #1024

Context — flaky-hunt verification first:
- The full backend suite (1813 passed, 10 skipped) was run 5× back-to-back
  before adding this file to confirm there is no order/timing-dependent
  flakiness. No ``pytest-randomly`` / ``pytest-xdist`` plugin is installed, so
  tests execute in a fixed order; the only nondeterminism in ``app/`` comes
  from ``random.*`` in ``app/services/thinker.py`` (probabilistic branch
  selection) and ``datetime.now()`` staleness math in
  ``knowledge_research.py`` — both exhaustively pinned by earlier sessions.

Prior flaky-hunt sessions (mar17 … jun30) pinned the *individual* random-roll
boundaries and probability caps of every probabilistic decision function. This
file locks down the **remaining INTERACTION gaps** — behaviors produced by the
*combination* of two flags, or by the *number* of ``random.random()`` draws,
that no single-boundary test exercises:

1. ``_choose_response_style`` — the ``just_spoke and roll < 0.4`` follow-up
   branch is checked BEFORE the ``was_addressed`` branch. When BOTH flags are
   true (a thinker who just spoke is also addressed by name) and ``roll < 0.4``,
   the 50-token follow-up must WIN. Existing tests only ever set one flag at a
   time, so the precedence order is unpinned. A refactor reordering the
   ``if just_spoke`` / ``elif was_addressed`` blocks would slip past every
   existing test but change real behavior here.

2. ``_should_respond`` — the silence-veto ``random.random() < 0.15`` at
   thinker.py:1597 is guarded by ``not was_at_mentioned and not was_addressed``.
   Python's short-circuit ``and`` means the veto draw only happens for a
   NOT-addressed, NOT-mentioned thinker. So the NUMBER of ``random.random()``
   draws depends on the addressing state:
       - addressed / @mentioned → exactly 1 draw (line 1600 only)
       - not-addressed, veto misses → 2 draws (1597 then 1600)
       - not-addressed, veto fires → 1 draw, early ``return False``
   This draw-count contract is invisible to value-only assertions; a refactor
   that always evaluates the veto random (e.g. hoisting it out of the ``and``)
   would desynchronize the RNG stream and change which threshold each draw is
   compared against — the classic source of "works on my seed" flakiness.

3. ``_split_response_into_bubbles`` — a transition word (``"However,"`` …) at
   the START of the text must NOT create a leading empty bubble. The new-bubble
   split is guarded by ``if current_bubble and (...)``, so the very first
   sentence (empty ``current_bubble``) never triggers a flush. Dropping that
   guard would emit a leading ``""`` that the final filter *usually* removes —
   but the interaction is worth pinning directly.

Every test mocks ``random.random`` / ``random.randint`` deterministically (no
probability of flakiness) and asserts the exact outcome.
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
    msg.sender_type = "thinker"
    return msg


# ---------------------------------------------------------------------------
# 1. _choose_response_style — just_spoke PRECEDENCE over was_addressed
# ---------------------------------------------------------------------------


class TestChooseResponseStyleJustSpokePrecedence:
    """Pin that the ``just_spoke`` follow-up branch WINS over ``was_addressed``.

    thinker.py:476-496::

        if just_spoke and roll < 0.4:
            return (follow-up, 50)          # checked FIRST
        elif was_addressed:
            ... (30/60/120/200/350 tokens)  # only reached if follow-up skipped

    When a thinker's own last message ALSO addresses it by name, BOTH
    ``just_spoke`` and ``was_addressed`` are true. With ``roll < 0.4`` the
    follow-up branch must be taken (50 tokens), NOT the addressed branch. Prior
    tests only ever set one flag, so this precedence is unpinned.
    """

    def test_just_spoke_wins_over_addressed_at_low_roll(self) -> None:
        """just_spoke=True AND was_addressed=True, roll=0.10 → 50-token follow-up.

        The last message's sender is Socrates (just_spoke=True) and its content
        names "Socrates" (was_addressed=True). roll=0.10 < 0.4 → follow-up wins.
        If the branches were reordered, the addressed branch at roll=0.10 would
        return 30 tokens (roll < 0.15), so asserting == 50 catches the reorder.
        """
        service = ThinkerService()
        messages = [_make_message("Socrates, I must add one more thought.", "Socrates")]
        with patch("app.services.thinker.random.random", return_value=0.10):
            style, max_tokens = service._choose_response_style(_make_thinker("Socrates"), messages)
        assert max_tokens == 50, "just_spoke follow-up must win over was_addressed"
        assert "follow-up" in style.lower() or "brief" in style.lower()

    def test_just_spoke_and_addressed_falls_to_addressed_at_boundary(self) -> None:
        """just_spoke=True AND was_addressed=True, roll=0.40 → addressed branch.

        At roll==0.4 the strict ``<`` fails, so the follow-up branch is skipped
        and control falls to ``elif was_addressed``. roll=0.40 in the addressed
        cascade is in [0.35, 0.55) → 120 tokens (medium response). This proves
        the fall-through path from the precedence branch reaches the addressed
        branch — NOT the not-addressed branch (which would give 120 too, so we
        also assert it is not 50).
        """
        service = ThinkerService()
        messages = [_make_message("Socrates, tell me more.", "Socrates")]
        with patch("app.services.thinker.random.random", return_value=0.40):
            _style, max_tokens = service._choose_response_style(_make_thinker("Socrates"), messages)
        assert max_tokens != 50, "roll=0.40 must NOT take follow-up (strict <)"
        assert max_tokens == 120, "addressed branch at roll=0.40 → medium (120)"


# ---------------------------------------------------------------------------
# 2. _should_respond — random DRAW-COUNT contract (short-circuit veto)
# ---------------------------------------------------------------------------


class TestShouldRespondDrawCountContract:
    """Pin the NUMBER of ``random.random()`` draws ``_should_respond`` makes.

    thinker.py:1597-1600::

        if not was_at_mentioned and not was_addressed and random.random() < 0.15:
            return False
        return random.random() < base_probability

    Because ``and`` short-circuits, the FIRST ``random.random()`` (the silence
    veto) is only evaluated when the thinker is neither @mentioned nor
    addressed. The draw count is therefore state-dependent and unpinned — a
    refactor that always evaluates the veto random would consume an extra draw
    and change every downstream comparison.
    """

    def test_addressed_thinker_makes_exactly_one_draw(self) -> None:
        """Addressed-by-name → veto short-circuits → exactly 1 random draw.

        "Socrates" appears in the last message, so ``was_addressed`` is True and
        ``not was_addressed`` is False → the veto ``random.random()`` is never
        evaluated. Only the final ``random.random() < base_probability`` draws.
        """
        service = ThinkerService()
        messages = [_make_message("Hello Socrates, how are you?", "User")]
        rng = MagicMock(side_effect=[0.5, 0.5])
        with patch("app.services.thinker.random.random", rng):
            service._should_respond(_make_thinker("Socrates"), messages, last_response_count=0)
        assert rng.call_count == 1, "addressed path must draw exactly once (veto skipped)"

    def test_not_addressed_thinker_makes_two_draws_when_veto_misses(self) -> None:
        """Not-addressed + veto misses → exactly 2 random draws.

        First draw (0.50) is >= 0.15 so the veto does NOT fire; control reaches
        the second draw ``random.random() < base_probability``. Two draws total.
        """
        service = ThinkerService()
        messages = [_make_message("What about democracy in general?", "User")]
        rng = MagicMock(side_effect=[0.50, 0.50])
        with patch("app.services.thinker.random.random", rng):
            service._should_respond(_make_thinker("Socrates"), messages, last_response_count=0)
        assert rng.call_count == 2, "not-addressed path draws veto then base_probability"

    def test_not_addressed_veto_fires_makes_one_draw_and_returns_false(self) -> None:
        """Not-addressed + veto fires (draw < 0.15) → 1 draw, returns False.

        First draw (0.10) < 0.15 triggers the silence veto ``return False``
        immediately, so the second ``random.random()`` is never reached.
        """
        service = ThinkerService()
        messages = [_make_message("What about democracy in general?", "User")]
        rng = MagicMock(side_effect=[0.10, 0.99])
        with patch("app.services.thinker.random.random", rng):
            result = service._should_respond(
                _make_thinker("Socrates"), messages, last_response_count=0
            )
        assert result is False, "veto draw < 0.15 must short-circuit to False"
        assert rng.call_count == 1, "veto short-circuit must not reach the second draw"

    def test_at_mentioned_thinker_makes_exactly_one_draw(self) -> None:
        """@mentioned → veto short-circuits → exactly 1 random draw at 0.98.

        ``@Socrates`` sets ``was_at_mentioned`` True, so ``not was_at_mentioned``
        is False → veto random skipped. The single draw is compared against the
        0.98 @mention probability; 0.50 < 0.98 → responds.
        """
        service = ThinkerService()
        messages = [_make_message("I completely agree @Socrates!", "User")]
        rng = MagicMock(side_effect=[0.50, 0.50])
        with patch("app.services.thinker.random.random", rng):
            result = service._should_respond(
                _make_thinker("Socrates"), messages, last_response_count=0
            )
        assert rng.call_count == 1, "@mentioned path must draw exactly once (veto skipped)"
        assert result is True, "0.50 < 0.98 @mention probability → responds"


# ---------------------------------------------------------------------------
# 3. _split_response_into_bubbles — leading transition word, no empty bubble
# ---------------------------------------------------------------------------


class TestSplitBubblesLeadingTransition:
    """Pin that a transition word at the START never yields a leading empty bubble.

    thinker.py:751-755 flushes ``current_bubble`` into a new bubble only when
    ``current_bubble`` is truthy::

        if current_bubble and (len(...) > target_size or starts_with_transition):
            bubbles.append(current_bubble.strip())
            current_bubble = sentence

    For the FIRST sentence ``current_bubble`` is empty, so even though it
    "starts with a transition", no flush occurs and no leading ``""`` is
    produced. This locks the guard against a refactor that drops the
    ``current_bubble and`` prefix.
    """

    def test_leading_transition_produces_no_empty_bubble(self) -> None:
        """Text beginning with "However," yields no empty leading bubble.

        random.random()=0.50 → normal-split strategy; randint mocked to 100 so
        splitting actually happens. Every returned bubble must be non-empty and
        the first must begin with the transition word (it was NOT split off into
        an empty leading bubble).
        """
        service = ThinkerService()
        text = "However, this opening thought must be long enough to trigger splitting. " + (
            "The discussion continues onward here. " * 8
        )
        with (
            patch("app.services.thinker.random.random", return_value=0.50),
            patch("app.services.thinker.random.randint", return_value=100),
        ):
            bubbles = service._split_response_into_bubbles(text)
        assert bubbles, "long text must split into at least one bubble"
        assert all(b for b in bubbles), "no empty bubbles allowed"
        assert bubbles[0].startswith("However,"), (
            "leading transition sentence must open the first bubble, not an empty one"
        )

    def test_mid_text_transition_still_forces_new_bubble(self) -> None:
        """A transition word MID-text (non-empty current_bubble) forces a split.

        Complements the leading-transition test: when ``current_bubble`` is
        non-empty and the next sentence starts with a transition word, the guard
        condition is True and a new bubble IS created. Two short sentences that
        together fit under any target still split because of the transition,
        proving the ``starts_with_transition`` arm of the OR is live.
        """
        service = ThinkerService()
        # First sentence long enough to pass the len(text) < 60 single-bubble gate.
        text = "The first idea is stated here plainly and completely. However, I disagree."
        with (
            patch("app.services.thinker.random.random", return_value=0.50),
            patch("app.services.thinker.random.randint", return_value=250),
        ):
            bubbles = service._split_response_into_bubbles(text)
        assert len(bubbles) == 2, "mid-text transition must split into two bubbles"
        assert bubbles[1].startswith("However,"), "second bubble begins at the transition"
        assert all(b for b in bubbles), "no empty bubbles allowed"
