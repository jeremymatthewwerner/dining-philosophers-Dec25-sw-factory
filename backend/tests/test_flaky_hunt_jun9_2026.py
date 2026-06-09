"""Flaky-hunt deterministic regression tests — QA Agent Tuesday session.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-06-09).
Issue: #952

Context — flaky-hunt verification first:
- The full backend suite (1758 passed, 10 skipped) ran clean.
- The random/timing-prone subset (331 tests matching ``flaky``, ``random``,
  ``bubble``, ``split``, ``should_respond``, ``should_prompt``,
  ``thinking_display``, ``choose_response``, ``choose_style``, ``strategy``,
  ``randint``, ``mention``) was run **5× back-to-back** before adding this file
  — 331 passed each run (~25s). No flakiness detected.

Prior flaky-hunt sessions (mar17, apr14, apr28, may5, may12, may19, may26,
jun2) have pinned the random-roll BOUNDARIES of the probabilistic decision
functions (``_should_respond``, ``_choose_response_style``,
``_split_response_into_bubbles``) and the ``_should_prompt_user`` probability
at ``speed_mult=1.0``.

This file pins the **remaining gap**: the *speed-multiplier scaling* of
``_should_prompt_user`` (thinker.py:1444-1470). Both the prompt threshold and
the prompt probability scale with ``speed_mult ** 0.3``, but existing tests
only exercise ``speed_mult=1.0`` (where ``speed**anything == 1`` so the
exponent is invisible) plus one ``speed_mult=6.0`` test that uses
``random=0.0`` (which passes *any* positive probability). A regression
changing the exponent ``0.3``, the base constant ``8``/``0.15``, or the
``max(4, ...)`` floor would slip past the current suite.

    threshold          = max(4, int(8 / speed_mult**0.3))
    prompt_probability = 0.15 * speed_mult**0.3

Verified scaling values (computed):

    speed   threshold   probability
    0.5     9           0.1218
    1.0     8           0.1500
    2.0     6           0.1847
    4.0     5           0.2274
    6.0     4           0.2568
    20.0    4 (floor)   0.3685

Exponent differentiation at speed 4.0: exp 0.2 → threshold 6, exp 0.3 → 5,
exp 0.5 → 4. Pinning threshold=5 at speed 4.0 therefore locks the ``0.3``
exponent (the speed-6.0 test cannot, since exp 0.3 and 0.5 both give 4 there).
"""

from typing import Any
from unittest.mock import MagicMock, patch

from app.services.thinker import ThinkerService

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _thinker_msg() -> Any:
    """A non-user (thinker) message — counted by _count_messages_since_user."""
    msg = MagicMock()
    msg.sender_type = "thinker"
    return msg


def _user_msg() -> Any:
    """A user message — stops the messages_since_user count."""
    msg = MagicMock()
    msg.sender_type = "user"
    return msg


def _messages_with_since_user(n: int, total_min: int = 5) -> list[Any]:
    """Build a message list where ``_count_messages_since_user`` returns ``n``.

    Layout: ``[thinker]*pad + [user] + [thinker]*n``. The trailing ``n``
    thinker messages (after the last user message) make
    ``messages_since_user == n``. ``pad`` is chosen so the total length is at
    least ``total_min`` (the function's ``len(messages) < 5`` short-circuit
    must NOT fire — we want to reach the threshold/probability logic).
    """
    pad = max(0, total_min - (n + 1))
    return [_thinker_msg() for _ in range(pad)] + [_user_msg()] + [_thinker_msg() for _ in range(n)]


# ---------------------------------------------------------------------------
# 1. _should_prompt_user — prompt_probability scales with speed_mult
# ---------------------------------------------------------------------------


class TestShouldPromptUserProbabilityScaling:
    """Pin ``prompt_probability = 0.15 * speed_mult**0.3`` (thinker.py:1469).

    Existing tests only check ``speed_mult=1.0`` (prob exactly 0.15) and a
    ``6.0`` case with ``random=0.0`` (passes any positive prob). Neither
    verifies the probability *grows* with speed, nor pins its scaled value.
    """

    def test_fixed_roll_flips_outcome_across_speeds(self) -> None:
        """A single roll of 0.20 is below prob at high speed but above it at 1.0.

        prob(1.0)=0.15 → 0.20 < 0.15 is False (no prompt).
        prob(6.0)=0.2568 → 0.20 < 0.2568 is True (prompt).

        Same roll, opposite outcomes: this pins that probability *increases*
        with speed. A regression that dropped the ``speed_mult**0.3`` factor
        (making prob a flat 0.15) would return False at speed 6.0 too.
        """
        service = ThinkerService()
        # 8 thinker messages since user: meets threshold at BOTH speeds
        # (threshold is 8 at speed 1.0 and 4 at speed 6.0), so only the
        # probability check distinguishes the two outcomes.
        messages = _messages_with_since_user(8)

        with patch("app.services.thinker.random.random", return_value=0.20):
            at_1x = service._should_prompt_user(messages, speed_mult=1.0)
            at_6x = service._should_prompt_user(messages, speed_mult=6.0)

        assert at_1x is False, "roll 0.20 is NOT < prob 0.15 at speed 1.0 → no prompt"
        assert at_6x is True, (
            "roll 0.20 IS < prob 0.2568 at speed 6.0 → prompt. If this is False, "
            "the speed_mult**0.3 probability scaling was lost."
        )

    def test_exact_probability_boundary_at_speed_1(self) -> None:
        """speed_mult=1.0 → prob exactly 0.15; strict ``<`` boundary.

        roll=0.149 < 0.15 → True; roll=0.15 NOT < 0.15 → False. Pins the
        base constant 0.15 at the strict-less-than boundary.
        """
        service = ThinkerService()
        messages = _messages_with_since_user(8)  # threshold=8 met at speed 1.0

        with patch("app.services.thinker.random.random", return_value=0.149):
            assert service._should_prompt_user(messages, speed_mult=1.0) is True

        with patch("app.services.thinker.random.random", return_value=0.15):
            assert service._should_prompt_user(messages, speed_mult=1.0) is False, (
                "roll=0.15 is NOT < prob 0.15 (strict <) → must be False. "
                "A flip to <= would return True here."
            )

    def test_scaled_probability_value_at_speed_6(self) -> None:
        """speed_mult=6.0 → prob ≈ 0.2568; pin the scaled value directly.

        roll=0.25 < 0.2568 → True; roll=0.26 NOT < 0.2568 → False. Brackets
        the computed probability so a changed exponent/base shifts it out of
        the [0.25, 0.26) window and fails one of these assertions.
        """
        service = ThinkerService()
        messages = _messages_with_since_user(8)  # threshold=4 at speed 6.0, easily met

        with patch("app.services.thinker.random.random", return_value=0.25):
            assert service._should_prompt_user(messages, speed_mult=6.0) is True

        with patch("app.services.thinker.random.random", return_value=0.26):
            assert service._should_prompt_user(messages, speed_mult=6.0) is False, (
                "roll=0.26 NOT < prob 0.2568 at speed 6.0 → False. "
                "Brackets the scaled probability value."
            )


# ---------------------------------------------------------------------------
# 2. _should_prompt_user — threshold scales with speed_mult (exponent 0.3)
# ---------------------------------------------------------------------------


class TestShouldPromptUserThresholdScaling:
    """Pin ``threshold = max(4, int(8 / speed_mult**0.3))`` (thinker.py:1462).

    The threshold gate (``messages_since_user < threshold → False``) runs
    BEFORE the random roll, so with ``random=0.0`` the only thing that can
    keep the result False is the threshold not being met. That makes
    ``random=0.0`` a clean probe for the threshold value.
    """

    def test_threshold_is_5_at_speed_4_locks_exponent(self) -> None:
        """speed_mult=4.0 → threshold = max(4, int(8/4**0.3)) = 5.

        4 messages-since-user (< 5) → False even with roll=0.0.
        5 messages-since-user (== 5, gate uses strict <) → proceeds → True.

        This pins the exponent: at speed 4.0 exp 0.2 gives threshold 6 and
        exp 0.5 gives 4, so only exp 0.3 yields exactly 5. The existing
        speed-6.0 test cannot distinguish these (exp 0.3 and 0.5 both → 4).
        """
        service = ThinkerService()

        below = _messages_with_since_user(4)
        with patch("app.services.thinker.random.random", return_value=0.0):
            assert service._should_prompt_user(below, speed_mult=4.0) is False, (
                "messages_since_user=4 < threshold 5 at speed 4.0 → False "
                "(threshold gate, before the random roll)"
            )

        at_threshold = _messages_with_since_user(5)
        with patch("app.services.thinker.random.random", return_value=0.0):
            assert service._should_prompt_user(at_threshold, speed_mult=4.0) is True, (
                "messages_since_user=5 == threshold 5 → gate passes (strict <) → "
                "roll 0.0 < prob → True. If threshold were 6 (exponent 0.2) this "
                "would be False."
            )

    def test_threshold_strict_less_than_boundary_at_speed_2(self) -> None:
        """speed_mult=2.0 → threshold=6; gate is strict ``<``.

        5 messages (< 6) → False; 6 messages (== 6, NOT < 6) → proceeds → True.
        Pins both the threshold value at speed 2.0 and the strict-< gate.
        """
        service = ThinkerService()

        below = _messages_with_since_user(5)
        with patch("app.services.thinker.random.random", return_value=0.0):
            assert service._should_prompt_user(below, speed_mult=2.0) is False

        at_threshold = _messages_with_since_user(6)
        with patch("app.services.thinker.random.random", return_value=0.0):
            assert service._should_prompt_user(at_threshold, speed_mult=2.0) is True, (
                "messages_since_user=6 == threshold 6 must pass the strict-< gate "
                "(6 < 6 is False) and prompt. A flip to <= would return False here."
            )

    def test_threshold_floor_of_4_at_high_speed(self) -> None:
        """Very high speed drives ``int(8/speed**0.3)`` below 4 → ``max(4,...)`` floor.

        At speed_mult=20.0, ``int(8/20**0.3) = int(3.26) = 3``, so the
        ``max(4, ...)`` floor clamps the threshold to 4. This guards the
        floor, which is never reached at the production-clamped max speed of
        6.0 (where the raw value is exactly 4).

        3 messages (< 4) → False; 4 messages (== 4) → proceeds → True.
        """
        service = ThinkerService()

        below = _messages_with_since_user(3)
        with patch("app.services.thinker.random.random", return_value=0.0):
            assert service._should_prompt_user(below, speed_mult=20.0) is False, (
                "messages_since_user=3 < floor threshold 4 → False"
            )

        at_floor = _messages_with_since_user(4)
        with patch("app.services.thinker.random.random", return_value=0.0):
            assert service._should_prompt_user(at_floor, speed_mult=20.0) is True, (
                "messages_since_user=4 == floor threshold 4 → proceeds → True. "
                "If the max(4,...) floor were removed, threshold would be 3 and "
                "this distinction (3 vs 4) would still hold, but the 3-message "
                "case above would then return True — the floor keeps it False."
            )


# ---------------------------------------------------------------------------
# 3. _should_prompt_user — short-history short-circuit interplay with speed
# ---------------------------------------------------------------------------


class TestShouldPromptUserShortHistoryBeatsSpeed:
    """The ``len(messages) < 5`` short-circuit (line 1456) fires before any
    speed-based threshold or probability logic.

    Even at a high speed_mult where the threshold would otherwise be low
    enough to prompt, a history shorter than 5 must return False without
    consulting the random roll.
    """

    def test_four_messages_returns_false_even_at_high_speed(self) -> None:
        """4 messages total < 5 → False regardless of speed or roll.

        Build exactly 4 trailing thinker messages (no user, total length 4).
        At speed 6.0 the threshold would be 4 and the roll would pass, but
        the short-history gate must short-circuit first.
        """
        service = ThinkerService()
        messages: Any = [_thinker_msg() for _ in range(4)]  # len 4 < 5

        with patch("app.services.thinker.random.random", return_value=0.0) as mock_rand:
            result = service._should_prompt_user(messages, speed_mult=6.0)

        assert result is False, "len(messages)=4 < 5 must short-circuit to False"
        assert mock_rand.call_count == 0, (
            "short-history gate must return before the random roll; "
            f"random.random() was called {mock_rand.call_count} times"
        )
