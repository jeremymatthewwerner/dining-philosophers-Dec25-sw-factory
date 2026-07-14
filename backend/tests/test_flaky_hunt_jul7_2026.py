"""Flaky-hunt deterministic regression tests — QA Agent Tuesday session.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-07-07).
Issue: #1010

Context — flaky-hunt verification first:
- The full backend suite (1813 passed, 10 skipped) was run before adding this
  file to confirm there is no order/timing-dependent flakiness. ``pytest-randomly``
  and ``pytest-xdist`` are not installed, so collection order is deterministic.

Prior flaky-hunt sessions (mar17, apr14, apr28, may5, may12, may19, may26,
jun2, jun9, jun30) have exhaustively pinned the *single-function* random-roll
boundaries and probability caps of the probabilistic decision functions in
``app/services/thinker.py``:

    _should_respond           — base formula, @mention 0.98, addressed 0.95 cap,
                                 silence 0.9 cap, self-message 0.05, silence
                                 boundary at exactly 2 vs 3, cap-override order.
    _choose_response_style    — all 5 addressed + 5 not-addressed branches,
                                 just_spoke follow-up boundary at 0.4.
    _split_response_into_bubbles — strategy_roll boundaries, randint ranges,
                                 transition words, force-split, <250 fall-through.
    _should_prompt_user       — threshold/probability speed-mult scaling,
                                 max(4,...) floor, strict-< boundary.

This file pins the **remaining gap**: the *cross-function WINDOW-SIZE
discrepancy* between ``_should_respond`` and ``_choose_response_style``.

Both functions independently decide whether a thinker was @mentioned or
addressed-by-name, but they look back over DIFFERENT numbers of recent
messages:

    _should_respond        (thinker.py:1570-1574)
        last_messages   = messages[-3:]            # <-- last THREE
        was_at_mentioned = any(is_mentioned(m.content, name) for m in last_messages)
        was_addressed    = any(name.lower() in m.content.lower() for m in last_messages)

    _choose_response_style (thinker.py:459-471)
        recent_messages  = messages[-5:]
        was_at_mentioned = any(is_mentioned(m.content, name) for m in recent_messages[-2:])
        was_addressed    = any(name.lower() in m.content.lower() for m in recent_messages[-2:]) ...

So a thinker mentioned/addressed **exactly 3 messages from the end** (index -3)
is seen as *addressed* by ``_should_respond`` (near-certain response, base
0.98 for @mention / 0.95 cap for name) but as *not addressed* by
``_choose_response_style`` (which picks from the shorter, skewed-shorter
not-addressed style distribution). The message at index -2 is inside BOTH
windows; the message at index -4 is inside NEITHER.

This interaction is invisible to every existing single-function test — a
refactor that "unified" the two windows (e.g. made both use ``[-2:]`` or both
use ``[-3:]``) would slip past the whole suite while changing real
conversation behavior. Each test below mocks ``random.random``
deterministically (zero probability of flakiness) and asserts the exact
window boundary in each direction.

Random-value choices used throughout (all pinned by prior sessions, restated
here for local clarity):

    _should_respond, random.random() == 0.8:
        - with new_message_count == 1, base_probability = min(0.25+0.12, 0.7) = 0.37
          → 0.8 < 0.37 is False, so a NON-addressed thinker does NOT respond.
        - @mentioned          → base 0.98  → 0.8 < 0.98 True  (responds)
        - addressed-by-name   → base min(0.37+0.5, 0.95) = 0.87 → 0.8 < 0.87 True
        (the 0.15 "stay silent" roll also uses 0.8, which is >= 0.15, so it never
         fires here; and it is bypassed entirely when addressed/@mentioned.)

    _choose_response_style, roll == 0.18:
        - addressed branch:      0.15 <= 0.18 < 0.35 → "brief, direct" → 60 tokens
        - not-addressed branch:  0.18 < 0.20        → "very brief reaction" → 30 tokens
        so the returned max_tokens (60 vs 30) cleanly reveals which window the
        function used.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from app.services.thinker import ThinkerService

# max_tokens returned by _choose_response_style at roll == 0.18, per branch.
ADDRESSED_TOKENS_AT_018 = 60  # addressed: 0.15 <= 0.18 < 0.35
NOT_ADDRESSED_TOKENS_AT_018 = 30  # not addressed: 0.18 < 0.20


def _msg(sender: str, content: str) -> MagicMock:
    """A message mock with the two attributes both functions read."""
    m = MagicMock()
    m.sender_name = sender
    m.content = content
    return m


def _thinker(name: str = "Plato") -> MagicMock:
    t = MagicMock()
    t.name = name
    t.bio = ""
    t.positions = ""
    t.style = ""
    return t


def _five_messages_with_target_at(index_from_end: int, target_content: str) -> list[Any]:
    """Build a 5-message list with ``target_content`` at ``messages[-index_from_end]``.

    All other messages are neutral ("a".."e") sent by a plain user "U" so they
    neither @mention nor name-address the thinker. index_from_end=2 puts the
    target at the second-from-last slot, =3 at third-from-last, =4 at
    fourth-from-last.
    """
    base = [
        _msg("U", "a"),
        _msg("U", "b"),
        _msg("U", "c"),
        _msg("U", "d"),
        _msg("U", "e"),
    ]
    base[len(base) - index_from_end] = _msg("U", target_content)
    return base


class TestShouldRespondMentionWindowIsLastThree:
    """``_should_respond`` @mention/addressed window is ``messages[-3:]`` (last 3).

    Uses random.random()==0.8 so that base probability (0.37 for
    new_message_count==1) is NOT enough to respond; only the @mention (0.98) or
    name-address (0.87) boost pushes it over 0.8. This isolates *detection*
    from the base-probability response path.
    """

    def _should_respond(self, msgs: list[Any]) -> bool:
        svc = ThinkerService()
        # last_response_count = len-1 → new_message_count == 1 → base_probability 0.37
        with patch("app.services.thinker.random.random", return_value=0.8):
            return svc._should_respond(
                _thinker(),
                msgs,
                last_response_count=len(msgs) - 1,
                consecutive_silence=0,
            )

    def test_mention_at_minus_two_is_seen(self) -> None:
        """@mention at index -2 (inside last 3) → responds despite 0.8 roll."""
        msgs = _five_messages_with_target_at(2, "@Plato hi")
        assert self._should_respond(msgs) is True

    def test_mention_at_minus_three_is_seen(self) -> None:
        """@mention at index -3 (the last-3 boundary) → still responds.

        This is the KEY row: index -3 is inside _should_respond's window but
        OUTSIDE _choose_response_style's last-2 window (see the discrepancy
        test below).
        """
        msgs = _five_messages_with_target_at(3, "@Plato hi")
        assert self._should_respond(msgs) is True

    def test_mention_at_minus_four_is_not_seen(self) -> None:
        """@mention at index -4 (outside last 3) → base prob only → no response.

        With base_probability 0.37 and roll 0.8, an unseen @mention leaves the
        thinker at 0.37, so 0.8 < 0.37 is False. This pins the outer edge of
        the last-3 window: extending it to last-4 would flip this to True.
        """
        msgs = _five_messages_with_target_at(4, "@Plato hi")
        assert self._should_respond(msgs) is False

    def test_name_address_at_minus_three_is_seen(self) -> None:
        """Name-addressing (no @) at index -3 is inside the last-3 window.

        addressed base = min(0.37 + 0.5, 0.95) = 0.87 → 0.8 < 0.87 True.
        """
        msgs = _five_messages_with_target_at(3, "What does Plato think")
        assert self._should_respond(msgs) is True

    def test_name_address_at_minus_four_is_not_seen(self) -> None:
        """Name-addressing at index -4 is outside the last-3 window → no boost."""
        msgs = _five_messages_with_target_at(4, "What does Plato think")
        assert self._should_respond(msgs) is False


class TestChooseResponseStyleMentionWindowIsLastTwo:
    """``_choose_response_style`` @mention/addressed window is the last 2 messages.

    Uses roll==0.18. When the thinker is treated as addressed the function
    returns 60 max_tokens ("brief, direct"); when treated as not-addressed it
    returns 30 ("very brief reaction"). The token count reveals which window
    was used, with no dependence on wording.
    """

    def _tokens(self, msgs: list[Any]) -> int:
        svc = ThinkerService()
        with patch("app.services.thinker.random.random", return_value=0.18):
            _, max_tokens = svc._choose_response_style(_thinker(), msgs)
        return max_tokens

    def test_mention_at_minus_two_is_seen(self) -> None:
        """@mention at index -2 IS inside the last-2 window → addressed style (60)."""
        msgs = _five_messages_with_target_at(2, "@Plato hi")
        assert self._tokens(msgs) == ADDRESSED_TOKENS_AT_018

    def test_mention_at_minus_three_is_not_seen(self) -> None:
        """@mention at index -3 is OUTSIDE the last-2 window → not-addressed style (30).

        Contrast with ``_should_respond`` which DOES see index -3. This is the
        exact cell where the two functions disagree.
        """
        msgs = _five_messages_with_target_at(3, "@Plato hi")
        assert self._tokens(msgs) == NOT_ADDRESSED_TOKENS_AT_018

    def test_name_address_at_minus_two_is_seen(self) -> None:
        """Name-addressing at index -2 → addressed style (60)."""
        msgs = _five_messages_with_target_at(2, "What does Plato think")
        assert self._tokens(msgs) == ADDRESSED_TOKENS_AT_018

    def test_name_address_at_minus_three_is_not_seen(self) -> None:
        """Name-addressing at index -3 → not-addressed style (30)."""
        msgs = _five_messages_with_target_at(3, "What does Plato think")
        assert self._tokens(msgs) == NOT_ADDRESSED_TOKENS_AT_018


class TestMentionWindowDiscrepancyAtIndexMinusThree:
    """The two functions DISAGREE for a thinker @mentioned at index -3.

    This is the single most important guard in this file: it exercises BOTH
    functions against the *same* message list and asserts the divergence
    directly. If a future refactor unifies the two windows, exactly one of
    these two assertions flips and the test fails — pointing straight at the
    behavior change.
    """

    def test_should_respond_yes_but_style_is_not_addressed(self) -> None:
        msgs = _five_messages_with_target_at(3, "@Plato hi")
        svc = ThinkerService()

        # _should_respond SEES the @mention (last-3 window) → responds even
        # though 0.8 would fail the 0.37 base probability.
        with patch("app.services.thinker.random.random", return_value=0.8):
            responds = svc._should_respond(
                _thinker(),
                msgs,
                last_response_count=len(msgs) - 1,
                consecutive_silence=0,
            )

        # _choose_response_style does NOT see the @mention (last-2 window) →
        # picks from the not-addressed distribution.
        with patch("app.services.thinker.random.random", return_value=0.18):
            _, max_tokens = svc._choose_response_style(_thinker(), msgs)

        assert responds is True, "_should_respond must see the @mention at index -3 (last-3 window)"
        assert max_tokens == NOT_ADDRESSED_TOKENS_AT_018, (
            "_choose_response_style must NOT see the @mention at index -3 (last-2 window); "
            "it should return the not-addressed style. If this fails, the two "
            "detection windows were unified — verify that is intended."
        )

    def test_name_address_same_discrepancy_at_minus_three(self) -> None:
        """The identical last-3-vs-last-2 split holds for name-addressing (no @)."""
        msgs = _five_messages_with_target_at(3, "What does Plato think")
        svc = ThinkerService()

        with patch("app.services.thinker.random.random", return_value=0.8):
            responds = svc._should_respond(
                _thinker(),
                msgs,
                last_response_count=len(msgs) - 1,
                consecutive_silence=0,
            )
        with patch("app.services.thinker.random.random", return_value=0.18):
            _, max_tokens = svc._choose_response_style(_thinker(), msgs)

        assert responds is True
        assert max_tokens == NOT_ADDRESSED_TOKENS_AT_018
