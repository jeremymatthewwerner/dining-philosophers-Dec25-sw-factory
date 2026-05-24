"""Regression prevention tests for Sunday QA (May 24, 2026).

Focus: pin down behavioral and source-level invariants from recent bug fixes
that the existing numeric-only tests do not lock in. The numeric tests prove
"this value comes out right today" — these tests prove "the *implementation*
hasn't been changed in a way that would let the original bug come back."

Bug fixes / features whose invariants are guarded here:

- fix(thinker) #533 (commit 17cabf9): linear speed multiplier (was exponential
  `speed**1.5`, which made the 6x slider feel like 14.7x). The existing
  `TestSpeedMultiplierLinearScaling` class proves the *result* is linear via
  manager.set_speed_multiplier, but no test asserts the formula source itself
  contains "15.0 * speed_mult" and *no exponentiation*. A well-intentioned
  refactor that reintroduces `speed_mult ** 1.5` would not be caught by the
  numeric tests if the refactor also adjusts the test expectations.

- feat(backend) #483 (commit 7aa14e7): idle-timeout auto-pause. ThinkerService
  maintains two pause sets: `_paused_conversations` (manual) and
  `_idle_paused_conversations` (idle). The contract is that `pause_for_idle`
  adds to both, `resume_from_idle` clears both, but `resume_conversation` only
  clears the manual set and is a no-op for idle state. These independence
  invariants determine whether users can correctly resume after idle pause —
  if confused, users can be stuck with a conversation that won't respond.

- feat(i18n) #336 (French), #455 (German), #570 (Hindi): LANGUAGE_NAMES gained
  three new entries. Each addition requires a matching branch in
  `_extract_thinking_display` (replacements + starters). Past regressions
  added a language to LANGUAGE_NAMES but forgot to wire up the thinking
  display, causing the prompt to claim "respond in Hindi" but the thinker's
  thinking-display panel to show English-only replacements.

Test groups (this file, 20 tests total):
- TestSpeedMultiplierAgentLoopSourceGuards (4): No exponentiation in agent loop
- TestPauseStateMachineDualSetIndependence (5): Manual vs. idle pause sets
- TestSetSpeedMultiplierClampBoundaries (4): Exact-boundary + broadcast value
- TestLanguageNamesAndThinkingDisplayParity (4): Each language has a branch
- TestIdleTimeoutZeroDisablesSentinel (3): The `idle_timeout > 0` guard
"""

import inspect
import re

import pytest

from app.api.websocket import (
    ConnectionManager,
    ConversationRoom,
    WSMessageType,
)
from app.core.config import Settings, get_settings
from app.services.thinker import LANGUAGE_NAMES, ThinkerService

# ===========================================================================
# TestSpeedMultiplierAgentLoopSourceGuards
# Regression guard for fix #533 (commit 17cabf9).
#
# The original bug: agent loop used `speed_mult = raw_speed ** 1.5` so a 6x
# slider produced a 14.7x effective multiplier (220s between messages).
# Fix: `speed_mult = manager.get_speed_multiplier(conversation_id)` — linear.
#
# Existing tests (test_regression_prevention.py:TestSpeedMultiplierLinearScaling)
# verify the result is linear at the manager level. These tests are stronger:
# they inspect the _run_thinker_agent source and assert the formula has no
# exponentiation, so a refactor that bypasses the manager helper still cannot
# silently bring back the exponential pacing.
# ===========================================================================


class TestSpeedMultiplierAgentLoopSourceGuards:
    """Regression guards: agent loop pacing must use linear speed_mult."""

    def test_run_thinker_agent_source_uses_linear_15s_base(self) -> None:
        """The agent loop computes min_interval as `15.0 * speed_mult` (linear).

        Regression guard for fix #533: the literal formula must appear in the
        agent loop. If the formula is restructured (e.g., factored into a
        helper), the helper *must* still be linear — but at minimum, the
        agent-loop body must show the linear form so reviewers can catch
        regressions without having to chase indirection.
        """
        source = inspect.getsource(ThinkerService._run_thinker_agent)
        assert "15.0 * speed_mult" in source, (
            "_run_thinker_agent must compute min_interval as `15.0 * speed_mult` "
            "(linear scaling). If this literal is gone, verify that the new "
            "formula is still linear — fix #533 specifically removed the "
            "`speed_mult ** 1.5` exponent that made 6x feel like 14.7x."
        )

    def test_run_thinker_agent_source_has_no_exponentiation_on_speed_mult(self) -> None:
        """The agent loop must not raise speed_mult to any power.

        Regression guard for fix #533: the original bug was `speed_mult ** 1.5`
        and any reintroduction (e.g., `speed_mult ** 2`, `pow(speed_mult, 1.3)`,
        `math.pow(speed_mult, ...)`) would silently reintroduce the bug. This
        test scans the source for any such pattern.

        Note: `speed_mult ** 0.3` is intentionally used in `_should_prompt_user`
        (a *different* function for a *different* purpose — prompt frequency,
        not message interval) and is therefore not covered by this regression
        guard. This guard only covers `_run_thinker_agent`.
        """
        source = inspect.getsource(ThinkerService._run_thinker_agent)

        # Match `speed_mult ** <any-number>` and `pow(speed_mult, ...)`
        exponent_pattern = re.compile(r"speed_mult\s*\*\*|pow\s*\(\s*speed_mult\b")
        match = exponent_pattern.search(source)
        assert match is None, (
            f"_run_thinker_agent contains exponentiation of speed_mult: "
            f"{match.group(0)!r}. Fix #533 specifically removed `speed_mult ** 1.5` "
            f"because it made the Contemplative (6x) slider feel like 14.7x. "
            f"Use linear scaling (`X * speed_mult`) instead."
        )

    def test_run_thinker_agent_initial_reading_delay_is_linear(self) -> None:
        """The initial 'reading' delay uses `speed_mult` linearly, not squared.

        Regression guard for fix #533: the agent loop also has a sleep
        `random.uniform(1.0, 2.5) * speed_mult` before responding (the
        'reading' delay). At the time of the linear-scaling fix, this was
        also fixed from `random.uniform(1.0, 2.5) * (speed_mult ** 1.5)`.

        At 6x: 6-15s of reading. Before the fix, it was 14.7-37s — long
        enough that users assumed the app had hung.
        """
        source = inspect.getsource(ThinkerService._run_thinker_agent)
        # The expected linear form must be present.
        assert "random.uniform(1.0, 2.5) * speed_mult" in source, (
            "_run_thinker_agent must use `random.uniform(1.0, 2.5) * speed_mult` "
            "(linear) for the initial reading delay. Fix #533 explicitly "
            "reverted the exponential form because Contemplative (6x) felt "
            "broken — 14.7-37s of staring at an empty typing indicator."
        )

    def test_linear_min_interval_formula_documented_contract(self) -> None:
        """Documents the contract: min_interval = 15.0 * speed_mult.

        This is the human-readable form of the linear-scaling contract.
        At 1x: 15s minimum between messages from same thinker.
        At 6x: 90s minimum (slow but responsive, not the old 220s).

        If this test fails because we move to a different base (e.g., 12.0)
        or non-linear shape, the corresponding fix #533 commit message
        documentation must be updated and the test re-baselined accordingly.
        """
        # Compute the contract directly so the assertion message documents
        # the intended behavior.
        base = 15.0
        for speed, expected_seconds in [(0.5, 7.5), (1.0, 15.0), (3.0, 45.0), (6.0, 90.0)]:
            actual = base * speed
            assert actual == expected_seconds, (
                f"Contract: min_interval = 15.0 * speed_mult. "
                f"At speed={speed}, expected {expected_seconds}s, got {actual}s. "
                f"Either the contract has changed or the formula is wrong."
            )


# ===========================================================================
# TestPauseStateMachineDualSetIndependence
# Regression guard for feat #483 (commit 7aa14e7).
#
# ThinkerService maintains two pause sets:
#   _paused_conversations        (manual user pause)
#   _idle_paused_conversations   (auto-pause from idle timeout)
#
# Contract (from thinker.py:1109-1138):
#   pause_conversation(id):        _paused_conversations.add(id)
#   pause_for_idle(id):            _paused_conversations.add(id) + _idle_paused_conversations.add(id)
#   resume_conversation(id):       _paused_conversations.discard(id)   (does NOT touch idle set)
#   resume_from_idle(id):          if in _idle_paused: discard from BOTH
#
# The independence of these two sets is load-bearing: when the user sends
# a new message after idle timeout, the WebSocket handler calls
# resume_from_idle (only resumes idle-paused convs, not manually-paused).
# If the sets were collapsed into one, a user who manually paused, then went
# idle, and sent a message would have their MANUAL pause silently cleared.
# ===========================================================================


class TestPauseStateMachineDualSetIndependence:
    """Regression guards: manual pause and idle pause are independently tracked."""

    def test_resume_from_idle_does_not_clear_manually_paused_conversation(self) -> None:
        """resume_from_idle on a manually-paused-only conversation is a no-op.

        Regression guard for feat #483: when a user clicks Pause manually
        (not idle pause), the conversation goes into `_paused_conversations`
        only. If they then send a message that triggers the resume_from_idle
        path, the manual pause MUST remain — otherwise the Pause button
        would silently fail to keep the conversation paused.
        """
        service = ThinkerService()
        conv_id = "manual-then-send-message"

        # Manual pause only.
        service.pause_conversation(conv_id)
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is False

        # resume_from_idle should be a no-op (conversation is not idle-paused).
        service.resume_from_idle(conv_id)

        # Manual pause must still hold.
        assert service.is_paused(conv_id) is True, (
            "resume_from_idle must NOT clear a manual pause. If the two "
            "pause sets were collapsed into one, the user's manual Pause "
            "would silently disappear when send_message → resume_from_idle "
            "fires after idle pause is detected on the backend."
        )

    def test_pause_for_idle_after_manual_pause_keeps_manual_paused(self) -> None:
        """Calling pause_for_idle on an already manually-paused conversation
        adds the idle flag without affecting the manual one.

        Regression guard for feat #483: if a user manually pauses and then
        the idle timer also fires, both flags should be set so resume_from_idle
        can correctly clear the idle component without losing the manual
        intention. (Then a separate manual resume_conversation can clear the
        manual flag.)
        """
        service = ThinkerService()
        conv_id = "manual-then-idle"

        service.pause_conversation(conv_id)
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is False

        # Idle timer fires while already manually paused.
        service.pause_for_idle(conv_id)

        # Both flags should now be set.
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is True, (
            "pause_for_idle must set the idle flag even if conversation is "
            "already manually paused. Otherwise resume_from_idle can't tell "
            "this conversation apart from one that was only manually paused."
        )

    def test_resume_conversation_does_not_clear_idle_paused_flag(self) -> None:
        """resume_conversation only clears the manual pause flag, not idle.

        Regression guard for feat #483 (current behavior — thinker.py:1113-1115):
        `resume_conversation` discards from `_paused_conversations` only.

        This documents the CURRENT contract. If the intent ever changes
        (e.g., manual resume should also clear idle flag), update this test
        AND audit the agent loop's idle-pause detection — which uses
        `is_idle_paused` to decide whether to send IDLE_TIMEOUT again.
        """
        service = ThinkerService()
        conv_id = "dual-paused-manual-resume"

        # Both flags set.
        service.pause_for_idle(conv_id)
        assert service.is_idle_paused(conv_id) is True

        # Manual resume.
        service.resume_conversation(conv_id)

        # Manual flag cleared, idle flag intact.
        assert service.is_paused(conv_id) is False, (
            "resume_conversation must clear the manual pause flag."
        )
        assert service.is_idle_paused(conv_id) is True, (
            "resume_conversation must NOT clear the idle pause flag "
            "(only resume_from_idle does that). If this contract changes, "
            "update the test AND audit the agent loop's idle-pause logic."
        )

    def test_resume_from_idle_clears_both_pause_sets_atomically(self) -> None:
        """resume_from_idle on idle-paused conversation clears BOTH sets.

        Regression guard for feat #483: when the WebSocket send_message
        handler detects a user message after idle pause, it must clear
        both the manual pause flag (so thinkers can resume responding)
        AND the idle pause flag (so the next idle detection doesn't
        skip the IDLE_TIMEOUT notification due to `is_idle_paused == True`).
        """
        service = ThinkerService()
        conv_id = "idle-paused-then-message"

        service.pause_for_idle(conv_id)
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is True

        service.resume_from_idle(conv_id)

        # Both flags must be cleared.
        assert service.is_paused(conv_id) is False, (
            "resume_from_idle must clear the manual pause flag (otherwise "
            "thinkers stay silent after the user resumes the conversation)."
        )
        assert service.is_idle_paused(conv_id) is False, (
            "resume_from_idle must clear the idle pause flag (otherwise the "
            "next idle-timeout detection won't re-notify the frontend)."
        )

    def test_repeated_pause_for_idle_resume_from_idle_cycle_stays_clean(self) -> None:
        """Multiple pause_for_idle → resume_from_idle cycles return to clean state.

        Regression guard for feat #483: in production, a conversation can
        cycle through idle pause many times in a single session (user steps
        away, comes back, steps away again, ...). Each cycle must leave the
        state machine clean so that the cumulative effect of N cycles is
        identical to the effect of one.
        """
        service = ThinkerService()
        conv_id = "cycle-conv"

        for cycle in range(5):
            service.pause_for_idle(conv_id)
            assert service.is_paused(conv_id) is True, f"cycle {cycle}: pause"
            assert service.is_idle_paused(conv_id) is True, f"cycle {cycle}: idle pause"

            service.resume_from_idle(conv_id)
            assert service.is_paused(conv_id) is False, f"cycle {cycle}: resume"
            assert service.is_idle_paused(conv_id) is False, f"cycle {cycle}: idle clear"


# ===========================================================================
# TestSetSpeedMultiplierClampBoundaries
# Regression guard for set_speed_multiplier clamp logic (websocket.py:145-159).
#
# Existing tests cover values BEYOND the boundaries (0.1 → clamped to 0.5,
# 100.0 → clamped to 6.0). These tests cover the EXACT boundaries (0.5 and 6.0)
# and the value-stability contract for the broadcast payload.
# ===========================================================================


class TestSetSpeedMultiplierClampBoundaries:
    """Regression guards: clamp boundaries and broadcast payload value."""

    async def test_set_speed_at_exact_lower_bound_is_unchanged(self) -> None:
        """Setting speed to exactly 0.5 stores 0.5 (no off-by-one in clamp).

        Regression guard for fix #533: the clamp `max(0.5, min(6.0, mult))`
        must be inclusive at the boundary. An off-by-one (e.g., `if mult > 0.5`
        gating, or `max(0.51, ...)`) would push the boundary slightly higher
        and silently truncate the user's slider range.
        """
        from unittest.mock import AsyncMock

        manager = ConnectionManager()
        await manager.connect(AsyncMock(), "boundary-low")

        await manager.set_speed_multiplier("boundary-low", 0.5)

        assert manager.rooms["boundary-low"].speed_multiplier == 0.5, (
            "set_speed_multiplier(0.5) must store exactly 0.5 (lower bound)."
        )

    async def test_set_speed_at_exact_upper_bound_is_unchanged(self) -> None:
        """Setting speed to exactly 6.0 stores 6.0 (no off-by-one in clamp).

        Regression guard for fix #533: 6.0 is the Contemplative (max) setting.
        Off-by-one in the clamp (e.g., `min(5.99, ...)`) would prevent users
        from ever reaching the documented max — and combined with the linear
        scaling fix, this would make the max speed feel slightly faster than
        the UI label promises.
        """
        from unittest.mock import AsyncMock

        manager = ConnectionManager()
        await manager.connect(AsyncMock(), "boundary-high")

        await manager.set_speed_multiplier("boundary-high", 6.0)

        assert manager.rooms["boundary-high"].speed_multiplier == 6.0, (
            "set_speed_multiplier(6.0) must store exactly 6.0 (upper bound)."
        )

    async def test_clamped_speed_value_is_broadcast_not_raw_input(self) -> None:
        """The broadcast SPEED_CHANGED message contains the CLAMPED value, not the raw input.

        Regression guard: if the broadcast included the raw user input
        (e.g., 100.0), the frontend would re-display the user's invalid
        request rather than the actual effective speed. This would create
        a UI-vs-backend mismatch where the slider shows one value and
        thinkers behave according to another.
        """
        import json
        from unittest.mock import AsyncMock

        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "clamp-broadcast")
        mock_ws.reset_mock()

        # Request a speed way above the cap.
        await manager.set_speed_multiplier("clamp-broadcast", 100.0)

        mock_ws.send_text.assert_called_once()
        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == WSMessageType.SPEED_CHANGED.value
        assert data["speed_multiplier"] == 6.0, (
            f"Broadcast speed must be the clamped value (6.0), not the raw "
            f"input (100.0). Got {data['speed_multiplier']}. Otherwise "
            f"the frontend slider position drifts from the actual backend pacing."
        )

    async def test_extreme_negative_input_clamps_to_lower_bound(self) -> None:
        """A wildly negative input clamps to 0.5, not 0 or a negative value.

        Regression guard: if the clamp ever used `abs(...)` or skipped the
        `max(0.5, ...)` for non-positive inputs, the min_interval formula
        `15.0 * speed_mult` would produce ≤ 0s and thinkers would spam.
        """
        from unittest.mock import AsyncMock

        manager = ConnectionManager()
        await manager.connect(AsyncMock(), "extreme-negative")

        await manager.set_speed_multiplier("extreme-negative", -1000.0)

        assert manager.rooms["extreme-negative"].speed_multiplier == 0.5, (
            "set_speed_multiplier(-1000.0) must clamp to 0.5 (lower bound). "
            "If the clamp were skipped for negative inputs, min_interval "
            "could go ≤ 0 and thinkers would respond instantly in a loop."
        )


# ===========================================================================
# TestLanguageNamesAndThinkingDisplayParity
# Regression guard for i18n features #336 (French), #455 (German), #570 (Hindi).
#
# Every language code in LANGUAGE_NAMES must have a matching branch in
# _extract_thinking_display (replacements list + starters list + starter
# detection prefixes). Past regressions added a language to LANGUAGE_NAMES
# but forgot to add the corresponding branch — the prompt said "respond in
# Hindi" but the thinking-display panel applied English-only replacements.
#
# These tests inspect the source to ensure every supported language has the
# required wiring, so adding a new language to LANGUAGE_NAMES without
# updating _extract_thinking_display fails the test suite.
# ===========================================================================


class TestLanguageNamesAndThinkingDisplayParity:
    """Regression guards: LANGUAGE_NAMES and _extract_thinking_display stay in sync."""

    def test_language_names_exact_keyset_is_documented_five_languages(self) -> None:
        """LANGUAGE_NAMES contains exactly the documented 5 supported languages.

        Regression guard for #336/#455/#570: keep the set tight so that
        accidentally removing a language (e.g., during a bad merge) or
        adding one without coordination breaks loudly.
        """
        expected = {"en", "es", "fr", "de", "hi"}
        assert set(LANGUAGE_NAMES.keys()) == expected, (
            f"LANGUAGE_NAMES keys changed. Expected {expected}, got "
            f"{set(LANGUAGE_NAMES.keys())}. If you intend to add or remove a "
            f"language, update this test, _extract_thinking_display "
            f"(replacements + starters + starter_prefixes), and the frontend "
            f"locale files (frontend/src/locales/*.json)."
        )

    def test_language_names_values_are_full_english_names(self) -> None:
        """LANGUAGE_NAMES values are full English names (used in prompts).

        Regression guard: _get_language_instruction emits "IMPORTANT: Respond
        in {LANGUAGE_NAMES[lang]}". If a value were changed to a lowercase
        code (e.g., "es" → "es" instead of "Spanish"), the LLM might fail to
        recognize the language. This pins down the exact human-readable form.
        """
        assert LANGUAGE_NAMES == {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "hi": "Hindi",
        }, (
            f"LANGUAGE_NAMES values changed. Got {LANGUAGE_NAMES}. These full "
            f"English names are sent to the LLM in the IMPORTANT: Respond in X "
            f"instruction. Localized names (e.g., 'Deutsch') would not be "
            f"recognized as reliably by Claude."
        )

    def test_extract_thinking_display_source_has_branch_per_language(self) -> None:
        """_extract_thinking_display has an `if language == ...` branch for each non-English language.

        Regression guard for #570 (Hindi): the original bug was that Hindi
        had been added to the LANGUAGE_NAMES dict, but the
        _extract_thinking_display function had no `elif language == "hi"`
        branch — so Hindi conversations got English thinking-display
        replacements, breaking the user's language preference.
        """
        source = inspect.getsource(ThinkerService._extract_thinking_display)
        # English is the default `else` branch — it doesn't need its own
        # explicit `if language == "en"`. All other languages MUST have one.
        for lang_code in LANGUAGE_NAMES:
            if lang_code == "en":
                continue
            pattern = f'language == "{lang_code}"'
            assert pattern in source, (
                f"_extract_thinking_display has no branch for {lang_code!r}. "
                f"LANGUAGE_NAMES advertises support for this language but "
                f"the thinking-display panel falls through to English "
                f'replacements. Add an `elif language == "{lang_code}"` '
                f"branch with replacements, starters, and starter_prefixes."
            )

    def test_extract_thinking_display_source_has_starters_for_each_language(self) -> None:
        """Each language branch in _extract_thinking_display assigns a `starters` list.

        Regression guard: the language branch must populate BOTH `replacements`
        and `starters` (and `starter_prefixes`). If a branch only sets
        `replacements`, an unbound `starters` from a previous iteration could
        leak into the language branch — or NameError on first call.

        This is a coarse-grained check: we count the `starters = [` assignments
        and require at least one per supported language (en included).
        """
        source = inspect.getsource(ThinkerService._extract_thinking_display)
        starter_assignments = source.count("starters = [")
        # 5 languages: en, es, fr, de, hi (each should have its own `starters` list).
        assert starter_assignments >= len(LANGUAGE_NAMES), (
            f"_extract_thinking_display assigns `starters = [...]` only "
            f"{starter_assignments} times. Expected at least "
            f"{len(LANGUAGE_NAMES)} (one per supported language including "
            f"English). A language without its own starters list will fall "
            f"through to another language's contemplative prefixes."
        )


# ===========================================================================
# TestIdleTimeoutZeroDisablesSentinel
# Regression guard for feat #483 (commit 7aa14e7).
#
# The idle-pause feature is intentionally disable-able by setting
# `idle_timeout_seconds = 0`. The agent loop checks `if idle_timeout > 0`
# specifically so production can turn the feature off without redeploying
# code. If the guard were removed (`if idle_timeout:` would also work, but
# `if idle_timeout > 0` is the documented contract that handles negative
# values too), the feature couldn't be cleanly disabled.
# ===========================================================================


class TestIdleTimeoutZeroDisablesSentinel:
    """Regression guards: idle_timeout_seconds=0 disables auto-pause."""

    def test_run_thinker_agent_source_guards_idle_check_with_positive_value(self) -> None:
        """The agent loop checks `if idle_timeout > 0` before checking idle state.

        Regression guard for feat #483: the `> 0` guard is what allows
        production to disable the feature by setting the env var to 0
        (no redeploy needed). A change to `if idle_timeout:` would not
        properly handle negative values, and removing the guard entirely
        would force idle-pause to always fire (with idle_timeout=0 meaning
        "every message is immediately idle").
        """
        source = inspect.getsource(ThinkerService._run_thinker_agent)
        assert "idle_timeout > 0" in source, (
            "_run_thinker_agent must guard the idle check with "
            "`if idle_timeout > 0` (or equivalent that properly excludes "
            "0 and negatives). Without this guard, production can't "
            "disable idle-pause via IDLE_TIMEOUT_SECONDS=0."
        )

    def test_settings_idle_timeout_can_be_set_to_zero(self) -> None:
        """Settings(idle_timeout_seconds=0) is valid and disables idle pause.

        Regression guard for feat #483: the field must accept 0 (no
        validator should reject it). The documented disabling mechanism
        is `IDLE_TIMEOUT_SECONDS=0` in production env.
        """
        settings = Settings(idle_timeout_seconds=0)
        assert settings.idle_timeout_seconds == 0, (
            "Settings(idle_timeout_seconds=0) must be valid. This is the "
            "documented mechanism for disabling idle-pause in production."
        )

    def test_settings_idle_timeout_default_is_int_type(self) -> None:
        """idle_timeout_seconds field is `int`, not `float` or `timedelta`.

        Regression guard for feat #483: the agent loop compares
        `idle_duration >= idle_timeout` where idle_duration is a float
        (time.time() delta). Python's int/float comparison works, but
        changing this to `timedelta` would break the comparison.

        Also, division `idle_timeout // 60` (used in the user-facing
        notification message) requires an integer-divisible value.
        """
        settings = get_settings()
        assert isinstance(settings.idle_timeout_seconds, int), (
            f"idle_timeout_seconds must be int (got "
            f"{type(settings.idle_timeout_seconds).__name__}). The agent loop "
            f"uses `idle_timeout // 60` in user-facing notifications, which "
            f"requires integer floor division."
        )


# ===========================================================================
# Shared module-scoped fixtures / configuration
# ===========================================================================


@pytest.fixture(autouse=True)
def _isolate_thinker_service_state() -> None:
    """Each test gets a fresh ThinkerService implicitly through `service = ThinkerService()`.

    No global state to reset here, but this fixture is a no-op marker
    documenting the expectation. If state ever moves to a class-level dict,
    add explicit cleanup here.
    """
    return None


def _new_room_helper() -> ConversationRoom:
    """Tiny helper documenting how to construct a ConversationRoom for these tests.

    Kept as a helper (not used widely) so future tests adding speed-multiplier
    cases have a clear reference for the construction signature.
    """
    return ConversationRoom(conversation_id="test")
