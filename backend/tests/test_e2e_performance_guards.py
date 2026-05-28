"""Source-level guards for E2E test performance hygiene (Thursday QA, May 28 2026).

The E2E suite under ``frontend/e2e/`` is in excellent perf shape today:

- 0 actual ``page.waitForTimeout()`` call sites (only 1 occurrence and it is
  inside a comment that anchors the policy "use Promise.race instead").
- ``playwright.config.ts`` sets ``fullyParallel: true``, ``workers: 4`` in CI,
  ``retries: 2`` in CI, global ``timeout: 90000``, ``expect.timeout: 10000``.
- Every single ``test.describe(`` block in ``*.spec.ts`` opts into
  ``mode: 'parallel'`` explicitly. There is zero ``mode: 'serial'`` usage.
- ``test-fixtures.ts`` exposes ``testWithAuth`` / ``test`` (with the
  ``conversationPage`` fixture) so individual tests skip the slow modal flow,
  saving the documented "15-30s per test" vs. UI-driven setup.

Nothing in the codebase currently locks any of that in. A single PR can:

- silently re-add ``await page.waitForTimeout(3000)`` "just for stability"
- bump ``workers`` to 1 (e.g. when debugging) and forget to revert
- drop ``mode: 'parallel'`` from a new ``test.describe`` block (the default
  is *serial* inside a parallel parent only if you write
  ``describe.configure({ mode: 'serial' })`` — but a new test author who
  reads other files may simply omit the configure call and inadvertently
  break parallelism if config defaults later change)
- "refactor" the docstring comment in ``test-fixtures.ts`` that documents
  why the fixture uses API calls instead of UI, removing the *why* and
  inviting a future contributor to swap it back to the UI flow

These tests pin source-level invariants. They are intentionally cheap (no
browser, no playwright, no node) and run in the same pytest process as the
rest of the backend suite, so a regression surfaces in normal CI without
having to wait for the E2E job.

Test groups (20 tests):
- TestNoWaitForTimeoutAntiPattern (4)
- TestPlaywrightConfigPerfInvariants (5)
- TestEveryDescribeBlockOptsIntoParallel (4)
- TestPerTestTimeoutsStayBounded (4)
- TestE2EFixturesAvailable (3)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Repository layout helpers
#
# Tests in this file inspect files outside ``backend/``. Resolving from
# ``__file__`` keeps them robust regardless of pytest's cwd.
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_DIR = REPO_ROOT / "frontend" / "e2e"
PLAYWRIGHT_CONFIG = REPO_ROOT / "frontend" / "playwright.config.ts"


def _spec_files() -> list[Path]:
    """Return every Playwright spec file under frontend/e2e/.

    Returned sorted so test failures are reproducible across runs.
    """
    files = sorted(E2E_DIR.glob("*.spec.ts"))
    # Sanity: the directory must contain spec files. If this returns empty,
    # something has gone very wrong (renamed directory, accidental deletion)
    # and we want to fail loudly rather than silently pass every guard.
    assert files, f"No *.spec.ts files found under {E2E_DIR}"
    return files


def _strip_line_comments(line: str) -> str:
    """Return the code portion of a line, dropping anything after ``//``.

    This is intentionally simplistic: it does NOT handle ``//`` inside
    strings. For Playwright spec files we only care about whether the
    *call* ``waitForTimeout(`` appears in executable code, and the only
    realistic way a substring like ``waitForTimeout`` ends up in a string
    in this repo is inside a single-line comment that documents the
    anti-pattern. The current sole occurrence is exactly that case.
    """
    idx = line.find("//")
    return line if idx == -1 else line[:idx]


# ---------------------------------------------------------------------------
# TestNoWaitForTimeoutAntiPattern
#
# Playwright's ``page.waitForTimeout(ms)`` introduces a fixed delay regardless
# of what the page is doing. It is the single biggest source of unnecessary
# slowness in long-running E2E suites and is explicitly called out as an
# anti-pattern in ``.claude/agents/qa-improver.md``. These tests pin its
# absence at the call-site level.
# ---------------------------------------------------------------------------


class TestNoWaitForTimeoutAntiPattern:
    """No spec file may *call* page.waitForTimeout — comments are fine."""

    def test_no_waitfortimeout_call_in_any_spec(self) -> None:
        """``page.waitForTimeout(`` must not appear in executable code.

        Mentions inside ``//`` comments are tolerated because they document
        the policy itself. We strip the comment portion of each line before
        searching so a future contributor can keep the docstring-style
        anchor that currently lives in ``settings-edge-cases.spec.ts``.
        """
        offenders: list[str] = []
        for spec in _spec_files():
            for lineno, raw in enumerate(spec.read_text().splitlines(), start=1):
                code = _strip_line_comments(raw)
                if "page.waitForTimeout(" in code or ".waitForTimeout(" in code:
                    offenders.append(f"{spec.name}:{lineno}: {raw.strip()}")
        assert not offenders, (
            "page.waitForTimeout() is an anti-pattern. Use event-driven "
            "waits (expect(...).toBeVisible, waitForResponse, "
            "waitForLoadState('networkidle')) instead. Offenders:\n  " + "\n  ".join(offenders)
        )

    def test_waitfortimeout_substring_appears_at_most_once(self) -> None:
        """Total mentions of the substring (including comments) stay <= 1.

        The single allowed mention is the policy-anchor comment in
        ``settings-edge-cases.spec.ts`` line 137. If a second mention
        creeps in, even in a comment, we want to know — comments often
        precede the call they describe.
        """
        total = 0
        for spec in _spec_files():
            total += spec.read_text().count("waitForTimeout")
        assert total <= 1, (
            f"Found {total} mentions of 'waitForTimeout' across spec files. "
            "Only the anchoring comment in settings-edge-cases.spec.ts is "
            "allowed; review whether a new call was added."
        )

    def test_policy_anchor_comment_is_preserved(self) -> None:
        """The 'use Promise.race instead of waitForTimeout' comment stays.

        This comment is the documented *why* — it tells future authors
        how to wait without ``waitForTimeout``. Removing it makes the
        repo silent about the policy and invites regression.
        """
        target = E2E_DIR / "settings-edge-cases.spec.ts"
        text = target.read_text()
        # Match flexible whitespace and slight rewording, but require the
        # 'Promise.race' alternative to be named so the comment keeps its
        # educational value.
        assert re.search(r"//.*Promise\.race.*waitForTimeout", text, re.IGNORECASE), (
            "Policy anchor comment ('use Promise.race instead of "
            "waitForTimeout') is missing from settings-edge-cases.spec.ts. "
            "Keep it so future authors know the alternative."
        )

    def test_no_raw_setTimeout_in_specs(self) -> None:
        """Browser ``setTimeout(`` should not appear in spec files.

        The same anti-pattern shows up wearing a different hat — instead
        of ``page.waitForTimeout`` someone reaches for the browser-level
        ``setTimeout`` inside a ``page.evaluate``. ``test.setTimeout(...)``
        is *Playwright's* per-test timeout override (different API) and
        is allowed; we explicitly exclude it from this check.
        """
        offenders: list[str] = []
        # Match a bare or method-qualified ``setTimeout(`` call but explicitly
        # exclude the Playwright ``test.setTimeout(`` form, which is the
        # intended escape hatch for marking a single test as slow.
        pattern = re.compile(r"(?<!test\.)(?<![A-Za-z_])setTimeout\s*\(")
        for spec in _spec_files():
            for lineno, raw in enumerate(spec.read_text().splitlines(), start=1):
                code = _strip_line_comments(raw)
                if pattern.search(code):
                    offenders.append(f"{spec.name}:{lineno}: {raw.strip()}")
        assert not offenders, (
            "Raw setTimeout() in E2E specs is an anti-pattern. Use "
            "Playwright's event-driven waits instead. Offenders:\n  " + "\n  ".join(offenders)
        )


# ---------------------------------------------------------------------------
# TestPlaywrightConfigPerfInvariants
#
# The Playwright config is the lever that controls parallelism and timing
# defaults for the whole suite. A single bad commit here can multiply CI
# time across every project. We pin each load-bearing setting.
# ---------------------------------------------------------------------------


class TestPlaywrightConfigPerfInvariants:
    """Pin the performance-critical settings in playwright.config.ts."""

    @pytest.fixture(scope="class")
    def config_text(self) -> str:
        assert PLAYWRIGHT_CONFIG.exists(), f"Expected Playwright config at {PLAYWRIGHT_CONFIG}"
        return PLAYWRIGHT_CONFIG.read_text()

    def test_fully_parallel_is_true(self, config_text: str) -> None:
        """fullyParallel: true is required for cross-file parallelism."""
        assert re.search(r"fullyParallel\s*:\s*true", config_text), (
            "playwright.config.ts must set 'fullyParallel: true' to keep "
            "the suite running tests across files concurrently."
        )

    def test_ci_workers_at_least_four(self, config_text: str) -> None:
        """CI must use >= 4 workers so the 4-core CI box stays saturated."""
        match = re.search(r"workers\s*:\s*process\.env\.CI\s*\?\s*(\d+)", config_text)
        assert match, (
            "Expected ternary 'workers: process.env.CI ? <N> : undefined' in playwright.config.ts."
        )
        worker_count = int(match.group(1))
        assert worker_count >= 4, (
            f"CI worker count is {worker_count}, must be >= 4 to keep CI "
            "E2E job under the 15-minute target."
        )

    def test_global_timeout_capped(self, config_text: str) -> None:
        """Global per-test timeout is <= 90s.

        Letting any single test run longer than 90s is almost always a
        sign the test is doing something it shouldn't (e.g. polling for
        an event that never fires). 90s matches the current config; a
        bump above that should be a deliberate, reviewed change.
        """
        match = re.search(r"^\s*timeout\s*:\s*(\d+)", config_text, re.MULTILINE)
        assert match, "Expected top-level 'timeout:' in playwright.config.ts."
        timeout_ms = int(match.group(1))
        assert timeout_ms <= 90_000, (
            f"Global Playwright timeout is {timeout_ms}ms (> 90000). "
            "Long timeouts hide real test problems and slow CI."
        )

    def test_expect_assertion_timeout_bounded(self, config_text: str) -> None:
        """expect() assertion timeout stays <= 10s.

        Per-assertion timeouts above 10s usually mean a test is waiting
        for something that should be event-driven. The current setting
        is 10000ms — we forbid raising it.
        """
        match = re.search(r"expect\s*:\s*\{\s*timeout\s*:\s*(\d+)\s*\}", config_text)
        assert match, "Expected 'expect: { timeout: <N> }' configuration in playwright.config.ts."
        expect_ms = int(match.group(1))
        assert expect_ms <= 10_000, (
            f"expect() timeout is {expect_ms}ms (> 10000). Lower it; "
            "use targeted per-assertion timeouts when truly needed."
        )

    def test_ci_retries_configured(self, config_text: str) -> None:
        """CI retries must be > 0 so transient flakes don't fail the suite."""
        match = re.search(
            r"retries\s*:\s*process\.env\.CI\s*\?\s*(\d+)\s*:\s*\d+",
            config_text,
        )
        assert match, "Expected 'retries: process.env.CI ? <N> : <M>' in playwright.config.ts."
        ci_retries = int(match.group(1))
        assert ci_retries >= 1, (
            f"CI retries is {ci_retries}; need at least 1 retry so "
            "transient network flakes don't fail the suite."
        )


# ---------------------------------------------------------------------------
# TestEveryDescribeBlockOptsIntoParallel
#
# A ``test.describe`` block, even inside ``fullyParallel: true``, will run
# its inner tests *serially* unless it explicitly opts into parallel mode.
# Today every top-level describe in our spec files does so. These tests
# guard against drift.
# ---------------------------------------------------------------------------


# Match top-level test.describe(, test.describe.skip(, and test.describe.only(.
# These all create the same kind of grouping; ``skip`` simply marks the whole
# block as skipped but the structural / parallelism contract still applies.
_DESCRIBE_PATTERN = re.compile(r"^test\.describe(?:\.(?:skip|only|fixme))?\(", re.MULTILINE)
_PARALLEL_CONFIG_PATTERN = re.compile(
    r"test\.describe\.configure\(\s*\{\s*mode:\s*['\"]parallel['\"]"
)
_SERIAL_CONFIG_PATTERN = re.compile(r"test\.describe\.configure\(\s*\{\s*mode:\s*['\"]serial['\"]")


class TestEveryDescribeBlockOptsIntoParallel:
    """Every spec file with top-level describes must opt into parallel."""

    def test_every_spec_with_top_level_describe_has_parallel_config(
        self,
    ) -> None:
        """Top-level ``test.describe(`` is paired with parallel configure.

        A spec file with at least one top-level describe and no
        ``test.describe.configure({ mode: 'parallel' })`` is flagged.
        Nested describes inherit the parent's mode so we don't require
        one per nested block.
        """
        offenders: list[str] = []
        for spec in _spec_files():
            text = spec.read_text()
            has_top_level = bool(_DESCRIBE_PATTERN.search(text))
            has_parallel = bool(_PARALLEL_CONFIG_PATTERN.search(text))
            if has_top_level and not has_parallel:
                offenders.append(spec.name)
        assert not offenders, (
            "These spec files have test.describe() blocks but no "
            "'describe.configure({ mode: \"parallel\" })' call — they will "
            "run serially inside their describe. Add the configure call:\n"
            "  " + "\n  ".join(offenders)
        )

    def test_no_spec_uses_serial_mode(self) -> None:
        """No spec file may opt into ``mode: 'serial'``.

        Serial mode forces tests in the describe block to run one at a
        time and share state. Today no spec file uses it; we forbid it
        to keep that property.
        """
        offenders: list[str] = []
        for spec in _spec_files():
            if _SERIAL_CONFIG_PATTERN.search(spec.read_text()):
                offenders.append(spec.name)
        assert not offenders, (
            "These spec files use 'mode: serial'. Serial mode kills "
            "parallelism — if tests share state, refactor instead:\n  " + "\n  ".join(offenders)
        )

    def test_every_spec_has_at_least_one_describe(self) -> None:
        """Every spec must wrap its tests in a describe for organization.

        The Playwright reporter groups results by describe, and our
        parallelism contract is per-describe — a top-level ``test(`` at
        file scope is fine functionally but breaks the assumption the
        other guards rely on. Catch it here.
        """
        offenders: list[str] = []
        for spec in _spec_files():
            text = spec.read_text()
            if not _DESCRIBE_PATTERN.search(text):
                offenders.append(spec.name)
        assert not offenders, (
            "These spec files have no top-level test.describe() block. "
            "Wrap tests in a describe so parallelism config applies:\n  " + "\n  ".join(offenders)
        )

    def test_parallel_configure_calls_outnumber_or_match_top_describes(
        self,
    ) -> None:
        """Per file, parallel-configure count >= top-level describe count.

        A spec with N top-level describes must have >= N parallel configures
        (one per describe — Playwright doesn't auto-inherit the mode from
        a sibling configure). This catches the case where a new describe
        is added but the configure line is forgotten.
        """
        offenders: list[str] = []
        for spec in _spec_files():
            text = spec.read_text()
            describes = len(_DESCRIBE_PATTERN.findall(text))
            # Count nested describes too: every test.describe(...) line
            # not preceded by ``.configure``. We use a broader pattern
            # matching ``test.describe(`` at any indentation that is not
            # followed by ``.configure``.
            all_describes = len(re.findall(r"(?<![A-Za-z_])test\.describe\(", text))
            parallels = len(_PARALLEL_CONFIG_PATTERN.findall(text))
            # If file has any describes at all, require at least one
            # parallel configure. We don't require strict equality because
            # nested describes inherit from the outermost parallel config.
            if all_describes > 0 and parallels < 1:
                offenders.append(
                    f"{spec.name}: describes={describes} "
                    f"all_describes={all_describes} parallels={parallels}"
                )
        assert not offenders, (
            "Spec files missing at least one parallel-mode configure:\n  " + "\n  ".join(offenders)
        )


# ---------------------------------------------------------------------------
# TestPerTestTimeoutsStayBounded
#
# Even with a 90s global cap, individual ``timeout: <ms>`` options inside a
# spec can push past the global if a test calls ``test.setTimeout(...)``
# or passes a custom timeout to an action. Cap per-call timeouts.
# ---------------------------------------------------------------------------


_INLINE_TIMEOUT_PATTERN = re.compile(r"timeout:\s*(\d+)")


class TestPerTestTimeoutsStayBounded:
    """Per-call timeout options in spec files stay within budget."""

    def test_no_per_call_timeout_above_global(self) -> None:
        """No ``timeout: N`` in spec files exceeds the global 90s cap."""
        offenders: list[str] = []
        for spec in _spec_files():
            for lineno, raw in enumerate(spec.read_text().splitlines(), start=1):
                code = _strip_line_comments(raw)
                for match in _INLINE_TIMEOUT_PATTERN.finditer(code):
                    value = int(match.group(1))
                    if value > 90_000:
                        offenders.append(
                            f"{spec.name}:{lineno}: timeout={value}ms -> {raw.strip()}"
                        )
        assert not offenders, (
            "Per-call timeouts must not exceed the 90s global cap. "
            "Offenders:\n  " + "\n  ".join(offenders)
        )

    def test_no_test_set_timeout_above_hard_ceiling(self) -> None:
        """``test.setTimeout(N)`` calls in spec files must be <= 120s.

        Individual slow tests may override the 90s global with
        ``test.setTimeout()``, which is the intended escape hatch. We
        still cap the escape hatch at 120s so a runaway 5-minute test
        doesn't sneak in unnoticed. The current ceiling is 120000ms in
        ``chat.spec.ts`` for a (currently skipped) multi-thinker test.
        """
        ceiling = 120_000
        offenders: list[str] = []
        pattern = re.compile(r"test\.setTimeout\(\s*(\d+)\s*\)")
        for spec in _spec_files():
            for lineno, raw in enumerate(spec.read_text().splitlines(), start=1):
                code = _strip_line_comments(raw)
                for match in pattern.finditer(code):
                    value = int(match.group(1))
                    if value > ceiling:
                        offenders.append(f"{spec.name}:{lineno}: setTimeout({value})")
        assert not offenders, (
            f"test.setTimeout() must not exceed {ceiling}ms. Anything "
            "longer indicates the test is doing too much. Offenders:\n  " + "\n  ".join(offenders)
        )

    def test_long_per_call_timeouts_are_concentrated(self) -> None:
        """Per-call timeouts of 60s only live in known race-condition specs.

        60s timeouts are reasonable for ``Promise.race([...])`` patterns
        where any-of-many resolves the wait, but they should not spread
        to every spec. Today only ``thinker-selection-edge.spec.ts`` uses
        them. This test pins that locality.
        """
        allowed = {"thinker-selection-edge.spec.ts"}
        offenders: list[str] = []
        for spec in _spec_files():
            if spec.name in allowed:
                continue
            text = spec.read_text()
            for match in _INLINE_TIMEOUT_PATTERN.finditer(text):
                value = int(match.group(1))
                if value >= 60_000:
                    offenders.append(f"{spec.name}: timeout={value}ms")
        assert not offenders, (
            "60s+ per-call timeouts should be concentrated in known "
            "race-condition specs. New offenders:\n  "
            + "\n  ".join(offenders)
            + "\n\nIf this is intentional, add the file to the allow-list "
            "in test_e2e_performance_guards.py."
        )

    def test_reuse_existing_server_only_outside_ci(self) -> None:
        """``reuseExistingServer`` must be gated to non-CI to keep CI deterministic.

        In CI we always start a fresh server so port reuse from a leftover
        process can't mask real failures. Locally we want to reuse the dev
        server for fast iteration.
        """
        text = PLAYWRIGHT_CONFIG.read_text()
        assert re.search(r"reuseExistingServer\s*:\s*!\s*process\.env\.CI", text), (
            "playwright.config.ts must set "
            "'reuseExistingServer: !process.env.CI' so CI always uses "
            "a fresh server."
        )


# ---------------------------------------------------------------------------
# TestE2EFixturesAvailable
#
# The fixtures in ``test-fixtures.ts`` are the single biggest per-test
# perf win we have: they replace UI-driven setup (15-30s) with API-driven
# setup. We pin their public surface and the *why* docstring.
# ---------------------------------------------------------------------------


class TestE2EFixturesAvailable:
    """Fixture file exists, exports expected names, and documents the why."""

    def test_test_fixtures_file_exports_expected_names(self) -> None:
        """test-fixtures.ts exports ``testWithAuth``, ``test``, ``expect``."""
        path = E2E_DIR / "test-fixtures.ts"
        assert path.exists(), f"Missing fixture file: {path}"
        text = path.read_text()
        assert re.search(r"export\s+const\s+testWithAuth", text), (
            "test-fixtures.ts must export `testWithAuth` so tests can "
            "use the authenticated-page fixture without UI auth flow."
        )
        assert re.search(r"export\s+const\s+test\b", text), (
            "test-fixtures.ts must export `test` (the extended fixture with conversationPage)."
        )
        assert re.search(r"export\s*\{\s*expect\s*\}", text), (
            "test-fixtures.ts must re-export `expect` so importing tests "
            "don't need a separate '@playwright/test' import."
        )

    def test_test_utils_exports_api_setup_helpers(self) -> None:
        """test-utils.ts exports the API-driven setup helpers.

        ``setupAuthenticatedUser`` and ``createAndNavigateToConversation``
        are the building blocks the fixtures call. If they disappear,
        the fixtures stop working and the perf win is lost.
        """
        path = E2E_DIR / "test-utils.ts"
        assert path.exists(), f"Missing helpers file: {path}"
        text = path.read_text()
        for name in (
            "setupAuthenticatedUser",
            "createAndNavigateToConversation",
            "createConversationViaAPI",
        ):
            assert re.search(rf"export\s+async\s+function\s+{name}\b", text), (
                f"test-utils.ts must export `{name}` — it's the API-driven "
                "alternative to UI-driven setup."
            )

    def test_fixture_docstring_explains_perf_motivation(self) -> None:
        """The 'saves 15-30s' note in test-fixtures.ts must stay.

        This sentence is the documented reason the fixtures use API calls
        instead of the UI modal flow. Removing it invites someone to
        "simplify" by going back to ``createConversationViaUI``. Pin it.
        """
        text = (E2E_DIR / "test-fixtures.ts").read_text()
        assert re.search(
            r"saves\s+15-30s|saves\s+~?20s|saves\s+\d+\s*-?\s*\d*\s*s",
            text,
            re.IGNORECASE,
        ), (
            "test-fixtures.ts must keep the docstring explaining that "
            "API-driven setup saves ~15-30s per test vs the UI modal "
            "flow. This is the *why* — preserve it."
        )
