"""Flaky test hunt and hardening tests for QA Agent Tuesday focus.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-05-19).
Issue: #906

Context — flaky-hunt verification first:
- Full backend suite (1503 passed, 9 skipped) ran cleanly on the baseline at
  98.75% coverage. No spurious failures across the run.
- Only `app/services/thinker.py` uses ``random.*`` for branch selection. The
  ``_split_response_into_bubbles`` / ``_should_respond`` / ``_should_prompt_user``
  random branches were locked down in earlier flaky-hunt sessions
  (apr28_2026, may5_2026, may12_2026).
- ``_choose_response_style`` still has ONLY seed-based tests
  (``test_thinker_service.py::TestChooseResponseStyle`` and
  ``test_flaky_hunt_mar17_2026.py::test_choose_response_style_always_returns_valid_values``),
  which assert distributional properties (``min(token_counts) >= 30``,
  ``len(set(...)) > 1``). A refactor that breaks a single branch or flips a
  ``<`` to ``<=`` would slip past those checks.

This file locks down ``_choose_response_style`` with **fully deterministic**
mocks (no seed-based luck, no real wall-clock dependency):

1. Each of the 5 "addressed" branches (roll < 0.15 / < 0.35 / < 0.55 / < 0.80
   / else) is pinned with a precise mocked ``random.random()`` value and the
   exact ``(style_keyword, max_tokens)`` tuple is asserted.

2. Each of the 5 "not-addressed" branches (roll < 0.20 / < 0.40 / < 0.60 /
   < 0.80 / else) is pinned the same way.

3. The ``just_spoke and roll < 0.4`` follow-up branch is exercised at the low
   end and just below the boundary; the strict ``<`` boundary at roll == 0.4
   is verified to fall THROUGH to the addressed/not-addressed branches.

4. The strict ``<`` boundary direction is verified at every cascading
   threshold (0.15, 0.20, 0.35, 0.40, 0.55, 0.60, 0.80). At exactly
   ``roll == threshold`` the NEXT branch must be taken — a regression that
   flips ``<`` to ``<=`` would change one of these tuples and fail loudly.

5. ``_suggest_single_batch`` line 272 (``return []`` when ``self.client`` is
   ``None``) is exercised directly. The public ``suggest_thinkers`` caller
   short-circuits earlier, so without this direct test the inner guard was
   uncovered — locking it down means a refactor that drops the guard (and
   later assumes client is non-None) will fail loudly.
"""

from typing import Any
from unittest.mock import PropertyMock, patch

import pytest

from app.services.thinker import ThinkerService
from tests.mock_factories import make_message as _make_message
from tests.mock_factories import make_thinker as _make_thinker

# ---------------------------------------------------------------------------
# 1. _choose_response_style — was_addressed branches, deterministic roll
# ---------------------------------------------------------------------------


class TestChooseResponseStyleAddressedBranchesDeterministic:
    """Each of the 5 ``was_addressed`` branches pinned with mocked roll.

    Branches (thinker.py lines 484-496):
        roll < 0.15 →  ("Respond with just 2-5 words ...",                30)
        roll < 0.35 →  ("Give a brief, direct response ...",              60)
        roll < 0.55 →  ("Give a medium response ...",                    120)
        roll < 0.80 →  ("Give a substantive response ...",               200)
        else       →  ("Give a fuller response exploring the idea ...", 350)

    To take the ``was_addressed`` branch and NOT the ``just_spoke``
    follow-up branch, we use a single message addressed to the thinker BY
    NAME but sent by a different sender, so ``just_spoke`` is False.
    """

    @pytest.fixture
    def service_and_messages(self) -> tuple[ThinkerService, list[Any]]:
        service = ThinkerService()
        # "Socrates, what do you think?" addresses Socrates by name but the
        # sender is "User", so just_spoke = False.
        messages = [_make_message("Socrates, what do you think?", "User")]
        return service, messages

    def test_addressed_roll_0_00_returns_30_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.00 → 2-5 word reply, 30 tokens (first addressed branch)."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.0):
            style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 30
        assert "2-5 words" in style

    def test_addressed_roll_0_14_returns_30_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.14 (just under 0.15) → still 30 tokens."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.14):
            style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 30

    def test_addressed_roll_0_15_boundary_returns_60_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.15 EXACTLY → next branch (60 tokens).

        Strict ``<`` boundary: 0.15 == 0.15 must NOT take the 30-token
        branch. A regression flipping ``<`` → ``<=`` would return 30 here.
        """
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.15):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 60, (
            "boundary roll=0.15 must take the NEXT branch (60 tokens); "
            "if this returns 30 the inequality has been flipped to <="
        )

    def test_addressed_roll_0_34_returns_60_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.34 (just under 0.35) → still 60 tokens."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.34):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 60

    def test_addressed_roll_0_35_boundary_returns_120_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.35 EXACTLY → next branch (120 tokens, strict ``<``)."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.35):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 120, (
            "boundary roll=0.35 must take the NEXT branch (120 tokens); "
            "if this returns 60 the inequality has been flipped to <="
        )

    def test_addressed_roll_0_54_returns_120_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.54 (just under 0.55) → still 120 tokens."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.54):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 120

    def test_addressed_roll_0_55_boundary_returns_200_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.55 EXACTLY → next branch (200 tokens, strict ``<``)."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.55):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 200, (
            "boundary roll=0.55 must take the NEXT branch (200 tokens); "
            "if this returns 120 the inequality has been flipped to <="
        )

    def test_addressed_roll_0_79_returns_200_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.79 (just under 0.80) → still 200 tokens."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.79):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 200

    def test_addressed_roll_0_80_boundary_returns_350_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.80 EXACTLY → final ``else`` branch (350 tokens)."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.80):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 350, (
            "boundary roll=0.80 must take the ELSE branch (350 tokens); "
            "if this returns 200 the inequality has been flipped to <="
        )

    def test_addressed_roll_0_99_returns_350_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.99 → final ``else`` branch (350 tokens, exploration)."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.99):
            style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 350
        assert "exploring" in style or "fuller" in style


# ---------------------------------------------------------------------------
# 2. _choose_response_style — not-addressed branches, deterministic roll
# ---------------------------------------------------------------------------


class TestChooseResponseStyleNotAddressedBranchesDeterministic:
    """Each of the 5 not-addressed branches pinned with mocked roll.

    Branches (thinker.py lines 499-517):
        roll < 0.20 → ("Give a very brief reaction (2-6 words only ...", 30)
        roll < 0.40 → ("Give a brief reaction (1 short sentence ...",    60)
        roll < 0.60 → ("Give a medium response ...",                    120)
        roll < 0.80 → ("Give a substantive response ...",               200)
        else        → ("Give a more developed response ...",            300)

    To take the not-addressed branch, neither the thinker's name nor an
    ``@mention`` may appear in the recent messages.
    """

    @pytest.fixture
    def service_and_messages(self) -> tuple[ThinkerService, list[Any]]:
        service = ThinkerService()
        # Generic prompt — does NOT contain "Socrates" or @Socrates
        messages = [_make_message("What about democracy in general?", "User")]
        return service, messages

    def test_not_addressed_roll_0_00_returns_30_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.00 → very brief reaction, 30 tokens."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.0):
            style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 30
        assert "brief" in style.lower() or "reaction" in style.lower()

    def test_not_addressed_roll_0_19_returns_30_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.19 (just under 0.20) → still 30 tokens."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.19):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 30

    def test_not_addressed_roll_0_20_boundary_returns_60_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.20 EXACTLY → next branch (60 tokens, strict ``<``)."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.20):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 60, (
            "boundary roll=0.20 must take the NEXT branch (60 tokens); "
            "if this returns 30 the inequality has been flipped to <="
        )

    def test_not_addressed_roll_0_39_returns_60_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.39 (just under 0.40) → still 60 tokens."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.39):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 60

    def test_not_addressed_roll_0_40_boundary_returns_120_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.40 EXACTLY → next branch (120 tokens, strict ``<``)."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.40):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 120, (
            "boundary roll=0.40 must take the NEXT branch (120 tokens); "
            "if this returns 60 the inequality has been flipped to <="
        )

    def test_not_addressed_roll_0_59_returns_120_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.59 (just under 0.60) → still 120 tokens."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.59):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 120

    def test_not_addressed_roll_0_60_boundary_returns_200_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.60 EXACTLY → next branch (200 tokens, strict ``<``)."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.60):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 200, (
            "boundary roll=0.60 must take the NEXT branch (200 tokens); "
            "if this returns 120 the inequality has been flipped to <="
        )

    def test_not_addressed_roll_0_79_returns_200_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.79 (just under 0.80) → still 200 tokens."""
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.79):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 200

    def test_not_addressed_roll_0_80_boundary_returns_300_tokens(
        self, service_and_messages: tuple[ThinkerService, list[Any]]
    ) -> None:
        """roll = 0.80 EXACTLY → final ``else`` branch (300 tokens).

        Note: 300 (not 350) — the not-addressed terminal branch uses a
        smaller cap than the addressed terminal branch (which is 350).
        Pins both the boundary direction AND the not-addressed cap value.
        """
        service, messages = service_and_messages
        with patch("app.services.thinker.random.random", return_value=0.80):
            _style, max_tokens = service._choose_response_style(_make_thinker(), messages)
        assert max_tokens == 300, (
            "boundary roll=0.80 must take the ELSE branch (300 tokens, "
            "NOT 350 — the not-addressed cap is 300, the addressed cap is 350)"
        )


# ---------------------------------------------------------------------------
# 3. _choose_response_style — just_spoke follow-up branch
# ---------------------------------------------------------------------------


class TestChooseResponseStyleJustSpokeFollowUp:
    """Pin the ``just_spoke and roll < 0.4`` follow-up branch.

    Branch (thinker.py lines 476-481):
        if just_spoke and roll < 0.4:
            return ("Respond with a VERY brief follow-up ...", 50)

    To take this branch:
      - ``just_spoke`` must be True → the LAST message's sender_name must
        equal ``thinker.name``.
      - ``roll`` (mocked ``random.random()``) must be < 0.4.

    At the strict ``<`` boundary (roll == 0.4), the function must FALL
    THROUGH to the was_addressed / not-addressed branches.
    """

    def test_just_spoke_roll_0_00_returns_follow_up(self) -> None:
        """just_spoke + roll=0.00 → 50-token VERY brief follow-up."""
        service = ThinkerService()
        # Last message sender is Socrates → just_spoke=True
        messages = [_make_message("I think the truth lies elsewhere.", "Socrates")]
        with patch("app.services.thinker.random.random", return_value=0.0):
            style, max_tokens = service._choose_response_style(_make_thinker("Socrates"), messages)
        assert max_tokens == 50
        assert "follow-up" in style.lower() or "brief" in style.lower()

    def test_just_spoke_roll_0_39_returns_follow_up(self) -> None:
        """just_spoke + roll=0.39 (just under 0.40) → 50-token follow-up."""
        service = ThinkerService()
        messages = [_make_message("I think the truth lies elsewhere.", "Socrates")]
        with patch("app.services.thinker.random.random", return_value=0.39):
            _style, max_tokens = service._choose_response_style(_make_thinker("Socrates"), messages)
        assert max_tokens == 50

    def test_just_spoke_roll_0_40_boundary_falls_through(self) -> None:
        """just_spoke + roll=0.40 EXACTLY → falls through (strict ``<``).

        With just_spoke=True and roll>=0.4, the follow-up branch is skipped.
        The thinker's last message DOES contain its own name ("Socrates" in
        sender_name does NOT count, but the content is generic), so this
        falls to the NOT-addressed branch. roll=0.40 in not-addressed →
        120 tokens.

        A regression flipping ``<`` → ``<=`` here would return 50 instead.
        """
        service = ThinkerService()
        # Content does not mention "Socrates", sender_name="Socrates"
        messages = [_make_message("Truth lies elsewhere.", "Socrates")]
        with patch("app.services.thinker.random.random", return_value=0.40):
            _style, max_tokens = service._choose_response_style(_make_thinker("Socrates"), messages)
        assert max_tokens != 50, (
            "boundary roll=0.40 must NOT take the follow-up branch; "
            "if this returns 50 the inequality has been flipped to <="
        )
        # Falls through to not-addressed roll=0.40 → 120 tokens
        assert max_tokens == 120

    def test_just_spoke_false_with_low_roll_does_not_return_follow_up(self) -> None:
        """When just_spoke=False, low roll does NOT trigger follow-up.

        Last message sender is "User" → just_spoke=False. roll=0.05 would
        still trigger follow-up IF the condition were broken. Verifies that
        the ``just_spoke and ...`` short-circuit guards the follow-up branch.
        """
        service = ThinkerService()
        # Last sender is User (not Socrates) → just_spoke=False
        # Content does not address Socrates → not_addressed branch
        messages = [_make_message("What about democracy in general?", "User")]
        with patch("app.services.thinker.random.random", return_value=0.05):
            _style, max_tokens = service._choose_response_style(_make_thinker("Socrates"), messages)
        # roll=0.05 in not-addressed branch → 30 tokens (NOT 50)
        assert max_tokens == 30, (
            "just_spoke=False must skip follow-up branch even at low roll; "
            f"got max_tokens={max_tokens} (expected 30 from not-addressed roll<0.20)"
        )


# ---------------------------------------------------------------------------
# 4. _suggest_single_batch — no-client guard, direct call
# ---------------------------------------------------------------------------


class TestSuggestSingleBatchNoClientGuard:
    """Cover the ``if not self.client: return []`` guard in _suggest_single_batch.

    Thinker.py line 271-272:
        if not self.client:
            return []

    The public caller ``suggest_thinkers`` short-circuits earlier
    (see lines 188-189), so the guard inside ``_suggest_single_batch``
    was unreachable from existing tests. A refactor that removed the
    inner guard and later assumed ``self.client`` was non-None would
    crash on direct calls — this test prevents that regression.
    """

    async def test_suggest_single_batch_returns_empty_when_client_is_none(self) -> None:
        """Direct call with client=None returns [] (line 272)."""
        service = ThinkerService()
        with patch.object(type(service), "client", new_callable=PropertyMock) as mock_client:
            mock_client.return_value = None
            result = await service._suggest_single_batch("philosophy", 3)
        assert result == [], (
            "_suggest_single_batch must return [] when client is None "
            "(line 272 guard); got: " + repr(result)
        )

    async def test_suggest_single_batch_returns_empty_with_exclude_when_client_is_none(
        self,
    ) -> None:
        """Direct call with exclude+language and client=None still returns []."""
        service = ThinkerService()
        with patch.object(type(service), "client", new_callable=PropertyMock) as mock_client:
            mock_client.return_value = None
            result = await service._suggest_single_batch(
                "philosophy",
                5,
                perspective_hint="contemporary",
                exclude=["Plato", "Aristotle"],
                language="es",
            )
        assert result == [], (
            "_suggest_single_batch must return [] regardless of args when client is None"
        )
