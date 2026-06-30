"""Flaky-hunt deterministic regression tests — QA Agent Tuesday session.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-06-30).
Issue: #997

Context — flaky-hunt verification first:
- The full backend suite (1807 tests collected) was run 5× back-to-back before
  adding this file to confirm there is no order/timing-dependent flakiness.

Prior flaky-hunt sessions (mar17, apr14, apr28, may5, may12, may19, may26,
jun2, jun9) have exhaustively pinned the *individual* random-roll boundaries
and the *individual* probability caps of the probabilistic decision functions
in ``app/services/thinker.py``:

    _should_respond           — base formula, @mention 0.98, addressed 0.95 cap,
                                 silence 0.9 cap, self-message 0.05, silence
                                 boundary at exactly 2 vs 3.
    _choose_response_style    — all 5 addressed + 5 not-addressed branches,
                                 just_spoke follow-up boundary at 0.4.
    _split_response_into_bubbles — strategy_roll boundaries, randint ranges,
                                 transition words, force-split.
    _should_prompt_user       — threshold/probability speed-mult scaling.

This file pins the **remaining gap**: the *cap-override INTERACTIONS* in
``_should_respond`` (thinker.py:1576-1600). The probability is computed by a
*sequence* of mutating statements, and the ORDER in which the caps are applied
produces behavior that no single-boundary test exercises. A refactor that
reordered the blocks, or changed one ``and not was_at_mentioned`` guard, would
slip past every existing test but change real behavior here:

    base = min(0.25 + new_message_count*0.12, 0.7)
    if was_at_mentioned:        base = 0.98
    elif was_addressed:         base = min(base + 0.5, 0.95)        # cap A = 0.95
    if consecutive_silence > 2 and not was_at_mentioned:
                                base = min(base + silence*0.1, 0.9)  # cap B = 0.9
    if last sender == self and not was_at_mentioned:
                                base = 0.05                          # override

Three interaction facts, each verified by direct computation, none pinned:

1. ``was_addressed`` caps at 0.95, but the silence block runs *afterward* and
   re-caps at 0.9 — so adding ``consecutive_silence >= 3`` to an addressed
   thinker LOWERS its response probability (0.95 -> 0.9). Counterintuitive but
   real; a reorder of the two blocks would change it.
2. ``@mention`` is IMMUNE to the silence boost (``and not was_at_mentioned``),
   so an @mentioned thinker stays at 0.98 no matter how high ``consecutive_silence``.
3. The self-last-message 0.05 floor is applied AFTER the silence boost, so it
   WINS: a thinker whose own message is last stays at 0.05 even at
   ``consecutive_silence=100``.

Each test mocks ``random.random`` deterministically (no probability of
flakiness) and asserts the exact threshold direction.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from app.services.thinker import ThinkerService


def _make_message(content: str, sender: str = "User") -> MagicMock:
    """Create a mock message with content and sender_name."""
    msg = MagicMock()
    msg.content = content
    msg.sender_name = sender
    return msg


def _make_thinker(name: str = "Socrates") -> MagicMock:
    thinker = MagicMock()
    thinker.name = name
    return thinker


# ---------------------------------------------------------------------------
# 1. addressed + silence: the 0.9 silence cap overrides the 0.95 addressed cap
#    DOWNWARD. This is the key interaction no single-boundary test covers.
# ---------------------------------------------------------------------------


class TestAddressedSilenceCapInteraction:
    """``was_addressed`` caps at 0.95; a later ``consecutive_silence`` re-caps at 0.9.

    To make the addressed branch HIT its 0.95 cap we need enough new messages
    that ``base = min(0.25 + n*0.12, 0.7) + 0.5`` exceeds 0.95, i.e. base must
    be >= 0.45 before the +0.5, which the 0.7 floor easily satisfies with many
    messages.

    With ``was_addressed=True`` the 15%-silence-skip line short-circuits
    (``not was_addressed`` is False) BEFORE calling ``random.random()``, so the
    ONLY ``random.random()`` call is the final ``return`` — a single mocked
    value controls the outcome.
    """

    # Many user messages addressing Socrates → base saturates at 0.7 before +0.5.
    _MESSAGES: Any = [_make_message("filler", "User")] * 6 + [
        _make_message("Socrates, what do you think?", "User")
    ]

    def test_addressed_alone_threshold_is_0_95(self) -> None:
        """addressed, silence=0 → threshold 0.95 (roll 0.94 responds)."""
        service = ThinkerService()
        with patch("app.services.thinker.random.random", return_value=0.94):
            result = service._should_respond(
                _make_thinker(), self._MESSAGES, 0, consecutive_silence=0
            )
        assert result is True, "addressed cap is 0.95: roll 0.94 < 0.95 must respond"

    def test_addressed_alone_roll_0_96_stays_silent(self) -> None:
        """addressed, silence=0 → roll 0.96 > 0.95 cap → silent."""
        service = ThinkerService()
        with patch("app.services.thinker.random.random", return_value=0.96):
            result = service._should_respond(
                _make_thinker(), self._MESSAGES, 0, consecutive_silence=0
            )
        assert result is False, "addressed cap is 0.95: roll 0.96 > 0.95 must stay silent"

    def test_addressed_plus_silence_recaps_at_0_9_responds_below(self) -> None:
        """addressed + silence=3 → threshold drops to 0.9 (roll 0.89 responds)."""
        service = ThinkerService()
        with patch("app.services.thinker.random.random", return_value=0.89):
            result = service._should_respond(
                _make_thinker(), self._MESSAGES, 0, consecutive_silence=3
            )
        assert result is True, "addressed+silence cap is 0.9: roll 0.89 < 0.9 must respond"

    def test_addressed_plus_silence_recaps_at_0_9_silent_above(self) -> None:
        """addressed + silence=3 → roll 0.91 > 0.9 cap → silent.

        This is the crux: 0.91 RESPONDS when addressed-alone (cap 0.95) but
        STAYS SILENT once silence is added (cap 0.9). The silence block runs
        after the addressed block and pulls the probability DOWN. A reorder of
        the two blocks, or a change to the 0.9 cap, would flip this assertion.
        """
        service = ThinkerService()
        with patch("app.services.thinker.random.random", return_value=0.91):
            result = service._should_respond(
                _make_thinker(), self._MESSAGES, 0, consecutive_silence=3
            )
        assert result is False, (
            "silence cap 0.9 overrides addressed cap 0.95 DOWNWARD: "
            "roll 0.91 responds when addressed-alone but must stay silent "
            "once consecutive_silence>=3 lowers the cap to 0.9"
        )

    def test_silence_lowers_addressed_probability_is_directional(self) -> None:
        """Same roll 0.91: responds addressed-alone, silent addressed+silence.

        Pins the *direction* of the interaction in one test so a regression
        that made silence raise (rather than lower) the addressed probability
        is caught even if the exact cap values drift.
        """
        service = ThinkerService()
        with patch("app.services.thinker.random.random", return_value=0.91):
            addressed_only = service._should_respond(
                _make_thinker(), self._MESSAGES, 0, consecutive_silence=0
            )
            addressed_silence = service._should_respond(
                _make_thinker(), self._MESSAGES, 0, consecutive_silence=3
            )
        assert addressed_only is True and addressed_silence is False, (
            "adding consecutive_silence to an addressed thinker must LOWER its "
            f"response probability (0.95->0.9); got addressed_only={addressed_only}, "
            f"addressed_silence={addressed_silence}"
        )


# ---------------------------------------------------------------------------
# 2. @mention is immune to the silence boost (the `and not was_at_mentioned`
#    guard on line 1588). High silence must NOT change the 0.98 probability.
# ---------------------------------------------------------------------------


class TestAtMentionImmuneToSilence:
    """An @mentioned thinker stays at 0.98 regardless of ``consecutive_silence``.

    The silence boost line is guarded by ``and not was_at_mentioned``, so the
    boost never applies to @mentioned thinkers. With ``was_at_mentioned=True``
    the 15%-silence-skip line also short-circuits, so a single mocked
    ``random.random()`` controls the final ``return``.
    """

    _MESSAGES: Any = [_make_message("hi", "User")] * 3 + [
        _make_message("@Socrates, your view?", "User")
    ]

    def test_at_mention_threshold_0_98_unaffected_by_zero_silence(self) -> None:
        """@mention, silence=0 → roll 0.97 responds, 0.99 silent (cap 0.98)."""
        service = ThinkerService()
        with patch("app.services.thinker.random.random", return_value=0.97):
            assert service._should_respond(_make_thinker(), self._MESSAGES, 0, 0) is True
        with patch("app.services.thinker.random.random", return_value=0.99):
            assert service._should_respond(_make_thinker(), self._MESSAGES, 0, 0) is False

    def test_at_mention_threshold_0_98_unchanged_at_high_silence(self) -> None:
        """@mention, silence=100 → STILL 0.98 (silence boost skipped).

        If the ``and not was_at_mentioned`` guard were dropped, silence=100
        would boost toward the 0.9 cap and roll 0.97 would flip to silent.
        Asserting roll 0.97 still RESPONDS at silence=100 pins the guard.
        """
        service = ThinkerService()
        with patch("app.services.thinker.random.random", return_value=0.97):
            result = service._should_respond(
                _make_thinker(), self._MESSAGES, 0, consecutive_silence=100
            )
        assert result is True, (
            "@mention must stay at 0.98 regardless of silence (guard "
            "`and not was_at_mentioned`); roll 0.97 < 0.98 must respond even "
            "at consecutive_silence=100"
        )

    def test_at_mention_roll_0_99_silent_even_at_high_silence(self) -> None:
        """@mention, silence=100, roll 0.99 → silent (cap is 0.98, not boosted up)."""
        service = ThinkerService()
        with patch("app.services.thinker.random.random", return_value=0.99):
            result = service._should_respond(
                _make_thinker(), self._MESSAGES, 0, consecutive_silence=100
            )
        assert result is False, (
            "@mention cap stays 0.98 even at silence=100; roll 0.99 > 0.98 "
            "must stay silent (silence does not raise the @mention cap)"
        )


# ---------------------------------------------------------------------------
# 3. self-last-message 0.05 floor is applied AFTER the silence boost, so it
#    WINS — a thinker whose own message is last stays at 0.05 even at high
#    silence (thinker.py:1593-1594 runs after the silence block at 1588-1589).
# ---------------------------------------------------------------------------


class TestSelfMessageOverrideWinsOverSilence:
    """The 0.05 self-message floor overrides the silence boost (applied later).

    Setup: last message sender == thinker, content does NOT address the
    thinker, no @mention → ``was_at_mentioned`` and ``was_addressed`` are both
    False. Two ``random.random()`` calls happen:
      1. the 15%-silence-skip line (``random.random() < 0.15``)
      2. the final ``return random.random() < base_probability``
    We use ``side_effect=[0.5, roll]``: 0.5 fails the 15% skip (0.5 >= 0.15,
    so no early ``return False``), then ``roll`` drives the final comparison.
    """

    _MESSAGES: Any = [_make_message("hi", "User")] * 3 + [
        _make_message("A closing thought of my own.", "Socrates")
    ]

    def test_self_message_floor_0_05_responds_below(self) -> None:
        """self-message, silence=0 → threshold 0.05 (roll 0.04 responds)."""
        service = ThinkerService()
        with patch("app.services.thinker.random.random", side_effect=[0.5, 0.04]):
            result = service._should_respond(
                _make_thinker(), self._MESSAGES, 0, consecutive_silence=0
            )
        assert result is True, "self-message floor is 0.05: roll 0.04 < 0.05 must respond"

    def test_self_message_floor_0_05_silent_above(self) -> None:
        """self-message, silence=0 → roll 0.06 > 0.05 → silent."""
        service = ThinkerService()
        with patch("app.services.thinker.random.random", side_effect=[0.5, 0.06]):
            result = service._should_respond(
                _make_thinker(), self._MESSAGES, 0, consecutive_silence=0
            )
        assert result is False, "self-message floor is 0.05: roll 0.06 > 0.05 must stay silent"

    def test_self_message_floor_survives_high_silence(self) -> None:
        """self-message, silence=100 → STILL 0.05 (override applied after boost).

        The silence block would push the probability toward 0.9, but the
        self-message reset to 0.05 runs *afterward* and wins. roll 0.06 must
        therefore stay SILENT even at silence=100. If the two statements were
        reordered (self-message before silence), the boost would override the
        floor and 0.06 would flip to respond.
        """
        service = ThinkerService()
        with patch("app.services.thinker.random.random", side_effect=[0.5, 0.06]):
            result = service._should_respond(
                _make_thinker(), self._MESSAGES, 0, consecutive_silence=100
            )
        assert result is False, (
            "self-message 0.05 floor is applied AFTER the silence boost and "
            "must win: roll 0.06 stays silent even at consecutive_silence=100"
        )

    def test_self_message_floor_responds_at_004_high_silence(self) -> None:
        """self-message, silence=100, roll 0.04 → responds (floor still 0.05).

        Positive control: confirms the floor stays at exactly 0.05 (not 0,
        not boosted) under high silence — roll just below the floor responds.
        """
        service = ThinkerService()
        with patch("app.services.thinker.random.random", side_effect=[0.5, 0.04]):
            result = service._should_respond(
                _make_thinker(), self._MESSAGES, 0, consecutive_silence=100
            )
        assert result is True, (
            "self-message floor stays exactly 0.05 even at silence=100; "
            "roll 0.04 < 0.05 must respond"
        )
