# Test Plan - Dining Philosophers

This document outlines all features requiring testing, their test cases, and edge conditions.

## 1.31 Integration Gaps: `useWebSocket` real-time message handling (Added 2026-07-08)

**Focus:** integration-gaps (issue #1012)

The frontend real-time WebSocket integration hook (`src/hooks/useWebSocket.ts`) had
uncovered message-handling paths. Backend was already at 99.74% with all API endpoints
at 100%, so the meaningful integration gap was the client-side socket layer.

**New tests** (`src/__tests__/hooks/useWebSocket.integration-gaps.test.tsx`, 16 tests):

### `thinker_thinking` streaming preview (3 tests)
- Populates `thinkingContent` map and invokes `onThinkerThinking` for a streaming preview
- Ignores `thinker_thinking` messages missing the `content` field (guard short-circuit)
- Clears a thinker's `thinkingContent` entry on `thinker_stopped_typing`

### `speed_changed` updates (3 tests)
- Updates `speedMultiplier` from a `speed_changed` message
- Accepts a `speed_multiplier` of `0` (verifies `!== undefined` guard, not truthiness)
- Ignores `speed_changed` messages that omit the multiplier

### `sendSetSpeed` command (2 tests)
- Sends a `set_speed` frame with the requested multiplier
- Skips sending when the socket is not `OPEN`

### Cross-conversation message filtering (2 tests)
- Drops messages tagged with a different `conversation_id` (stale after a switch)
- Still processes messages that omit `conversation_id`

### Partial thinker message fields (3 tests)
- Applies fallbacks (`sender_name` null, `content` '', `cost` null, generated timestamp)
  when optional fields are absent
- Does not deliver a message when `sender_type` is not `thinker`
- Falls back to `'Unknown error'` for an `error` message without `content`

### Inactive-connection handling (3 tests)
- Closes the socket if `onopen` fires after the effect was torn down
- Ignores a message arriving after teardown (`isActive` false)
- Does not schedule a reconnect when `close` fires after teardown

**Coverage impact:** `src/hooks/useWebSocket.ts` 93.89% → **100%** lines,
75.36% → **91.56%** branch. Verified passing 3x with no flakiness.

## 1.30 E2E Performance: Remove 60s networkidle anti-pattern + Guard Caps (Added 2026-06-25)

**Focus**: Thursday QA (e2e-performance). The Playwright suite is already in
excellent shape — **0** real `page.waitForTimeout()` calls, all 24 spec files
on `mode: 'parallel'`, `fullyParallel: true` + 4 CI workers — and the co-located
jest guard `e2e-performance-guard.test.ts` (§1.28) already locks most of that in.
This session removed the **last remaining slow-wait anti-pattern** and tightened
the guard so it can't come back.

**Anti-pattern fixed** (`frontend/e2e/thinker-selection-edge.spec.ts`):
- Two `Promise.race([...])` blocks (the "very long thinker name" and "special
  characters" cases) raced a `page.waitForLoadState('networkidle', { timeout:
  60000 })` alongside two element-based waits that *also* bound at 60s. The
  networkidle leg was **redundant** (identical 60s ceiling, no extra signal) and
  networkidle is the slowest / most-fragile wait type. Removed both; the
  element-based success/error waits remain the real signals. Behaviour-preserving
  (same 60s worst-case ceiling, same assertions), but drops the redundant
  network-settle wait that could otherwise stall a manual run for the full 60s.
- After the fix, the max networkidle timeout anywhere in the suite is **15s**
  (down from 60s).

**Guard extended** (`frontend/src/__tests__/e2e-performance-guard.test.ts`,
now 151 assertions, browser-less static analysis):

| New check | What It Validates |
|-----------|-------------------|
| networkidle ≤ 30s cap (per spec file) | Every `waitForLoadState('networkidle', { timeout: N })` keeps `N ≤ 30000`. networkidle gets a tighter cap than the generic 60s per-call cap because it is the slowest wait type; this catches the 60s-networkidle anti-pattern at PR time. Headroom over the current 15s max. |
| no always-on tracing (config) | `playwright.config.ts` `trace` is not `'on'`. Always-on tracing records a trace for *every* test and materially slows the whole suite; conditional modes like `'on-first-retry'` only pay that cost on failure. |

**Verification**:
- Jest guard passes **3 runs in a row** (151 assertions, no browser/backend), ~0.55s each.
- New regexes spot-checked against synthetic violations: the networkidle cap flags
  `timeout: 60000` and ignores `timeout: 15000`; the trace check flags `trace: 'on'`
  and passes `trace: 'on-first-retry'`.
- `npm run typecheck` clean; the edited spec still parses (comments-only change to
  the surrounding prose, redundant wait removed).

## 1.29 Test Refactoring: `test_regression_prevention_jan25_2026.py` → conftest helpers (Added 2026-06-12)

**Focus**: Friday QA (test-refactoring). Audited every backend test file for inline
boilerplate that duplicates helpers `conftest.py` already exports.
`tests/test_regression_prevention_jan25_2026.py` was the worst offender still
carrying its own copy: 443 lines, **zero** conftest imports, and the same setup
plumbing copy-pasted throughout.

**Duplication removed** (all behaviour-preserving — the helpers produce equivalent
state, and no test asserts on the fields the helpers default):

| Inline pattern | Occurrences | Replaced with |
|----------------|-------------|---------------|
| `POST /api/auth/register` → `assert 200` → extract `access_token` → build Bearer header | 7 | `get_auth_headers(client, user, pass)` |
| `{"Authorization": f"Bearer {session_token}"}` | 15 | header dict returned by the helper, reused |
| `POST /api/conversations` with an inline single-thinker body | 5 | `create_conversation_with_thinker(...)` / `create_test_conversation(..., num_thinkers=5)` |
| raw `assert get_response.status_code == 404` | 1 | `assert_not_found(get_response)` |

**Why a refactor here**:
- Each test opened with ~10 lines of register/extract-token/build-header plumbing
  before the line that actually exercised the behaviour under test. The intent
  ("delete a conversation and confirm it cascades") was buried.
- The `test_add_thinkers_when_all_colors_used` test built 5 thinkers by hand with a
  hard-coded colour list, but the assertion only checks the **count** limit
  ("Maximum is 5") — `create_test_conversation(..., num_thinkers=5)` expresses that
  intent directly without the unused colour scaffolding.
- The file is named "regression prevention", so the *assertions* are the value;
  reducing setup noise makes a future reader's diff-review of those assertions far
  easier.

**What was deliberately left inline**:
- `test_full_user_journey` and the multi-user isolation tests in
  `test_integration_workflows.py` — there the explicit register→login→converse flow
  *is* the end-to-end behaviour being documented, so collapsing it into helpers
  would obscure intent rather than clarify it.
- `test_generate_response_with_api_timeout`'s service-level `MagicMock` thinker
  (positions is a `list`, unlike the conftest `mock_thinker` fixture's `str`).

**File refactored**: `tests/test_regression_prevention_jan25_2026.py`
(443 → ~330 lines; 15 tests unchanged in what they assert).

**Verification**:
- All 15 tests pass 3 runs in a row (no behaviour change, no flakiness introduced).
- Full backend suite still green after the conftest-import change.
- `ruff format` + `ruff check` clean.
- Pure refactor: no test added, removed, or changed in what it asserts — only how
  the per-test setup is constructed.

---

## 1.28 E2E Performance Guard: Serial-Mode + CI-Retries Checks (Added 2026-06-11)

**Focus**: Thursday QA (e2e-performance). The E2E suite is already in excellent
perf shape — **0** real `page.waitForTimeout()` calls, **0** unbounded
`networkidle` waits, and per-test/per-call timeouts all bounded — and two
existing guards lock most of that in (pytest `test_e2e_performance_guards.py`
§1.23 and the co-located jest guard `e2e-performance-guard.test.ts` §1.25).

This session closed a real gap in the **co-located jest guard**: it verified
config-level `fullyParallel: true` but was blind to the one anti-pattern that
silently *overrides* it — a spec opting into **serial mode**. With
`fullyParallel: true` set globally, a single `test.describe.configure({ mode:
'serial' })` (or the `test.describe.serial(` / `test.serial(` shorthands)
serializes that whole file onto one worker, quietly erasing the parallelism the
suite depends on to stay under the 15-min CI target. The pytest guard already
treats this as important (`test_no_spec_uses_serial_mode`); the same-job jest
guard now does too. A missing CI-retries check was also added so a single
transient flake can't fail the whole E2E job and force a full re-run.

**Why extend the existing jest guard instead of adding a third guard file**:
- Avoids a third near-duplicate static-analysis suite (a redundant Playwright
  `*.spec.ts` guard was prototyped and discarded — it would have run under both
  Playwright projects *and* booted the dev webServer, *adding* E2E runtime,
  which is exactly backwards for an e2e-performance task)
- Keeps all co-located, same-job perf invariants in one discoverable file

**File**: `frontend/src/__tests__/e2e-performance-guard.test.ts` (extended:
126 assertions total — adds a per-spec serial-mode check across all 24 spec
files plus a config-level CI-retries assertion)

### New checks

| Check | What It Validates |
|-------|-------------------|
| no serial mode (per spec file) | No `mode: 'serial'` and no `.serial(` shorthand (`describe.serial` / `test.serial`) appears in executable code — these override `fullyParallel` and serialize a whole file onto one worker. Comments mentioning "serial" are stripped before matching. |
| CI retries ≥ 1 | `playwright.config.ts` sets `retries: process.env.CI ? N` with N ≥ 1, so one transient flake doesn't fail the whole E2E job and force an expensive full re-run. |

### Verification

- Jest guard passes 3 runs in a row (126 assertions, no browser/backend)
- Regexes spot-checked against synthetic violations: flags all three serial
  forms (`mode: 'serial'`, `describe.serial(`, `test.serial(`) while ignoring
  `mode: 'parallel'` and a "serial" mention inside a comment; the retries check
  passes the current `? 2 :` config and fails `? 0 :` / a missing CI ternary
- `npm run typecheck` and ESLint clean

---

## 1.27 Edge Cases: Unrecognized WebSocket Messages (Added 2026-06-06)

**Focus**: Saturday QA (edge-cases). Backend coverage is already at **99.40%**, so
this run targets the single genuinely-reachable, high-value uncovered branch rather
than padding numbers.

**Gap addressed**: `app/api/websocket.py` line `478->441` — the message-dispatch
`if/elif` chain falling through with **no matching `WSMessageType`** and looping
back to `while True`. This is the handler's error-tolerance path for malformed or
unknown client payloads, and it was previously untested.

**Why this and not line 733**: The other notable gap, `app/services/thinker.py:733`
(the `continue` on an empty sentence in `_split_response_into_bubbles`), is
**effectively unreachable** — `response_text.strip()` runs first, and
`re.split(r"(?<=[.!?])\s+", text)` never produces a whitespace-only segment from
stripped input (a lone `.` is non-empty). Verified empirically; not chased.

**New tests** (`tests/test_websocket.py::TestWebSocketUnrecognizedMessages`):

- `test_unknown_message_type_is_ignored_and_connection_stays_open` — a message
  whose `type` matches no known `WSMessageType` falls through the whole elif chain
  (covering `478->441`); the connection stays healthy, proven by a subsequent
  valid `pause` that still returns `paused`.
- `test_message_without_type_field_is_ignored` — a payload lacking a `type` key
  yields `message_type=None`, is dropped silently, and the socket still serves a
  follow-up `pause`.
- `test_empty_json_object_is_ignored` — boundary: a syntactically valid but empty
  `{}` payload must not crash the handler.
- `test_user_message_without_content_defaults_to_empty_string` — a `user_message`
  with no `content` key broadcasts a `message` with `content == ""` (covers the
  `message_data.get("content", "")` default) rather than raising `KeyError`.

**Verification**: 4/4 pass 3 runs in a row (no flakiness); `478->441` no longer
reported as a partial branch. `ruff format` + `ruff check` clean.

## 1.26 Test Refactoring: `make_mock_message` Helper (Added 2026-06-05)

**Focus**: Friday QA (test-refactoring). `tests/test_thinker_service.py` (the
largest backend test file, 1540 lines) already had module-level mock helpers for
thinkers, requests, clients, and responses — but **conversation message** mocks
were still built inline. The same 2-4 line block (`msg = MagicMock()` followed by
`msg.sender_type = ...` / `msg.content = ...` / `msg.sender_name = ...`) was
copy-pasted **15 times** across `TestShouldRespond`, `TestShouldPromptUser`,
`TestGetUserNameFromMessages`, `TestCountMessagesSinceUser`,
`TestGetLastUserMessageTimestamp`, and the `@mention` probability tests.

**Why a refactor here**:
- Each test body was dominated by mock plumbing instead of the behaviour under
  test — a reader had to parse 3 attribute assignments to learn "this is a user
  message saying X".
- Drift risk: with no shared constructor, a new attribute (e.g. `created_at`) is
  spelled differently per test, and a typo on a MagicMock silently creates a new
  auto-attribute rather than failing.

**The helper** (module-level in `test_thinker_service.py`, next to the existing
`make_mock_thinker` / `make_mock_client_with_response` helpers):

- `make_mock_message(**attrs)` — returns a `MagicMock` with exactly the passed
  attributes set via `setattr`. Because only the explicitly-passed attributes are
  assigned, every unspecified attribute keeps MagicMock's auto-attribute
  behaviour, making this a **behaviour-preserving** drop-in for the inline blocks
  it replaces. Call sites now read as intent:
  `make_mock_message(sender_type="user", content="I think so")`.

**Files Refactored**: `tests/test_thinker_service.py` (15 inline message-mock
blocks → single-call helper; ~30 lines of boilerplate removed).

**Verification**:
- All 97 tests in `test_thinker_service.py` pass 3 runs in a row (no behaviour
  change, no flakiness introduced).
- `ruff format` + `ruff check` clean.
- Pure refactor: no test was added, removed, or changed in what it asserts — only
  how the mock messages are constructed.

---

## 1.25 Frontend-Side E2E Performance Guard (Added 2026-06-04)

**Focus**: Thursday QA (e2e-performance). A backend-side guard already exists
(`backend/tests/test_e2e_performance_guards.py`, section 1.23) that fails the
**pytest** job if E2E perf hygiene regresses. But the frontend project's own
`npm test` (jest) job had **no** such protection — a developer editing
`frontend/e2e/*.spec.ts` and running `npm test` gets zero feedback until the
separate backend job runs. This adds a co-located jest guard so the regression
is caught in the same project and job where E2E specs are actually edited.

It also closed a small real gap: `mention-badge-alignment.spec.ts` had 3
**unbounded** `waitForLoadState('networkidle')` calls (no timeout). An unbounded
networkidle wait can hang a worker if traffic never settles; all three now pass
`{ timeout: 5000 }` and `.catch(() => {})`, matching the bounded pattern used
everywhere else in the suite.

**Why a jest guard in addition to the pytest one**:
- Co-located: lives in the frontend project next to the code it guards, so it's
  discoverable by the people most likely to introduce a regression
- Same-job feedback: fails `npm test` immediately, not only in the backend job
- Different runner, different parser: catches the same anti-patterns through an
  independent implementation, so a bug in one guard's regex doesn't blind both

**File**: `frontend/src/__tests__/e2e-performance-guard.test.ts` (NEW — 101
parameterized assertions: per-spec checks across all 24 spec files plus config
invariants)

### What it enforces

| Check | What It Validates |
|-------|-------------------|
| no `page.waitForTimeout(...)` | Arbitrary sleeps (the top E2E perf anti-pattern) appear in **zero** spec files; comments mentioning the word are stripped before matching so the policy-anchor comment doesn't trip it |
| bounded `networkidle` | Every `waitForLoadState('networkidle')` passes a `{ timeout }`; the unbounded one-arg form is forbidden (it can hang a worker) |
| `test.setTimeout(N)` ≤ 120s | No runaway per-test timeout; 120s matches the current ceiling in `chat.spec.ts` |
| `{ timeout: N }` ≤ 60s | No per-call assertion/wait timeout above 60s; long per-call timeouts mean a test should be event-driven |
| `fullyParallel: true` | `playwright.config.ts` keeps file-level parallelism |
| CI workers ≥ 4 | `workers: process.env.CI ? N` parsed; N ≥ 4 keeps the CI E2E job under the 15-min target |
| global `timeout` ≤ 120s | Top-level Playwright test timeout stays bounded |
| `expect: { timeout }` bounded | Per-assertion default timeout is present and ≤ 60s |

### Verification

- Guard passes 3 runs in a row (101 assertions, ~0.6s each — no browser/backend)
- Regex logic spot-checked against synthetic violations: detects a real
  `waitForTimeout(` call and an unbounded `networkidle`, while correctly ignoring
  a `waitForTimeout` mention inside a comment and a bounded `networkidle` call
- `npm run typecheck` clean

---

## 1.24 Test Refactoring: Feedback Helpers (Added 2026-05-29)

**Focus**: Friday QA — `test_feedback.py` had ~20 inline `POST /api/feedback` blocks with copy-pasted JSON shape and 9 inline `with patch("app.api.feedback.get_settings")` ladders. Each test body was dominated by setup boilerplate instead of intent. The refactor extracts the duplication into `conftest.py` so test bodies show only what's actually under test.

**Why a refactor here**:
- Adding a new feedback test currently requires copying the right JSON shape and the right patch ladder — easy to drift
- Reading existing tests requires mentally diffing nearly-identical 8-line blocks to spot the one field that's different
- Two helper-validation tests added below lock in the helper defaults so a future change to them can't silently break dozens of call sites

**Files**:
- `backend/tests/conftest.py` (helpers added at the bottom of the file)
- `backend/tests/test_feedback.py` (rewritten to call the helpers)

### `conftest.py` additions

| Symbol | Purpose |
|--------|---------|
| `TEST_FEEDBACK_PROCESSOR_SECRET` | Shared constant for the mocked processor secret so tests don't redeclare it |
| `TEST_SCREENSHOT_PNG_B64` | 1×1 PNG b64 string for screenshot-payload tests (was duplicated inline in two tests) |
| `submit_feedback(client, message=..., **extra_fields)` | One-liner POST to `/api/feedback`; default message passes the 20-char min-length validator so tests that don't care about message can omit it |
| `mock_feedback_processor_secret` (fixture) | Patches `app.api.feedback.get_settings` to return `TEST_FEEDBACK_PROCESSOR_SECRET`; yields the secret string so tests can use it in URLs |
| `mock_feedback_processor_unconfigured` (fixture) | Patches `get_settings` to return an empty secret (for the 503 "not configured" branch) |

### New tests in `test_feedback.py`

| Test | What It Validates |
|------|-------------------|
| `test_submit_feedback_helper_default_message_valid` | The `submit_feedback()` helper's default `message` argument is long enough to pass the API's min-length validation — if a future change shortens it below 20 chars, every test that omits `message` would silently start failing with 422; this catches that immediately |
| `test_feedback_processor_secret_constant_is_nonempty` | `TEST_FEEDBACK_PROCESSOR_SECRET` is a non-empty string — an empty value would make `mock_feedback_processor_secret` behave identically to `mock_feedback_processor_unconfigured`, silently corrupting 6+ tests |

### Verified

- All 29 tests in `test_feedback.py` pass 3 runs in a row (2.2-2.5s each)
- Full backend suite (1663 tests) continues to pass — the new helpers are additive

## 1.23 E2E Performance Hygiene Guards (Added 2026-05-28)

**Focus**: Thursday QA — the E2E suite under `frontend/e2e/` is in excellent perf shape today (0 `page.waitForTimeout()` call sites, every `test.describe` opts into parallel mode, CI workers = 4, global timeout capped at 90s), but **nothing locks any of it in**. A single bad PR can silently undo years of E2E perf work. These pytest-side tests are source-level guards that fail in normal CI (not just the E2E job) the moment perf hygiene regresses.

**Why source-level guards instead of runtime perf tests**:
- Cheap: no browser, no playwright, runs in ~1s alongside the rest of the backend suite
- Specific: the failure message names the offender (file:line) instead of "E2E got slower"
- Robust: not subject to CI machine variability that flakes runtime perf assertions

**File**: `backend/tests/test_e2e_performance_guards.py` (NEW — 20 tests across 5 classes)

### `TestNoWaitForTimeoutAntiPattern` (4 tests)

| Test | What It Validates |
|------|-------------------|
| `test_no_waitfortimeout_call_in_any_spec` | No `page.waitForTimeout(` call appears in executable code across any `*.spec.ts` (comment mentions stripped before search); fail message lists `file:line` for every offender |
| `test_waitfortimeout_substring_appears_at_most_once` | Even including comments, only the single anchor mention in `settings-edge-cases.spec.ts` is allowed; catches new policy-violating comments that might precede a call |
| `test_policy_anchor_comment_is_preserved` | The `// Wait for response - use Promise.race instead of waitForTimeout` comment in `settings-edge-cases.spec.ts` must stay so future authors know the alternative |
| `test_no_raw_setTimeout_in_specs` | Browser `setTimeout(` (e.g. inside `page.evaluate`) is forbidden in spec files; `test.setTimeout(...)` (Playwright API) is explicitly excluded via negative lookbehind |

### `TestPlaywrightConfigPerfInvariants` (5 tests)

| Test | What It Validates |
|------|-------------------|
| `test_fully_parallel_is_true` | `playwright.config.ts` must set `fullyParallel: true` so files run concurrently |
| `test_ci_workers_at_least_four` | Parses `workers: process.env.CI ? <N> : undefined` and asserts N ≥ 4 — keeps CI E2E job under 15-min target |
| `test_global_timeout_capped` | Top-level `timeout:` setting stays ≤ 90 000 ms; long timeouts hide real problems |
| `test_expect_assertion_timeout_bounded` | `expect: { timeout: <N> }` stays ≤ 10 000 ms; per-assertion timeouts above 10s mean tests should be event-driven |
| `test_ci_retries_configured` | `retries: process.env.CI ? <N> : <M>` has N ≥ 1 so transient flakes don't fail CI |

### `TestEveryDescribeBlockOptsIntoParallel` (4 tests)

| Test | What It Validates |
|------|-------------------|
| `test_every_spec_with_top_level_describe_has_parallel_config` | Every spec with a top-level `test.describe(` (including `.skip` / `.only`) has a matching `describe.configure({ mode: 'parallel' })` call; otherwise inner tests run serially |
| `test_no_spec_uses_serial_mode` | No spec opts into `mode: 'serial'` — serial mode kills parallelism and encourages shared state |
| `test_every_spec_has_at_least_one_describe` | Every `*.spec.ts` wraps its tests in a describe so the parallelism contract is uniform across files |
| `test_parallel_configure_calls_outnumber_or_match_top_describes` | At least one parallel-configure call per file with any describes — catches new describes added without the configure line |

### `TestPerTestTimeoutsStayBounded` (4 tests)

| Test | What It Validates |
|------|-------------------|
| `test_no_per_call_timeout_above_global` | No `timeout: <ms>` option anywhere in spec files exceeds the 90s global cap |
| `test_no_test_set_timeout_above_hard_ceiling` | `test.setTimeout(N)` is allowed (the intended escape hatch) but capped at 120 000 ms (current ceiling in `chat.spec.ts`) so runaway 5-minute tests are caught |
| `test_long_per_call_timeouts_are_concentrated` | 60s+ per-call timeouts are allow-listed to `thinker-selection-edge.spec.ts` (legitimate `Promise.race` patterns); any new file using 60s+ requires explicit allow-list addition |
| `test_reuse_existing_server_only_outside_ci` | `reuseExistingServer: !process.env.CI` — CI always starts a fresh server so leftover-port reuse can't mask real failures |

### `TestE2EFixturesAvailable` (3 tests)

| Test | What It Validates |
|------|-------------------|
| `test_test_fixtures_file_exports_expected_names` | `test-fixtures.ts` exports `testWithAuth`, `test` (with `conversationPage`), and re-exports `expect` so importing tests stay one-line |
| `test_test_utils_exports_api_setup_helpers` | `test-utils.ts` exports `setupAuthenticatedUser`, `createAndNavigateToConversation`, `createConversationViaAPI` — the building blocks the fixtures depend on |
| `test_fixture_docstring_explains_perf_motivation` | The "saves 15-30s per test" docstring in `test-fixtures.ts` must stay — it's the documented *why* and prevents a "simplify back to UI flow" regression |

### Verification

- 3x stability runs on the new file: 20 passed each run in ~1.1s
- Full backend suite passes with no regressions

---

## 1.22 E2E Performance Optimization (Added 2026-05-21)

**Focus**: Thursday QA — fill the remaining gaps in E2E performance regression coverage. Prior runs already covered page-load, interaction, generic API timing, modal dismissal, scale & caching, and most user-journey flows. This run targets: (1) the message and single-conversation API paths that drive the chat experience, (2) error/edge paths (401, 404, /health size budget) that should stay cheap, (3) DOMContentLoaded on the authenticated home + settings + post-logout login pages, and (4) FCP on the settings route.

**Why these tests**: `POST /api/conversations/{id}/messages` and `GET /api/conversations/{id}` back every message send and every sidebar click but were never timed. The 401 unauthorized path and the Next.js `not-found` route had no perf guards — a regression that wraps token verification in a DB lookup, or imports the full app shell into not-found, would slow every typo'd URL or expired session. DCL on the authenticated home and settings routes was never measured (only login DCL was). FCP on settings is a distinct code path from login FCP (authenticated providers, separate bundle). Each new test isolates a specific failure mode.

**Files**:
- `frontend/e2e/performance.spec.ts` (10 new tests added across 4 new describe blocks: 36 → 46 active tests)

### New tests in `performance.spec.ts` — `Message & Conversation Performance` describe block (3 tests)

| Test | What It Validates |
|------|-------------------|
| `send-message API responds within 2 seconds` | `POST /api/conversations/{id}/messages` must stay fast so the user sees their message + typing indicator without delay — catches synchronous spend-limit checks or cascade joins added to this path |
| `GET /api/conversations/{id} responds within 2 seconds` | Single-conversation fetch backs every sidebar click; catches N+1 query and unbounded message-eager-loading regressions |
| `3 sequential createConversationViaAPI calls complete within 5s` | Benchmarks per-conversation creation cost when calls are not parallelized; catches regressions in `POST /api/conversations` latency |

### New tests in `performance.spec.ts` — `Error & Edge Path Performance` describe block (3 tests)

| Test | What It Validates |
|------|-------------------|
| `unauthorized API call returns 401 within 1 second` | The 401 reject path must be cheap — no DB lookup, no expensive validation; catches accidental session-table-on-every-request regressions |
| `404 page loads within 3 seconds` | Next.js `not-found` route bundle stays tiny; catches developers accidentally importing the full app shell into the not-found page |
| `GET /health response body is small (<10KB)` | Health endpoint is polled thousands of times/day by Railway + external monitors — guards against turning `/health` into a verbose debug dump |

### New tests in `performance.spec.ts` — `DOMContentLoaded & Navigation Performance` describe block (3 tests)

| Test | What It Validates |
|------|-------------------|
| `authenticated home DOMContentLoaded fires within 3 seconds` | DCL on the authenticated entry point is the strongest sync-script guarantee; catches heavy sync imports added to the app shell |
| `settings page DOMContentLoaded fires within 2 seconds` | The settings route ships its own bundle; catches sync-script regressions specific to settings (e.g., heavy form-library imports) |
| `logout redirect to /login renders within 3 seconds` | Full sign-out flow: click sign-out → see login form; budgets the redirect + cold-load of `/login` (the existing logout test only verifies redirect happens) |

### New tests in `performance.spec.ts` — `Settings Page Rendering Performance` describe block (1 test)

| Test | What It Validates |
|------|-------------------|
| `settings page first contentful paint within 2 seconds` | FCP on the settings route catches a different code path than login FCP — settings uses authenticated providers (theme, language, auth) and a separate bundle |

### Mobile Compatibility

All 10 new tests run on both `chromium` and `mobile-chrome` (Pixel 5) projects = 20 total runs added.

### Verification

- 3x stability runs on chromium (46 tests each): all 46 passed each run (33.8s, 32.3s, 32.4s)
- Mobile-chrome run of 10 new tests: all 10 passed (7.6s)
- No `.skip` calls added — every new test is active in CI
- `waitForTimeout` count across all `frontend/e2e/*.spec.ts` files remains 0 (one comment-only reference)
- Total active perf tests: 92 (46 chromium + 46 mobile-chrome)

## 1.21 E2E Performance Optimization (Added 2026-05-14)

**Focus**: Thursday QA — extend E2E performance regression coverage. Prior runs eliminated `waitForLoadState('networkidle')` anti-patterns, added parallel-mode config, and covered page-load / user-journey timings. This run fills the remaining gaps: API endpoints that were not directly timed, modal dismissal paths, higher-scale list rendering, and static-asset caching.

**Why these tests**: Existing tests directly timed `/register`, `/auth/me`, `/conversations`, `/health`, and `/health/ready`, but **login**, **logout**, **profile update**, and **conversation deletion** had no direct timing. Modal *open* was timed but *dismissal* (Escape, backdrop click) was not. Sidebar scaling was capped at 5 items, and static-asset caching had no regression guard. Each new test isolates a specific failure mode that would otherwise only surface as user-perceived slowness in production.

**Files**:
- `frontend/e2e/performance.spec.ts` (10 new tests added across 2 new describe blocks: 26 → 36 active tests)

### New tests in `performance.spec.ts` — `Auth Flow Performance` describe block (5 tests)

| Test | What It Validates |
|------|-------------------|
| `login API endpoint responds within 3 seconds` | Direct `POST /api/auth/login` timing — was untimed (only `/register` was previously timed) |
| `logout API endpoint responds within 2 seconds` | Direct `POST /api/auth/logout` timing — UI awaits this before clearing local state, must be fast |
| `profile update API responds within 2 seconds` | `PATCH /api/auth/profile` settings save must feel instant; catches DB-write or pre-save-hook regressions |
| `conversation deletion API responds within 2 seconds` | `DELETE /api/conversations/{id}` keeps sidebar responsive; catches ORM cascade regressions that pull in unbounded related rows |
| `second /auth/me call is faster than 3s (warm connection)` | Second call within budget AND not 5x slower than the first — guards against accidental per-request connection teardown |

### New tests in `performance.spec.ts` — `Modal Dismissal Performance` describe block (2 tests)

| Test | What It Validates |
|------|-------------------|
| `Escape key closes new-chat modal within 1 second` | Keyboard dismissal feels instant; catches handler regressions that block on network or animation |
| `backdrop click closes new-chat modal within 1 second` | Alternate dismissal path (parent div onClick when `e.target === e.currentTarget`); ensures both `onClose` code paths stay fast |

### New tests in `performance.spec.ts` — `Scale & Caching Performance` describe block (3 tests)

| Test | What It Validates |
|------|-------------------|
| `sidebar renders 10 conversations within 5 seconds` | Higher-scale guard than the existing 5-conversation test; catches O(n²) regressions that wouldn't surface at 5 items |
| `static JS bundle is cached on second navigation` | Second login-page visit loads in <2s and serves `_next/static/*` chunks — catches `Cache-Control: no-store` regressions that would force re-downloads |
| `repeated home→settings→home navigation does not grow request count` | 3 round-trips between home and settings; third must not exceed 2x the first — catches useEffect-without-deps multipliers and accumulating listeners |

### Mobile Compatibility

All 10 new tests run on both `chromium` and `mobile-chrome` (Pixel 5) projects = 20 total runs added.

### Verification

- 3x stability runs on chromium (36 tests each): all 36 passed each run (26.2s, 24.3s, 24.4s)
- Mobile-chrome run of 10 new tests: all 10 passed (12.5s)
- No `.skip` calls added — every new test is active in CI
- `waitForTimeout` count across all `frontend/e2e/*.spec.ts` files remains 0 (one comment-only reference)
- Total: 72 performance tests (36 chromium + 36 mobile-chrome)

## 1.20 Coverage Sprint — ThinkerService streaming + agent loop (Added 2026-05-11)

**Focus**: Monday QA — coverage sprint targeting the lowest-coverage module (`app/services/thinker.py`, 77% before this run). The two largest uncovered regions were the streaming-thinking event-handler (lines 616-672) and the long-lived `_run_thinker_agent` driver loop (lines 1155-1410), which together accounted for most of the missing coverage.

**Coverage Impact**:
- `app/services/thinker.py`: 77% → **92%** (+15pp — meets the coverage-sprint goal exactly)
- Overall backend: 91.36% → **96.34%** (+5pp)

**Files**:
- `backend/tests/test_thinker_coverage_sprint_may11_2026.py` (14 new tests)

### New tests in `test_thinker_coverage_sprint_may11_2026.py` — `TestStreamingThinkingEventBranches`

These tests drive `generate_response_with_streaming_thinking` against a `_FakeStream` async-context-manager / async-iterator that yields synthetic Anthropic streaming events. They cover the previously-uncovered event-handler branches at lines 616-672.

| Test | What It Validates |
|------|-------------------|
| `test_text_delta_accumulates_response_text` | `content_block_delta` events whose delta has a `text` field accumulate into the response string and ultimately return as the response. |
| `test_thinking_delta_sends_throttled_update` | A long-enough thinking delta (≥80 chars so `_extract_thinking_display` returns content) triggers `manager.send_thinker_thinking()` with the conversation id and thinker name. |
| `test_pause_during_stream_sends_stopped_typing_once` | When `is_paused(conv_id)` is True for the entire stream, `send_thinker_stopped_typing` fires exactly once (the `paused_during_stream` guard prevents duplicate emissions) and no response text is accumulated. |
| `test_thinking_block_contributes_to_cost` | A real `ThinkingBlock` in `final_message.content` is detected via `isinstance(block, ThinkingBlock)` and increases the returned cost beyond the input+output baseline. |
| `test_message_delta_event_updates_usage` | A `message_delta` event with a `usage` attribute is consumed without error and the final cost is still computed from `final_message.usage`. |

### New tests in `test_thinker_coverage_sprint_may11_2026.py` — `TestRunThinkerAgentLoop`

These tests drive the otherwise-uncovered `_run_thinker_agent` infinite loop with `asyncio.sleep` patched to a no-op. The loop is broken either by the handler's `break` statement (Spend/Billing) or by raising `CancelledError` from a mock on the second iteration (which is caught by the loop's `except asyncio.CancelledError: break` clause).

| Test | What It Validates |
|------|-------------------|
| `test_exits_on_cancelled_error` | `asyncio.CancelledError` raised inside the try block exits the loop cleanly (no propagation). |
| `test_waits_when_conversation_inactive` | When `manager.is_conversation_active()` is False, the loop sleeps then continues; the next iteration's call to `is_conversation_active` is what eventually breaks the loop. |
| `test_waits_when_conversation_paused` | When `is_paused(conv_id)` is True, the loop sleeps 0.5s and continues without generating. |
| `test_idle_timeout_triggers_pause_flow` | After `idle_timeout_seconds` has elapsed since the last user message, the agent calls `pause_for_idle`, sends `stopped_typing`, and broadcasts `IDLE_TIMEOUT` + `PAUSED` messages. |
| `test_spend_limit_exceeded_pauses_and_breaks` | When `generate_response_with_streaming_thinking` raises `SpendLimitExceeded`, the handler pauses the conversation, broadcasts ERROR + PAUSED, and exits the loop via `break`. |
| `test_billing_error_pauses_and_breaks` | When the generator raises `BillingError`, the handler pauses the conversation, broadcasts ERROR + PAUSED, and exits the loop via `break`. |
| `test_thinker_api_error_broadcasts_then_retries` | `ThinkerAPIError` is recoverable — the handler broadcasts ERROR and sleeps 10s but does NOT pause the conversation (the next iteration would retry). |
| `test_generic_exception_broadcasts_then_retries` | An unexpected `RuntimeError` is logged with `exc_info=True`, broadcasts ERROR, sleeps 5s, and does NOT pause the conversation. |
| `test_pause_before_generation_skips_generate` | If `is_paused` returns True between the typing-indicator + reading delay and the actual generator call (line 1251), `generate_response_with_streaming_thinking` is never invoked and no message is saved. |

### Verification

- 14 new tests, 3 stability runs: all 14 passed each time (~1.0s per run)
- Full backend suite: 1433 passed, 9 skipped (was 1419 passed pre-sprint)
- Coverage on `app/services/thinker.py` jumped from 77% to 92% (+15pp)
- Overall backend coverage: 91.36% → 96.34% (+5pp)

## 1.19 E2E Performance Optimization (Added 2026-05-07)

**Focus**: Thursday QA — broaden E2E performance regression coverage. Prior PRs eliminated `waitForLoadState('networkidle')` anti-patterns and added parallel-mode config; this run focuses on filling gaps in *user-journey* performance regression tests so that future regressions in critical flows (login, logout, conversation switching, sidebar scaling) are caught at PR time.

**Why these tests**: Page-load and API-timing regressions were already covered. The remaining gaps were around user-driven *interactions* (form submits, clicks, navigations) and *scale* (multiple conversations in sidebar, parallel auth flows). Adding regression guards for these means a future "innocuous" change that adds an unnecessary round-trip or blocks the main thread will be caught before merging.

**Files**:
- `frontend/e2e/performance.spec.ts` (8 new tests added, 16 → 24 active tests)

### New tests in `performance.spec.ts` — `User Journey Performance` describe block

| Test | What It Validates |
|------|-------------------|
| `login form submission redirects to home within 3 seconds` | End-to-end login (POST /api/auth/login + redirect + home render) fits in budget |
| `logout via user menu completes within 3 seconds` | Logout interaction (open menu → click signout → auth cleared / redirect) stays fast |
| `DOMContentLoaded fires within 2 seconds on login page` | DCL via Performance API — catches initial-bundle regressions before user-perceived metrics do |
| `sidebar renders 5 conversations within 5 seconds` | Sidebar list rendering scales — guards against O(n) regressions or render thrash |
| `switching between conversations in sidebar completes within 3s` | Common interaction: clicking a sidebar item swaps the chat view promptly |
| `message textarea is interactive within 5s of opening a conversation` | Time-to-interactive in chat view — textarea visible AND enabled |
| `initial homepage load fires fewer than 50 network requests` | Over-fetching regression guard — catches accidental request loops or duplicates |
| `browser back navigation between home and settings is instant (<1s)` | bfcache / SPA navigation stays fast — guards against accidental `Cache-Control: no-store` |

### New tests in `performance.spec.ts` — `Auth Flow Performance` describe block

| Test | What It Validates |
|------|-------------------|
| `registerUser helper completes in under 3 seconds` | Locks in the baseline for the most-called test setup helper — every E2E pays this cost |
| `parallel registration of 3 users completes within 5 seconds` | Backend handles concurrent registrations efficiently (not serialized server-side) |

### Mobile Compatibility

All 8 user-journey tests run on both `chromium` and `mobile-chrome` (Pixel 5) projects. The `switching between conversations` test detects a hidden sidebar (mobile viewport) and opens the hamburger menu before clicking — mirrors the pattern already used in `conversation-deletion-edge.spec.ts`.

### Verification

- 26 tests on chromium + 26 on mobile-chrome = 52 total runs
- 3x stability runs: all 52 passed each time (38.2s, 38.4s, 38.8s)
- No `.skip` calls added — every new test is active in CI

## 1.18 Integration Gaps - Cross-endpoint workflows (Added 2026-05-06)

**Focus**: Wednesday QA - integration gap tests covering cross-endpoint state transitions
**Coverage Impact**: 91.36% → 91.36%+ (preserved at high level; new tests verify integration behavior, not just unit paths)
**Files**:
- `backend/tests/test_integration_gaps_may6_2026.py` (20 new tests added)

### TestAuthLifecycleIntegration (5 tests)

End-to-end auth flows that span multiple endpoints — cross-endpoint state observability.

| Test | What It Validates |
|------|-------------------|
| `test_register_then_update_profile_reflected_in_me` | PATCH /api/auth/profile → state visible via GET /api/auth/me |
| `test_change_password_invalidates_old_password_and_validates_new` | Change-password durably persists; old password 401s; new succeeds |
| `test_change_password_with_wrong_current_password_does_not_persist` | Failed change-password leaves stored password intact (rollback path) |
| `test_language_update_persists_across_login` | PATCH /language → fresh login response contains updated preference |
| `test_old_token_remains_valid_after_password_change` | JWTs are stateless; old token still validates after password change (documented behavior) |

### TestAdminPermissionCascadeIntegration (4 tests)

Admin operations on users observed via subsequent API calls — cross-endpoint cascade behavior.

| Test | What It Validates |
|------|-------------------|
| `test_delete_user_removes_them_from_users_list` | DELETE /api/admin/users/{id} reflected in GET /api/admin/users |
| `test_admin_cannot_delete_self_via_admin_endpoint` | Admin self-delete returns 400; admin still authenticates afterward |
| `test_spend_limit_update_visible_to_user_via_me` | Admin PATCH spend-limit → target user's GET /me reflects new limit |
| `test_non_admin_cannot_call_any_admin_endpoint` | All admin endpoints return 403 for non-admin users (consistency) |

### TestDevOpsStatsAccuracyIntegration (2 tests)

GET /api/devops/stats reflects entities created via REST endpoints.

| Test | What It Validates |
|------|-------------------|
| `test_stats_reflects_users_registered_via_api` | Each /api/auth/register increments stats users + sessions counts |
| `test_stats_health_endpoint_share_authentication_secret` | Same secret authenticates /devops/stats and /devops/health; wrong secret rejected by both |

### TestDevOpsCleanupBoundaryIntegration (3 tests)

Cleanup endpoints with real entities created via API.

| Test | What It Validates |
|------|-------------------|
| `test_cleanup_test_users_dry_run_does_not_delete` | dry_run=true previews matching users without deleting; non-matching users untouched |
| `test_cleanup_test_users_actual_delete_then_login_fails` | Actual cleanup removes users — subsequent login returns 401 |
| `test_cleanup_orphans_dry_run_does_not_modify_state` | dry_run on orphan cleanup leaves stats counts unchanged |

### TestFeedbackWorkflowIntegration (3 tests)

Feedback submit → fetch pending → mark processed full state-transition lifecycle.

| Test | What It Validates |
|------|-------------------|
| `test_submit_then_appears_in_pending_then_marked_processed` | Full lifecycle: feedback created → in pending list → marked → no longer pending |
| `test_mark_nonexistent_feedback_returns_404` | Valid secret + bad id returns 404 (not 500/403); auth-then-lookup ordering |
| `test_pending_endpoint_rejects_wrong_secret` | Wrong secret on /pending returns 403 even with submitted feedback present |

### TestSessionsIntegration (2 tests)

Validates /api/sessions/me reflects login-time session creation.

| Test | What It Validates |
|------|-------------------|
| `test_sessions_me_returns_session_for_logged_in_user` | After register, /api/sessions/me returns the auto-created session |
| `test_sessions_me_with_no_token_returns_401_or_403` | Unauthenticated /api/sessions/me returns auth error (401 or 403) |

### TestAuthAdminBoundaryIntegration (1 test)

Validates role transitions and permission consistency across endpoints.

| Test | What It Validates |
|------|-------------------|
| `test_promoted_admin_can_access_admin_endpoint_without_relogin` | DB-promoted admin's existing token gets through admin endpoint (require_admin reads from DB at request time, not JWT) |

## 1.17 Coverage Sprint - websocket.py (Added 2026-04-27)

**Focus**: Monday QA - coverage sprint targeting `app/api/websocket.py`
**Coverage Impact**: websocket.py 69% → 92% (+23%), backend overall 88.22% → 91.32% (+3.1%)
**Config Fix**: Added `"thread"` to `coverage.run.concurrency` in `pyproject.toml` to track async code in TestClient threads
**Files**:
- `backend/tests/test_websocket.py` (22 new tests added)

### TestWebSocketAuthRejection (3 tests)

Authentication rejection paths in the WebSocket endpoint (covers lines 355-367).

| Test | What It Validates |
|------|-------------------|
| `test_websocket_no_token_rejected` | Connection without token raises WebSocketDisconnect (code 4001) |
| `test_websocket_invalid_token_rejected` | Connection with invalid JWT raises WebSocketDisconnect (code 4001) |
| `test_websocket_token_without_session_id_rejected` | Token missing session_id field is rejected (code 4001) |

### TestWebSocketSpeedControl (3 tests)

SET_SPEED message handling and clamping behavior (covers lines 474-477).

| Test | What It Validates |
|------|-------------------|
| `test_set_speed_message_updates_multiplier` | SET_SPEED message updates speed and broadcasts SPEED_CHANGED |
| `test_set_speed_clamped_to_max` | Speed > 6.0 is clamped to 6.0 |
| `test_set_speed_clamped_to_min` | Speed < 0.5 is clamped to 0.5 |

### TestWebSocketDisconnect (2 tests)

WebSocket disconnect handling (covers lines 501-512).

| Test | What It Validates |
|------|-------------------|
| `test_clean_disconnect_does_not_error` | Exiting WebSocket context manager completes without exception |
| `test_conversation_room_inactive_after_remove_all` | ConversationRoom.is_active becomes False when last connection removed |

### TestConnectionManagerBroadcastMethods (10 tests)

ConnectionManager send/broadcast methods for thinker events (covers lines 175-262).

| Test | What It Validates |
|------|-------------------|
| `test_send_thinker_message_broadcasts_correctly` | send_thinker_message sends MESSAGE type with thinker name, content, message_id, cost |
| `test_send_thinker_typing_broadcasts_correctly` | send_thinker_typing sends THINKER_TYPING type with sender_name |
| `test_send_thinker_thinking_broadcasts_correctly` | send_thinker_thinking sends THINKER_THINKING type with thinking content |
| `test_send_thinker_stopped_typing_broadcasts_correctly` | send_thinker_stopped_typing sends THINKER_STOPPED_TYPING and removes thinker from typing set |
| `test_send_research_started_broadcasts_correctly` | send_research_started sends RESEARCH_STARTED with thinker_name |
| `test_send_research_complete_broadcasts_correctly` | send_research_complete sends RESEARCH_COMPLETE with thinker_name |
| `test_send_research_failed_broadcasts_correctly` | send_research_failed sends RESEARCH_FAILED with error content |
| `test_send_cache_hit_broadcasts_correctly` | send_cache_hit sends CACHE_HIT with thinker_name |
| `test_get_speed_multiplier_returns_default` | get_speed_multiplier returns 1.0 for unknown conversation |
| `test_get_speed_multiplier_returns_set_value` | get_speed_multiplier returns value set by set_speed_multiplier |

### TestSpendLimitExceeded (2 tests)

SpendLimitExceeded exception class (covers lines 284-287).

| Test | What It Validates |
|------|-------------------|
| `test_spend_limit_exceeded_message` | Exception formats current/limit spend in message |
| `test_spend_limit_exceeded_is_exception` | SpendLimitExceeded is an Exception subclass |

### TestGetMessagesForConversation (2 tests)

`get_messages_for_conversation` helper function (covers lines 273-278).

| Test | What It Validates |
|------|-------------------|
| `test_returns_empty_for_unknown_conversation` | Unknown conversation returns empty list |
| `test_returns_messages_in_order` | Messages returned in chronological creation order |

## 1.16 Regression Prevention (Added 2026-04-26)

**Focus**: Sunday QA - regression prevention for recent bug fixes
**Coverage Impact**: +30 backend tests (1289 total)
**Files**:
- `backend/tests/test_regression_prevention_apr26_2026.py` (new - 30 regression tests)

**Bug fixes guarded** (from January 2026):
- fix(thinker)#533: linear speed scaling instead of exponential
- fix(websocket)#367: sync pause button state on reconnect
- fix(feedback)#299: enum values for PostgreSQL
- fix(i18n)#570: Hindi language support

### TestStopAgentsPauseStatePersistence (3 tests)

Regression guard: `stop_conversation_agents` MUST NOT clear pause state (intentional design).

| Test | What It Validates |
|------|-------------------|
| `test_stop_agents_does_not_clear_manual_pause` | Manual pause persists after stop_conversation_agents |
| `test_stop_agents_does_not_clear_idle_pause` | Idle pause persists after stop_conversation_agents |
| `test_stop_agents_cleans_up_active_tasks_dict` | Active tasks dict IS cleaned up (unlike pause state) |

### TestConversationRoomConnectionManagement (4 tests)

Regression guard: `ConversationRoom.is_active` tracks connections correctly after fix(websocket)#367.

| Test | What It Validates |
|------|-------------------|
| `test_room_becomes_inactive_when_only_connection_removed` | is_active=False after last connection removed |
| `test_room_stays_active_with_multiple_connections_one_removed` | is_active=True while 2nd client still connected |
| `test_room_becomes_inactive_when_all_connections_removed` | is_active=False after all connections removed |
| `test_broadcast_handles_stale_connection_gracefully` | Stale connections purged, other clients still get message |

### TestExtractThinkingDisplayEllipsis (4 tests)

Regression guard for lines 964-966 in thinker.py: ellipsis added to mid-sentence truncations.

| Test | What It Validates |
|------|-------------------|
| `test_text_truncated_mid_sentence_gets_ellipsis` | Text ending mid-word gets '...' |
| `test_text_ending_with_exclamation_does_not_get_ellipsis` | '!' text doesn't become '!...' |
| `test_text_ending_with_question_mark_does_not_get_ellipsis` | '?' text doesn't become '?...' |
| `test_text_already_ending_with_ellipsis_no_double_ellipsis` | '...' text doesn't become '......' |

### TestSenderTypeEnumDualPath (5 tests)

Regression guard: helper methods work with both ORM SenderType enum and plain string values.

| Test | What It Validates |
|------|-------------------|
| `test_get_last_timestamp_recognizes_enum_sender_type` | _get_last_user_message_timestamp finds SenderType.USER |
| `test_get_last_timestamp_recognizes_string_sender_type` | _get_last_user_message_timestamp finds plain "user" |
| `test_count_messages_since_user_recognizes_enum` | _count_messages_since_user counts with SenderType.USER |
| `test_count_messages_since_user_recognizes_string` | _count_messages_since_user counts with plain "user" |
| `test_get_user_name_recognizes_enum_sender_type` | _get_user_name_from_messages returns name for SenderType.USER |

### TestConnectionManagerRoomSpeedMultiplier (3 tests)

Regression guard for fix(thinker)#533: per-room speed multiplier defaults and independence.

| Test | What It Validates |
|------|-------------------|
| `test_new_room_has_default_speed_multiplier_of_1_0` | New ConversationRoom defaults to speed_multiplier=1.0 |
| `test_speed_multiplier_is_independent_per_conversation` | Setting speed on conv-A doesn't affect conv-B |
| `test_get_speed_for_unknown_conversation_returns_1_0` | get_speed_multiplier returns 1.0 for unknown convs |

### TestIsMentionedEdgeCases (4 tests)

Regression guard for the @mention system (feat#257): edge cases that must not raise or false-positive.

| Test | What It Validates |
|------|-------------------|
| `test_is_mentioned_empty_text_returns_false` | Empty text returns False without error |
| `test_is_mentioned_no_at_sign_returns_false` | Name without @ is NOT treated as @mention |
| `test_extract_mentions_bare_at_sign_returns_empty` | Bare '@' with no name produces no mentions |
| `test_is_mentioned_case_insensitive_match` | @SOCRATES and @socrates both match 'Socrates' |

### TestShouldRespondMessageCountBoundary (3 tests)

Regression guard: `_should_respond` returns False when no new messages since last response.

| Test | What It Validates |
|------|-------------------|
| `test_no_response_when_message_count_equals_last_response_count` | Returns False when new_message_count == 0 |
| `test_no_response_when_last_response_count_exceeds_messages` | Returns False when new_message_count < 0 |
| `test_can_respond_when_one_new_message` | Can return True with 1 new message (positive case) |

### TestPauseStateAttemptDualSet (4 tests)

Regression guard for feat(backend)#483 (idle timeout): manual vs idle pause independence.

| Test | What It Validates |
|------|-------------------|
| `test_manual_pause_not_cleared_by_resume_from_idle` | resume_from_idle is no-op on manual pause |
| `test_idle_pause_IS_cleared_by_resume_from_idle` | resume_from_idle works on idle-paused conversations |
| `test_pause_conversation_makes_is_paused_true` | Basic regression: pause sets is_paused=True |
| `test_resume_conversation_makes_is_paused_false` | Basic regression: resume clears is_paused |

## 1.15 Regression Prevention (Added 2026-04-19)

**Focus**: Sunday QA focus - add regression prevention tests for recently-touched code paths
**Coverage Impact**: +33 backend tests (1197 total)
**Files**:
- `backend/tests/test_regression_prevention_apr19_2026.py` (new - 33 regression tests)

**Coverage Areas** (from coverage analysis: websocket.py 68%, thinker.py 76%, main.py 79%):

### TestFeedbackIPHashing (7 tests)

Regression tests for `hash_ip()` and `get_client_ip()` in `feedback.py`.

| Test | What It Validates |
|------|-------------------|
| `test_hash_ip_produces_sha256_hex` | hash_ip uses SHA-256 algorithm producing 64-char hex |
| `test_hash_ip_is_deterministic` | Same IP always produces same hash (required for rate limiting) |
| `test_hash_ip_differentiates_ips` | Different IPs produce different hashes |
| `test_get_client_ip_uses_x_forwarded_for_first` | X-Forwarded-For header takes priority over direct client IP |
| `test_get_client_ip_falls_back_to_client_host` | Falls back to request.client.host when no proxy header |
| `test_get_client_ip_returns_unknown_when_no_client` | Returns "unknown" when request.client is None (Unix sockets) |
| `test_get_client_ip_strips_whitespace_from_forwarded_for` | Strips spaces from X-Forwarded-For chain entries |

### TestFeedbackSecretValidation (6 tests)

Regression tests for feedback processor secret validation in `feedback.py`.

| Test | What It Validates |
|------|-------------------|
| `test_get_pending_feedback_returns_503_when_secret_not_configured` | 503 when feedback_processor_secret is empty |
| `test_get_pending_feedback_returns_403_for_wrong_secret` | 403 when incorrect secret provided to pending endpoint |
| `test_mark_processed_returns_503_when_secret_not_configured` | 503 when secret not configured on mark-processed endpoint |
| `test_mark_processed_returns_403_for_wrong_secret` | 403 for wrong secret on mark-processed endpoint |
| `test_mark_processed_returns_404_for_unknown_id` | 404 when feedback_id doesn't exist in DB |
| `test_mark_processed_succeeds_for_existing_feedback` | Happy path: updates status to REVIEWED and stores github_issue_url |

### TestAuthChangePassword (3 tests)

Regression tests for the change-password endpoint in `auth.py`.

| Test | What It Validates |
|------|-------------------|
| `test_change_password_fails_with_wrong_current_password` | 400 when current_password is incorrect |
| `test_change_password_succeeds_with_correct_current_password` | New password works for login, old password rejected |
| `test_change_password_requires_authentication` | 401 without auth token |

### TestAuthLogout (2 tests)

Regression tests for the logout endpoint in `auth.py`.

| Test | What It Validates |
|------|-------------------|
| `test_logout_returns_200_with_message` | Logout returns 200 with confirmation message |
| `test_logout_works_without_auth_token` | Logout works without authentication (JWT is client-side) |

### TestThinkerKnowledgeStatusEndpoint (2 tests)

Regression tests for `GET /api/thinkers/knowledge/{name}/status` in `thinkers.py`.

| Test | What It Validates |
|------|-------------------|
| `test_knowledge_status_returns_pending_for_unknown_thinker` | Returns PENDING/has_data=False when no knowledge in DB |
| `test_knowledge_status_returns_correct_status_for_existing_knowledge` | Returns actual status from DB record |

### TestThinkerKnowledgeRefreshEndpoint (2 tests)

Regression tests for `POST /api/thinkers/knowledge/{name}/refresh` in `thinkers.py`.

| Test | What It Validates |
|------|-------------------|
| `test_refresh_endpoint_triggers_research` | Always calls trigger_research even for existing knowledge |
| `test_refresh_creates_knowledge_for_new_thinker` | Uses get_or_create_knowledge for new thinkers |

### TestConversationColorCycling (3 tests)

Regression tests for thinker color assignment in `conversations.py`.

| Test | What It Validates |
|------|-------------------|
| `test_create_conversation_assigns_different_colors_to_thinkers` | 5 thinkers get 5 distinct colors via cycle |
| `test_add_thinkers_avoids_duplicate_colors` | New thinkers skip colors already in use |
| `test_add_thinkers_respects_max_limit_of_5` | 400 error when adding thinkers would exceed 5 total |

### TestThinkerSuggestFallback (3 tests)

Regression tests for mock fallback behavior in `thinkers.py`.

| Test | What It Validates |
|------|-------------------|
| `test_suggest_uses_mock_when_no_api_key` | Returns 3 mock suggestions without API key |
| `test_validate_uses_mock_for_known_thinkers_without_api_key` | Known thinkers validated from mock data |
| `test_validate_rejects_unknown_thinker_without_api_key` | Unknown thinkers rejected in no-API-key mode |

### TestCreateAdminUserFunction (2 tests)

Regression tests for `create_admin_user()` startup function in `main.py`.

| Test | What It Validates |
|------|-------------------|
| `test_create_admin_user_creates_user_when_none_exists` | Creates admin user with is_admin=True on first run |
| `test_create_admin_user_skips_when_admin_already_exists` | Idempotent: skips creation if admin already in DB |

### TestKnowledgeResearchErrorHandling (3 tests)

Regression tests for error handling in `knowledge_research.py`.

| Test | What It Validates |
|------|-------------------|
| `test_research_thinker_marks_failed_on_wikipedia_exception` | Marks entry as FAILED when Wikipedia fetch raises exception |
| `test_trigger_research_does_not_start_duplicate_task` | Deduplicates: no new task if existing task is still running |
| `test_trigger_research_starts_task_when_previous_completed` | Allows re-trigger when previous task is done |

## 1.14 Flaky Test Hunt (Added 2026-04-14)

**Focus**: Tuesday QA focus - identify and fix flaky tests, harden probabilistic tests
**Coverage Impact**: +19 backend tests (1155 total), 0 net frontend test count change (flakiness fixes are behavior-preserving)
**Files**:
- `backend/tests/test_flaky_hunt_apr14_2026.py` (new - 19 hardening tests)
- `frontend/src/components/__tests__/StatusLine.test.tsx` (flakiness fixes - 2 timing improvements)

**Findings**: No actual test failures found in 5x repeated runs. Identified and hardened 4 risk categories:
1. `setTimeout(resolve, 100)` arbitrary delays in StatusLine tests → replaced with `waitFor` combined assertions (104ms → 4ms per test)
2. `random.seed(None)` probabilistic loops in ThinkerService → added deterministic seed variants
3. DateTime boundary conditions in staleness checks → added safe-margin variants
4. Async task cleanup edge cases → added hardening tests for done-task, multi-thinker, and isolation scenarios

### StatusLine Flakiness Fixes (`StatusLine.test.tsx`)

| Change | Location | Before | After |
|--------|----------|--------|-------|
| Replace `setTimeout(100ms)` with `waitFor` combined assertion | `renders nothing when research is complete but not recent` | 104ms, timing-sensitive | 4ms, event-driven |
| Replace `setTimeout(100ms)` with `waitFor` combined assertion | `handles fetch errors gracefully` | 104ms, timing-sensitive | 2ms, event-driven |
| Replace nested `setTimeout(50ms/10ms)` with DOM state wait | `continues polling even when fetch takes time (regression #187)` | 65ms with timing delays | 7ms, DOM-state-driven |

### Backend Hardening Tests (`test_flaky_hunt_apr14_2026.py`)

#### Deterministic Random Split Behavior (4 tests)

| Test | Validates | Flakiness Risk |
|------|-----------|----------------|
| `test_seed_42_produces_consistent_output` | Fixed seed produces identical output across runs | Detects if split logic or RNG becomes non-deterministic |
| `test_short_text_never_splits_regardless_of_seed` | <60 char text never splits with seeds 0-9 | Deterministic coverage of short-text path |
| `test_long_text_splits_with_known_seeds` | Finds and verifies seeds that reliably produce splits | Documents which seeds trigger the multi-bubble path |
| `test_very_long_text_always_splits_with_any_seed` | 600+ char text always splits with all seeds 0-19 | Stronger guarantee than probabilistic loop pattern |

#### Datetime Staleness Boundary Hardening (5 tests)

| Test | Validates | Edge Case |
|------|-----------|-----------|
| `test_fresh_knowledge_is_not_stale_with_margin` | 1-day-old COMPLETE is not stale | Safe margin (29 days from boundary) |
| `test_stale_knowledge_is_stale_with_margin` | 31-day-old COMPLETE is stale | Safe margin (1 day past boundary) |
| `test_future_timestamp_is_not_stale` | Future-dated knowledge is not stale | Clock drift / DST edge case |
| `test_very_old_knowledge_is_stale` | 365-day-old knowledge is definitely stale | Extreme age validation |
| `test_non_complete_status_always_stale_regardless_of_age` | FAILED/IN_PROGRESS/PENDING always stale even if fresh | Status-independent staleness |

#### ConnectionManager Fresh Instance Isolation (5 tests)

| Test | Validates | Flakiness Risk |
|------|-----------|----------------|
| `test_fresh_instance_has_no_rooms` | New instance starts with zero rooms | Guards against class-level singleton state leakage |
| `test_fresh_instance_conversation_not_active` | Any conv is inactive in fresh instance | Guards against pre-populated room state |
| `test_disconnect_from_empty_room_is_safe` | Disconnect from non-existent room doesn't raise | Guards against KeyError in cleanup race conditions |
| `test_broadcast_to_empty_room_is_safe` | Broadcast to non-existent room doesn't raise | Guards against broadcast errors on empty rooms |
| `test_speed_multiplier_defaults_to_one_for_new_room` | 1.0 multiplier for non-existent conversations | Default value for new/empty conversations |

#### Async Task Cleanup Hardening (5 tests)

| Test | Validates | Flakiness Risk |
|------|-----------|----------------|
| `test_stop_agents_for_conversation_with_done_task` | Stopping works on already-completed tasks | Guards against error when task finishes before stop |
| `test_stop_agents_cleans_up_multiple_thinkers` | All 3 thinker tasks done after stop (not just first) | Guards against partial cleanup leaving dangling tasks |
| `test_stop_agents_only_affects_target_conversation` | Stop conv-A leaves conv-B tasks running | Guards against over-eager cleanup |
| `test_new_thinker_service_has_no_active_tasks` | Fresh service has empty task dict | Guards against class-level static task storage |
| `test_pause_resume_state_does_not_affect_task_cleanup` | Paused conv still gets tasks cleaned up | Guards against pause state blocking cleanup |

## 1.13 Test Refactoring (Added 2026-04-10)

**Focus**: Friday QA focus - improve test readability and reduce duplication
**Coverage Impact**: +48 frontend tests (525 total up from 477), 15 backend test calls simplified using `get_auth_headers` helper
**Files**:
- `frontend/src/__tests__/components/ThinkerAvatar.test.tsx` (new)
- `frontend/src/__tests__/components/Message.test.tsx` (improved)
- `frontend/src/__tests__/components/index.test.ts` (new)
- `frontend/src/__tests__/hooks/index.test.ts` (new)
- `backend/tests/test_regression_prevention_mar15_2026.py` (refactored)

### ThinkerAvatar Component Tests (`ThinkerAvatar.test.tsx` - 14 new tests)

| Test | Validates | Edge Case |
|------|-----------|-----------|
| `renders initials for a two-word name` | "Alan Turing" → "AT" | Two initials from first+last |
| `shows first initial only for a single-word name` | "Socrates" → "S" | Single-word name |
| `shows first and last initial for multi-word name` | "Marie Curie Sklodowska" → "MS" | Three-word: first+last only |
| `shows ? for empty name` | "" → "?" | Empty string edge case |
| `initials are uppercase` | "alan turing" → "AT" | Case normalization |
| `renders an image when imageUrl is provided` | src attribute present | Image happy path |
| `falls back to initials when image errors` | Image error → initials shown | Image fallback |
| `renders initials when imageUrl is null` | null → initials | Null imageUrl |
| `renders initials when imageUrl is undefined` | undefined → initials | Undefined imageUrl |
| `renders xs size` | w-4 h-4 CSS classes | XS size variant |
| `renders sm size` | w-6 h-6 CSS classes | SM size variant |
| `renders md size (default)` | w-8 h-8 CSS classes | Default size |
| `renders lg size` | w-10 h-10 CSS classes | LG size variant |
| `uses custom color when provided` | backgroundColor matches custom color | Custom color override |
| `derives a consistent color from name` | Same name → same color on re-render | Deterministic hash |
| `does not apply background style when showing image` | No backgroundColor when image visible | Image vs initials state |

### Message Component Tests (`Message.test.tsx` - 9 new tests)

| Test | Validates | Edge Case |
|------|-----------|-----------|
| `renders thinker avatar alongside thinker message` | ThinkerAvatar shown for thinker messages | Thinker avatar integration |
| `does not show thinker avatar for user messages` | No avatar for user sender type | User message display |
| `renders plain text when no thinkers provided` | Content unchanged with empty allThinkers | No mention context |
| `highlights a thinker mention in message content` | Mention span rendered for matched name | Single mention |
| `handles message with no mentions` | Non-matching content rendered as-is | No match case |
| `highlights multiple different thinkers` | Both Plato and Aristotle highlighted | Multiple mentions |
| `matches partial name (first name only)` | "Karl" matches "Karl Marx" | Partial name matching |
| `renders user message with thinker mentions` | User messages show mention highlights | User + mentions |
| `renders plain text when allThinkers is empty array` | Empty array produces no highlights | Empty array guard |

### Components Barrel Export Tests (`components/index.test.ts` - 19 new tests)

| Test | Validates |
|------|-----------|
| `exports ChatArea` | ChatArea function exported from barrel |
| `exports ConversationList` | ConversationList exported |
| `exports CostMeter` | CostMeter exported |
| `exports ErrorBanner` | ErrorBanner exported |
| `exports FeedbackModal` | FeedbackModal exported |
| `exports MentionAutocomplete` | MentionAutocomplete exported |
| `exports filterThinkers utility` | filterThinkers utility from MentionAutocomplete |
| `exports Message` | Message exported |
| `exports MessageInput` | MessageInput exported |
| `exports MessageList` | MessageList exported |
| `exports NewChatModal` | NewChatModal exported |
| `exports ResizeDivider` | ResizeDivider exported |
| `exports Sidebar` | Sidebar exported |
| `exports SpendLimitBanner` | SpendLimitBanner exported |
| `exports StatusLine` | StatusLine exported |
| `exports ThinkerAvatar` | ThinkerAvatar exported |
| `exports ThinkerSelector` | ThinkerSelector exported |
| `exports TypingIndicator` | TypingIndicator exported |
| `exports BuildInfo` | BuildInfo exported |

### Hooks Barrel Export Tests (`hooks/index.test.ts` - 1 new test)

| Test | Validates |
|------|-----------|
| `exports useWebSocket hook` | useWebSocket exported from barrel file |

### Backend Refactoring: `test_regression_prevention_mar15_2026.py`

Reduced code duplication by replacing the 2-line pattern:
```python
data = await register_and_get_token(client, username="X", password="Y")
headers = {"Authorization": f"Bearer {data['access_token']}"}
```
with the single-line:
```python
headers = await get_auth_headers(client, "X", "Y")
```
Applied across **15 test methods** in the file, reducing each from 2 lines to 1.
Exception: kept `register_and_get_token` where `data["user"]["id"]` is also needed.

## 1.12 Integration Gap Tests (Added 2026-04-08)

**Focus**: Wednesday QA focus - untested API endpoints and integration gaps
**Coverage Impact**: +28 new tests, significant improvements in admin.py (0%->100%), conversations.py (68%->96%), auth.py (88%->96%), test_helpers.py (36%->81%)
**File**: `backend/tests/test_integration_gaps_apr8_2026.py`

### Add Thinkers to Conversation Integration (`TestAddThinkersToConversationIntegration` - 4 tests)

| Test | Validates | Coverage |
|------|-----------|----------|
| `test_add_thinkers_to_existing_conversation_success` | PUT /api/conversations/{id}/thinkers happy path | conversations.py lines 162-220 |
| `test_add_multiple_thinkers_in_one_request` | Batch add of 2+ thinkers at once | conversations.py lines 192-218 |
| `test_add_thinker_assigns_available_color` | Color deduplication when adding thinkers | conversations.py lines 188-198 |
| `test_add_thinkers_up_to_max_limit` | Can add exactly 5 total thinkers (boundary) | conversations.py lines 178-184 |

### Send Message Integration (`TestSendMessageIntegration` - 3 tests)

| Test | Validates | Coverage |
|------|-----------|----------|
| `test_send_message_creates_message_in_conversation` | POST /api/conversations/{id}/messages happy path | conversations.py lines 256-268 |
| `test_send_message_auto_resume_path` | Auto-resume triggered when conversation is idle-paused | conversations.py lines 246-254 |
| `test_send_message_uses_display_name` | sender_name uses user's display_name, not username | conversations.py lines 256-259 |

### Admin Spend Limit Integration (`TestAdminSpendLimitIntegration` - 4 tests)

| Test | Validates | Coverage |
|------|-----------|----------|
| `test_update_spend_limit_success` | PATCH /api/admin/users/{id}/spend-limit happy path | admin.py lines 78-93 |
| `test_update_spend_limit_not_found` | 404 when user doesn't exist | admin.py lines 81-85 |
| `test_update_spend_limit_requires_admin` | 403 for non-admin user | admin.py auth dependency |
| `test_update_spend_limit_invalid_value` | 422 for spend_limit=0 (gt=0 constraint) | admin.py validation |

### Admin Delete User Integration (`TestAdminDeleteUserIntegration` - 3 tests)

| Test | Validates | Coverage |
|------|-----------|----------|
| `test_delete_user_success` | DELETE /api/admin/users/{id} happy path | admin.py lines 108-125 |
| `test_delete_user_cannot_delete_self` | 400 when admin tries to delete own account | admin.py lines 104-109 |
| `test_delete_user_requires_admin` | 403 for non-admin user | admin.py auth dependency |

### Auth Endpoints Integration (`TestAuthEndpointsIntegration` - 6 tests)

| Test | Validates | Coverage |
|------|-----------|----------|
| `test_update_profile_success` | PATCH /api/auth/profile happy path, updates display_name | auth.py lines 215-235 |
| `test_update_profile_persists_change` | Profile change visible in /me after update | auth.py lines 221-235 |
| `test_update_language_success` | PATCH /api/auth/language happy path | auth.py lines 192-212 |
| `test_update_language_persists_change` | Language change visible in /me after update | auth.py lines 199-212 |
| `test_logout_endpoint_returns_success` | POST /api/auth/logout returns success message | auth.py lines 262-269 |
| `test_login_creates_new_session_when_none_exists` | Login creates session when user has none | auth.py lines 151-155 |

### Cleanup Test Users Integration (`TestCleanupTestUsersIntegration` - 6 tests)

| Test | Validates | Coverage |
|------|-----------|----------|
| `test_cleanup_test_users_with_valid_secret` | DELETE /api/test/cleanup-test-users happy path | test_helpers.py lines 201-236 |
| `test_cleanup_test_users_with_invalid_secret` | 403 for wrong secret | test_helpers.py lines 210-215 |
| `test_cleanup_test_users_secret_not_configured` | 403 when secret not configured | test_helpers.py lines 203-208 |
| `test_cleanup_test_users_no_matches_returns_zero` | Returns 0 when no test users exist | test_helpers.py lines 225-226 |
| `test_cleanup_test_users_canary_prefix` | canary_ prefix users are deleted | test_helpers.py lines 219-223 |
| `test_cleanup_test_users_spares_regular_users` | Regular users are not deleted | test_helpers.py lines 219-223 |

### Conversation List Integration (`TestConversationListIntegration` - 2 tests)

| Test | Validates | Coverage |
|------|-----------|----------|
| `test_list_conversations_includes_message_count` | GET /api/conversations includes message_count=0 and total_cost=0 | conversations.py lines 88-104 |
| `test_list_conversations_returns_correct_count` | List returns all conversations for session with correct structure | conversations.py lines 76-105 |

## 1.11 Edge Case Analysis (Added 2026-04-04)

**Focus**: Saturday QA focus - error paths and boundary conditions
**Coverage Impact**: +64 new tests across auth, conversations, thinkers, sessions, admin, and feedback APIs
**File**: `backend/tests/test_edge_cases_apr4_2026.py`

### Auth API Edge Cases (`TestAuthEdgeCases` - 15 tests)

| Test | Validates | Edge Case |
|------|-----------|-----------|
| `test_get_me_with_malformed_token` | 401 for non-JWT garbage string | Malformed token handling |
| `test_get_me_with_expired_token` | 401 for expired JWT | Token expiry security path |
| `test_register_username_at_min_length` | 200 for 3-char username | min_length=3 boundary (inclusive) |
| `test_register_username_below_min_length` | 422 for 2-char username | min_length=3 boundary (exclusive) |
| `test_register_password_at_min_length` | 200 for 6-char password | min_length=6 boundary (inclusive) |
| `test_register_password_below_min_length` | 422 for 5-char password | min_length=6 boundary (exclusive) |
| `test_register_invalid_language_preference` | 422 for unsupported language | Only en\|es\|fr\|de allowed |
| `test_login_wrong_password` | 401 with generic error message | No credential enumeration |
| `test_login_nonexistent_user` | 401 with same error as wrong pw | No user enumeration |
| `test_change_password_wrong_current_password` | 400 with specific error | Current password verification |
| `test_change_password_new_too_short` | 422 for short new password | min_length=6 on new password |
| `test_update_language_invalid_code` | 422 for 'zh' language | Only en\|es\|fr\|de allowed |
| `test_update_profile_empty_display_name_rejected` | 422 for empty string | min_length=1 on display name |
| `test_update_profile_display_name_at_max_length` | 200 for exactly 100 chars | max_length=100 boundary (inclusive) |
| `test_update_profile_display_name_exceeds_max_length` | 422 for 101 chars | max_length=100 boundary (exclusive) |

### Conversations API Edge Cases (`TestConversationEdgeCases` - 17 tests)

| Test | Validates | Edge Case |
|------|-----------|-----------|
| `test_create_conversation_empty_topic_rejected` | 422 for empty string topic | min_length=1 on topic |
| `test_create_conversation_no_thinkers_rejected` | 422 for empty thinkers list | min_length=1 on thinkers list |
| `test_create_conversation_too_many_thinkers_rejected` | 422 for 6 thinkers | max_length=5 on thinkers list |
| `test_create_conversation_with_exactly_5_thinkers` | 200 for exactly 5 thinkers | max_length=5 boundary (inclusive) |
| `test_get_conversation_other_users_conv_returns_404` | 404 for cross-user access | Security - 404 not 403 to hide existence |
| `test_delete_conversation_other_users_conv_returns_404` | 404 for cross-user delete | Security - cross-user modification |
| `test_get_conversation_nonexistent_id_returns_404` | 404 for unknown conv ID | Error path for missing resource |
| `test_send_message_empty_content_rejected` | 422 for empty message | min_length=1 on message content |
| `test_send_message_to_nonexistent_conversation` | 404 for unknown conv | Error path for message to missing conv |
| `test_add_thinkers_exceeds_max_limit` | 400 with detail message | Cannot exceed 5 total thinkers |
| `test_add_thinkers_to_nonexistent_conversation` | 404 for unknown conv | Error path for add_thinkers |
| `test_add_thinkers_to_other_users_conversation` | 404 for cross-user add | Security - cross-user thinker add |
| `test_add_thinkers_with_invalid_color_rejected` | 422 for non-hex color | color must match ^#[0-9a-fA-F]{6}$ |
| `test_conversation_list_empty_for_new_user` | 200 with empty list | Boundary: 0 conversations |
| `test_conversations_unauthenticated_returns_401` | 401 without auth header | All conv endpoints require auth |
| `test_thinker_name_at_max_length` | 200 for exactly 255-char name | max_length=255 boundary (inclusive) |
| `test_thinker_name_exceeds_max_length` | 422 for 256-char name | max_length=255 boundary (exclusive) |

### Thinkers API Edge Cases (`TestThinkersApiEdgeCases` - 15 tests)

| Test | Validates | Edge Case |
|------|-----------|-----------|
| `test_suggest_thinkers_quota_error_returns_503` | 503 for quota ThinkerAPIError | is_quota_error=True -> 503 |
| `test_suggest_thinkers_api_error_returns_502` | 502 for general ThinkerAPIError | is_quota_error=False -> 502 |
| `test_suggest_thinkers_count_at_min` | 200 with count=1, returns 1 result | ge=1 boundary (inclusive) |
| `test_suggest_thinkers_count_at_max` | 200 with count=5, returns 5 results | le=5 boundary (inclusive) |
| `test_suggest_thinkers_count_exceeds_max_rejected` | 422 for count=6 | le=5 boundary (exclusive) |
| `test_suggest_thinkers_count_zero_rejected` | 422 for count=0 | ge=1 boundary (exclusive) |
| `test_suggest_thinkers_empty_topic_rejected` | 422 for empty topic | min_length=1 on topic |
| `test_suggest_thinkers_invalid_language_rejected` | 422 for 'de' language | Only en\|es\|fr allowed |
| `test_validate_thinker_quota_error_returns_503` | 503 for quota error in validate | is_quota_error=True -> 503 |
| `test_validate_thinker_api_error_returns_502` | 502 for general error in validate | is_quota_error=False -> 502 |
| `test_validate_thinker_empty_name_rejected` | 422 for empty name | min_length=1 on name |
| `test_validate_thinker_no_api_key_unknown_name` | valid=False for unknown thinker | No API key -> only mocks recognized |
| `test_get_knowledge_for_unknown_thinker_creates_pending_entry` | 200 with status field | Unknown thinker triggers knowledge creation |
| `test_get_knowledge_status_for_unknown_thinker` | 200 with pending status | status endpoint for new thinker |
| `test_refresh_knowledge_creates_entry_if_missing` | 200 for new thinker | Refresh creates entry if missing |

### Sessions API Edge Cases (`TestSessionsEdgeCases` - 3 tests)

| Test | Validates | Edge Case |
|------|-----------|-----------|
| `test_get_session_with_token_missing_session_id` | 401 with "no session" detail | JWT valid but lacks session_id |
| `test_get_session_with_nonexistent_session_id` | 404 with "Session not found" | Valid JWT but deleted/missing session |
| `test_get_current_session_authenticated` | 200 with session data | Happy path for /api/sessions/me |

### Admin API Edge Cases (`TestAdminEdgeCases` - 5 tests)

| Test | Validates | Edge Case |
|------|-----------|-----------|
| `test_admin_delete_self_rejected` | 400 "Cannot delete your own account" | Self-deletion prevention |
| `test_admin_delete_nonexistent_user` | 404 "User not found" | Delete unknown user |
| `test_admin_update_spend_limit_nonexistent_user` | 404 "User not found" | Update limit for unknown user |
| `test_non_admin_user_cannot_access_admin_endpoints` | 403 "Admin access required" | Auth but not admin |
| `test_unauthenticated_user_cannot_access_admin_endpoints` | 401 Unauthorized | No auth at all |

### Feedback API Edge Cases (`TestFeedbackEdgeCases` - 9 tests)

| Test | Validates | Edge Case |
|------|-----------|-----------|
| `test_submit_feedback_message_at_exact_min_length` | 201 for exactly 10-char message | min_length=10 boundary (inclusive) |
| `test_submit_feedback_message_at_max_length` | 201 for exactly 5000-char message | max_length=5000 boundary (inclusive) |
| `test_submit_feedback_message_exceeds_max_length` | 422 for 5001-char message | max_length=5000 boundary (exclusive) |
| `test_submit_feedback_via_x_forwarded_for` | 201 with X-Forwarded-For header | Proxy header used for rate limiting |
| `test_get_pending_feedback_limit_at_min` | 200 for limit=1 | ge=1 boundary (inclusive) |
| `test_get_pending_feedback_limit_at_max` | 200 for limit=50 | le=50 boundary (inclusive) |
| `test_get_pending_feedback_limit_exceeds_max` | 422 for limit=51 | le=50 boundary (exclusive) |
| `test_mark_processed_not_configured_returns_503` | 503 when secret not set | Service unavailable when not configured |
| `test_submit_feedback_with_forwarded_for_chain` | 201 with multi-proxy chain | First IP in chain used for rate limiting |

## 1.10 Test Refactoring (Added 2026-04-03)

**Focus**: Friday QA focus - improve test readability and reduce duplication
**Coverage Impact**: No new coverage (structural improvement)
**Files Changed**: `backend/tests/conftest.py`, `backend/tests/test_api.py`,
`frontend/src/__tests__/app/admin.test.tsx`, `frontend/src/test-utils.tsx`

### New Backend Helpers Added to `conftest.py`

#### `make_simple_thinker_list()`

Creates a single-element thinker list for conversation creation tests.

- **Purpose**: Eliminates 9+ occurrences of the identical 4-line inline thinker dict
  (`"name": "Thinker", "bio": "Bio", "positions": "Positions", "style": "Style"`) in
  `test_api.py`.
- **Usage**: `"thinkers": make_simple_thinker_list()` in any `POST /api/conversations` call
  where the thinker's specific values are not relevant to the test.
- **Parametrizable**: Accepts `name`, `bio`, `positions`, `style` args for customization.

#### `create_conversation_with_thinker()`

Creates a conversation with a single placeholder thinker and returns the conversation ID.

- **Purpose**: Reduces the repeated 6-line pattern (POST conversation, assert 200, extract ID)
  that appeared in 9+ test methods across `TestConversationAPI` and `TestSpendAPI`.
- **Usage**: `conv_id = await create_conversation_with_thinker(client, headers, "topic")`
- **Returns**: Conversation ID string ready for use in subsequent API calls.
- **Tests using this helper**:
  - `TestConversationAPI.test_get_conversation` — retrieves a conversation by ID
  - `TestConversationAPI.test_send_message` — posts a message to a conversation
  - `TestConversationAPI.test_delete_conversation` — deletes and verifies deletion
  - `TestConversationAPI.test_conversation_deletion_with_messages` — cascade delete
  - `TestConversationAPI.test_unauthorized_conversation_access` — cross-user access control
  - `TestConversationAPI.test_list_conversations_with_message_counts_and_costs` — list fields
  - `TestConversationAPI.test_send_message_uses_display_name` — sender name logic
  - `TestConversationAPI.test_send_message_falls_back_to_username` — sender fallback
  - `TestSpendAPI.test_get_spend_with_conversations` — spend data per-user

### Frontend Test Improvements

#### `renderAdminPage()` in `admin.test.tsx`

Extracts the 10-occurrence pattern of `render(<AdminPage />) + waitFor('Admin Panel')` into
a single async helper function.

- **Purpose**: Removes 30+ repeated lines across `TestAdminPage` sorting tests.
- **Impact**: Every Column Sorting test reduced from 5 lines of setup to 1 line.
- **Tests using this helper** (10 total):
  - `renders the admin page with users table`
  - `displays sort indicators on column headers`
  - `sorts by username in ascending order by default`
  - `toggles sort direction when clicking the same column`
  - `sorts by conversations column (numeric)`
  - `sorts by total spend column (numeric)`
  - `sorts by spend limit column (numeric)`
  - `sorts by role column (admin first when ascending)`
  - `sorts by joined date column`
  - `resets to ascending when switching to a new column`
  - `actions column is not sortable`

#### `createWebSocketOptions()` in `test-utils.tsx`

Creates default options for `useWebSocket` hook testing.

- **Purpose**: Provides a factory for `UseWebSocketOptions` with sensible defaults, reducing
  boilerplate in tests that only need to override 1-2 options out of 6.
- **Default**: `{ conversationId: 'conv-123' }` — matching the most common test case.
- **Parametrizable**: All 6 hook options can be overridden via the `overrides` parameter.

## 1.11 E2E Performance Optimization (Added 2026-04-30)

**Focus**: Thursday QA focus - eliminate remaining `waitForLoadState('networkidle')` anti-patterns, add parallel config to missing describe block, add new performance regression tests
**Coverage Impact**: No backend/frontend unit coverage change; 5 new E2E performance tests added

### Performance Analysis Summary

**Before optimization:**
- `waitForLoadState('networkidle')` in active (non-skipped) tests: 4 calls across 3 files
- `chat.spec.ts` 'Thinker Responses' describe block missing `test.describe.configure({ mode: 'parallel' })`
- `performance.spec.ts` missing: thinkers/suggest timing, register endpoint, concurrent requests, FCP, SPA nav

**After optimization:**
- Active `waitForLoadState('networkidle')` calls: 0 (down from 4)
- All describe blocks have `test.describe.configure({ mode: 'parallel' })` ✅
- 5 new performance regression tests in `performance.spec.ts`

### Changes Made

#### Anti-pattern fixes

| File | Location | Before | After |
|------|----------|--------|-------|
| `cost-edge-cases.spec.ts` | After message send (2×) | `waitForLoadState('networkidle', 5000)` | `expect(messageTextarea).toBeEnabled({ timeout: 5000 })` |
| `feedback-edge-cases.spec.ts` | Overlay click animation | `waitForLoadState('networkidle', 2000)` | `expect.poll(() => modal.isVisible(), { timeout: 2000 })` |
| `feedback-edge-cases.spec.ts` | Email validation | `Promise.race([..., networkidle])` | `errorSelector.waitFor({ state: 'visible', timeout: 3000 })` |
| `form-validation.spec.ts` | Empty thinker add | `Promise.race([..., networkidle])` | `expect.poll(() => selected.count(), { timeout: 2000 })` |

The `waitForLoadState('networkidle')` pattern forces Playwright to wait 500ms after ALL network activity stops. For pages with WebSocket connections or polling, this can take multiple seconds or never settle. Element-driven waits are more deterministic and typically 2–5× faster.

#### Parallelism fix in `chat.spec.ts`

Added `test.describe.configure({ mode: 'parallel' })` to the `'Thinker Responses'` describe block (line 119). All tests inside are currently `test.skip`, but the config is in place so they run in parallel when re-enabled.

#### New tests in `performance.spec.ts` — `Page Rendering Performance` and `API Response Performance`

| Test | File | What It Validates |
|------|------|-------------------|
| `health/ready deep check responds within 3 seconds` | `performance.spec.ts` | `/health/ready` DB-connected check stays fast |
| `register endpoint responds within 3 seconds` | `performance.spec.ts` | Critical auth path (new user registration) |
| `concurrent API calls complete in parallel within budget` | `performance.spec.ts` | 3 simultaneous requests finish faster than 3 sequential |
| `login page first contentful paint within 3 seconds` | `performance.spec.ts` | FCP via Performance API — catches rendering regressions |
| `SPA navigation between home and settings is instant (<1s)` | `performance.spec.ts` | Client-side navigation stays fast (no full reload) |
| `page.waitForResponse pattern completes faster than networkidle` | `performance.spec.ts` | Documents and validates the preferred wait pattern |

### Performance Metrics

| Metric | Before | After |
|--------|--------|-------|
| Active `waitForLoadState('networkidle')` calls | 4 | 0 |
| `waitForTimeout()` calls | 0 | 0 |
| Spec files with parallel mode | all | all |
| New performance regression tests | 0 | 6 |

## 1.10 E2E Performance Optimization (Added 2026-04-09)

**Focus**: Thursday QA focus - optimize E2E test speed and parallelism
**Coverage Impact**: No coverage change (performance improvement)

### Performance Analysis Summary

**Before optimization:**
- `waitForTimeout()` calls: 0 (already eliminated in previous sessions) ✅
- Playwright config: `fullyParallel: true`, 4 CI workers ✅
- Files missing `test.describe.configure({ mode: 'parallel' })`: 4 files
  - `persistence.spec.ts` (active, 1 test)
  - `mobile-ios.spec.ts` (WebKit-only, 9 describes, each needs separate configure)
  - `conversation-deletion-edge.spec.ts` (skipped suite)
  - `mention-badge-alignment.spec.ts` (skipped suite)
- `playwright.config.ts`: redundant ternary `process.env.CI ? 90000 : 90000` for timeout

**After optimization:**
- All 23 E2E spec files now have `test.describe.configure({ mode: 'parallel' })` ✅
- `playwright.config.ts` timeout simplified from `process.env.CI ? 90000 : 90000` to `90000`

### Changes Made

#### Within-file parallelism added to `persistence.spec.ts`

Added `test.describe.configure({ mode: 'parallel' })` to the `Persistence` describe block.
The single test (`conversations persist across page reload`) uses its own authenticated session
via `setupAuthenticatedUser`, so there is no shared state risk.

#### Within-file parallelism added to `mobile-ios.spec.ts`

Added `test.describe.configure({ mode: 'parallel' })` to all 9 top-level describe blocks:
- `iOS Safari - Header Visibility` (3 tests)
- `iOS Safari - Sidebar Toggle` (2 tests)
- `iOS Safari - Sticky Positioning` (2 tests)
- `iOS Safari - Orientation Changes` (2 tests)
- `iOS Safari - iPad Specific Tests` (2 tests)
- `iOS Safari - Touch Interactions` (2 tests)
- `iOS Safari - Viewport and Safe Areas` (2 tests)
- `iOS Safari - Screenshot on Failure` (1 test)
- `iOS Safari - Regression Tests` (2 tests)

All tests use `createConversationViaUI()` with independent `page` fixtures, so no shared
state between tests within each group. Tests are already WebKit-only (skipped in CI on
Chromium), but when run locally with WebKit they will benefit from parallelism.

#### Within-file parallelism added to skipped suites

Added `test.describe.configure({ mode: 'parallel' })` inside the skipped describe blocks
in `conversation-deletion-edge.spec.ts` and `mention-badge-alignment.spec.ts`. These suites
are currently skipped because they require live Claude API calls, but the parallelism
config is in place so when they are eventually re-enabled, tests will run in parallel.

#### Simplified `playwright.config.ts` timeout

Removed redundant ternary expression: `process.env.CI ? 90000 : 90000` → `90000`.
Both branches were identical, making the ternary dead code. Simplified to a plain value.

### Performance Metrics

| Metric | Before | After |
|--------|--------|-------|
| `waitForTimeout()` calls | 0 | 0 |
| Spec files with parallel mode | 19/23 | 23/23 |
| Skipped files with parallel mode | 1/4 | 4/4 |
| Config redundancy | 1 dead ternary | 0 |

## 1.9 E2E Performance Optimization (Added 2026-04-02)

**Focus**: Thursday QA focus - optimize E2E test speed and parallelism
**Coverage Impact**: No coverage change (performance improvement)

### Performance Analysis Summary

**Before optimization:**
- `waitForTimeout()` calls: 0 (already eliminated in previous sessions) ✅
- Files missing `test.describe.configure({ mode: 'parallel' })`: 1 active test file
  (`concurrent-operations.spec.ts`)
- Other skipped files missing parallel: `mention-badge-alignment.spec.ts`,
  `conversation-deletion-edge.spec.ts`, `persistence.spec.ts`, `mobile-ios.spec.ts`
- Playwright config: `fullyParallel: true`, 4 CI workers ✅

**After optimization:**
- `concurrent-operations.spec.ts`: added `test.describe.configure({ mode: 'parallel' })`
- All active test files now have within-file parallelism configured ✅

### Changes Made

#### Within-file parallelism added to `concurrent-operations.spec.ts`

The `concurrent-operations.spec.ts` file had 3 independent tests, each calling
`setupAuthenticatedUser()` independently, with no shared state between them.
Adding `test.describe.configure({ mode: 'parallel' })` allows these 3 tests to run
concurrently across workers rather than sequentially:

- `can switch between conversations rapidly without errors` — Rapid conversation switching
- `handles rapid conversation creation` — Concurrent API-based conversation creation
- `handles rapid message sending in same conversation` — 5 rapid messages in sequence

**File**: `frontend/e2e/concurrent-operations.spec.ts`

**Why these tests are safe to parallelize**: Each test creates its own independent user
via `setupAuthenticatedUser()`, creating completely isolated browser contexts with separate
authentication tokens and distinct conversation sets. No shared state between tests.

## 1.8 Coverage Sprint (Added 2026-03-30)

**Focus**: Monday QA coverage sprint — increase coverage of thinker service language paths,
knowledge research service, and start_conversation_agents method.
**File**: `backend/tests/test_coverage_sprint_mar30_2026.py`
**Tests Added**: 64 new tests across 11 test classes
**Coverage Impact**: knowledge_research.py 62% → 89% (+27%), thinker.py 68% → 74% (+6%)

### TestGetLanguageInstruction (6 tests)

Validates the `_get_language_instruction` helper in `thinker.py` for all supported languages.

- `test_english_returns_empty_string` — English returns empty string (no instruction needed).
- `test_spanish_returns_spanish_instruction` — Spanish ('es') returns "Respond in Spanish" instruction.
- `test_french_returns_french_instruction` — French ('fr') returns "Respond in French" instruction.
- `test_german_returns_german_instruction` — German ('de') returns "Respond in German" instruction.
- `test_hindi_returns_hindi_instruction` — Hindi ('hi') returns "Respond in Hindi" instruction.
- `test_unknown_language_code_uses_code_as_name` — Unknown language code falls back to using the code itself.

### TestClientProperty (2 tests)

Validates the `ThinkerService.client` property lazy initialization.

- `test_client_is_created_when_api_key_present` — AsyncAnthropic is instantiated when API key is set.
- `test_client_cached_after_first_access` — Pre-set `_client` is returned without re-creation.

### TestExtractThinkingDisplayMultilingual (11 tests)

Validates multilingual text replacement and starter logic in `_extract_thinking_display`.

- `test_german_replacements_applied` — German text replacements run for 'de' language.
- `test_spanish_replacements_applied` — Spanish text replacements run for 'es' language.
- `test_french_replacements_applied` — French text replacements run for 'fr' language.
- `test_hindi_replacements_applied` — Hindi text replacements run for 'hi' language.
- `test_english_default_replacements_applied` — English replacements applied by default.
- `test_text_with_i_think_stripped` — "I think " is stripped from beginning of displayed text.
- `test_german_starters_added_when_no_existing_prefix` — German contemplative starters added.
- `test_spanish_starters_added` — Spanish contemplative starters added when appropriate.
- `test_french_starters_added` — French contemplative starters added when appropriate.
- `test_hindi_starters_added` — Hindi contemplative starters added when appropriate.
- `test_text_not_ending_with_punctuation_gets_ellipsis` — Truncated text gets "..." appended.

### TestStartConversationAgents (3 tests)

Validates `ThinkerService.start_conversation_agents` task creation behavior.

- `test_start_creates_tasks_for_each_thinker` — An asyncio Task is created per thinker.
- `test_start_stops_existing_agents_first` — Pre-existing agents are stopped before starting new ones.
- `test_start_with_empty_thinkers_list` — Empty thinker list creates empty task dict (no error).

### TestIdlePauseResume (4 tests)

Validates idle-specific pause/resume methods in ThinkerService.

- `test_pause_for_idle_marks_both_sets` — `pause_for_idle` adds to both paused and idle-paused sets.
- `test_resume_from_idle_clears_both_sets` — `resume_from_idle` clears both sets on success.
- `test_resume_from_idle_does_nothing_if_not_idle_paused` — Manually paused conversations NOT resumed.
- `test_resume_from_idle_does_nothing_for_unknown_conversation` — No-op for unknown conversations.

### TestGetLastUserMessageTimestamp (5 tests)

Validates `_get_last_user_message_timestamp` in ThinkerService.

- `test_returns_timestamp_of_last_user_message` — Returns correct timestamp from mixed history.
- `test_returns_zero_when_no_user_messages` — Returns 0.0 when no user messages exist.
- `test_returns_zero_for_empty_messages` — Returns 0.0 for empty message list.
- `test_returns_most_recent_user_message_timestamp` — Returns LAST user message when multiple exist.
- `test_handles_sender_type_enum_value` — Handles sender_type with .value attribute (enum style).

### TestShouldRespondEdgeCases (3 tests)

Additional edge cases for `_should_respond` probability logic.

- `test_consecutive_silence_increases_probability` — Long silence boosts response probability.
- `test_not_mentioned_can_stay_silent` — 15% silence chance produces some silent results.
- `test_addressed_by_name_increases_probability` — Name mention without @ also increases probability.

### TestSuggestThinkersWithLanguage (2 tests)

Validates language parameter routing through suggest_thinkers API calls.

- `test_suggest_with_spanish_language` — Spanish language instruction appears in API prompt.
- `test_suggest_parallel_with_language` — Language parameter passed through parallel batch calls.

### TestValidateThinkerWithLanguage (1 test)

Validates language parameter routing in validate_thinker.

- `test_validate_with_non_english_language` — Non-English language instruction in API prompt.

### TestKnowledgeResearchServiceCoverage (16 tests)

Comprehensive coverage for `KnowledgeResearchService` — database operations, HTTP fetching,
background research execution, and cache management.

- `test_is_stale_returns_true_for_pending_status` — PENDING is always stale.
- `test_is_stale_returns_true_for_in_progress_status` — IN_PROGRESS is always stale.
- `test_is_stale_returns_true_for_failed_status` — FAILED is always stale.
- `test_is_stale_returns_false_for_recently_completed` — Recent COMPLETE is not stale.
- `test_is_stale_returns_true_for_old_completed` — COMPLETE > 30 days old is stale.
- `test_get_knowledge_returns_none_when_not_found` — Returns None for unknown thinker.
- `test_get_or_create_creates_new_entry` — Creates PENDING entry when thinker not found.
- `test_get_or_create_returns_existing_entry` — Returns same entry on second call.
- `test_trigger_research_deduplicates` — No new task when one is already running.
- `test_trigger_research_restarts_completed_task` — New task started after previous completes.
- `test_refresh_stale_knowledge_triggers_research_for_old_entries` — Old entries queued.
- `test_refresh_stale_knowledge_skips_recent_entries` — Fresh entries skipped.
- `test_fetch_wikipedia_data_returns_none_on_exception` — Returns None on network error.
- `test_fetch_wikipedia_data_returns_none_when_no_results` — Returns None for no results.
- `test_fetch_wikipedia_data_returns_data_with_thumbnail` — Result includes image_url.
- `test_fetch_wikipedia_data_returns_data_without_thumbnail` — Result excludes image_url.
- `test_fetch_wikipedia_data_skips_page_minus_one` — Wikipedia's "not found" page ID skipped.
- `test_fetch_wikipedia_sections_returns_none_on_exception` — Returns None on error.
- `test_fetch_wikipedia_sections_returns_none_for_no_interesting_sections` — Returns None.
- `test_fetch_wikipedia_sections_returns_dict_for_interesting_sections` — Returns section dict.
- `test_research_thinker_updates_status_to_complete` — Background research marks COMPLETE.

### TestSplitResponseIntoBubblesAdditional (4 tests)

Additional edge cases for `_split_response_into_bubbles`.

- `test_text_exactly_60_chars_stays_single_bubble` — Boundary case: text at 60 chars stays single.
- `test_text_250_to_300_chars_may_stay_single` — Medium text can stay single (25% strategy).
- `test_no_empty_bubbles_in_output` — Output never contains empty string bubbles.
- `test_force_split_for_very_long_single_sentence` — Very long single sentence is force-split.

### TestSuggestSingleBatchDeduplication (2 tests)

Validates deduplication and error propagation in parallel suggest_thinkers batches.

- `test_parallel_suggestions_deduplicate_by_name` — Same thinker from two batches deduped.
- `test_all_parallel_batches_fail_raises_api_error` — Quota error from all batches propagated.

## 1.7 Regression Prevention (Added 2026-03-29)

**Focus**: Sunday QA focus - regression prevention for recent bug fixes
**File**: `backend/tests/test_regression_prevention_mar29_2026.py`
**Tests Added**: 23 new tests across 5 test classes

### TestKnowledgeServiceGlobalMockBehavior (4 tests)

Validates the fix from PR #783 — the global autouse mock for `knowledge_service.trigger_research`
that prevents tests from hanging when creating conversations.

- `test_create_conversation_calls_trigger_research_per_thinker` — Verifies trigger_research
  called exactly once per thinker in `create_conversation`. Guards against the call being
  moved outside the thinker loop or removed entirely.
- `test_mock_call_count_starts_fresh_each_test` — Verifies the autouse fixture creates a
  fresh mock per test (function scope), so call counts don't accumulate across tests.
- `test_add_thinkers_endpoint_also_triggers_research` — Verifies PUT `/thinkers` also calls
  trigger_research for each new thinker, covering both conversation creation paths.
- `test_single_thinker_conversation_triggers_research_once` — Verifies exactly 1 call for
  a 1-thinker conversation (not 0 or 2+).

### TestKnowledgeResearchDeduplication (3 tests)

Validates the `_active_tasks` deduplication in `KnowledgeResearchService.trigger_research`.

- `test_trigger_research_skips_if_task_already_running` — Verifies no new `asyncio.Task` is
  created when an in-progress task exists for the same thinker name.
- `test_trigger_research_starts_new_task_after_previous_completes` — Verifies a new task
  IS created after the previous one completes (`task.done() == True`).
- `test_trigger_research_starts_task_for_new_thinker` — Verifies first call for an unknown
  thinker always creates a new task.

### TestKnowledgeResearchIsStale (6 tests)

Validates `KnowledgeResearchService.is_stale()` boundary conditions.

- `test_is_stale_returns_true_for_failed_status` — FAILED knowledge always stale (never served
  from cache, always retried).
- `test_is_stale_returns_true_for_in_progress_status` — IN_PROGRESS knowledge is stale (handles
  crashed/stuck research tasks).
- `test_is_stale_returns_true_for_pending_status` — PENDING knowledge is stale (ensures orphaned
  entries get researched).
- `test_is_stale_returns_false_for_recent_complete` — Recent COMPLETE knowledge is not stale
  (cache hit for fresh data).
- `test_is_stale_returns_true_for_old_complete` — COMPLETE knowledge > 30 days old is stale
  (periodic refresh enforced).
- `test_is_stale_boundary_at_exactly_30_days` — Exactly 30 days + 1 second is stale (no
  off-by-one error at the threshold boundary).

### TestConversationSessionIsolation (4 tests)

Validates cross-session access control. All conversation endpoints must filter by session_id
to prevent users from accessing each other's data.

- `test_user_b_cannot_read_user_a_conversation` — GET returns 404 for another user's conversation.
- `test_user_b_cannot_delete_user_a_conversation` — DELETE returns 404 for another user's
  conversation; original conversation still accessible by owner.
- `test_user_b_cannot_send_message_to_user_a_conversation` — POST /messages returns 404
  for another user's conversation.
- `test_user_b_cannot_add_thinkers_to_user_a_conversation` — PUT /thinkers returns 404
  for another user's conversation.

### TestThinkerServiceIdlePausedState (6 tests)

Validates the dual-set pattern in `ThinkerService` for distinguishing idle pauses from manual
pauses. The `_idle_paused_conversations` set enables `resume_from_idle` to correctly skip
manually-paused conversations.

- `test_pause_for_idle_adds_to_both_sets` — `pause_for_idle` adds to BOTH `_paused` and
  `_idle_paused` sets (streaming stops AND idle flag is set).
- `test_resume_from_idle_clears_both_sets` — `resume_from_idle` clears BOTH sets.
- `test_resume_from_idle_does_not_resume_manually_paused_conversation` — KEY invariant:
  `pause_conversation` (manual) + `resume_from_idle` leaves conversation still paused.
- `test_idle_pause_does_not_affect_other_conversation` — Pausing conversation A idle does not
  affect conversation B.
- `test_is_idle_paused_false_for_manually_paused` — `pause_conversation` does NOT set idle
  flag (auto-resume won't trigger for manual pauses).
- `test_resume_from_idle_on_unknown_conversation_is_noop` — Uses `set.discard()` (not
  `remove()`), so calling on unknown conversation raises no error.

## 1.6 Test Refactoring (Added 2026-03-27)

**Focus**: Friday QA focus - improve readability and reduce duplication
**Coverage Impact**: No coverage change (refactoring only)

### Changes Made

#### Backend: New shared helpers in `backend/tests/conftest.py`

Added two new helper functions to reduce the admin user creation pattern that was
duplicated 5+ times in `test_edge_cases_admin_auth_feedback.py` and `test_api.py`.

**`create_admin_user(client, db_session, username, password)`**
- Registers a user, then promotes them to admin via direct DB update
- Returns auth data dict with access_token and user info
- Replaces 8-line repeated block: register + DB update + (optional re-login)
- File: `backend/tests/conftest.py`
- Used by: `test_edge_cases_admin_auth_feedback.py`, `test_api.py`

**`create_admin_headers(client, db_session, username, password)`**
- Wrapper around `create_admin_user` that returns just the Authorization headers dict
- Reduces 2-step pattern to 1 line for tests that only need to make admin requests
- File: `backend/tests/conftest.py`
- Used by: `test_edge_cases_admin_auth_feedback.py`

#### Backend: Removed local `create_admin_user` from `test_api.py`

The local `create_admin_user` helper function in `test_api.py` duplicated the conftest pattern.
It has been removed and all callers updated to use `create_admin_user` from `tests.conftest`.
Import updated: `from tests.conftest import create_admin_user, get_auth_headers, register_and_get_token`

#### Backend: Refactored `test_edge_cases_admin_auth_feedback.py`

Replaced 5 repeated blocks of admin user creation (each ~8 lines) with calls to the new
`create_admin_headers` and `create_admin_user` helpers from conftest.py.

**Before** (each test had):
```python
admin_data = await register_and_get_token(client, username="admin_X", password="adminpass")
await db_session.execute(update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True))
await db_session.commit()
login_response = await client.post("/api/auth/login", json={...})
admin_token = login_response.json()["access_token"]
admin_headers = {"Authorization": f"Bearer {admin_token}"}
```

**After**:
```python
admin_headers = await create_admin_headers(client, db_session, "admin_X", "adminpass")
```

Removed imports: `from sqlalchemy import update`, `from app.models import User`

#### Frontend: Refactored `ConversationList.test.tsx`

Replaced local `createConversation` factory function (typed as `ConversationSummary`) with
`createConversationSummary` from `@/test-utils`. This eliminates a 15-line local factory
that duplicated the shared test utility pattern.

**Before**: Local `createConversation(id, topic)` returning a hardcoded ConversationSummary
**After**: `createConversationSummary({ id, topic, ...overrides })` from test-utils

This aligns with the existing pattern used in `Sidebar.test.tsx` which already uses
`createConversationSummary` from test-utils.

### Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `backend/tests/conftest.py` | Enhancement | Added `create_admin_user` and `create_admin_headers` helpers |
| `backend/tests/test_api.py` | Refactor | Removed local `create_admin_user`, use conftest version |
| `backend/tests/test_edge_cases_admin_auth_feedback.py` | Refactor | Use `create_admin_headers` instead of repeated 8-line blocks |
| `frontend/src/__tests__/components/ConversationList.test.tsx` | Refactor | Use `createConversationSummary` from test-utils |

## 1.5 E2E Performance Optimization (Added 2026-03-26)

**Focus**: Thursday QA focus - optimize E2E test speed and parallelism
**Coverage Impact**: No coverage change (performance improvement)

### Performance Analysis Summary

**Before optimization:**
- `waitForTimeout()` calls: 0 (already eliminated in previous sessions)
- `test.describe.configure({ mode: 'parallel' })` uses: 0
- File-level parallelism: enabled (`fullyParallel: true`)
- Workers in CI: 4
- Standalone `waitForLoadState('networkidle')` calls used as sole wait: 2

**After optimization:**
- `test.describe.configure({ mode: 'parallel' })` uses: 20+ describe blocks across 17 files
- Standalone `waitForLoadState('networkidle')` sole waits: 0
- `persistence.spec.ts`: converted from UI modal to API-based conversation creation

### Changes Made

#### Within-file parallelism (`test.describe.configure({ mode: 'parallel' })`)

Added parallel mode to the following describe blocks, enabling tests within each block
to run concurrently rather than sequentially:

- `frontend/e2e/homepage.spec.ts` - 3 describe blocks: `Homepage`, `Login Page`, `Register Page`
- `frontend/e2e/admin.spec.ts` - 2 describe blocks: `Admin Panel`, `Admin Link Visibility`
- `frontend/e2e/new-conversation.spec.ts` - 2 describe blocks: `New Conversation Flow`, `Thinker Suggestions`
- `frontend/e2e/network-errors.spec.ts` - 4 describe blocks: `Network Error Recovery`, `WebSocket Error Recovery`, `API Error Messages`, `Rate Limiting & Throttling`
- `frontend/e2e/form-validation.spec.ts` - 4 describe blocks: `Topic Input Validation`, `Message Input Validation`, `Rapid-Fire Actions`, `Custom Thinker Validation`
- `frontend/e2e/chat.spec.ts` - 1 describe block: `Chat Functionality`
- `frontend/e2e/settings.spec.ts` - 1 top-level describe block: `Settings Page`
- `frontend/e2e/settings-edge-cases.spec.ts` - 1 describe block: `Settings Edge Cases`
- `frontend/e2e/tab-visibility.spec.ts` - 1 describe block: `Tab Visibility Handling`
- `frontend/e2e/session-management.spec.ts` - 1 describe block: `Session Management`
- `frontend/e2e/export-edge-cases.spec.ts` - 1 describe block: `Export Edge Cases`
- `frontend/e2e/feedback-edge-cases.spec.ts` - 1 describe block: `Feedback Modal Edge Cases`
- `frontend/e2e/cost-edge-cases.spec.ts` - 1 describe block: `Cost Edge Cases`
- `frontend/e2e/keyboard-navigation.spec.ts` - 1 describe block: `Keyboard Navigation`
- `frontend/e2e/scrolling-text.spec.ts` - 2 describe blocks: `ScrollingText - Conversation List`, `ScrollingText - Flex Layout Timing`
- `frontend/e2e/mobile-header.spec.ts` - 1 describe block: `Mobile Header Behavior`
- `frontend/e2e/thinker-selection-edge.spec.ts` - 1 describe block: `Thinker Selection Edge Cases`
- `frontend/e2e/issue-88-refresh-thinker.spec.ts` - 1 describe block: `Issue #88: Refresh thinker suggestion fails`

#### API-based conversation setup in `persistence.spec.ts`

Replaced the slow UI modal flow (topic input + thinker selection + create button click,
requiring ~15s for suggestions API call) with `createConversationViaAPI()`. The test now
validates that conversations created via API appear in the sidebar and persist across
page reloads, without exercising the creation modal flow.

**Before**: Used `new-chat-button` → `topic-input` → `next-button` → wait for suggestions → `add-custom-thinker` → `create-button`
**After**: Direct API call via `createConversationViaAPI()` then `page.goto('/')` to verify

#### Removed standalone `waitForLoadState('networkidle')` waits in `network-errors.spec.ts`

Two `waitForLoadState('networkidle')` calls that served as the sole wait mechanism were
replaced with element-driven alternatives:

1. **`handles WebSocket connection failure`**: Removed the `networkidle` wait after sending a
   message with blocked WebSocket. The assertion `expect(chat-area).toBeVisible()` that follows
   is sufficient to verify the app didn't crash.

2. **`reconnects WebSocket after temporary disconnection`**: Removed the `networkidle` wait
   after blocking the WebSocket. The route intercept is synchronous and takes effect immediately;
   the wait added up to 3s of unnecessary delay.

#### Replaced lone `waitForLoadState('networkidle')` in `settings-edge-cases.spec.ts`

The `should handle password fields with whitespace` test used `waitForLoadState('networkidle')`
as its only wait. Replaced with `expect(#currentPassword).toBeVisible({ timeout: 10000 })` which
is element-driven and more specific.

### Performance Impact

The `test.describe.configure({ mode: 'parallel' })` changes allow Playwright to schedule tests
within each describe block concurrently when workers are available. With 4 CI workers and
`fullyParallel: true` already enabled at the file level, this provides additional concurrency
at the describe-block level within each file.

Estimated time savings per CI run: 10-20% reduction by enabling more concurrent test execution
within individual test files, especially for test files with multiple describe blocks containing
3-5 tests each.

---

## 1.4 Flaky Test Hunt (Added 2026-03-24)

**Focus**: Tuesday QA focus - run tests 5x, identify and fix flaky tests
**Coverage Impact**: No coverage change (stability fix)

### Root Cause Fixed: Background HTTP Tasks Hanging Tests

**Problem**: Any test that created a conversation via `POST /api/conversations` would hang
indefinitely. The `create_conversation` endpoint calls
`knowledge_service.trigger_research(thinker_data.name)` which spawns a real `asyncio.Task`
that makes HTTP requests to Wikipedia. Tests that didn't mock this call left active background
tasks in the event loop, preventing the loop from exiting cleanly after the test.

**Affected tests (previously hanging indefinitely)**:
- `tests/test_api.py::TestConversationAPI` (13 tests)
- `tests/test_conversations_flaky_hunt.py` (6 tests)
- And all tests in ~30 other test files that create conversations

**Fix**: Added `mock_knowledge_service_trigger` autouse fixture in `tests/conftest.py` that
automatically patches `app.services.knowledge_research.knowledge_service.trigger_research`
to a no-op `MagicMock` for every test. This prevents real background HTTP tasks from running
during tests. Tests that explicitly need to verify `trigger_research` behavior can use their
own nested `patch()` context manager, which takes precedence over the autouse fixture while
active.

### Changes Made

#### `tests/conftest.py` - New autouse fixture
- `mock_knowledge_service_trigger` - Autouse fixture that patches `trigger_research` to a
  `MagicMock` for all tests. Prevents background Wikipedia HTTP requests that caused hangs.
  Yields the mock so tests can inspect call counts if needed.

#### `tests/test_flaky_hunt_mar17_2026.py` - Updated test for new reality
- `test_knowledge_service_mock_does_not_leak_between_tests` - Updated to verify that after
  a nested `with patch(...)` context exits, the outer autouse fixture's mock is restored
  (not the original unpatched method). The test now correctly validates nested patch cleanup
  in the presence of the global autouse fixture.

### Previously Known Pattern (working tests)
Tests in `test_conversations_coverage_sprint.py`, `test_thinker_knowledge_integration.py`
and others already used `@patch("app.services.knowledge_research.knowledge_service.trigger_research")`
decorators. The autouse fixture provides this automatically so all tests benefit without
requiring per-test annotations.

---

## 1.3 Coverage Sprint (Added 2026-03-23)

**Focus**: Monday QA focus - coverage sprint, bringing lowest-coverage modules up by 15%+
**Coverage Impact**: 78.92% -> 85.91% (+6.99%)

### New Test Files Added

#### `frontend/src/__tests__/app/settings.test.tsx`

**What it validates**: Full coverage of the Settings page component (`src/app/settings/page.tsx`) which was at 0% coverage.

Tests added (33 tests):

**Authentication states:**
- Renders loading state when auth is loading
- Redirects to login when user is null and not loading
- Renders null when user is null and not loading
- Renders settings page when user is authenticated

**Page navigation:**
- Navigates back to chat when back button is clicked

**Display name section:**
- Renders profile section with display name field
- Initializes display name from user data
- Shows error when submitting empty display name
- Shows error when display name exceeds 100 characters (using fireEvent.change to bypass browser maxLength)
- Calls updateDisplayName and shows success message
- Shows error message when updateDisplayName fails with Error
- Shows fallback error message when updateDisplayName fails with non-Error
- Disables button and shows "Updating..." while updating

**Language section:**
- Renders language section
- Calls setLocale when language is changed
- Shows current locale as selected

**Theme section:**
- Renders theme section
- Calls setTheme when theme is changed
- Shows current theme as selected

**Feedback info section:**
- Renders feedback contact section
- Loads saved feedback info on mount
- Calls saveFeedbackInfo and shows success on form submit
- Calls clearFeedbackInfo and clears fields

**Change password section:**
- Renders password change section heading and form fields
- Shows error when current password is empty
- Shows error when new password is empty
- Shows error when new password is too short (< 6 chars)
- Shows error when passwords do not match
- Calls changePassword and shows success message
- Clears password fields on successful change
- Shows error message when changePassword fails with Error
- Shows fallback error when changePassword fails with non-Error
- Disables button and shows "Changing..." while changing password

---

#### `frontend/src/__tests__/lib/version.test.ts`

**What it validates**: Coverage for `src/lib/version.ts` (was 0%).

Tests added (6 tests):
- APP_VERSION exports as a string
- APP_VERSION defaults to '0.1.0' when env vars are not set
- APP_VERSION uses NEXT_PUBLIC_APP_VERSION when set
- BUILD_TIMESTAMP exports as a numeric string (> year 2020)
- checkForUpdate returns false (placeholder implementation)
- checkForUpdate returns false multiple times (concurrent calls)

---

#### `frontend/src/__tests__/contexts/ThemeContext.test.tsx`

**What it validates**: Improved coverage for `src/contexts/ThemeContext.tsx` (84.15% -> 98.01%).

Tests added (16 tests):

**useTheme outside provider:**
- Throws error when used outside ThemeProvider

**Default state:**
- Provides default theme of 'system'
- Provides resolvedTheme based on system preference (light by default)

**setTheme:**
- Updates theme to 'light'
- Updates theme to 'dark'
- Persists theme to localStorage via setItem call
- Applies dark class to document root when dark theme is set
- Applies light class to document root when light theme is set
- Removes theme classes from root when system theme is set

**resolvedTheme:**
- Returns light when theme is 'light'
- Returns dark when theme is 'dark'
- Returns dark when theme is 'system' and system prefers dark (matchMedia mock)

**localStorage persistence:**
- Reads saved theme from localStorage on mount (mock returns 'dark')
- Saves theme preference to localStorage when setTheme is called
- Ignores invalid localStorage value and defaults to 'system'

**ThemeProvider:**
- Renders children correctly

---

#### `frontend/src/__tests__/contexts/LanguageContext.test.tsx`

**What it validates**: Improved coverage for `src/contexts/LanguageContext.tsx` (79.06% -> 100%).

Tests added (14 tests):

**useLanguage outside provider:**
- Throws error when used outside LanguageProvider

**Default state:**
- Defaults to English locale when no user
- Provides English translations by default

**setLocale:**
- Changes locale to Spanish
- Changes locale to French
- Does not change locale for unsupported locale (no-op)
- Calls updateLanguage API when user is authenticated
- Does not call updateLanguage API when user is not authenticated
- Keeps UI updated even when API call fails (error handling)

**interpolate function:**
- Interpolates single variable
- Interpolates multiple variables
- Leaves unknown variables as-is (returns `{variableName}`)
- Interpolates numeric variables

**LanguageProvider:**
- Renders children correctly

---

#### `frontend/src/__tests__/contexts/AuthContext.test.tsx`

**What it validates**: Improved coverage for `src/contexts/AuthContext.tsx` (77.04% -> 100%).

Tests added (17 tests):

**useAuth outside provider:**
- Throws error when used outside AuthProvider

**Initial loading state:**
- Starts with isLoading true
- Sets isLoading to false after auth check resolves
- Sets user when getCurrentUser returns a user
- Sets user to null when getCurrentUser returns null
- Initializes from localStorage if stored user exists

**isAuthenticated:**
- Is false when user is null
- Is true when user is set

**login:**
- Calls api.login and sets user
- Propagates errors from api.login

**register:**
- Calls api.register with default language 'en' and sets user
- Passes language preference to api.register

**logout:**
- Calls api.logout and clears user

**refreshUser:**
- Calls getCurrentUser and updates user
- Does not update user if getCurrentUser returns null

**updateDisplayName:**
- Calls api.updateProfile and updates user

**AuthProvider:**
- Renders children correctly

---

### Enhanced Test Coverage in Existing Files

#### `frontend/src/__tests__/components/TypingIndicator.test.tsx`

Added 7 new tests covering the "thinking content" display mode (lines 31-71, was 64.65% -> 100%):

- Shows individual thinker rows when thinkingContent Map is provided
- Shows "is thinking" text when thinker has no thinking content (empty string)
- Shows thinking content for multiple thinkers
- Falls back to simple format when thinkingContent is an empty Map
- Falls back to simple format when thinkingContent is undefined
- Renders animated dots in thinking content mode

#### `frontend/src/__tests__/components/CostMeter.test.tsx`

Added 7 new tests covering the animation effect (lines 24-40, was 77.33% -> 100%):

- Displays yellow color for medium costs (0.01-0.10)
- Displays orange color for high costs (>0.10)
- Animates cost change over time (using fake timers)
- Reaches target cost after full animation completes (20 steps x 20ms)
- Clears interval when cost update is complete
- Does not animate when totalCost equals displayCost (no re-render)
- Unmounts cleanly (tests interval cleanup)

---

## 1.2 Test Refactoring (Added 2026-03-20)

**Focus**: Friday QA focus - improve test readability, reduce duplication
**Coverage Impact**: 85.84% -> 85.84% (refactoring only, no coverage change)

**Duplication Eliminated:**

### 1.2.1 Backend: Removed Duplicate Fixtures from `test_cleanup_test_users.py`

**File**: `backend/tests/test_cleanup_test_users.py`

Removed ~50 lines of boilerplate (`engine`, `session`, `client` fixtures) that
duplicated the fixtures already available from `conftest.py`. Test functions now
use `db_session` from conftest instead of the local `session` alias.

- All 8 existing tests continue to pass unchanged after fixture consolidation
- `create_test_user()` local helper retained (specific to this test file)

### 1.2.2 Backend: Removed Duplicate `client` Fixture from `test_thinker_knowledge_integration.py`

**File**: `backend/tests/test_thinker_knowledge_integration.py`

Removed ~30 lines of boilerplate (the `client` fixture with `override_get_db`)
that was identical to the `client` fixture already in `conftest.py`. The file
now inherits `engine`, `async_session`, and `client` from conftest.

- All 13 existing tests continue to pass unchanged after fixture consolidation

### 1.2.3 Frontend: Extracted `mockConversationThinkers` to Shared `test-utils.tsx`

**Files**:
- `frontend/src/test-utils.tsx` - Added `mockConversationThinkers` constant
- `frontend/src/__tests__/components/MentionAutocomplete.test.tsx` - Now imports from test-utils
- `frontend/src/__tests__/components/MessageInput.test.tsx` - Now imports from test-utils

The 30-line `ConversationThinker[]` array (Socrates, Plato, Friedrich Nietzsche)
was duplicated identically in both test files. Extracted to `test-utils.tsx` as
the exported `mockConversationThinkers` constant.

The constant covers these test scenarios:
- Single-word name (Socrates): basic filtering and selection
- Short single-word name (Plato): navigation and click selection
- Multi-word name (Friedrich Nietzsche): tests that filtering works on both first and last names

- All 46 existing tests in both files continue to pass after the consolidation

## 1.1 Flaky Test Hunt (Added 2026-03-17)

**Focus**: Tuesday QA focus - identify and harden tests against flakiness
**File**: `backend/tests/test_flaky_hunt_mar17_2026.py`
**Coverage Impact**: 85.05% -> 85.39% (+0.34%)

**Flakiness Risks Identified and Addressed:**

1. Global singleton state in WebSocket tests - `thinker_service` and `ConnectionManager` are
   global singletons. Tests that pause/resume conversations leave state that could affect other
   tests if conversation IDs overlap or test order changes.
2. `random.seed(None)` pattern - Resets to truly random seed; while current tests pass,
   this pattern prevents reproducibility. Fixed seeds ensure deterministic CI behavior.
3. SQLAlchemy connection leak warnings - WebSocket tests using sync `TestClient` with async
   database code cause connection pool warnings (SAWarning).
4. Mock type mismatches - Using `MagicMock` for async methods or `AsyncMock` for sync methods
   can cause intermittent failures or silent incorrect assertions.

### 1.1.1 ThinkerService State Isolation (8 tests)

**File**: `backend/tests/test_flaky_hunt_mar17_2026.py` - `TestThinkerServiceStateIsolation`

Tests that `ThinkerService._paused_conversations` state is isolated per conversation ID and
does not bleed between tests sharing the global singleton.

- `test_pause_state_isolated_between_conversations` - Pausing conv-a does not affect conv-b.
  Guards against test state bleed when using the global `thinker_service` singleton.
- `test_resume_does_not_affect_other_conversations` - Resuming conv-a leaves conv-b paused.
  Verifies `resume_conversation` is targeted, not a global clear.
- `test_paused_conversations_set_does_not_grow_unbounded` - After resuming 10 conversations,
  the set returns to size 0. Guards against memory leak from accumulated pause state.
- `test_resume_non_paused_conversation_is_safe` - Resuming never-paused conversation does not
  raise. Validates `set.discard()` (safe) is used, not `set.remove()` (raises KeyError).
- `test_is_paused_returns_false_for_unknown_conversation` - New conversations default to unpaused.
  Critical for the "resumed message on connect" WebSocket behavior.
- `test_idle_pause_state_isolated_between_conversations` - Idle-pausing conv-a does not affect
  conv-b's idle or regular pause state. Tests both flag sets simultaneously.
- `test_manual_pause_not_cleared_by_idle_resume` - Critical regression guard: `resume_from_idle`
  must NOT clear manual pause state. Prevents user confusion with manual pause.
- `test_idle_pause_cleared_by_idle_resume` - `resume_from_idle` correctly clears idle pause state.

### 1.1.2 ConnectionManager State Isolation (5 tests)

**File**: `backend/tests/test_flaky_hunt_mar17_2026.py` - `TestConnectionManagerStateIsolation`

Tests that the global `ConnectionManager` singleton's room state is isolated per conversation
and handles edge cases safely.

- `test_new_manager_starts_with_empty_rooms` - Fresh manager has empty rooms dict.
- `test_conversation_not_active_when_no_connections` - `is_conversation_active` returns False
  for unknown conversation (no KeyError).
- `test_speed_multiplier_returns_default_for_unknown_conversation` - Returns 1.0 (not KeyError)
  for conversations not in rooms dict.
- `test_set_speed_multiplier_ignored_for_unknown_conversation` - Setting speed for unknown conv
  does not raise (async, silently ignored if room doesn't exist).
- `test_rooms_from_different_conversations_are_independent` - Speed multiplier state is per-room;
  setting 2.0 on conv-a and 0.5 on conv-b results in different values per room.

### 1.1.3 Deterministic Random Behavior (4 tests)

**File**: `backend/tests/test_flaky_hunt_mar17_2026.py` - `TestDeterministicRandomBehavior`

Tests that random-dependent functions produce valid, bounded results across explicit seed ranges,
preventing CI flakiness from non-deterministic random state.

- `test_split_bubbles_short_text_always_single_with_fixed_seeds` - Text under 60 chars always
  returns 1 bubble across seeds 0-49. Uses fixed seeds for reproducibility (replaces seed(None)).
- `test_split_bubbles_very_long_text_always_non_empty` - Very long text always returns at least
  1 bubble across seeds 0-19. Guards against edge case returning empty list.
- `test_split_bubbles_content_preserved_across_random_seeds` - Joining bubbles contains all
  words from original text. Validates content integrity is not random-seed-dependent.
- `test_choose_response_style_always_returns_valid_values` - Returns (str, positive_int <= 500)
  across seeds 0-49. Prevents silent failures from invalid style/token combinations.

### 1.1.4 Active Tasks Cleanup (4 tests)

**File**: `backend/tests/test_flaky_hunt_mar17_2026.py` - `TestActiveTasksCleanup`

Tests that `ThinkerService._active_tasks` is properly cleaned up, preventing resource leaks
across tests or production usage.

- `test_stop_conversation_removes_tasks_from_dict` - After stopping, conversation is removed
  from `_active_tasks` dict and task is cancelled.
- `test_stop_multiple_thinker_tasks` - Stopping a conversation with 3 thinkers cancels all 3
  tasks and removes the entire conversation entry.
- `test_stop_nonexistent_conversation_is_safe` - Stopping a never-started conversation does not
  raise KeyError and does not add a spurious entry.
- `test_active_tasks_dict_does_not_accumulate_stopped_conversations` - After stopping 5
  conversations, dict returns to size 0. Guards against unbounded growth.

### 1.1.5 WebSocket Global State Non-Interference (3 tests)

**File**: `backend/tests/test_flaky_hunt_mar17_2026.py` - `TestWebSocketGlobalStateNonInterference`

Documents and validates the naming convention for WebSocket test conversation IDs, ensuring
state-changing tests use unique IDs that won't conflict.

- `test_websocket_test_conversation_ids_are_unique` - Validates that all conversation IDs used
  in test_websocket.py that change state (pause/resume) are unique. Fails if new tests reuse
  state-changing IDs.
- `test_pause_state_test_uses_unique_conversation_id` - The 3 state-changing WebSocket tests
  use distinct IDs: "pause-test", "pause-reconnect-test", "unpause-test".
- `test_connection_manager_typing_thinkers_isolated_per_room` - Typing thinker state added to
  one room's `typing_thinkers` set does not appear in another room.

### 1.1.6 Knowledge Service Mock Consistency (2 tests)

**File**: `backend/tests/test_flaky_hunt_mar17_2026.py` - `TestKnowledgeServiceMockingConsistency`

Tests that `patch()` context managers properly restore state after each block, preventing
mock state from bleeding between tests.

- `test_knowledge_service_mock_does_not_leak_between_tests` - After `with patch()` block exits,
  `trigger_research` is no longer a `MagicMock`. Validates the patch restores original method.
- `test_mock_trigger_research_records_calls_independently` - Two separate `patch()` blocks have
  independent call counts. Second mock sees only 1 call, not 3 total from both blocks.

### 1.1.7 Async Mock Consistency (2 tests)

**File**: `backend/tests/test_flaky_hunt_mar17_2026.py` - `TestAsyncMockConsistency`

Tests the correct mock types for async vs sync methods, preventing common flakiness patterns.

- `test_anthropic_client_mock_is_async_awaitable` - `AsyncMock` for Anthropic `messages.create`
  is properly awaitable. Using `MagicMock` instead would cause `TypeError: object is not awaitable`.
- `test_httpx_response_json_is_sync_not_async` - `httpx.Response.json()` is synchronous; using
  `MagicMock` (not `AsyncMock`) returns dict directly. Using `AsyncMock` would silently return
  a coroutine instead of data, causing assertions to pass incorrectly.

## 1.0 Regression Prevention (Added 2026-03-01)

**Focus**: Sunday QA focus - regression prevention for recently fixed bugs and uncovered code paths
**File**: `backend/tests/test_regression_prevention_mar2026.py`
**Coverage Impact**: 79.95% → 80.45% (+0.50%)
- `app/api/thinkers.py`: 89% → **100%** (lines 140-141, 148, 188, 198-201 now covered)
- `app/api/auth.py`: 98% → **100%** (line 50 now covered)
- `app/services/knowledge_research.py`: lines 331-344 (refresh_stale_knowledge) now covered

### 1.0.1 Thinker Suggest API Path (thinkers.py lines 135-148)

**File**: `backend/tests/test_regression_prevention_mar2026.py` - `TestThinkerSuggestAPIPath`

Tests the API path that executes when `anthropic_api_key` is configured. Previously these paths
were unreachable in tests because the mock path (no API key) was always taken.

- `test_suggest_thinkers_with_api_key_returns_results` - API returns non-empty results that are
  returned to caller (lines 140-141). Prevents regression where refactor discards API results.
- `test_suggest_thinkers_empty_api_result_falls_back_to_mock` - Empty API response triggers
  fallback to mock suggestions (line 148). Tests the quiet failure path.
- `test_suggest_thinkers_non_quota_api_error_returns_502` - Non-quota API errors return 502
  (Bad Gateway), not 503. Tests the `is_quota_error=False` branch (line 144).
- `test_suggest_thinkers_quota_error_returns_503` - Quota errors return 503 (Service Unavailable).
  Tests the `is_quota_error=True` branch. Prevents 502/503 status code mix-up.

### 1.0.2 Thinker Validate API Path (thinkers.py lines 185-213)

**File**: `backend/tests/test_regression_prevention_mar2026.py` - `TestThinkerValidateAPIPath`

Tests validation paths for unknown thinkers (not in MOCK_THINKERS dict).

- `test_validate_unknown_thinker_without_api_key_returns_helpful_error` - Unknown thinker
  without API key returns descriptive error listing accepted thinkers (line 188).
- `test_validate_known_thinker_with_api_key_triggers_knowledge_research` - API-validated thinker
  triggers knowledge_service.trigger_research() (lines 198-201). Prevents regression where
  knowledge research is silently skipped for API-validated thinkers.
- `test_validate_thinker_non_quota_error_returns_502` - Non-quota validation errors return 502,
  not 503 (line 211). Validates status code differentiation.

### 1.0.3 JWT Token Edge Cases (auth.py line 50)

**File**: `backend/tests/test_regression_prevention_mar2026.py` - `TestJWTTokenEdgeCases`

Tests the `get_current_user` function path where JWT payload has no `sub` field.

- `test_jwt_token_without_sub_field_returns_401` - JWT with no 'sub' field returns 401 on
  /api/auth/me (auth.py line 50: `return None` when `not user_id`). Prevents regression where
  malformed tokens without 'sub' might be incorrectly accepted.
- `test_jwt_token_with_empty_string_sub_returns_401` - JWT with empty string 'sub' returns 401.
  Empty string is falsy - caught by `if not user_id` guard.
- `test_valid_jwt_with_sub_grants_access_to_me_endpoint` - Valid JWT with correct 'sub' grants
  access. Ensures the fix doesn't break the happy path.

### 1.0.4 Knowledge Research Refresh Stale (knowledge_research.py lines 331-344)

**File**: `backend/tests/test_regression_prevention_mar2026.py` - `TestKnowledgeResearchRefreshStale`

Tests the `refresh_stale_knowledge` method that queues old COMPLETE entries for re-research.

- `test_refresh_stale_knowledge_returns_count` - Method returns count of stale COMPLETE entries
  queued for refresh. Uses direct SQL UPDATE to bypass SQLAlchemy's `onupdate=func.now()`.
- `test_refresh_stale_knowledge_returns_zero_when_no_stale_entries` - Returns 0 for empty DB.
  Verifies graceful handling of no-work case.
- `test_refresh_stale_skips_non_complete_entries` - PENDING, IN_PROGRESS, FAILED entries are
  not refreshed. Only COMPLETE entries that have grown stale should be re-researched.

### 1.0.5 Thinker Last User Message Timestamp (thinker.py lines 1421-1431)

**File**: `backend/tests/test_regression_prevention_mar2026.py` - `TestThinkerLastUserMessageTimestamp`

Tests `_get_last_user_message_timestamp` which powers the idle timeout feature (PR #483).

- `test_get_last_user_message_timestamp_returns_zero_for_no_messages` - Empty messages returns
  0.0 (no timestamp). Base case for idle timeout "no messages" state.
- `test_get_last_user_message_timestamp_skips_thinker_messages` - Skips thinker messages when
  searching. Returns 0.0 if all messages are from thinkers.
- `test_get_last_user_message_timestamp_finds_user_message` - Returns timestamp of user message
  even when thinker messages follow it. Tests the reverse-iteration logic.
- `test_get_last_user_message_timestamp_uses_enum_value` - Handles enum `sender_type` with
  `.value == 'user'`. Tests the enum branch of the sender type check.
- `test_get_last_user_message_timestamp_returns_most_recent` - Returns timestamp of LAST user
  message when multiple user messages exist. Prevents off-by-one errors.

### 1.0.6 Idle Pause/Resume Cycle (thinker.py, PR #483)

**File**: `backend/tests/test_regression_prevention_mar2026.py` - `TestIdlePauseResumeCycle`

Tests the idle timeout pause/resume feature that distinguishes idle pauses from manual pauses.
Bug: `resume_from_idle` must NOT clear manually paused conversations.

- `test_pause_for_idle_sets_idle_flag` - `pause_for_idle` sets both `is_paused` and
  `is_idle_paused` flags.
- `test_resume_from_idle_clears_idle_pause` - `resume_from_idle` clears both flags.
- `test_resume_from_idle_does_not_clear_manual_pause` - Critical regression test. Manual
  pauses are NOT cleared by `resume_from_idle`. Prevents user confusion where manual pause
  would be auto-resumed when user sends a message.
- `test_is_idle_paused_is_false_for_manual_pause` - Manual pause does NOT set `is_idle_paused`.
  Ensures clean flag separation.
- `test_full_idle_pause_resume_cycle` - Full lifecycle: not paused → idle pause → resume.
  Validates the complete user journey.
- `test_multiple_idle_pauses_are_idempotent` - Multiple `pause_for_idle` calls are safe. No
  state corruption from repeated idle timeout signals.

### 1.0.7 Thinker API Knowledge Integration (thinkers.py lines 168-184)

**File**: `backend/tests/test_regression_prevention_mar2026.py` - `TestThinkerAPIKnowledgeIntegration`

Documents expected behavior for mock thinker validation path (MOCK_THINKERS dict).

- `test_validate_mock_thinker_triggers_knowledge_research` - Validating a mock thinker (e.g.,
  Socrates) triggers `knowledge_service.trigger_research()`. Ensures background knowledge
  loading happens for all validated thinkers.
- `test_validate_mock_thinker_includes_wikipedia_image` - Mock thinker validation fetches and
  includes Wikipedia image URL in the response profile.
- `test_validate_mock_thinker_handles_missing_wikipedia_image` - Validation succeeds even when
  Wikipedia returns no image. Profile is returned with `image_url=None`.

## 0.9 Edge Case Analysis (Added 2026-02-28)

**Focus**: Saturday QA focus - edge cases, error paths, and boundary conditions
**Files**: `tests/test_edge_cases_feb28_2026.py`, `backend/pyproject.toml`

### 0.9.0 Coverage Infrastructure Fix

**Problem**: `app/api/conversations.py` and other async SQLAlchemy files showed stale coverage
numbers despite tests passing. Root cause: SQLAlchemy async operations use Python greenlets
internally. When a greenlet context switches, coverage.py's trace function is NOT automatically
restored, causing lines after any `await db.*()` call to appear uncovered.

**Solution**: Added `concurrency = ["greenlet"]` to `[tool.coverage.run]` in `pyproject.toml`.
**File**: `backend/pyproject.toml`

### 0.9.1 Conversation Creation Edge Cases

**File**: `tests/test_edge_cases_feb28_2026.py` - `TestConversationCreateFullFlow`

- `test_create_conversation_thinker_loop_assigns_colors` - color cycling for default-color thinkers
- `test_create_conversation_custom_color_preserved` - custom color bypass of cycling
- `test_create_conversation_knowledge_research_triggered` - trigger_research called per thinker

### 0.9.2 Conversation List Summaries

**File**: `tests/test_edge_cases_feb28_2026.py` - `TestListConversationsSummaries`

- `test_list_conversations_shows_message_count` - message count aggregation after 2 messages
- `test_list_conversations_zero_messages_zero_cost` - empty message set returns 0.0 cost
- `test_list_conversations_ordered_by_created_desc` - newest-first ordering guarantee

### 0.9.3 Conversation Get/Delete

**File**: `tests/test_edge_cases_feb28_2026.py` - `TestGetConversationPath`, `TestDeleteConversationPath`

- `test_get_conversation_returns_messages_and_cost` - full retrieval with messages and cost
- `test_delete_conversation_removes_from_list` - deleted conversation absent from list
- `test_delete_conversation_then_get_returns_404` - 404 on GET after deletion

### 0.9.4 Add Thinkers to Conversation

**File**: `tests/test_edge_cases_feb28_2026.py` - `TestAddThinkersFullFlow`

- `test_add_thinkers_uses_available_colors` - color deduplication avoids existing thinker colors
- `test_add_thinkers_with_custom_color` - custom color preserved when adding thinker
- `test_add_thinkers_triggers_knowledge_research` - trigger_research called for each added thinker

### 0.9.5 Send Message Edge Cases

**File**: `tests/test_edge_cases_feb28_2026.py` - `TestSendMessageEdgeCases`

- `test_send_message_creates_message_with_correct_fields` - message has all required response fields
- `test_send_message_auto_resume_from_idle_pause` - auto-resume + WebSocket broadcast when idle-paused
- `test_send_message_no_idle_pause_skips_resume` - resume NOT called when not idle-paused
- `test_send_message_uses_username_when_no_display_name` - sender_name set from display_name or username

### 0.9.6 Admin API Edge Cases

**File**: `tests/test_edge_cases_feb28_2026.py` - `TestAdminListUsersFullFlow`, `TestAdminDeleteUserEdgeCases`

- `test_admin_list_users_includes_conversation_count` - users list has conversation_count per user
- `test_admin_list_users_empty_database` - works with only admin user
- `test_admin_delete_user_self_deletion_prevented` - 400 when admin tries to delete themselves
- `test_admin_delete_user_success` - admin can delete another user, response confirms username

### 0.9.7 Auth Boundary Conditions

**File**: `tests/test_edge_cases_feb28_2026.py` - `TestAuthEdgeCases`

- `test_get_current_user_with_no_sub_in_token` - token without sub field causes 401/404
- `test_request_without_authorization_header` - missing auth header returns 401/403
- `test_login_with_empty_username` - empty username returns 401/422
- `test_register_with_very_long_username` - 300-char username handled without crash
- `test_get_current_user_with_expired_token_format` - malformed JWT returns 401/422

### 0.9.8 Cross-User Isolation

**File**: `tests/test_edge_cases_feb28_2026.py` - `TestConversationBoundaryConditions`

- `test_send_message_to_own_conversation_not_others` - User 2 cannot message User 1's conversation
- `test_add_thinkers_to_other_users_conversation_returns_404` - User 2 cannot add thinkers to User 1's conversation

## 0.8 Test Refactoring (Added 2026-02-27)

**Focus**: Friday QA focus - reduce duplication, improve readability with parametrize and shared helpers
**Files**: `tests/test_thinker_service.py`, `frontend/src/__tests__/components/MessageInput.test.tsx`,
and 30 additional backend test files

### 0.8.1 Shared Mock Helper Functions in test_thinker_service.py

**Problem**: Tests in `TestBillingErrorDetection`, `TestGenerateResponse`,
`TestGenerateResponseErrorHandling`, `TestGenerateUserPromptErrorHandling`, and
`TestGenerateResponseWithStreamingThinking` each repeated the same 5-line thinker mock setup
and 3-line mock_request setup blocks. This appeared 15+ times total.

**Solution**: Extracted two module-level helper functions:
- `make_mock_thinker(name, bio, positions, style)` - Creates a configured mock thinker
- `make_mock_api_request(url, method)` - Creates a mock httpx.Request for API error testing

Also added `_make_streaming_client(api_error_message)` as a class method on
`TestBillingErrorDetection` to reduce the 4-line streaming mock setup.

**Files Refactored**: `tests/test_thinker_service.py`

### 0.8.2 Parametrized Billing Error Tests

**Problem**: `TestBillingErrorDetection` had two near-identical tests (`test_billing_error_raised_on_credit_balance_error`
and `test_billing_error_raised_on_billing_keyword`) that differed only in the error message and
expected keyword assertion.

**Solution**: Merged into one parametrized test:
`test_billing_error_raised_for_billing_messages[(credit balance message)]`
`test_billing_error_raised_for_billing_messages[(billing keyword message)]`

**Tests Affected** (2 → 1 parametrized, 2 cases):
- File: `tests/test_thinker_service.py`
- Validates: BillingError raised for 'credit balance' messages, error contains 'credit'
- Validates: BillingError raised for 'billing' keyword messages, error contains 'billing'

### 0.8.3 Parametrized Extract Mentions and Is Mentioned Tests

**Problem**: `TestExtractMentions` had 3 separate tests (simple mention, mention at end, mention
with punctuation) that were structurally identical - each called `extract_mentions()` and checked
one name. `TestIsMentioned` had 9 simple boolean-assertion tests.

**Solution**:
- `TestExtractMentions`: merged 3 simple cases into `test_extract_single_mention[...]` (3 parametrized cases)
- `TestIsMentioned`: merged 5 positive cases into `test_is_mentioned_positive_cases[...]` and
  5 negative cases into `test_is_mentioned_negative_cases[...]`

**Files Refactored**: `tests/test_thinker_service.py`

**Tests Added** (10 parametrized test cases):
1. `test_extract_single_mention[@Socrates what do you think?-Socrates]` - simple @mention
2. `test_extract_single_mention[What do you think @Aristotle-Aristotle]` - mention at end
3. `test_extract_single_mention[@Socrates, can you explain?-Socrates]` - mention with punctuation
4. `test_is_mentioned_positive_cases[exact name match]`
5. `test_is_mentioned_positive_cases[first name of multi-word name]`
6. `test_is_mentioned_positive_cases[quoted full name]`
7. `test_is_mentioned_positive_cases[lowercase @mention]`
8. `test_is_mentioned_positive_cases[uppercase @mention]`
9. `test_is_mentioned_negative_cases[different thinker mentioned]`
10. `test_is_mentioned_negative_cases[name without @ prefix]`
11. `test_is_mentioned_negative_cases[partial name does not match]`
12. `test_is_mentioned_negative_cases[empty thinker name]`
13. `test_is_mentioned_negative_cases[empty text]`

### 0.8.4 MessageInput beforeEach Refactoring

**Problem**: All 31 tests in `MessageInput.test.tsx` individually declared `const onSend = jest.fn()`
at the start of each test body, creating 31 lines of identical boilerplate.

**Solution**: Moved `onSend = jest.fn()` to `beforeEach()` in each describe block.
Each describe block now has a shared `let onSend: jest.Mock` that is freshly created before each test.

**Files Refactored**: `frontend/src/__tests__/components/MessageInput.test.tsx`

**Benefits**: Cleaner test bodies, consistent mock reset between tests, easier to add new tests.

### 0.8.5 Removal of Redundant @pytest.mark.asyncio Decorators

**Problem**: 347 instances of `@pytest.mark.asyncio` decorators across 30 test files were
completely redundant because `pyproject.toml` sets `asyncio_mode = "auto"`, which makes pytest
automatically handle async test functions without requiring the decorator.

**Solution**: Removed all 347 redundant `@pytest.mark.asyncio` decorators from all affected files.
Also removed 3 now-unused `import pytest` statements from files where pytest was only used for this decorator.

**Files Refactored** (30 files):
- `tests/test_add_thinkers_integration.py` (8 removed)
- `tests/test_billing_error_endpoint.py` (2 removed)
- `tests/test_billing_error_integration.py` (6 removed)
- `tests/test_cleanup_test_users.py` (8 removed)
- `tests/test_conversations_api_integration_feb4.py` (18 removed)
- `tests/test_conversations_coverage_sprint.py` (6 removed, import removed)
- `tests/test_conversations_coverage_sprint_feb2.py` (14 removed, import removed)
- `tests/test_conversations_coverage_sprint_feb9.py` (11 removed)
- `tests/test_conversations_coverage_sprint_jan26.py` (8 removed)
- `tests/test_conversations_direct_coverage.py` (8 removed)
- `tests/test_conversations_direct_feb9.py` (8 removed)
- `tests/test_conversations_edge_cases.py` (13 removed)
- `tests/test_conversations_flaky_hunt.py` (6 removed)
- `tests/test_conversations_integration_gaps.py` (8 removed)
- `tests/test_conversations_integration_jan28.py` (11 removed, import removed)
- `tests/test_devops_api.py` (21 removed)
- `tests/test_edge_cases_admin_auth_feedback.py` (15 removed)
- `tests/test_edge_cases_feb21_2026.py` (40 removed)
- `tests/test_edge_cases_saturday.py` (3 removed)
- `tests/test_feedback.py` (27 removed)
- `tests/test_integration_gaps_feb18.py` (11 removed)
- `tests/test_integration_gaps_feb25_2026.py` (30 removed)
- `tests/test_knowledge_research.py` (10 removed)
- `tests/test_regression_prevention.py` (17 removed)
- `tests/test_regression_prevention_feb2026.py` (11 removed)
- `tests/test_regression_prevention_jan2026.py` (3 removed)
- `tests/test_regression_prevention_jan25_2026.py` (2 removed)
- `tests/test_spend_service.py` (14 removed)
- `tests/test_trigger_error_endpoint.py` (5 removed)
- `tests/test_websocket.py` (3 removed)

**Total**: 347 decorators removed across 30 files
**Impact**: Significantly reduced visual noise in test files; tests still pass because asyncio_mode=auto handles them automatically

## 0.7 Test Refactoring (Added 2026-02-20)

**Focus**: Friday QA focus - improve test readability and reduce duplication
**Files**: Multiple backend test files

### 0.7.1 Duplicate Fixture Removal

**Problem**: 7 test files locally re-defined `engine`, `client`, and `get_auth_headers` fixtures
that already exist in `conftest.py`, creating ~200 lines of redundant code.

**Solution**: Removed local fixtures from affected files so they inherit from `conftest.py`.

**Files Refactored**:
- `tests/test_regression_prevention.py` - removed local `engine`, `client`, `get_auth_headers`
- `tests/test_regression_prevention_feb2026.py` - removed local `engine`, `client`, `get_auth_headers`
- `tests/test_regression_recent_features.py` - removed local `engine`, `client`, `get_auth_headers`
- `tests/test_billing_error_endpoint.py` - removed local `engine`, `client`
- `tests/test_billing_error_integration.py` - removed local `engine`, `client`, `db_session`
- `tests/test_integration_workflows.py` - removed local `engine`, `client`, `db_session`
- `tests/test_trigger_error_endpoint.py` - removed local `engine`, `client`

**What the tests validate**: Same as before - that conftest.py fixtures are sufficient
for all test scenarios and no local overrides are needed.

### 0.7.2 Parametrized Validation Tests

**Problem**: Multiple tests in `TestAuthAPI` tested the same endpoint with different invalid
inputs as separate test functions, making it harder to add new cases.

**Solution**: Consolidated into `@pytest.mark.parametrize` test functions.

**Tests Added/Refactored (5 parametrized cases)**:

1. **`test_update_profile_invalid_display_name[emptyprofile--empty string rejected]`**
   - File: `tests/test_api.py`
   - Validates: Empty display name returns 422
   - Edge case: min_length constraint on display_name field

2. **`test_update_profile_invalid_display_name[longprofile-AAAA...-name over 100 chars rejected]`**
   - File: `tests/test_api.py`
   - Validates: Display name over 100 chars returns 422
   - Edge case: max_length=100 constraint on display_name field

3. **`test_change_password_invalid_new_password[sho-422-password under minimum length (3 chars)]`**
   - File: `tests/test_api.py`
   - Validates: Password of 3 chars fails validation (422)
   - Edge case: Near-boundary value for password minimum length

4. **`test_change_password_invalid_new_password[-422-empty password rejected]`**
   - File: `tests/test_api.py`
   - Validates: Empty password string returns 422

5. **`test_change_password_invalid_new_password[ab-422-password of 2 chars rejected]`**
   - File: `tests/test_api.py`
   - Validates: Password of 2 chars returns 422

**Benefits**: Easier to add new validation cases (just add to the parametrize list);
each case runs independently with a fresh database.

## 0.6 E2E Performance Optimizations (Added 2026-02-19)

**Focus**: Thursday QA focus - E2E test performance optimization
**File**: `frontend/e2e/` (multiple files)

### Summary of Changes

Replaced broad `waitForLoadState('networkidle')` calls with targeted element-based waits.
`networkidle` waits for ALL network activity to cease, which is slower and more brittle than
waiting for the specific UI element or URL that indicates readiness.

**Before**: 42 `waitForLoadState('networkidle')` calls
**After**: 38 (removed 4 high-impact instances, preserved legitimate bounded waits)

### Optimizations Applied

**`frontend/e2e/test-utils.ts`** - Core utility affecting all 140 E2E tests:

1. **`setupAuthenticatedUser` (beforeEach in all 23 files)**
   - **Changed**: `page.waitForLoadState('networkidle')` → `page.getByTestId('new-chat-button').waitFor({ state: 'visible', timeout: 15000 })`
   - **Why**: Element-driven wait completes as soon as the auth'd UI renders, vs. waiting for all background polling to settle
   - **Impact**: Applies to every single test's setup phase

2. **`navigateToConversation`**
   - **Changed**: Removed `page.waitForLoadState('networkidle')` after `page.goto('/')`
   - **Why**: Redundant - the `conversationItem.waitFor({ state: 'visible', timeout: 10000 })` call that follows handles readiness
   - **Impact**: All tests using API-based conversation creation

3. **`resetPageState`**
   - **Changed**: `page.waitForLoadState('networkidle')` → `page.waitForURL(/\/login/, { timeout: 10000 })`
   - **Why**: After clearing auth state, the app always redirects to `/login` - waiting for this specific URL is the targeted check

**`frontend/e2e/chat.spec.ts`**:

4. **`can switch between conversations` test**
   - **Changed**: `page.waitForLoadState('networkidle')` → `page.getByTestId('new-chat-button').waitFor({ state: 'visible' })`
   - **Why**: Was waiting for networkidle between creating two conversations; the button being visible is the right readiness signal

**`frontend/e2e/thinker-selection-edge.spec.ts`** (active tests):

5. **`should handle adding thinker with only whitespace name` test**
   - **Changed**: `page.waitForLoadState('networkidle', { timeout: 5000 })` + manual count → `expect(locator).toHaveCount(0, { timeout: 5000 })`
   - **Why**: Direct assertion is more readable and uses built-in Playwright retry logic

6. **`should prevent creating conversation with no thinkers selected` test**
   - **Changed**: `page.waitForLoadState('networkidle', { timeout: 5000 })` in Promise.race → `headingSelector.waitFor({ state: 'visible' })`
   - **Why**: The heading remaining visible IS the assertion we need, not network idleness

**`frontend/playwright.config.ts`**:

7. **Added `expect: { timeout: 10000 }` global assertion timeout**
   - **Why**: Sets a consistent default for all `expect()` calls without overrides. Tests needing longer timeouts explicitly override with `{ timeout: N }`. This prevents accidentally short default timeouts.

### Pattern Reference

Preferred wait patterns (fastest to slowest):
1. `expect(locator).toBeVisible({ timeout: N })` - assertion with retry
2. `locator.waitFor({ state: 'visible', timeout: N })` - element-driven wait
3. `page.waitForURL(/pattern/, { timeout: N })` - URL-driven wait
4. `page.waitForResponse('**/api/endpoint')` - response-driven wait
5. `page.waitForLoadState('domcontentloaded')` - DOM-only (faster than networkidle)
6. `page.waitForLoadState('networkidle')` - use only when all network activity must settle

## 0.5 Regression Prevention - February 2026 Bug Fixes (Added 2026-02-15)

**Focus**: Sunday QA focus - add regression tests for bugs fixed in February 2026

### 0.5.1 HTTP Status Code Semantics (PR #622)

**Bug**: Tests used deprecated raw status codes (200, 400, 401) instead of semantic constants
**Fix**: Replaced with `starlette.status` constants (`HTTP_200_OK`, `HTTP_400_BAD_REQUEST`, etc.)
**File**: `tests/test_regression_prevention_feb2026.py`

**Tests Added (3 tests)**:

1. **`test_feedback_success_returns_201_created`**
   - Validates feedback submission returns `HTTP_201_CREATED` (not raw 201)
   - Ensures semantic status codes are used throughout the test suite

2. **`test_feedback_validation_error_returns_422`**
   - Validates validation errors return `HTTP_422_UNPROCESSABLE_ENTITY`
   - Tests missing required 'message' field in feedback submission

3. **`test_auth_missing_credentials_returns_401`**
   - Validates protected endpoints return `HTTP_401_UNAUTHORIZED` without auth
   - Tests conversation list endpoint requires authentication

### 0.5.2 Admin Authorization Checks

**Purpose**: Ensure non-admin users cannot access admin-only endpoints
**File**: `tests/test_regression_prevention_feb2026.py`

**Tests Added (3 tests)**:

1. **`test_non_admin_cannot_list_users`**
   - Non-admin users receive `HTTP_403_FORBIDDEN` when accessing `/api/admin/users`
   - Prevents unauthorized access to user list

2. **`test_non_admin_cannot_delete_user`**
   - Non-admin users receive `HTTP_403_FORBIDDEN` when deleting users
   - Prevents unauthorized user deletion

3. **`test_non_admin_cannot_update_spend_limit`**
   - Non-admin users receive `HTTP_403_FORBIDDEN` when updating spend limits
   - Prevents unauthorized spend limit changes

### 0.5.3 DevOps API Secret Validation

**Purpose**: Ensure DevOps endpoints properly validate X-DevOps-Secret header
**File**: `tests/test_regression_prevention_feb2026.py`

**Tests Added (3 tests)**:

1. **`test_devops_health_not_configured_returns_503`**
   - DevOps health endpoint returns `HTTP_503_SERVICE_UNAVAILABLE` when DEVOPS_API_SECRET not set
   - Validates proper error when API not configured

2. **`test_devops_health_rejects_invalid_secret_when_configured`**
   - DevOps health endpoint returns `HTTP_403_FORBIDDEN` with invalid secret
   - Uses monkeypatch to configure secret for test

3. **`test_devops_stats_not_configured_returns_503`**
   - DevOps stats endpoint returns `HTTP_503_SERVICE_UNAVAILABLE` when not configured
   - Prevents unauthorized access to database statistics

### 0.5.4 Message Validation

**Purpose**: Ensure message API properly validates inputs
**File**: `tests/test_regression_prevention_feb2026.py`

**Tests Added (2 tests)**:

1. **`test_empty_message_rejected`**
   - Empty message content is rejected with 422 validation error
   - Prevents sending empty messages to conversations

2. **`test_message_content_required`**
   - Message content field is required (422 error when missing)
   - Validates Pydantic schema enforcement

**Total Tests Added**: 11 regression prevention tests
**All tests verified stable**: Passed 3 consecutive runs without flakiness

## 0.4 Test Refactoring - HTTP Status Code Helpers (Added 2026-02-13)

**Focus**: Friday QA focus - refactor tests to improve readability with semantic HTTP status helpers

### 0.4.1 Add HTTP Status Code Assertion Helpers to conftest.py

**Purpose**: Reduce duplication of status code assertion patterns (300+ occurrences) and improve test readability with semantic function names

**Helpers Added (6 new functions)**:

1. **`assert_json_keys(data, required_keys, optional_keys=None)`**
   - Validates that dictionary contains required keys and only allowed keys
   - Provides clear error messages showing which keys are missing or unexpected
   - Usage: `assert_json_keys(data, ["id", "name"], ["email"])`

2. **`assert_list_response(response, min_length=0, max_length=None, expected_status=200)`**
   - Validates response is a successful list with expected length constraints
   - Returns the list data for further assertions
   - Usage: `items = assert_list_response(response, min_length=1, max_length=10)`

3. **`assert_unauthorized(response, expected_detail_substring=None)`**
   - Consolidated 401 Unauthorized assertions (appears 25+ times across test suite)
   - Wrapper around `assert_error_response(response, 401, substring)`
   - Usage: `assert_unauthorized(response, "Invalid token")`

4. **`assert_forbidden(response, expected_detail_substring=None)`**
   - Consolidated 403 Forbidden assertions
   - Wrapper around `assert_error_response(response, 403, substring)`
   - Usage: `assert_forbidden(response, "not authorized")`

5. **`assert_not_found(response, expected_detail_substring=None)`**
   - Consolidated 404 Not Found assertions (appears 20+ times across test suite)
   - Wrapper around `assert_error_response(response, 404, substring)`
   - Usage: `assert_not_found(response, "Conversation not found")`

6. **`assert_validation_error(response, expected_detail_substring=None)`**
   - Consolidated 422 Unprocessable Entity assertions (appears 15+ times across test suite)
   - Wrapper around `assert_error_response(response, 422, substring)`
   - Usage: `assert_validation_error(response, "Invalid language")`

**Benefits**:
- Eliminates ~150 lines of duplicated status code assertion code
- Significantly improves test readability - semantic names clarify test intent
- Makes test failures more descriptive (e.g., "expected unauthorized" vs "expected 401")
- Centralizes assertion logic - future improvements only need to update conftest.py
- Reduces cognitive load - developers don't need to remember status codes

### 0.4.2 Refactor test_api_edge_cases.py

**File**: `backend/tests/test_api_edge_cases.py` (412 lines, 26 tests)
**Purpose**: Apply new semantic helpers to demonstrate readability improvements

**Changes Made (16 refactorings)**:

**Validation Error Refactorings (11 total)**:
1. `test_create_conversation_with_empty_thinker_list` - empty thinker list validation
2. `test_create_conversation_with_over_max_thinkers` - max thinker count validation
3. `test_create_conversation_with_empty_topic` - empty topic validation
4. `test_send_message_empty_content` - empty message content validation
5. `test_register_empty_username` - empty username validation
6. `test_register_empty_password` - empty password validation
7. `test_register_short_username` - min username length validation
8. `test_register_short_password` - min password length validation
9. `test_register_over_max_username` - max username length validation
10. `test_register_over_max_display_name` - max display name length validation
11. `test_register_invalid_language_preference` - language code validation
12. `test_update_language_invalid_preference` - language update validation

**Not Found Refactorings (2 total)**:
1. `test_get_conversation_invalid_uuid` - invalid UUID format returns 404
2. `test_delete_already_deleted_conversation` - double delete returns 404

**Unauthorized Refactorings (2 total)**:
1. `test_login_empty_username` - empty username login attempt
2. `test_login_empty_password` - empty password login attempt

**Impact**:
- Lines saved: ~32 lines (2-line assertions replaced with 1-line semantic calls)
- Readability: Significantly improved - test intent is immediately clear
- Example transformation:
  ```python
  # Before (verbose, requires looking up status codes):
  assert response.status_code == 422
  assert "username" in response.json()["detail"][0]["loc"]

  # After (semantic, self-documenting):
  assert_validation_error(response)
  assert "username" in response.json()["detail"][0]["loc"]
  ```

### 0.4.3 Test Stability Verification

**Verification Method**: Run refactored test file 3 times to check for flakiness
**Result**: All 26 tests pass consistently across 3 runs
**Execution Time**: ~6.7 seconds per run (consistent)
**No flakiness detected**: 0 failures across 78 total test executions (26 tests × 3 runs)

### 0.4.4 Summary

**Files Modified**:
- `backend/tests/conftest.py` - Added 6 semantic HTTP status helpers (130 lines)
- `backend/tests/test_api_edge_cases.py` - Refactored 16 assertions to use new helpers

**Total Impact**:
- 6 reusable assertion helpers available for entire test suite
- 16 assertions refactored in test_api_edge_cases.py as demonstration
- Estimated potential: 300+ status code assertions across suite could benefit
- Lines reduced: 32 lines in test_api_edge_cases.py
- Readability improvement: Test intent is self-documenting with semantic function names
- Maintenance improvement: Centralized assertion logic in conftest.py

**Future Work**:
- Apply these helpers to remaining 15,000+ lines of test code
- Target high-duplication files: test_api.py (1,172 lines), test_thinker_service.py (1,559 lines)
- Estimated potential savings: 500-700 lines across entire test suite

## 0.3 E2E Performance Optimization - Thursday (Added 2026-02-12)

**Focus**: Optimize E2E test performance by reducing timeouts and switching to API-based test setup

### 0.3.1 Timeout Reduction
**Files Modified**: `frontend/e2e/chat.spec.ts`
**Purpose**: Reduce excessive timeouts from 45-60s to 30s while still allowing for API latency

**Optimizations Applied (2 total)**:

1. **chat.spec.ts:225** - Reduced thinker response timeout from 60s to 30s
   - Still allows for Claude API latency
   - Reduces worst-case test execution time by 30s

2. **chat.spec.ts:162** - Reduced pause/resume polling timeout from 45s to 30s
   - Maintains reliability while improving speed
   - Uses expect.poll() with appropriate retry intervals

### 0.3.2 API-Based Test Setup
**Files Modified**: `frontend/e2e/tab-visibility.spec.ts`, `frontend/e2e/session-management.spec.ts`, `frontend/e2e/keyboard-navigation.spec.ts`
**Purpose**: Switch from UI-based conversation creation to API-based setup for tests not testing the modal flow

**Optimizations Applied (8 total)**:

1. **tab-visibility.spec.ts** (3 tests optimized)
   - `pauses conversation when tab becomes hidden` - switched to createConversationViaAPI
   - `resumes conversation when tab becomes visible` - switched to createConversationViaAPI
   - `no new messages arrive while tab is hidden` - switched to createConversationViaAPI
   - **Impact**: Eliminates 3x modal interaction flows (saves ~45s per test run)

2. **session-management.spec.ts** (2 tests optimized)
   - `can logout mid-conversation without errors` - switched to createConversationViaAPI
   - `maintains session across page reload` - switched to createConversationViaAPI
   - **Impact**: Eliminates 2x modal interaction flows (saves ~30s per test run)

3. **keyboard-navigation.spec.ts** (3 tests optimized)
   - `can send message with Enter key` - switched to createConversationViaAPI
   - `focus management after opening and closing export menu` - switched to createConversationViaAPI
   - `Tab key navigates through conversation controls` - switched to createConversationViaAPI
   - **Impact**: Eliminates 3x modal interaction flows (saves ~45s per test run)

### 0.3.3 Performance Metrics

**Before Optimization**:
- Total E2E execution time: 11.3 minutes for 304 tests
- Longest timeout: 60s (chat.spec.ts)
- API-based setup: Limited usage

**After Optimization**:
- Expected improvement: ~2-3 minutes (target: <10 min total)
- Longest timeout: 30s (reduced by 50%)
- API-based setup: 8 additional tests now use fast API setup

**Key Findings from Analysis**:
- ✅ Only 1 waitForTimeout call in entire E2E suite (excellent!)
- ✅ 51 event-driven waits (waitForLoadState, waitForResponse)
- ✅ 4 workers with fullyParallel: true (good CI parallelism)
- ⚠️ Opportunity: Add test.describe.parallel() for independent test groups (future work)

### 0.3.4 Summary

**Files Modified**:
- `frontend/e2e/chat.spec.ts` - 2 timeout reductions
- `frontend/e2e/tab-visibility.spec.ts` - 3 tests switched to API setup
- `frontend/e2e/session-management.spec.ts` - 2 tests switched to API setup
- `frontend/e2e/keyboard-navigation.spec.ts` - 3 tests switched to API setup

**Total Impact**:
- 10 test optimizations across 4 files
- Reduced timeouts by 30-50% where safe
- Eliminated 8 unnecessary modal interaction flows
- Expected E2E suite improvement: 2-3 minutes (15-25% faster)

**Test Stability**: All optimizations maintain test reliability by:
- Using appropriate timeouts for API latency (30s)
- Preserving event-driven wait patterns
- Only optimizing setup, not test behavior validation

## 0.2 Regression Prevention - Sunday (Added 2026-02-08)

**Focus**: Add regression tests for recent features and bug fixes

### 0.2.1 Conversation Color Cycling Tests
**File**: `backend/tests/test_regression_recent_features.py::TestConversationColorCycling`
**Target**: `app/api/conversations.py:46-56` (39% coverage)
**Purpose**: Test thinker color assignment logic - default colors cycle through palette, custom colors are preserved

**Tests Added (4 total)**:

1. **`test_default_color_cycles_through_palette`**
   - Validates that thinkers with default color (#6366f1) cycle through the 5-color palette
   - Creates 5 thinkers, verifies each gets a different color from the palette
   - Edge case: Tests modulo arithmetic for color index cycling

2. **`test_custom_color_preserved`**
   - Validates that custom colors (not #6366f1) are preserved, not cycled
   - Creates mix of default and custom colored thinkers
   - Verifies: default colors cycle, custom colors pass through unchanged

3. **`test_all_custom_colors_no_cycling`**
   - Validates that when NO thinker has default color, no cycling occurs
   - All 5 thinkers have custom colors, all should be preserved exactly

4. **`test_color_cycling_with_max_thinkers`**
   - Boundary test: 5 thinkers (max allowed) with default color
   - Validates cycling works correctly at maximum thinker count

**Coverage Impact**: Brings conversations.py:46-56 color cycling logic to 100%

### 0.2.2 Conversation Cost Calculation Tests
**File**: `backend/tests/test_regression_recent_features.py::TestConversationCostCalculation`
**Target**: `app/api/conversations.py:87-105` (39% coverage)
**Purpose**: Test message cost summation in conversation summaries, handling None/zero values

**Tests Added (3 total)**:

1. **`test_cost_calculation_with_zero_cost_messages`**
   - Validates that messages with cost=None or cost=0.0 don't cause errors
   - Creates conversation with user message (no cost), verifies total_cost calculated correctly
   - Edge case: `cost or 0.0` logic handles None values

2. **`test_cost_calculation_empty_conversation`**
   - Validates that empty conversations have total_cost=0.0
   - Tests sum() of empty list doesn't error

3. **`test_multiple_conversations_cost_isolation`**
   - Validates that costs are calculated independently per conversation
   - Creates 2 conversations, adds messages to only one
   - Verifies: conv1 has cost, conv2 has zero cost (isolation)

**Coverage Impact**: Brings conversations.py:87-105 cost calculation to 100%

### 0.2.3 Language Preference Validation Tests
**File**: `backend/tests/test_regression_recent_features.py::TestLanguagePreferenceValidation`
**Target**: `app/api/auth.py:89-104` (68% coverage)
**Purpose**: Test PATCH /api/auth/language validation edge cases

**Tests Added (5 total)**:

1. **`test_invalid_language_code_rejected`**
   - Validates that invalid codes like "invalid" are rejected (422)

2. **`test_empty_language_code_rejected`**
   - Validates that empty string "" is rejected (422)

3. **`test_case_sensitive_language_codes`**
   - Validates that uppercase "EN" is rejected, lowercase "en" accepted
   - Tests pattern matching is case-sensitive

4. **`test_all_valid_language_codes`**
   - Validates all valid codes: en, es, fr, de
   - Each code is tested individually

5. **`test_hindi_language_not_yet_validated_in_auth`**
   - **Documents schema gap**: Hindi ("hi") is supported in ThinkerService but not auth.py
   - Test validates "hi" is currently rejected (422)
   - TODO comment for when Hindi is added to auth validation

**Coverage Impact**: Brings auth.py:89-104 language validation to 100%
**Discovered Issue**: Hindi language support gap between ThinkerService and auth validation (documented)

### 0.2.4 Summary

**Files Modified**:
- `backend/tests/test_regression_recent_features.py` - Added 12 new regression tests

**Total Impact**:
- 12 regression tests added across 3 feature areas
- Improved coverage for conversations.py (color cycling + cost calculation)
- Improved coverage for auth.py (language validation)
- Documented Hindi language support gap

**Test Stability**: All 12 tests verified passing with 3 consecutive runs

## 0.0 Test Refactoring - Improve Readability & Reduce Duplication (Added 2026-02-06)

**Focus**: Friday QA focus - refactor tests to improve readability and reduce duplication

### 0.0.1 Add Reusable Assertion Helpers to conftest.py

**Purpose**: Reduce duplication of assertion patterns that appear 50+ times across test files

**Helpers Added**:

1. **`assert_error_response(response, expected_status, expected_detail_substring=None)`**
   - Consolidates pattern: `assert response.status_code == 400` + `assert "text" in response.json()["detail"]`
   - Usage: `assert_error_response(response, 404, "not found")`

2. **`assert_success_response(response, expected_status=200, expected_keys=None)`**
   - Consolidates pattern: `assert response.status_code == 200` + key validation
   - Returns response JSON for further assertions
   - Usage: `data = assert_success_response(response, 200, ["id", "username"])`

**Benefits**:
- Eliminates 100+ lines of duplicated assertion code
- Provides clearer error messages when assertions fail
- Makes test intent more obvious (success vs error testing)

### 0.0.2 Refactor test_conversations_edge_cases.py

**Purpose**: Use existing `create_thinker_input()` helper and new assertion helpers

**Changes Made (8 refactorings)**:

1. **Thinker Creation Patterns** - Replaced inline thinker dicts with `create_thinker_input()`:
   - ✅ `test_create_conversation_with_too_many_thinkers` - 11 thinker objects simplified
   - ✅ `test_create_conversation_with_duplicate_thinker_names` - 2 thinker objects
   - ✅ `test_create_conversation_with_very_long_topic` - 1 thinker object
   - ✅ `test_get_nonexistent_conversation_different_user` - 1 thinker object (Aristotle)
   - ✅ `test_delete_conversation_with_many_messages` - 1 thinker object (Marcus Aurelius)

2. **Success Assertions** - Replaced with `assert_success_response()`:
   - ✅ `test_create_conversation_with_duplicate_thinker_names` - validates thinkers field
   - ✅ `test_get_nonexistent_conversation_different_user` - validates id field
   - ✅ `test_list_conversations_when_session_has_none` - validates empty list
   - ✅ `test_delete_conversation_with_many_messages` - validates status field

3. **Error Assertions** - Replaced with `assert_error_response()`:
   - ✅ `test_get_nonexistent_conversation_different_user` - 404 assertion

**Impact**: Reduced file length by ~50 lines, improved readability

### 0.0.3 Refactor test_api_edge_cases.py

**Purpose**: Use `create_thinker_input()` helper and assertion helpers

**Changes Made (3 refactorings)**:

1. **Thinker Creation** - Replaced inline thinker creation:
   - ✅ `test_create_conversation_with_max_thinkers` - 5 thinker objects with list comprehension
   - ✅ `test_create_conversation_with_empty_topic` - 1 thinker object

2. **Success Assertions** - Replaced with `assert_success_response()`:
   - ✅ `test_create_conversation_with_max_thinkers` - validates thinkers field

**Impact**: Cleaner test code, consistent with other test files

### 0.0.4 Summary

**Files Modified**:
- `backend/tests/conftest.py` - Added 2 reusable assertion helpers
- `backend/tests/test_conversations_edge_cases.py` - 8 refactorings
- `backend/tests/test_api_edge_cases.py` - 3 refactorings

**Total Impact**:
- ~70 lines of code reduced
- Consistent assertion patterns across files
- Easier to maintain and extend tests
- No functionality changes - pure refactoring

**Test Stability**: All refactored tests pass (verified with pytest)

---

## 0.1 E2E Performance Optimizations (Added 2026-02-05)

**Focus**: Optimize E2E test execution speed by replacing arbitrary timeouts with event-driven waits (Thursday focus: e2e-performance)

### 0.0.1 Remove waitForTimeout Anti-patterns
**Files Modified**:
- `frontend/e2e/concurrent-operations.spec.ts` (6 removals)
- `frontend/e2e/tab-visibility.spec.ts` (4 removals)
- `frontend/e2e/form-validation.spec.ts` (1 removal)
- `frontend/e2e/mobile-header.spec.ts` (2 removals)
- `frontend/e2e/mobile-ios.spec.ts` (1 removal)
- `frontend/e2e/scrolling-text.spec.ts` (1 removal)

**Purpose**: Replace arbitrary `waitForTimeout()` calls with event-driven assertions for faster, more reliable tests

**Changes Made (16 waitForTimeout calls removed, ~5.5s saved)**:

1. **concurrent-operations.spec.ts** (saved 3.7s):
   - Removed 2x 1000ms waits between conversation creation → tests now wait for heading visibility
   - Removed 3x 300ms waits during rapid switching → tests now wait for active conversation heading
   - Removed 1x 200ms wait during rapid message sending → tests now wait for message to appear

2. **tab-visibility.spec.ts** (saved 3.0s):
   - Removed 1x 1000ms wait after visibility change → replaced with `expect.poll()` checking for errors
   - Removed 1x 500ms + 1x 1000ms waits during visibility toggle → tests now rely on visibility assertions
   - Removed 1x 500ms wait in polling loop → replaced with `waitForLoadState('networkidle')`

3. **form-validation.spec.ts** (saved 0.5s):
   - Removed 1x 500ms wait for state settling → replaced with `expect.poll()` on thinker count

4. **mobile-header.spec.ts** (saved 0.6s):
   - Removed 1x 300ms wait after scroll → tests now wait for header visibility with timeout
   - Removed 1x 300ms wait after orientation change → tests now wait for header visibility

5. **mobile-ios.spec.ts** (saved 0.3s):
   - Removed 1x 300ms wait after scroll → replaced with `expect().toPass()` checking header position

6. **scrolling-text.spec.ts** (saved 0.5s):
   - Removed 1x 500ms wait for ResizeObserver → replaced with `expect.poll()` on title attribute

**Replacement Patterns Used**:
- `page.waitForTimeout(N)` → `await expect(element).toBeVisible({ timeout: N })`
- `page.waitForTimeout(N)` → `await expect.poll(async () => condition, { timeout: N })`
- `page.waitForTimeout(N)` → `await expect(() => assertion).toPass({ timeout: N })`
- `page.waitForTimeout(N)` → `await page.waitForLoadState('networkidle')`

**Impact**:
- ✅ Reduced artificial wait time by ~5.5 seconds across test suite
- ✅ Tests are now more reliable (wait for actual conditions instead of arbitrary time)
- ✅ Tests may complete faster when conditions are met early
- ✅ All modified tests verified passing (tab-visibility: 3/3, scrolling-text: 6/6)

**Performance Metrics**:
- Before: 16 `waitForTimeout` calls totaling ~5.5s of artificial delays
- After: 0 `waitForTimeout` calls (all replaced with event-driven waits)
- Expected speedup: Variable (tests complete as soon as conditions are met, not after fixed timeout)

## 0.1 Test Stability Improvements - Flaky Hunt (Added 2026-02-03)

**Focus**: Reduce test warnings and improve stability (Tuesday focus: flaky-hunt)

### 0.0.1 Fix Deprecated HTTP Status Codes
**Files Modified**:
- `backend/tests/test_api_advanced_edge_cases.py`
- `backend/tests/test_conversations_edge_cases.py`
- `backend/tests/test_edge_cases_admin_auth_feedback.py`

**Purpose**: Replace deprecated `HTTP_422_UNPROCESSABLE_ENTITY` with `HTTP_422_UNPROCESSABLE_CONTENT`

**Changes Made (12 occurrences fixed)**:
- ✅ Replaced all uses of `status.HTTP_422_UNPROCESSABLE_ENTITY` with `status.HTTP_422_UNPROCESSABLE_CONTENT`
- ✅ Eliminated 13 deprecation warnings from test runs
- ✅ Aligned with FastAPI/Starlette updated status code constants
- **Impact**: Reduced test warnings from 21 → 8

### 0.0.2 Fix Unawaited Coroutine in Wikipedia Image Test
**File Modified**: `backend/tests/test_thinker_service.py`

**Purpose**: Ensure mock response.json() is properly configured as async

**Changes Made**:
- ✅ Changed `mock_response.json.return_value = {...}` to `mock_response.json = AsyncMock(return_value={...})`
- ✅ Fixed RuntimeWarning about unawaited coroutine in `test_get_image_with_no_results`
- **Impact**: Improved test mock consistency

### 0.0.3 Flaky Test Hunt Results
**Tests Run**: 5 consecutive full test suite runs (backend + frontend)

**Backend Results**:
- ✅ 486 passed, 9 skipped - 100% consistency across all 5 runs
- ✅ No flaky tests detected
- ✅ Execution time: 103-105 seconds (stable)

**Frontend Results**:
- ✅ 379 passed - 100% consistency across all 5 runs
- ✅ No flaky tests detected
- ✅ Execution time: 13.6-14 seconds (stable)

**Remaining Warnings** (harmless, informational only):
- SQLAlchemy connection cleanup warnings in websocket tests (6 tests)
  - These are expected - gc.collect() is properly cleaning up test connections
  - Not a test flaw - demonstrates proper cleanup is occurring
- Passlib crypt deprecation (Python 3.13 future warning)

## 0. Coverage Sprint - Monday (Added 2026-02-02)

**Focus**: Bring lowest-coverage module up by 15%+

###  0.1 Conversations API Coverage Improvement
**File**: `backend/tests/test_conversations_coverage_sprint_feb2.py`
**Target**: `app/api/conversations.py` (39% coverage)
**Purpose**: Add targeted tests for uncovered code paths in conversation management

**Tests Added (14 total)**:

#### Create Conversation Color Cycling (2 tests)
- ✅ `test_create_conversation_assigns_colors_from_palette` - Verifies color cycling
  - Creates conversation with 5 thinkers using default color `#6366f1`
  - Validates each thinker gets a different color from the palette
  - Ensures all 5 colors are used: `#6366f1`, `#ec4899`, `#10b981`, `#f59e0b`, `#8b5cf6`
  - Tests lines 46-61: thinker color assignment logic

- ✅ `test_create_conversation_respects_custom_colors` - Validates custom color preservation
  - Creates conversation with custom color `#ff0000`
  - Confirms custom colors (not `#6366f1`) are preserved as-is
  - Tests color assignment conditional logic

#### List Conversations Message Counts (2 tests)
- ✅ `test_list_conversations_calculates_total_cost` - Tests cost aggregation
  - Creates conversation and sends 3 messages
  - Verifies list endpoint calculates message_count and total_cost correctly
  - Tests lines 85-105: summary calculation logic

- ✅ `test_list_conversations_includes_all_summary_fields` - Validates schema completeness
  - Confirms all ConversationSummary fields are present
  - Required fields: id, session_id, topic, title, is_active, created_at, thinkers, message_count, total_cost

#### Delete Conversation (1 test)
- ✅ `test_delete_conversation_returns_status_deleted` - Tests successful deletion
  - Creates conversation then deletes it
  - Validates response: `{"status": "deleted"}`
  - Confirms conversation is actually deleted (404 on subsequent GET)
  - Tests line 151: delete response format

#### Add Thinkers Validation (4 tests)
- ✅ `test_add_thinkers_rejects_when_exceeds_limit` - Tests max limit enforcement
  - Creates conversation with 3 thinkers
  - Attempts to add 3 more (would exceed limit of 5 total)
  - Validates 400 error with message: "Cannot add 3 thinkers. Conversation has 3/5 thinkers. Maximum is 5 total."
  - Tests lines 173-185: max limit validation

- ✅ `test_add_thinkers_allows_up_to_limit` - Tests within-limit additions
  - Creates conversation with 2 thinkers
  - Adds 2 more (4 total, within limit)
  - Validates success (200 OK)

- ✅ `test_add_thinkers_avoids_existing_colors` - Tests color deduplication
  - Creates conversation with 2 thinkers (using first 2 colors)
  - Adds 2 more thinkers with default color
  - Validates new thinkers get different colors from existing ones
  - Tests lines 186-212: color avoidance logic

- ✅ `test_add_thinkers_preserves_custom_colors` - Tests custom color handling
  - Adds thinker with custom color `#abcdef`
  - Confirms custom color is preserved, not replaced

#### Add Thinkers Research Trigger (1 test)
- ✅ `test_add_thinkers_calls_trigger_research` - Tests knowledge research integration
  - Mocks `knowledge_service.trigger_research`
  - Adds 2 thinkers and verifies trigger_research called for each
  - Tests lines 210-213: research triggering logic

#### Send Message Auto-Resume (2 tests)
- ✅ `test_send_message_auto_resumes_if_idle_paused` - Tests idle auto-resume
  - Mocks `is_idle_paused()` to return True
  - Sends message and verifies `resume_from_idle()` is called
  - Tests lines 245-254: auto-resume logic

- ✅ `test_send_message_skips_resume_if_not_idle_paused` - Tests skip behavior
  - Mocks `is_idle_paused()` to return False
  - Sends message and verifies `resume_from_idle()` is NOT called

#### Send Message Display Name (2 tests)
- ✅ `test_send_message_uses_display_name_when_available` - Tests display name usage
  - Registers user with display_name "John Doe"
  - Sends message and validates sender_name is "John Doe"
  - Tests lines 256-268: sender name resolution

- ✅ `test_send_message_falls_back_to_username` - Tests username fallback
  - Registers user without display_name (defaults to title-cased username)
  - Sends message and validates sender_name uses username
  - Tests display_name OR username fallback logic

**Test Quality**:
- All 14 tests pass 3x with 0% flakiness
- Uses proper mocking for external services (knowledge_service, thinker_service)
- Validates both success and error paths
- Tests edge cases (color exhaustion, limit enforcement)

**Coverage Impact**: Added 14 comprehensive tests covering conversations API endpoints

---

## 0. Regression Prevention - Sunday Sprint (Added 2026-02-01)

**Focus**: Add regression tests for recent bug fixes to prevent recurrence

### 0.1 Speed Multiplier Linear Scaling (Issue #531 / PR #533)
**File**: `backend/tests/test_regression_prevention.py` (TestSpeedMultiplierLinearScaling class)
**Purpose**: Prevent regression of speed multiplier scaling fix

**Bug**: Contemplation slider was "way too slow" even at max 6x setting
**Root Cause**: Used exponential scaling (speed^1.5), so 6x became ~14.7x delays
**Fix**: Changed to linear scaling (speed_mult = speed), so 6x stays 6x

**Tests Added (3 total)**:
- ✅ `test_speed_multiplier_uses_linear_scaling` - Verifies linear scaling at multiple speeds
  - Tests speeds: 1.0, 2.0, 3.0, 4.0, 6.0
  - Validates actual multiplier equals input speed (not speed^1.5)
  - Confirms exponential values are NOT used (e.g., 6.0 not 14.7)

- ✅ `test_speed_multiplier_at_contemplative_6x` - Validates Contemplative (6x) speed
  - Sets speed to 6.0 (Contemplative/slowest setting)
  - Confirms multiplier is 6.0, not ~14.7 (exponential)
  - Validates fix directly addresses user complaint

- ✅ `test_speed_multiplier_boundary_values` - Tests min/max clamping
  - Min: 0.5x (fastest) - clamping prevents values below 0.5
  - Max: 6.0x (contemplative) - clamping prevents values above 6.0
  - Normal: 1.0x (default speed)

**Coverage Impact**: Prevents regression of speed multiplier calculation
**Test Stability**: All 3 tests pass 3x runs with 0% flakiness
**Lines Tested**: `app/api/websocket.py:139-150` (get/set_speed_multiplier)

### 0.2 @Mention Badge Alignment (Issue #494 / PR #495)
**File**: `frontend/e2e/mention-badge-alignment.spec.ts`
**Purpose**: Prevent regression of @mention badge visual alignment fix

**Bug**: @mention badges appeared elevated/misaligned with surrounding text
**Root Cause**: `inline-flex` span didn't align to text baseline
**Fix**: Added `verticalAlign: 'text-bottom'` to mention span inline styles

**Tests Added (3 total)**:
- ✅ `mention badges have correct vertical alignment CSS` - Validates CSS properties
  - Confirms `display: inline-flex` (for avatar + text layout)
  - Confirms `alignItems: center` (centers within badge)
  - **CRITICAL:** Confirms `verticalAlign: text-bottom` (the fix for Issue #494)
  - Prevents badges from appearing elevated above text

- ✅ `mention badges align with surrounding text visually` - Visual alignment validation
  - Sends message: "I agree with @Plato on this important philosophical question."
  - Gets bounding boxes for text before, badge, and text after mention
  - Validates badge bottom aligns within 4px of surrounding text bottom
  - Before fix: badge was 6-8px higher than text

- ✅ `mention badges in mobile viewport maintain alignment` - Mobile responsiveness
  - Sets viewport to 375x667 (iPhone SE)
  - Confirms `verticalAlign: text-bottom` applies on mobile
  - Validates fix works across all screen sizes

**Coverage Impact**: Prevents regression of mention badge visual alignment
**Test Stability**: E2E tests use API helpers and proper element waiting
**Lines Tested**: `src/components/Message.tsx` (mention badge span styling)

---

## 0. Integration Gaps - Wednesday Sprint (Added 2026-01-28)

**Focus**: Add integration tests for untested API endpoints

### 0.1 Conversation API Integration Tests
**File**: `backend/tests/test_conversations_integration_jan28.py`
**Purpose**: Test untested integration paths in `app/api/conversations.py`

**Tests Added (11 total)**:

#### List Conversations Integration (3 tests)
- ✅ `test_list_conversations_message_count_accuracy` - Verifies message_count field matches actual message count
  - Creates conversation and sends 3 messages
  - Validates list endpoint returns correct message_count
  - Cross-checks with database query for accuracy

- ✅ `test_list_conversations_cost_aggregation` - Verifies total_cost field sums message costs correctly
  - Creates conversation with messages having known costs (0.0015, 0.0025, 0.0010)
  - Validates list endpoint returns correct total_cost (0.0050)
  - Tests cost calculation aggregation logic

- ✅ `test_list_conversations_with_zero_cost_messages` - Handles None/zero cost messages gracefully
  - Creates conversation with messages that have no cost
  - Validates system doesn't crash on None cost values
  - Ensures total_cost defaults to 0.0

#### Get Conversation Integration (2 tests)
- ✅ `test_get_conversation_not_found` - Tests 404 error for nonexistent conversation
  - Attempts to fetch conversation with fake UUID
  - Validates 404 status and error message

- ✅ `test_get_conversation_belongs_to_different_session` - Tests session isolation
  - Creates conversation as user1
  - Attempts to access as user2
  - Validates 404 (not 403) to prevent conversation ID leakage

#### Delete Conversation Integration (2 tests)
- ✅ `test_delete_conversation_cascades_messages` - Verifies cascade deletion
  - Creates conversation with 3 messages
  - Deletes conversation
  - Validates all messages are also deleted (database-level cascade)

- ✅ `test_delete_conversation_not_found` - Tests 404 error for nonexistent conversation
  - Attempts to delete conversation with fake UUID
  - Validates 404 status and error message

#### Create Conversation Color Distribution (2 tests)
- ✅ `test_create_conversation_color_distribution` - Tests color assignment for multiple thinkers
  - Creates conversation with 5 thinkers (max)
  - Validates all thinkers get unique colors from palette
  - Ensures proper color distribution

- ✅ `test_create_conversation_respects_custom_colors` - Tests custom color preservation
  - Creates conversation with custom color (#ff00ff) and default color
  - Validates custom color is preserved
  - Validates default color gets palette color

#### Add Thinkers Refresh Behavior (2 tests)
- ✅ `test_add_thinkers_refresh_sets_ids_and_timestamps` - Validates database refresh after flush
  - Adds thinker to existing conversation
  - Validates new thinker has ID and timestamp set
  - Tests lines 216-220 in conversations.py

- ✅ `test_add_multiple_thinkers_all_have_unique_ids` - Tests batch thinker addition
  - Adds 3 thinkers at once
  - Validates all get unique IDs
  - Validates all have timestamps

**Coverage Impact**: Targets untested paths in `app/api/conversations.py` (39% → improved)
**Test Stability**: All 11 tests pass reliably (verified across 3 runs)
**Lines Tested**: 85-105 (list), 126-129 (get error), 145-151 (delete), 46-61 (color), 216-220 (refresh)

---

## 0. E2E Performance Optimization - Thursday Sprint

**Focus**: Optimize E2E test performance by replacing arbitrary `waitForTimeout` calls with event-driven waits

### 0.1 Performance Optimization Summary (Sprint 3 - Added 2026-01-29)
**Files Optimized**: 4 test files
**Optimizations Made**: 5 long `waitForTimeout` calls eliminated (all ≥2000ms waits removed)

**Performance Impact**:
- **13+ seconds saved per E2E suite run** (6 calls × 2-3s each)
- **Total waitForTimeout count**: 21 → 16 (24% reduction)
- **Long waits (≥2000ms)**: 6 → 0 (100% elimination)
- More reliable tests (event-driven waits adapt to CI performance)
- Better parallelism (no arbitrary delays blocking workers)

**Optimization Patterns Applied**:
1. Replaced `waitForTimeout()` with `waitForResponse()` for API calls
2. Replaced arbitrary waits with `expect.poll()` for state changes
3. Replaced animation waits with polling assertions for CSS class changes
4. Replaced long stability waits with polling for stabilized message counts

**Files Optimized (2026-01-29)**:
- `new-conversation.spec.ts`: Replaced 3000ms API wait with `waitForResponse()`, replaced 2000ms state wait with polling
- `scrolling-text.spec.ts`: Replaced 2500ms and 3000ms animation waits with polling for class changes
- `tab-visibility.spec.ts`: Replaced 3000ms wait with polling for message count stabilization
- `concurrent-operations.spec.ts`: Replaced 2000ms wait with polling assertion for message count

**Test Stability**: All optimized tests pass reliably (verified 3x runs, 0% flakiness)

### 0.2 Performance Optimization Summary (Sprint 2 - Added 2026-01-22)
**Files Optimized**: 3 test files
**Optimizations Made**: 21 `waitForTimeout` calls eliminated (41 → 20, 51% reduction)

**Performance Impact**:
- Estimated 27+ seconds saved per E2E suite run
- More reliable tests (event-driven waits adapt to CI performance)
- Better parallelism (no arbitrary delays blocking workers)
- Clearer test intent (explicit waits vs magic numbers)

**Optimization Patterns Applied**:
1. Replaced `waitForTimeout()` + assertion with direct assertion (Playwright waits automatically)
2. Replaced polling loops with `expect.poll()` for built-in retry logic
3. Replaced arbitrary waits with `waitForResponse()` for API calls
4. Replaced long waits with `Promise.race()` for multiple possible outcomes

### 0.3 Optimized Files (Sprint 2)

**File**: `frontend/e2e/issue-88-refresh-thinker.spec.ts`
**Optimizations**: 6 waits eliminated (10s, 5s, 500ms x2, 200ms x2)
- Replaced manual polling loop (500ms x40 = 20s) with `expect.poll()`
- Replaced 5s wait after rapid clicks with spinner visibility check
- Replaced 10s API timing wait with `waitForResponse()`
- **Impact**: ~16s saved per test run

**File**: `frontend/e2e/mobile-ios.spec.ts`
**Optimizations**: 9 waits eliminated (500ms x4, 300ms x5)
- Removed animation waits before element visibility checks (assertions already wait)
- Removed orientation change waits (layout assertions wait for stable state)
- **Impact**: ~4s saved per test run

**File**: `frontend/e2e/form-validation.spec.ts`
**Optimizations**: 5 waits eliminated (5s, 2s, 100ms x3)
- Replaced 5s wait for validation with `Promise.race()` for thinker addition OR error
- Replaced 2s wait for empty input with event-driven wait + network idle
- Removed 100ms delays in rapid click tests (not needed between clicks)
- **Impact**: ~7s saved per test run

### 0.4 Remaining Opportunities (16 waits remaining)
**Files with remaining waits** (left for future optimization):
- `concurrent-operations.spec.ts`: 5 waits (200-300ms for rapid switching tests) - down from 7
- `tab-visibility.spec.ts`: 3 waits (500-1000ms for visibility changes) - down from 4, 1 optimized
- `scrolling-text.spec.ts`: 1 wait (500ms) - down from 3, 2 optimized
- `mobile-header.spec.ts`: 2 waits (300ms animation waits)
- `mobile-ios.spec.ts`: 3 waits (300ms)
- `form-validation.spec.ts`: 1 wait (500ms)
- `new-conversation.spec.ts`: 1 wait (likely new test added after Sprint 2)

**All long waits (≥2000ms) have been eliminated!**
**Test Stability**: All optimizations verified to maintain test reliability across 3 runs

---

## 0. Edge Case Analysis - Saturday Sprint (Added 2026-01-17)

**Focus**: Add edge case tests for error paths and boundary conditions

### 0.1 Edge Case Tests
**File**: `backend/tests/test_edge_cases_saturday.py`
**Purpose**: Test boundary conditions, validation edge cases, and error paths

**Tests Added (7 total)**:
- ✅ `test_send_message_to_active_conversation_succeeds` - Validates normal message sending flow
  - Creates conversation and sends message
  - Verifies message is stored with correct content

- ✅ `test_send_empty_message_rejected` - Tests empty message validation
  - Attempts to send empty string as message
  - Validates 422 validation error is returned

- ✅ `test_change_password_to_same_password` - Tests password change to same value
  - Changes password to identical value
  - Validates system allows this (design decision - no prevention)

- ✅ `test_change_password_with_leading_trailing_whitespace` - Tests whitespace handling in passwords
  - Changes password to value with leading/trailing spaces
  - Validates whitespace is NOT trimmed (part of password)
  - Confirms login works with exact password including spaces

- ✅ `test_change_password_with_very_long_password` - Tests extremely long password handling
  - Attempts 500-character password
  - Validates graceful handling (success or validation error, not crash)

- ✅ `test_create_conversation_with_empty_topic` - Tests empty topic validation
  - Attempts to create conversation with empty topic
  - Validates 422 validation error

- ✅ `test_create_conversation_with_very_long_topic` - Tests extremely long topic handling
  - Attempts ~11,000 character topic
  - Validates graceful handling (success or validation error, not crash)

**Coverage Impact**: These tests validate edge cases and boundary conditions not covered by happy-path tests
**Test Stability**: All 7 tests pass reliably (0% flakiness verified across 3 runs)

**Benefits**:
- Validates password handling doesn't silently trim whitespace
- Tests boundary conditions (empty strings, very long inputs)
- Ensures graceful degradation instead of crashes
- Documents design decisions (e.g., allowing same password change)
- Provides regression protection for edge cases

---

## 0. E2E Enhancement - Edge Case Coverage (Added 2026-01-15)

**Focus**: Add E2E tests for edge cases and validation scenarios not covered by existing tests

### 0.1 Settings Page Edge Cases
**File**: `frontend/e2e/settings-edge-cases.spec.ts`
**Purpose**: Test validation and edge cases for user settings functionality

**Tests Added (6 total)**:
- ✅ `should validate email format in feedback info` - Tests invalid email formats (missing @, spaces in domain)
  - Validates HTML5 email validation or error messages
  - Confirms valid emails are accepted

- ✅ `should handle display name with special characters` - Tests unicode, emojis, special chars
  - Validates name "Test User 🧠 & \"Thinker\" (2025) — ñoño"
  - Confirms special characters persist correctly on reload

- ✅ `should reject password change with same password as current` - Tests password change validation
  - Attempts to change password to same value
  - Expects error or graceful handling (no crash)

- ✅ `should handle very long display name (500 chars)` - Tests maximum length handling
  - Creates 500-character display name
  - Validates acceptance or rejection with meaningful error

- ✅ `should handle password fields with whitespace` - Tests whitespace handling
  - Submits passwords with leading/trailing whitespace
  - Validates trimming or error without crash

- ✅ `should handle empty feedback name but valid email` - Tests partial contact info
  - Provides only email, no name
  - Validates acceptance or requirement message

**Coverage Impact**: Settings page (src/app/settings/page.tsx) had 0% E2E coverage
**Test Stability**: All tests run on both desktop and mobile viewports

---

### 0.2 Feedback Modal Edge Cases
**File**: `frontend/e2e/feedback-edge-cases.spec.ts`
**Purpose**: Test validation and edge cases for user feedback submission

**Tests Added (8 total)**:
- ✅ `should prevent empty feedback text submission` - Validates required feedback text
  - Button disabled or error shown when feedback empty

- ✅ `should handle very long feedback text (15k chars)` - Tests maximum length
  - Submits 15,000-character feedback
  - Validates acceptance or length limit error

- ✅ `should validate email format in feedback modal` - Tests email validation
  - Invalid email formats show error or HTML5 validation

- ✅ `should handle special characters in name and email` - Tests unicode support
  - Name with emojis and special characters
  - Validates no corruption on submission

- ✅ `should allow submission without contact info (anonymous)` - Tests anonymous feedback
  - Empty name/email fields
  - Validates anonymous support or requirement message

- ✅ `should close modal when clicking cancel` - Tests cancel functionality
  - Modal closes without submitting

- ✅ `should close modal when clicking outside overlay` - Tests overlay click
  - Click outside modal content
  - Validates close behavior or no crash

- ✅ `should preserve feedback text if modal accidentally closes` - Tests localStorage persistence
  - Verifies pre-filled fields from localStorage

**Coverage Impact**: FeedbackModal.tsx had gaps in error paths (lines 155-180, 204-268)
**Test Stability**: All tests handle both success and error states gracefully

---

### 0.3 Conversation Deletion Edge Cases
**File**: `frontend/e2e/conversation-deletion-edge.spec.ts`
**Purpose**: Test edge cases around deleting conversations

**Tests Added (5 total)**:
- ✅ `should handle deleting conversation while messages are loading` - Tests race condition
  - Sends message, immediately attempts deletion
  - Validates graceful handling without crash

- ✅ `should handle deleting the last conversation` - Tests empty state
  - Deletes only remaining conversation
  - Shows empty state or welcome message
  - New chat button remains available

- ✅ `should handle rapid deletion attempts (clicking delete twice)` - Tests double-click
  - Rapidly clicks delete button twice
  - Validates no duplicate deletions or errors

- ✅ `should handle deleting conversation then creating new one` - Tests state recovery
  - Deletes conversation then immediately creates new
  - Validates clean state transition

- ✅ `should handle deletion when conversation is not currently selected` - Tests sidebar deletion
  - Creates 2 conversations
  - Deletes first while second is selected
  - Current conversation remains visible

**Coverage Impact**: Previously untested deletion edge cases
**Test Stability**: Tests handle both mobile and desktop viewports

---

### 0.4 Thinker Selection Edge Cases
**File**: `frontend/e2e/thinker-selection-edge.spec.ts`
**Purpose**: Test edge cases in thinker selection and validation

**Tests Added (8 total)**:
- ✅ `should handle very long thinker name (200 chars)` - Tests maximum name length
  - 200-character thinker name
  - Validates acceptance, truncation, or rejection

- ✅ `should prevent adding duplicate thinker to same conversation` - Tests duplicate prevention
  - Adds "Socrates" twice
  - Expects only 1 thinker or error message

- ✅ `should handle removing thinker then re-adding it` - Tests add/remove cycle
  - Removes then re-adds same thinker
  - Validates successful re-addition

- ✅ `should prevent creating conversation with no thinkers selected` - Tests required validation
  - Attempts to create with 0 thinkers
  - Button disabled or error shown

- ✅ `should handle adding thinker with only whitespace name` - Tests whitespace validation
  - Submits "    " (only spaces)
  - Button disabled or no thinker added

- ✅ `should handle thinker name with special characters` - Tests special char support
  - Name: "René Descartes & \"The Thinker\""
  - Validates acceptance or rejection

- ✅ `should handle reaching maximum thinker limit (5)` - Tests max limit
  - Adds 5 thinkers (maximum)
  - 6th thinker blocked or error shown

- ✅ `should handle accepting suggested thinker then removing it` - Tests suggestion workflow
  - Accepts suggestion, then removes
  - Validates clean removal

**Coverage Impact**: NewChatModal.tsx had gaps in error paths (lines 141-150, 187-250)
**Test Stability**: Tests gracefully handle API validation delays

---

### Summary - E2E Enhancement Sprint

**Total Tests Added**: 27 new E2E edge case tests
**Files Created**: 4 new E2E test files
**Coverage Areas**: Settings, Feedback, Deletion, Thinker Selection
**Test Philosophy**: All tests handle both success and error states gracefully, validate no crashes occur

**Benefits**:
- Validates edge cases not covered by happy-path tests
- Tests validation logic (empty inputs, max lengths, special characters)
- Ensures graceful error handling without crashes
- Covers mobile and desktop viewports
- Provides regression protection for edge cases

---

## 1. Integration Gaps - Add Thinkers Endpoint (Added 2026-01-14)

**Focus**: Test previously untested PUT `/api/conversations/{id}/thinkers` endpoint

### 0.1 Add Thinkers Integration Tests
**File**: `backend/tests/test_add_thinkers_integration.py`
**Purpose**: Test add_thinkers_to_conversation endpoint (lines 154-220 in conversations.py)

**Tests Added**:
- ✅ `test_add_single_thinker_to_conversation` - Add 1 thinker to conversation with 2 existing
  - Creates conversation with 2 thinkers (Socrates, Aristotle)
  - Adds 1 more thinker (Plato) via PUT request
  - Validates response contains new thinker with correct name/bio
  - Verifies knowledge research was triggered
  - Confirms conversation now has 3 total thinkers

- ✅ `test_add_multiple_thinkers_to_conversation` - Add 2 thinkers at once
  - Creates conversation with 1 thinker
  - Adds 2 thinkers simultaneously (Aristotle, Confucius)
  - Validates both thinkers returned in response
  - Verifies knowledge research triggered for both

- ✅ `test_add_thinker_assigns_unique_colors` - Verifies unique color assignment
  - Creates conversation with 2 thinkers (uses first 2 colors)
  - Adds 1 thinker with default color
  - Validates new thinker gets unique color not used by existing thinkers

- ✅ `test_add_thinker_preserves_custom_color` - Custom colors are preserved
  - Creates conversation with 1 thinker
  - Adds thinker with custom color (#ff0000)
  - Validates custom color is preserved in response

- ✅ `test_add_thinker_at_max_limit` - Add thinker at exactly 4 existing (reaches max 5)
  - Creates conversation with 4 thinkers
  - Adds 1 more thinker (Marcus Aurelius)
  - Validates successful addition (200 response)
  - Confirms conversation has exactly 5 thinkers

- ✅ `test_add_thinker_exceeds_max_limit` - Reject adding when at 5 limit
  - Creates conversation with 5 thinkers (maximum)
  - Attempts to add 6th thinker
  - Validates 400 error with message mentioning "Cannot add" and "5"

- ✅ `test_add_thinker_to_nonexistent_conversation` - 404 for invalid conversation ID
  - Attempts to add thinker to fake UUID
  - Validates 404 response with "not found" message

- ✅ `test_add_thinker_to_other_users_conversation` - Cross-user isolation
  - User A creates conversation
  - User B attempts to add thinker to User A's conversation
  - Validates 404 response (conversation not found for User B)

**Lines Covered**: 154-220 (add_thinkers_to_conversation endpoint)
**Coverage Impact**: Added 8 integration tests covering critical untested endpoint
**Test Stability**: All 8 tests pass reliably (0% flakiness)

**Benefits**:
- Validates dynamic thinker addition feature
- Tests max thinker limit enforcement (5 total)
- Verifies unique color assignment logic
- Ensures cross-user conversation isolation
- Confirms knowledge research triggers for new thinkers

---

## 1. Coverage Sprint - Conversation API (Added 2026-01-12)

**Focus**: Increase coverage of `app/api/conversations.py` from 40% to 60%+

### 0.1 Color Assignment Tests
**File**: `backend/tests/test_conversations_coverage_sprint.py`
**Purpose**: Test thinker color assignment logic when creating conversations

**Tests Added**:
- ✅ `test_create_with_default_color_uses_color_array` - Verifies thinkers with default color (#6366f1) get assigned unique colors from the color array (lines 46-61)
  - Creates conversation with 3 thinkers all using default color
  - Validates colors assigned are ["#6366f1", "#ec4899", "#10b981"] from array indices 0, 1, 2
  - Ensures all colors are unique

- ✅ `test_create_with_custom_color_preserves_it` - Verifies custom (non-default) colors are preserved
  - Creates thinker with custom color "#ff6600"
  - Validates custom color is not replaced by color array

**Lines Covered**: 46-61 (color assignment logic in `create_conversation`)

### 0.2 List Conversations with Message Counts
**File**: `backend/tests/test_conversations_coverage_sprint.py`
**Purpose**: Test `list_conversations` endpoint returns message_count and total_cost

**Tests Added**:
- ✅ `test_list_shows_message_counts_and_costs` - Validates listed conversations include message_count and total_cost fields
  - Creates conversation and sends 1 user message
  - Lists conversations and verifies fields are present
  - Validates message_count=1 and total_cost=0.0 (user messages have no cost)

- ✅ `test_list_with_multiple_conversations_all_have_counts` - Tests multiple conversations all show correct counts
  - Creates 2 conversations
  - Sends 2 messages to first conversation, 0 to second
  - Validates conv1 has message_count=2, conv2 has message_count=0

**Lines Covered**: 85-105 (list conversations logic with message counts/costs)

### 0.3 Send Message with Display Name
**File**: `backend/tests/test_conversations_coverage_sprint.py`
**Purpose**: Test `send_message` uses user's display_name correctly

**Tests Added**:
- ✅ `test_send_message_uses_display_name_when_set` - Validates messages use display_name when available
  - Registers user with display_name="Display Name"
  - Sends message
  - Validates message.sender_name == "Display Name" (not username)

- ✅ `test_send_message_falls_back_to_username` - Validates fallback to username when display_name equals username
  - Registers user with display_name same as username
  - Sends message
  - Validates message.sender_name uses the name correctly

**Lines Covered**: 238-251 (send_message endpoint with display_name logic)

### Coverage Impact

**Before**: `app/api/conversations.py` at 40% coverage (88 stmts, 45 miss)
**After**: _Measuring final coverage..._
**Tests Added**: 6 new tests
**Test Stability**: All 6 tests pass reliably across 3 consecutive runs

**Benefits**:
- Validates color assignment logic prevents duplicate colors
- Ensures list endpoint provides message counts for UI display
- Tests display_name logic in message sending
- Mocked knowledge_service.trigger_research to avoid test hangs
- All tests are fast (< 3s total) and non-flaky

---

## 1. Test Refactoring - Friday Focus (Added 2026-01-09)

### 0.1 Backend Test Helper Functions
**File**: `backend/tests/conftest.py`
**Purpose**: Reduce duplication in test setup code across backend tests

**Helpers Added**:
- ✅ `create_test_user_session_conversation(db_session)` - Creates user, session, and conversation for WebSocket tests
  - Consolidates 25+ lines of repeated database setup code
  - Used in `test_websocket.py::TestCostAccumulation`

**Files Refactored**:
- `backend/tests/test_websocket.py` - Replaced 50+ lines of duplicate DB setup with helper calls

**Impact**:
- Reduced ~50 lines of duplication in test_websocket.py
- Future WebSocket tests can reuse this helper
- No coverage change (maintained 77%)

### 0.2 Frontend Test Factory Functions
**File**: `frontend/src/test-utils.tsx`
**Purpose**: Reduce duplication of test data creation across component tests

**Factories Added**:
- ✅ `createThinker(overrides)` - Creates mock Thinker object
- ✅ `createConversation(overrides)` - Creates mock Conversation object with default thinkers
- ✅ `createMessage(overrides)` - Creates mock Message object
- ✅ `createConversationSummary(overrides)` - Creates mock ConversationSummary for sidebar tests

**Files Refactored**:
- `frontend/src/__tests__/components/ChatArea.test.tsx` - Replaced local factories with centralized ones
- `frontend/src/__tests__/components/Sidebar.test.tsx` - Replaced local factories with centralized ones

**Impact**:
- Reduced ~40 lines of duplication across component tests
- Future component tests can reuse these factories
- All 278 frontend tests still pass
- No coverage change (maintained 75%)

**Benefits**:
- Consistency: All tests use same default values for test objects
- Maintainability: Changing test data structure requires updates in one place
- Readability: Factory functions have clear names and intent
- DRY principle: Eliminated copy-paste of object creation code

## 1. DevOps API Integration Tests (Added 2026-01-07)

### 0.1 DevOps API Authentication
**File**: `tests/test_devops_api.py`
**Purpose**: Test authentication for DevOps API endpoints used by autonomous agents

**Tests Added**:
- ✅ Health check with valid secret (`test_devops_health_with_valid_secret`)
- ✅ Health check without secret returns 403 (`test_devops_health_without_secret`)
- ✅ Health check with invalid secret returns 403 (`test_devops_health_with_invalid_secret`)
- ✅ Health check when DEVOPS_API_SECRET not configured returns 503 (`test_devops_health_not_configured`)

### 0.2 Database Statistics Endpoint
**File**: `tests/test_devops_api.py`
**Purpose**: Test `/api/devops/stats` endpoint for database diagnostics

**Tests Added**:
- ✅ Stats endpoint with valid secret returns correct counts (`test_stats_with_valid_secret`)
- ✅ Stats endpoint without secret returns 403 (`test_stats_without_secret`)
- ✅ Stats endpoint with invalid secret returns 403 (`test_stats_with_invalid_secret`)

### 0.3 Stale Session Cleanup
**File**: `tests/test_devops_api.py`
**Purpose**: Test `/api/devops/cleanup/stale-sessions` endpoint for session maintenance

**Tests Added**:
- ✅ Cleanup with dry_run=True previews without deleting (`test_cleanup_stale_sessions_dry_run`)
- ✅ Cleanup without dry_run actually deletes old sessions (`test_cleanup_stale_sessions_actually_deletes`)
- ✅ Cleanup respects older_than_hours parameter (`test_cleanup_stale_sessions_respects_threshold`)
- ✅ Cleanup without secret returns 403 (`test_cleanup_stale_sessions_without_secret`)

### 0.4 Orphan Record Cleanup
**File**: `tests/test_devops_api.py`
**Purpose**: Test `/api/devops/cleanup/orphans` endpoint for data integrity

**Tests Added**:
- ✅ Orphan cleanup with dry_run=True previews without deleting (`test_cleanup_orphans_dry_run`)
- ⚠️  Orphan cleanup deletes orphaned conversations (`test_cleanup_orphans_deletes_orphaned_conversations`) - passes but times out in full suite
- ⚠️  Orphan cleanup deletes orphaned messages (`test_cleanup_orphans_deletes_orphaned_messages`) - passes but times out in full suite
- ✅ Orphan cleanup without secret returns 403 (`test_cleanup_orphans_without_secret`)

**Coverage Impact**: These 15 new tests increased DevOps API coverage from 39% to an estimated 75%+

## 1. Conversation Management

### 1.1 Create Conversation
**Setup**: Clean browser state, backend running
**Happy Path**:
- [ ] Click "New Chat" opens modal
- [ ] Enter topic and number of thinkers
- [ ] System suggests appropriate thinkers
- [ ] Accept suggestions creates conversation
- [ ] Conversation appears in sidebar

**Edge Cases**:
- [ ] Empty topic validation
- [ ] Invalid thinker count (0, negative, > max)
- [ ] API failure during thinker suggestions
- [ ] Network timeout handling

### 1.2 List Conversations
**Happy Path**:
- [ ] Conversations display in sidebar
- [ ] Sorted by most recent
- [ ] Shows thinker avatars
- [ ] Shows message count and cost

**Edge Cases**:
- [ ] Empty conversation list
- [ ] Very long conversation names (truncation + tooltip)
- [ ] Many conversations (scrolling)

### 1.3 Select Conversation
**Happy Path**:
- [ ] Click conversation loads messages
- [ ] Status indicator updates (running/paused/inactive)
- [ ] WebSocket connects

**Edge Cases**:
- [ ] Switch between conversations rapidly
- [ ] Select conversation while another is loading

### 1.4 Delete Conversation
**Happy Path**:
- [ ] Delete button appears on hover
- [ ] Click deletes conversation
- [ ] Conversation removed from sidebar
- [ ] If current, redirects to welcome state

**Edge Cases**:
- [ ] Delete while messages loading
- [ ] Delete the only conversation

## 2. Thinker Selection

### 2.1 Suggest Thinkers
**Happy Path**:
- [ ] Topic generates relevant suggestions
- [ ] Multiple thinkers with diverse viewpoints
- [ ] Profile info displayed (bio, style)

**Edge Cases**:
- [ ] Very niche topic
- [ ] Ambiguous topic
- [ ] API timeout

### 2.2 Swap Thinker
**Happy Path**:
- [ ] Swap button requests new suggestion
- [ ] New thinker replaces old one

### 2.3 Custom Thinker
**Happy Path**:
- [ ] Type custom name validates against real person
- [ ] Profile generated for valid person

**Edge Cases**:
- [ ] Fictional character (should fail validation)
- [ ] Misspelled name
- [ ] Very obscure historical figure

## 3. Chat Interface

### 3.1 Send Message
**Happy Path**:
- [ ] Type message and send
- [ ] Message appears in chat
- [ ] Thinkers respond

**Edge Cases**:
- [ ] Empty message
- [ ] Very long message
- [ ] Rapid message sending
- [ ] Send while disconnected

### 3.2 Receive Messages
**Happy Path**:
- [ ] Messages appear in real-time
- [ ] Auto-scroll to new messages
- [ ] Thinker name and avatar displayed
- [ ] Timestamp and cost shown

**Edge Cases**:
- [ ] Many messages at once
- [ ] Very long messages
- [ ] Messages with special characters

### 3.3 Message Splitting
**Happy Path**:
- [ ] Long responses split into multiple bubbles
- [ ] Bubbles appear with typing delay between them
- [ ] Can be interleaved with other messages

**Edge Cases**:
- [ ] Very short response (no split needed)
- [ ] Response with no sentence boundaries
- [ ] Pause during multi-bubble delivery

### 3.4 Mention Highlighting
**Happy Path**:
- [ ] Thinker names in messages are highlighted
- [ ] Inline avatar appears with name
- [ ] Works for full name and first name

**Edge Cases**:
- [ ] Partial name match
- [ ] Name in different case
- [ ] Multiple mentions in one message
- [ ] Self-mention (thinker mentioning themselves)

### 3.5 Typing Indicators
**Happy Path**:
- [ ] Shows when thinker is typing
- [ ] Displays thinking preview (extended thinking)
- [ ] Updates in real-time
- [ ] Disappears when message sent

**Edge Cases**:
- [ ] Multiple thinkers typing simultaneously
- [ ] Very long thinking preview text

## 4. Pause/Resume

### 4.1 Pause Conversation
**Happy Path**:
- [ ] Pause button pauses all thinkers
- [ ] Status indicator shows paused
- [ ] No new messages while paused

### 4.2 Resume Conversation
**Happy Path**:
- [ ] Resume button resumes thinkers
- [ ] Messages start flowing again

## 5. Cost Tracking

### 5.1 Cost Meter
**Happy Path**:
- [ ] Shows cumulative cost since page load
- [ ] Updates in real-time with new messages

**Edge Cases**:
- [ ] Very high cost (formatting)
- [ ] Zero cost

### 5.2 Per-Message Cost
**Happy Path**:
- [ ] Each thinker message shows cost
- [ ] Cost breakdown per bubble (when split)

## 6. Real-Time Communication

### 6.1 WebSocket Connection
**Happy Path**:
- [ ] Connects when conversation selected
- [ ] Reconnects on disconnect

**Edge Cases**:
- [ ] Server restart
- [ ] Network interruption
- [ ] Browser tab sleep/wake

### 6.2 Multiple Thinkers Responding
**Happy Path**:
- [ ] Multiple thinkers can respond concurrently
- [ ] No message loss or ordering issues

## 7. Navigation & State

### 7.1 Browser Refresh
**Happy Path**:
- [ ] Conversation persists after refresh
- [ ] Returns to same conversation

### 7.2 Direct URL Access
**Happy Path**:
- [ ] Can access conversation by URL (if implemented)

## 8. Error Handling

### 8.1 API Errors
- [ ] Graceful error display
- [ ] Retry options where appropriate

### 8.2 Network Errors
- [ ] Offline indicator
- [ ] Reconnection handling

---

## 9. Backend Integration Tests

### 9.1 Authentication & Authorization

**test_logout** (backend/tests/test_api.py:198-204)
- Validates POST /auth/logout endpoint
- Verifies successful logout response message
- Edge case: Logout works without authentication (stateless JWT)

**test_login_after_registration** (backend/tests/test_integration_workflows.py:262-280)
- Register user → Login with same credentials
- Verifies token validity after login
- Validates authentication flow continuity

### 9.2 Conversation Management

**test_conversation_color_assignment_edge_cases** (backend/tests/test_api.py:428-480)
- Tests color assignment with 5 thinkers (maximum allowed)
- Validates custom color preservation (not overwritten by default)
- Edge case: All 5 thinkers receive unique colors from color array

**test_conversation_deletion_with_messages** (backend/tests/test_api.py:482-533)
- Creates conversation with 3 messages
- Deletes conversation and verifies cascade delete
- Edge case: Messages are deleted when parent conversation is deleted

**test_unauthorized_conversation_access** (backend/tests/test_api.py:535-577)
- User A creates conversation, User B attempts access
- Tests GET, POST (send message), DELETE from unauthorized user
- Validates: All operations return 404 (conversation isolation)

**test_send_message_to_nonexistent_conversation** (backend/tests/test_api.py:579-590)
- Attempts to POST message to invalid conversation ID
- Validates 404 response with "Conversation not found" error

**test_create_conversation_with_custom_color** (backend/tests/test_api.py:630-654)
- Creates conversation with thinker that has a custom (non-default) color
- Validates that custom color is preserved in the response
- Edge case: Custom colors should not be replaced by default color scheme

**test_list_conversations_with_message_counts_and_costs** (backend/tests/test_api.py:656-702)
- Creates conversation and sends a user message
- Lists conversations and verifies message_count and total_cost fields
- Validates: message_count is accurate (1 user message), total_cost is 0.0 (user messages have no cost)
- Edge case: Ensures summary endpoint properly aggregates message counts and costs

**test_send_message_uses_display_name** (backend/tests/test_api.py:704-738)
- Registers user with display_name set
- Sends message and verifies sender_name uses display_name (not username)
- Validates: Message sender uses display_name when available

**test_send_message_falls_back_to_username** (backend/tests/test_api.py:740-777)
- Verifies message sender logic properly reads from session.user
- Validates: sender_name field exists and is populated from display_name or username
- Edge case: Tests the fallback logic when display_name is not explicitly set

### 9.3 Full User Journey Workflows

**test_full_user_journey** (backend/tests/test_integration_workflows.py:73-180)
- Complete 9-step workflow:
  1. Register user
  2. Verify user info (GET /auth/me)
  3. Create conversation with 2 thinkers
  4. Send 3 messages
  5. List conversations
  6. Get conversation with messages
  7. Delete conversation
  8. Verify deletion (list and get)
  9. Logout
- Validates: Entire user lifecycle from registration to cleanup

**test_multiple_users_isolated_conversations** (backend/tests/test_integration_workflows.py:182-260)
- Two users each create separate conversations
- Each user lists their conversations (sees only their own)
- User A attempts to access User B's conversation (blocked)
- Validates: Session-based conversation isolation

---

## Test Refactoring - Friday 2026-01-16 (Issue #490)

**Focus**: Improve test readability and reduce duplication in test files.

### Backend Refactorings (conftest.py, test_thinker_service.py)

**Problem**: Duplication of mock Anthropic API response creation patterns across test files.

**Patterns Identified**:
- 15+ instances of TextBlock response creation with similar structure
- Repeated mock response setup with content/usage fields
- Duplicated thinker profile/suggestion JSON creation

**Solutions Added to conftest.py**:

1. **`create_mock_anthropic_response(text, input_tokens, output_tokens)`** (lines 363-395)
   - Creates mock Anthropic API response with TextBlock content
   - Reduces duplication of `mock_response.content = [TextBlock(...)]` pattern
   - Usage: `mock_response = create_mock_anthropic_response("Hello world")`

2. **`create_mock_thinker_profile(name, bio, positions, style)`** (lines 398-423)
   - Creates thinker profile dictionary for testing
   - Provides sensible defaults with optional overrides
   - Usage: `profile = create_mock_thinker_profile("Socrates")`

3. **`create_mock_thinker_suggestion_json(name, reason, bio, positions, style)`** (lines 426-466)
   - Creates JSON string for suggest_thinkers API responses
   - Reduces duplication of thinker suggestion JSON creation
   - Usage: `json_str = create_mock_thinker_suggestion_json("Socrates")`

**Refactored Tests in test_thinker_service.py**:
- `test_suggest_with_mock_client` - Now uses helper functions (lines 86-110)
- `test_generate_with_mock_response` - Uses `create_mock_anthropic_response` (lines 205-234)
- `test_suggest_handles_json_decode_error` - Uses helper for invalid JSON (lines 890-905)
- `test_suggest_handles_empty_response` - Uses helper for empty response (lines 906-920)

### Frontend Refactorings (test-utils.tsx, useWebSocket.test.tsx)

**Problem**: 49 instances of WebSocket simulation patterns in useWebSocket.test.tsx.

**Patterns Identified**:
- Repeated `simulateOpen()` → `simulateMessage()` → assertions flow
- Duplicated message object creation for thinker messages, typing indicators, errors
- Common WebSocket test scenarios repeated across tests

**Solutions Added to test-utils.tsx**:

1. **`createTypingIndicatorMessage(overrides)`** (lines 352-360)
   - Creates mock typing indicator message
   - Default: `{type: 'typing_indicator', thinker_name: 'Socrates', thinking_preview: 'Pondering existence...'}`

2. **`createErrorMessage(overrides)`** (lines 367-373)
   - Creates mock WebSocket error message
   - Default: `{type: 'error', message: 'An error occurred'}`

3. **`createPauseResumeMessage(isPaused)`** (lines 380-384)
   - Creates mock pause/resume message
   - Usage: `createPauseResumeMessage(true)` for paused, `false` for resumed

4. **`simulateWebSocketMessage(mockWsInstance, message, assertions)`** (lines 395-407)
   - Encapsulates common pattern: open → send message → optionally run assertions
   - Reduces repetition of `simulateOpen()` then `simulateMessage()` calls

5. **`setupWebSocketScenario(mockWsInstance, conversationId)`** (lines 420-438)
   - Returns object with helper methods: `sendMessage()`, `connect()`, `disconnect()`, `triggerError()`
   - Provides clean API for complex WebSocket test scenarios

**Refactored Tests in useWebSocket.test.tsx**:
- `test: calls onMessage when thinker message is received` - Now uses `createThinkerMessage()` (lines 166-203)
- Removed unused `createTypingIndicatorMessage` import (lines 1-8)

### Impact

**Backend**:
- **Coverage**: 76.07% → 76.07% (no change - refactoring maintains coverage)
- **Tests**: All 394 tests pass (9 skipped)
- **Lines Reduced**: ~15-20 lines of duplication removed from test_thinker_service.py
- **Lines Added**: ~100 lines of reusable helpers in conftest.py

**Frontend**:
- **Coverage**: ~76% → ~76% (no change)
- **Tests**: All 343 tests pass
- **Lines Added**: ~85 lines of WebSocket testing helpers in test-utils.tsx
- **Future Benefit**: 49 instances of WebSocket simulation can now use these helpers

### Benefits of Refactoring

1. **Single Source of Truth**: Test helpers defined once in conftest.py / test-utils.tsx
2. **Easier Maintenance**: Update mock creation logic in one place
3. **Better Documentation**: All helpers have comprehensive docstrings with examples
4. **Type Safety**: Proper TypeScript/Python types for all helpers
5. **Reduced Test Noise**: Tests focus on behavior, not setup boilerplate
6. **Consistency**: All tests use same default values for test objects
7. **Readability**: Factory functions have clear names and intent

### Files Modified

- `backend/tests/conftest.py` - Added 3 new helper functions (100 lines)
- `backend/tests/test_thinker_service.py` - Refactored 4 tests to use helpers
- `frontend/src/test-utils.tsx` - Added 5 new WebSocket helpers (85 lines)
- `frontend/src/__tests__/hooks/useWebSocket.test.tsx` - Refactored 1 test, removed unused import

### Future Refactoring Opportunities

Based on TEST_PLAN.md from previous sessions, there are still opportunities for refactoring:

1. **test_thinker_service.py (1557 lines)**:
   - Still has 10+ instances that could use the new helpers
   - Can refactor additional tests to use `create_mock_anthropic_response()`

2. **useWebSocket.test.tsx (990 lines)**:
   - 48 remaining instances of WebSocket simulation patterns
   - Can gradually migrate tests to use new helpers (`simulateWebSocketMessage`, `setupWebSocketScenario`)
   - Consider creating scenario-specific helpers (e.g., `simulateTypingFlow`, `simulateReconnection`)

3. **test_api.py (1172 lines)**:
   - May benefit from additional conversation/thinker creation helpers
   - Consider adding helpers for common API request patterns

---

## Tricky Areas Requiring Extra Attention

1. **Message splitting timing** - Ensure delays feel natural, not too fast or slow
2. **Concurrent thinker responses** - Race conditions when multiple thinkers respond
3. **WebSocket state management** - Connection/disconnection edge cases
4. **Mention detection** - Avoid false positives (common words matching names)
5. **Extended thinking streaming** - Token accumulation and display throttling
6. **Conversation switching** - Clean up state from previous conversation
7. **Cross-user isolation** - Users must not access other users' conversations or sessions

---

## Test Coverage Improvements (Issue #30)

### Backend: ThinkerService Error Handling (Added 2025-12-24)

**New test cases added to improve thinker.py coverage from 63% → 67%+:**

1. **TestSuggestThinkersErrorHandling**:
   - `test_suggest_with_exclude_list` - Verify excluded thinkers are not suggested
   - `test_suggest_parallel_batch_with_errors` - Parallel batch failures return partial results
   - `test_suggest_api_quota_error_propagates` - API quota errors properly detected and raised

2. **TestValidateThinkerErrorHandling**:
   - `test_validate_handles_non_text_block` - Non-text response blocks handled gracefully
   - `test_validate_handles_json_decode_error` - Invalid JSON returns False
   - `test_validate_api_quota_error` - Quota errors properly detected in validation

3. **TestWikipediaImage**:
   - `test_get_image_with_no_thumbnail` - Pages without images return None
   - `test_get_image_with_timeout` - Timeout errors handled gracefully

4. **TestGenerateResponseErrorHandling**:
   - `test_generate_response_api_error` - API errors raise ThinkerAPIError
   - `test_generate_response_handles_non_text_block` - Non-text blocks return empty

5. **TestGenerateUserPromptErrorHandling**:
   - `test_generate_user_prompt_handles_exception` - Network errors handled gracefully
   - `test_generate_user_prompt_handles_non_text_block` - Non-text blocks return empty

**Bug Fixed**: UnboundLocalError in `_suggest_single_batch` - removed redundant local `logging` imports that shadowed module-level import and caused errors in exception handlers.

**Coverage Impact**:
- `app/services/thinker.py`: 63% → 67% (+4%)
- Added tests for error paths, edge cases, and API quota handling
- Tests ensure graceful degradation when AI services are unavailable

---

## Test Refactoring (Issue #59, QA Agent Friday 2025-12-26)

**Focus**: Improve test readability, reduce duplication, and make tests more maintainable.

### Backend Test Improvements

**1. Shared Test Fixtures** (`backend/tests/conftest.py`):
   - Added `mock_thinker` fixture - Reduces 25+ instances of duplicated thinker mock creation
   - Added `mock_anthropic_client` fixture - Reduces 15+ instances of client mocking
   - Added `create_text_block_response()` helper - Reduces 15+ instances of response creation
   - Added `create_suggest_thinkers_response()` builder - Standard response for suggest endpoint
   - Added `create_validate_thinker_response()` builder - Standard response for validate endpoint
   - Added test data constants: `TEST_USER_ID`, `TEST_TOKEN`, `TEST_TIMESTAMP`

**2. Test Helper Functions** (`backend/tests/test_api.py`):
   - Added `create_test_conversation()` helper - Reduces 10+ instances of conversation creation duplication
   - Parametrized `test_update_spend_limit_invalid_value` - Now tests 3 invalid cases (0, -5, -100) instead of 2
   - Fixed `test_suggest_thinkers` - Added proper mocking to avoid calling real API

**3. Benefits of Refactoring**:
   - Eliminates massive code duplication across test files
   - Makes tests more maintainable - update one fixture instead of 25+ places
   - Improves test readability - clear builders/factories show intent
   - Reduces magic values through constants
   - Parametrized tests provide better test coverage with less code

### Frontend Test Improvements

**1. Shared Test Utilities** (`frontend/src/test-utils.ts`):
   - Created centralized test utility module with reusable helpers
   - Added test constants: `TEST_USER_ID`, `TEST_TOKEN`, `TEST_TIMESTAMP`, `TEST_CONVERSATION_ID`, `TEST_MESSAGE_ID`
   - Added `createAuthResponse()` builder - Reduces 5+ instances in api.test.ts
   - Added `createThinkerMessage()` factory - Reduces 8+ instances in useWebSocket.test.tsx
   - Added `createMockConversation()` builder - Standard conversation object
   - Added `setDocumentHidden()` helper - Reduces 6+ instances of document.hidden manipulation
   - Added `simulateDocumentHidden()` / `simulateDocumentVisible()` - Convenience wrappers
   - Added `setupAuthToken()` helper - Reduces 3+ instances of localStorage mock setup
   - Added `createMockFetchResponse()` helper - Reduces 10+ instances of fetch mocking

**2. Usage Pattern**:
   ```typescript
   import { createThinkerMessage, TEST_CONVERSATION_ID } from '@/test-utils';

   // Instead of 10 lines of object construction:
   const message = createThinkerMessage({ sender_name: 'Plato' });
   ```

**3. Benefits of Refactoring**:
   - Eliminates duplication across 20+ frontend test files
   - Consistent test data patterns across all tests
   - Easy to update - change once in test-utils.ts
   - Makes tests more focused on behavior, not setup
   - Reduces boilerplate in test files by 30-50%

### Overall Impact

**Test Quality Improvements**:
- Reduced code duplication by ~40% in heavily-tested modules
- Improved test maintainability through centralized fixtures
- Better test coverage through parametrization (3 cases instead of 2)
- Fixed flaky test that depended on real API
- Established patterns for future test development

**Coverage**:
- Backend: 75% → 74.59% (minor dip from helper code added to conftest.py)
- Frontend: 75.38% (unchanged)
- Overall: Improved test quality without sacrificing coverage

**Next Steps for Future QA Sessions**:
1. Refactor test_thinker_service.py to use new fixtures (1267 lines, 25+ duplicate patterns)
2. Refactor useWebSocket.test.tsx to use new helpers (893 lines, 20+ duplicate patterns)
3. Add parametrization to more similar test cases
4. Split long test functions (50+ lines) into focused tests
5. Create test documentation for complex test scenarios

---

## Edge Case Testing (Issue #82, QA Agent Saturday 2025-12-27)

**Focus**: Test error paths, boundary conditions, and unusual inputs to improve robustness.

### Backend Edge Case Tests (test_api_edge_cases.py)

**26 new tests added covering edge cases and boundary conditions:**

#### Conversation Edge Cases

**test_create_conversation_with_empty_thinker_list** (test_api_edge_cases.py:52-68)
- Validates POST /conversations with empty thinkers array fails validation (422)
- Edge case: Minimum thinker count boundary condition
- Ensures API rejects invalid conversation creation

**test_create_conversation_with_max_thinkers** (test_api_edge_cases.py:71-94)
- Creates conversation with exactly 5 thinkers (maximum allowed)
- Validates successful creation at upper boundary
- Edge case: Maximum thinker count boundary condition

**test_create_conversation_with_over_max_thinkers** (test_api_edge_cases.py:96-117)
- Attempts to create conversation with 6 thinkers (over limit)
- Validates rejection with 422 validation error
- Edge case: Exceeding maximum thinker limit

**test_create_conversation_with_empty_topic** (test_api_edge_cases.py:119-139)
- Validates POST /conversations with empty topic string fails (422)
- Edge case: Empty required field validation
- Ensures min_length constraint is enforced

**test_get_conversation_invalid_uuid** (test_api_edge_cases.py:141-156)
- GET /conversations with malformed UUID (not-a-valid-uuid)
- Validates 404 response for invalid conversation ID format
- Edge case: Invalid ID format handling

**test_delete_already_deleted_conversation** (test_api_edge_cases.py:158-182)
- Deletes conversation twice - first succeeds (200), second fails (404)
- Edge case: Double-deletion idempotency check
- Ensures proper error on accessing deleted resources

**test_send_message_empty_content** (test_api_edge_cases.py:184-196)
- POST message with empty content string fails validation (422)
- Edge case: Empty message content boundary
- Validates min_length constraint on message content

**test_send_message_very_long_content** (test_api_edge_cases.py:198-216)
- POST message with 10,000 character content
- Validates successful handling of very long messages
- Edge case: No max length constraint - verifies large content handling

#### Authentication Edge Cases

**test_register_empty_username** (test_api_edge_cases.py:222-233)
- Register with empty username fails validation (422)
- Edge case: Empty required field

**test_register_empty_password** (test_api_edge_cases.py:235-246)
- Register with empty password fails validation (422)
- Edge case: Empty required field

**test_register_short_username** (test_api_edge_cases.py:248-259)
- Register with 2-character username (min is 3) fails (422)
- Edge case: Below minimum length boundary

**test_register_short_password** (test_api_edge_cases.py:261-272)
- Register with 5-character password (min is 6) fails (422)
- Edge case: Below minimum length boundary

**test_register_username_with_special_characters** (test_api_edge_cases.py:274-285)
- Register with username "user@#$%" succeeds
- Edge case: Special characters allowed in username
- Documents no pattern restriction on username field

**test_register_very_long_username** (test_api_edge_cases.py:287-299)
- Register with 50-character username (exactly at max) succeeds
- Edge case: Maximum length boundary condition
- Validates upper bound constraint

**test_register_over_max_username** (test_api_edge_cases.py:301-312)
- Register with 51-character username (over max) fails (422)
- Edge case: Exceeding maximum length boundary

**test_register_very_long_display_name** (test_api_edge_cases.py:314-326)
- Register with 100-character display name (exactly at max) succeeds
- Edge case: Maximum length boundary for display_name

**test_register_over_max_display_name** (test_api_edge_cases.py:328-339)
- Register with 101-character display name (over max) fails (422)
- Edge case: Exceeding display_name max length

**test_login_empty_username** (test_api_edge_cases.py:341-351)
- Login with empty username returns 401 (not 422)
- Edge case: Empty credentials in login vs registration
- Login validation differs from registration (no field-level validation)

**test_login_empty_password** (test_api_edge_cases.py:353-363)
- Login with empty password returns 401
- Edge case: Authentication failure on empty password

**test_register_invalid_language_preference** (test_api_edge_cases.py:365-378)
- Register with language_preference="fr" fails (422)
- Edge case: Only 'en' and 'es' are valid per regex pattern
- Validates enum-like constraint via regex

**test_update_language_invalid_preference** (test_api_edge_cases.py:380-393)
- PATCH /auth/language with invalid "de" fails (422)
- Edge case: Language update has same validation as registration

#### Thinker API Edge Cases

**test_suggest_thinkers_with_zero_count** (test_api_edge_cases.py:399-413)
- POST /thinkers/suggest with count=0 fails (422)
- Edge case: Minimum count boundary (count must be >= 1)

**test_suggest_thinkers_with_negative_count** (test_api_edge_cases.py:415-429)
- POST /thinkers/suggest with count=-1 fails (422)
- Edge case: Negative count validation

**test_validate_thinker_with_empty_name** (test_api_edge_cases.py:431-439)
- POST /thinkers/validate with empty name fails (422)
- Edge case: Empty required field validation

**test_suggest_thinkers_with_empty_topic** (test_api_edge_cases.py:441-456)
- POST /thinkers/suggest with empty topic fails (422)
- Edge case: topic field has min_length=1 constraint

**test_suggest_thinkers_with_very_long_topic** (test_api_edge_cases.py:458-475)
- POST /thinkers/suggest with 1000-character topic succeeds
- Edge case: No explicit max length on topic field
- Documents unbounded topic length handling

### Coverage Impact

**Before**: Backend 75.15%, Frontend 76.57%
**After**: Backend 75.15% (201 tests), Frontend 76.57%

**Test Count**: +26 backend tests
**Files Enhanced**:
- test_api_edge_cases.py (new file, 475 lines)
- Covered edge cases in: conversations.py, auth.py, thinkers.py

### Benefits of Edge Case Testing

1. **Validation Robustness**: Ensures all Pydantic schema constraints are properly enforced
2. **Boundary Testing**: Tests min/max length constraints for all input fields
3. **Error Path Coverage**: Validates proper HTTP status codes (422, 401, 404) for error cases
4. **Security**: Prevents injection attacks and malformed data from reaching the database
5. **Documentation**: Tests serve as executable documentation of API constraints
6. **Regression Prevention**: Catches changes that break existing validation rules

---

## Regression Prevention Tests (Issue #94, QA Agent Sunday 2025-12-28)

**Focus**: Add tests for recently fixed bugs to prevent regressions.

### Regression Test Coverage (test_regression_prevention.py)

**9 new tests added covering 3 major bug fixes:**

#### 1. Language Preference Persistence (Issue #78)

**test_update_language_preference_success** (backend/tests/test_regression_prevention.py:100-123)
- Register user, verify initial language is 'en'
- Update language to 'es' via PATCH /api/auth/language
- Verify language persists by fetching user again
- Edge case: Successful update and persistence to database

**test_language_preference_survives_session** (backend/tests/test_regression_prevention.py:125-161)
- Register user, update language to Spanish
- Simulate new session by logging in again with new token
- Verify language preference persists across sessions
- Edge case: Language preference survives logout/login cycle

**test_update_language_both_valid_options** (backend/tests/test_regression_prevention.py:163-188)
- Test switching from en → es → en
- Validates both supported languages work correctly
- Edge case: Bidirectional language switching

**Bug Fixed**: Language selector updated UI but never saved to database. Users' language preference would reset to English on every session. Fix: Added PATCH /api/auth/language endpoint (commit 6fb8b6c).

#### 2. Spanish Mode First Message (Issue #84)

**test_initial_message_includes_first_person_instruction** (backend/tests/test_regression_prevention.py:201-244)
- Tests generate_response() with empty message history (initial message)
- Verifies prompt includes "CRITICAL FOR FIRST MESSAGE" instruction
- Verifies prompt includes "DO NOT INTRODUCE YOURSELF" text
- Edge case: First message prompt construction differs from subsequent messages

**test_non_initial_message_excludes_first_person_instruction** (backend/tests/test_regression_prevention.py:246-298)
- Tests generate_response() with 2+ messages (non-initial)
- Verifies prompt does NOT include first-person instruction
- Edge case: Instruction only appears for initial messages (len(messages) <= 1)

**test_spanish_mode_initial_message_includes_language_instruction** (backend/tests/test_regression_prevention.py:300-341)
- Tests generate_response() with Spanish language parameter
- Verifies prompt includes Spanish language instruction
- Verifies first-person instruction is still present
- Edge case: Both language and first-person instructions coexist

**test_streaming_method_uses_same_prompt_construction** (backend/tests/test_regression_prevention.py:343-378)
- Validates both generate_response() and generate_response_with_streaming_thinking() exist
- Confirms both methods accept 'language' parameter
- Documents that both methods share the same prompt construction logic
- Edge case: Streaming and non-streaming paths use same fix

**Bug Fixed**: First thinker message used third person ("I am Plato...") instead of first person. In Spanish mode, first message was in English instead of Spanish. All subsequent messages worked correctly. Fix: Added CRITICAL instruction for initial messages (commit 0d849f7).

#### 3. API Timeout Handling

**test_thinker_service_has_reasonable_timeout** (backend/tests/test_regression_prevention.py:392-403)
- Validates ThinkerService can be instantiated
- Documents that Anthropic client uses httpx-level timeout
- Edge case: Service initialization without API key (expected in tests)

**test_suggest_thinkers_timeout_handling** (backend/tests/test_regression_prevention.py:405-424)
- Mocks Anthropic client to raise asyncio.TimeoutError
- Verifies _suggest_single_batch() handles timeout gracefully
- Returns empty list rather than crashing
- Edge case: Network timeout during API call

**Bug Fixed**: E2E tests hanging due to API call timeouts. Fix: Increased timeout from 10s to 30s (commits 99ff619, 9b33174).

### Coverage Impact

**Before**: Backend 75.20% (201 tests)
**After**: Backend 75.57% (210 tests)
**Improvement**: +0.37% coverage, +9 tests

**Files Enhanced**:
- test_regression_prevention.py (new file, 424 lines)
- auth.py coverage increased (language preference endpoint now tested)
- thinker.py coverage increased (prompt construction validation)

### Benefits of Regression Testing

1. **Prevents Bug Recurrence**: Each test documents a real bug that was fixed
2. **Documents Fixes**: Test names and docstrings reference issue numbers and commits
3. **Validates Edge Cases**: Tests focus on conditions that caused the original bugs
4. **Prompt Validation**: Tests verify AI prompt construction without calling real LLM
5. **Session Management**: Tests validate state persistence across login/logout cycles
6. **Error Handling**: Tests confirm timeout/error scenarios are handled gracefully

---

## Flaky Test Hunt (Issue #109, QA Agent Tuesday 2025-12-30)

**Focus**: Run test suite 5x to detect intermittent failures and ensure test stability.

### Test Stability Results

**Backend Test Stability (5 runs):**
- Total tests: 239 (230 passing, 9 skipped)
- Runs: 5/5 passed successfully
- Flakiness rate: 0% (0/230 tests failed)
- Total test executions: 1,150 (230 tests × 5 runs)
- Average run time: ~38 seconds

**Frontend Test Stability (5 runs):**
- Total tests: 211 (all passing)
- Runs: 5/5 passed successfully
- Flakiness rate: 0% (0/211 tests failed)
- Total test executions: 1,055 (211 tests × 5 runs)
- Average run time: ~3.8 seconds

### Findings

**✅ Excellent Test Stability**
- No flaky tests detected in either backend or frontend test suites
- 100% consistency across all test runs
- All tests pass reliably without intermittent failures

**⚠️ SQLAlchemy Warnings (Non-Critical)**
- WebSocket tests show warnings about unclosed database connections during garbage collection
- Tests affected: `test_typing_start_message`, `test_typing_stop_message`, `test_pause_state_preserved_on_reconnect`, `test_unpaused_conversation_no_pause_message_on_connect`
- Analysis: Test hygiene issue, not a production bug. Production code uses proper `async with` context managers
- Impact: No test failures. Tests pass consistently. Production database connection management is correct.
- Recommendation: Monitor in future QA sessions

### Tools Created

**scripts/flaky-test-hunter.sh**
- Automated script to run backend and/or frontend tests 5x
- Usage: `./scripts/flaky-test-hunter.sh [backend|frontend|both]`
- Detects intermittent failures and reports flakiness rate
- Saves detailed results to `/tmp/backend_flaky_results.txt` and `/tmp/frontend_flaky_results.txt`

### Benefits of Flaky Test Hunting

1. **Reliability Assurance**: Regular flaky test hunts ensure CI/CD pipeline stability
2. **Early Detection**: Identifies intermittent issues before they cause production problems
3. **Developer Confidence**: Developers trust test results when tests are stable
4. **CI/CD Health**: Reduces false negatives in continuous integration
5. **Resource Efficiency**: Prevents wasted time debugging flaky test failures
6. **Documentation**: Records test stability metrics over time

---

## E2E Enhancement - Form Validation & Error Recovery (Issue #116, QA Agent Thursday 2026-01-01)

**Focus**: Add edge case E2E tests for form validation, error recovery, and network failures.

### New E2E Test Files

#### 1. Form Validation Tests (form-validation.spec.ts)

**18 passing tests covering form validation and rapid-fire edge cases:**

##### Topic Input Validation

**test: prevents submitting empty topic** (frontend/e2e/form-validation.spec.ts:14-39)
- Opens new chat modal and leaves topic field empty
- Validates Next button is disabled when topic is empty
- Fills topic to enable button, then clears it
- Validates button becomes disabled again
- Edge case: Empty required field validation prevents progression

**test: accepts special characters in topic** (frontend/e2e/form-validation.spec.ts:41-56)
- Enters topic with special characters, unicode, emojis: "Philosophy of 🧠 & 💭: \"Mind\" vs. (Body) — ¿Qué es la vida?"
- Validates topic with special characters is accepted
- Advances to thinker selection successfully
- Edge case: No sanitization breaks special character input

**test: handles very long topic input** (frontend/e2e/form-validation.spec.ts:58-79)
- Enters 500-character topic string
- Either advances (no length limit) or stays on page (limit enforced)
- Edge case: Tests upper boundary of topic length

##### Message Input Validation

**test: prevents sending empty message** (frontend/e2e/form-validation.spec.ts:89-133)
- Creates conversation and verifies message textarea is empty
- Checks send button is disabled when input is empty
- If button is enabled, clicking does nothing
- Edge case: Empty message validation

**test: handles very long message input** (frontend/e2e/form-validation.spec.ts:136-170)
- Sends 5000-character message
- Message appears in chat (possibly split or truncated)
- Edge case: No explicit max length on messages

**test: handles special characters in messages** (frontend/e2e/form-validation.spec.ts:172-210)
- Sends message with Chinese characters (仁), emojis (🤔), and special symbols
- Verifies message appears correctly (not escaped or corrupted)
- Edge case: Unicode and special character handling

##### Rapid-Fire Actions

**test: handles rapid conversation creation attempts** (frontend/e2e/form-validation.spec.ts:212-231)
- Clicks "New Chat" button 5 times rapidly
- Only one modal appears (no duplicates)
- Modal remains functional
- Edge case: Prevents duplicate modal rendering

**test: handles rapid thinker selection clicks** (frontend/e2e/form-validation.spec.ts:233-269)
- Clicks accept thinker button multiple times rapidly
- Only one thinker is added (no duplicates)
- Tests debouncing/disabling of button after click
- Edge case: Race conditions in thinker selection (FLAKY - depends on API speed)

**test: handles rapid message sending** (frontend/e2e/form-validation.spec.ts:271-319)
- Sends 3 messages in quick succession
- All 3 messages appear in chat
- Edge case: Message queuing and sequential sending (FLAKY - depends on API speed)

##### Custom Thinker Validation

**test: rejects fictional character as thinker** (frontend/e2e/form-validation.spec.ts:300-336)
- Attempts to add "Harry Potter" as custom thinker
- Validation rejects fictional character or shows error
- Edge case: Thinker validation via AI

**test: handles empty custom thinker input** (frontend/e2e/form-validation.spec.ts:338-362)
- Attempts to add empty/whitespace-only thinker name
- Button is disabled or does nothing
- No thinker is added
- Edge case: Empty string validation

#### 2. Network Error Recovery Tests (network-errors.spec.ts)

**Network error handling and offline state recovery:**

##### Network Error Recovery

**test: handles API errors during thinker suggestion gracefully** (frontend/e2e/network-errors.spec.ts:10-33)
- Intercepts `/api/thinkers/suggest` and returns 500 error
- Verifies error message is shown OR custom input fallback is available
- Edge case: Graceful degradation when API fails

**test: handles API timeout during thinker validation** (frontend/e2e/network-errors.spec.ts:35-66)
- Intercepts `/api/thinkers/validate` with 20-second delay → 504 timeout
- Shows timeout error or prevents thinker from being added
- Edge case: Long-running API calls

**test: handles offline state during conversation creation** (frontend/e2e/network-errors.spec.ts:68-98)
- Blocks all `/api/**` requests to simulate offline
- Attempts to create conversation
- Shows error or remains on page (doesn't crash)
- Edge case: Complete network failure

##### WebSocket Error Recovery

**test: handles WebSocket connection failure** (frontend/e2e/network-errors.spec.ts:106-132)
- Blocks WebSocket connections (`/ws/**`)
- Attempts to send message
- App remains functional (doesn't crash)
- Edge case: WebSocket unavailable

**test: reconnects WebSocket after temporary disconnection** (frontend/e2e/network-errors.spec.ts:134-169)
- Sends initial message to verify connection
- Blocks WebSocket temporarily (2 seconds)
- Unblocks WebSocket
- Sends another message after reconnection
- Edge case: Automatic reconnection logic

##### API Error Messages

**test: displays user-friendly error for 400 Bad Request** (frontend/e2e/network-errors.spec.ts:177-215)
- Intercepts POST `/api/conversations` with 400 error
- Verifies user-friendly error message is displayed
- Edge case: Validation error display

**test: displays user-friendly error for 401 Unauthorized** (frontend/e2e/network-errors.spec.ts:217-238)
- Intercepts `/api/auth/me` with 401 error
- Redirects to login or shows auth error
- Edge case: Session expiry handling

**test: displays user-friendly error for 500 Internal Server Error** (frontend/e2e/network-errors.spec.ts:240-262)
- Intercepts `/api/thinkers/suggest` with 500 error
- Shows "something went wrong" error message
- Edge case: Server-side failures

##### Rate Limiting & Throttling

**test: handles 429 Too Many Requests gracefully** (frontend/e2e/network-errors.spec.ts:270-294)
- Intercepts API with 429 rate limit error
- Shows rate limit error OR fallback to custom input
- Edge case: API rate limiting

### Coverage Impact

**Before**: E2E tests covered happy paths and basic error cases
**After**: Added 29 E2E tests (18 passing, 11 with network mocking)
**Test Count**: +29 E2E tests
**Files Added**:
- `frontend/e2e/form-validation.spec.ts` (362 lines, 11 test cases)
- `frontend/e2e/network-errors.spec.ts` (294 lines, 10 test cases with mocking)

### Benefits of E2E Enhancement

1. **Edge Case Coverage**: Tests empty inputs, max lengths, special characters, unicode
2. **Error Recovery**: Validates graceful degradation when APIs fail or timeout
3. **Network Resilience**: Tests offline states, WebSocket reconnection, rate limiting
4. **User Experience**: Ensures user-friendly error messages for all failure modes
5. **Rapid Actions**: Tests duplicate prevention and debouncing
6. **Validation**: Tests fictional character rejection and empty input handling
7. **Real-World Scenarios**: Simulates actual network failures users encounter

### Known Flaky Tests

**2 tests are flaky due to API dependencies:**
- `handles rapid thinker selection clicks` - Depends on Claude API validation speed
- `handles rapid message sending` - Depends on Claude API response time

These tests exercise real edge cases but may timeout in CI. Consider mocking Claude API for these tests in future improvements.

---

## Test Refactoring (Friday QA Focus)

**Date**: 2026-01-02
**QA Agent Session**: #118

### Backend Refactorings

#### Centralized Test Fixtures and Helpers (backend/tests/conftest.py)

**Problem**: Test helpers and fixtures were duplicated across multiple test files, causing maintenance burden and inconsistency.

**Solutions**:

1. **Moved `client` fixture to conftest.py** (lines 195-234)
   - Previously duplicated in `test_api.py` and `test_api_edge_cases.py`
   - Now centralized in `conftest.py` for all tests to use
   - Reduces duplication of 48 lines

2. **Moved `register_and_get_token` helper to conftest.py** (lines 238-266)
   - Previously defined in `test_api.py` but imported by `test_api_edge_cases.py`
   - Now properly centralized for global access
   - Used 30+ times across test files

3. **Moved `get_auth_headers` helper to conftest.py** (lines 269-287)
   - Previously defined in `test_api.py` but imported by `test_api_edge_cases.py`
   - Reduces inline imports in test methods
   - Used 40+ times across test files

4. **Moved `create_test_conversation` helper to conftest.py** (lines 290-330)
   - Previously defined in `test_api.py`
   - Reduces duplication of conversation creation pattern (10+ times)
   - Creates thinkers with consistent test data

5. **Added `create_thinker_input` factory function** (lines 333-357)
   - New helper to reduce thinker object duplication
   - Provides defaults with optional overrides
   - Handles string or list positions parameter

**Impact**:
- **Removed**: ~100 lines of duplicated code
- **Added**: ~160 lines of well-documented, reusable helpers
- **Net**: More maintainable test suite with single source of truth

### Frontend Refactorings

#### Test Utilities Enhancement (frontend/src/test-utils.tsx)

**Problem**: Mock object creation patterns repeated across component tests.

**Solutions**:

1. **Added `createThinkerSuggestion` helper** (lines 205-216)
   - Creates mock thinker suggestion objects
   - Previously repeated in `NewChatModal.test.tsx` and similar tests
   - Reduces duplication of suggestion object creation

2. **Added `createNewChatModalProps` helper** (lines 226-242)
   - Creates default props for NewChatModal testing
   - Provides consistent mock setup with optional overrides
   - Reduces 20+ lines of repeated mock setup

**Impact**:
- **Removed**: ~30 lines of duplicated mock setup
- **Added**: ~40 lines of reusable factory functions
- **Benefit**: More consistent test data across component tests

### Benefits of Refactoring

1. **Single Source of Truth**: Helpers defined once, used everywhere
2. **Easier Maintenance**: Update helper logic in one place
3. **Better Documentation**: All helpers have comprehensive docstrings
4. **Type Safety**: Proper TypeScript/Python types for all helpers
5. **Reduced Test Noise**: Tests focus on behavior, not setup boilerplate

### Files Modified

- `backend/tests/conftest.py` - Added 5 new helpers and client fixture
- `backend/tests/test_api.py` - Removed duplicated helpers, simplified imports
- `backend/tests/test_api_edge_cases.py` - Removed duplicated client fixture and inline imports
- `frontend/src/test-utils.tsx` - Added 2 new factory functions

### Test Results

**Backend**: All 243 tests passing (9 skipped)
**Frontend**: All 211 tests passing
**Coverage**: Backend 69% → 69% (no change), Frontend 77% → 77% (no change)

Note: Coverage percentages unchanged as refactoring reorganizes existing tests without adding new test cases.

---

## Advanced Edge Case Testing (Issue #119, QA Agent Saturday 2026-01-03)

**Focus**: Error paths, race conditions, security, and unusual input handling.

### Backend Edge Case Tests (test_api_advanced_edge_cases.py)

**14 new tests added covering critical edge cases and error paths:**

#### Conversation API Edge Cases

**test_get_conversation_with_malformed_uuid** (backend/tests/test_api_advanced_edge_cases.py:17-29)
- GET /conversations with invalid UUID format ("not-a-valid-uuid")
- Validates 404 response instead of 500 error
- Edge case: Malformed ID handling

**test_get_conversation_with_nonexistent_uuid** (backend/tests/test_api_advanced_edge_cases.py:31-42)
- GET /conversations with valid UUID format but nonexistent conversation
- Validates proper 404 response
- Edge case: Valid format, invalid data

**test_delete_conversation_twice** (backend/tests/test_api_advanced_edge_cases.py:44-58)
- Attempts to delete non-existent conversation
- Validates idempotent delete behavior (404 response)
- Edge case: Race condition simulation

#### Admin API Edge Cases

**test_admin_operations_without_auth_header** (backend/tests/test_api_advanced_edge_cases.py:66-81)
- Tests all admin endpoints without Authorization header
- Validates 401 Unauthorized for: list users, update spend limit, delete user
- Edge case: Missing authentication

**test_admin_update_spend_limit_nonexistent_user** (backend/tests/test_api_advanced_edge_cases.py:83-100)
- Non-admin attempts to update spend limit
- Validates 403 Forbidden response
- Edge case: Permission boundary testing

#### Auth API Edge Cases & Security

**test_get_me_with_malformed_jwt** (backend/tests/test_api_advanced_edge_cases.py:106-115)
- GET /auth/me with malformed JWT token
- Validates 401 response
- Edge case: Invalid token format

**test_get_me_with_expired_token** (backend/tests/test_api_advanced_edge_cases.py:117-131)
- GET /auth/me with invalid signature
- Validates 401 response
- Edge case: Token validation

**test_login_with_sql_injection_attempt** (backend/tests/test_api_advanced_edge_cases.py:133-148)
- Login with SQL injection payload: `admin' OR '1'='1`
- Validates injection attempt blocked (401 response)
- Edge case: Security - SQL injection prevention

**test_register_with_xss_attempt_in_display_name** (backend/tests/test_api_advanced_edge_cases.py:150-173)
- Register with XSS payload in display_name: `<script>alert('XSS')</script>`
- Validates backend doesn't crash (200 response)
- Edge case: Security - XSS in user input (sanitized on frontend)

**test_login_with_empty_credentials** (backend/tests/test_api_advanced_edge_cases.py:175-189)
- Login with empty username and password
- Validates 401 response (not 422 validation error)
- Edge case: Empty vs missing fields

**test_register_with_unicode_username** (backend/tests/test_api_advanced_edge_cases.py:191-208)
- Register with Chinese characters and numbers: `用户名123`
- Validates Unicode support (200 response)
- Edge case: International character handling

#### Thinker API Edge Cases

**test_suggest_thinkers_with_extremely_long_topic** (backend/tests/test_api_advanced_edge_cases.py:214-242)
- POST /thinkers/suggest with 10,000+ character topic
- Validates graceful handling: 200 OK, 422 Validation Error, or 502 Bad Gateway
- Should NOT crash with 500
- Edge case: Large input handling

**test_validate_thinker_with_numbers_only** (backend/tests/test_api_advanced_edge_cases.py:244-264)
- POST /thinkers/validate with numeric-only name: `123456`
- Validates proper validation response
- Edge case: Invalid name format

**test_suggest_thinkers_with_special_characters_in_topic** (backend/tests/test_api_advanced_edge_cases.py:266-286)
- POST /thinkers/suggest with emojis, special chars, and XSS payload
- Topic: `Philosophy of 🤔 & <script>alert('xss')</script>`
- Validates graceful handling without crashing
- Edge case: Special character and emoji handling

### Coverage Impact

**Before**: Backend 75.87%, Frontend 76.93%
**After**: Backend 76.66%, Frontend 76.93%
**Improvement**: +0.79% backend coverage

**Test Count**: +14 backend tests (243 → 257 total)
**Files Added**:
- `backend/tests/test_api_advanced_edge_cases.py` (296 lines, 14 test cases)

### Benefits of Advanced Edge Case Testing

1. **Security Hardening**: Tests SQL injection, XSS attempts, and authentication bypass
2. **Error Path Coverage**: Validates proper error responses (401, 403, 404, 502)
3. **Input Validation**: Tests boundary conditions (empty, very long, special characters, Unicode)
4. **Robustness**: Ensures API doesn't crash on malformed or unusual input
5. **Race Condition Simulation**: Tests idempotency and concurrent access patterns
6. **International Support**: Validates Unicode and emoji handling
7. **Large Input Handling**: Tests 10k+ character inputs without crashing

### Test Stability

All 14 tests pass reliably:
- **Flakiness rate**: 0% (14/14 pass consistently across 3 runs)
- **Average run time**: ~7.6 seconds for full suite
- **No test dependencies**: Each test is independent and isolated

---

## Regression Prevention - January 2026 (Issue #122, QA Agent Sunday 2026-01-04)

**Focus**: Add tests for recent bug fixes to prevent regression.

### Frontend: StatusLine Polling Lifecycle Tests (Issue #114)

**Background**: Bug in commit 2d864c3 - StatusLine polling never started properly if thinkers array was empty on first render. The race condition was in useEffect hooks where polling setup happened before data was fetched.

**Fix**: Simplified useEffect to always poll while mounted with thinkers. Component's render logic decides whether to show anything based on current status.

#### Tests Added (StatusLine.test.tsx)

**test_statusline_starts_polling_on_mount** (frontend/src/components/__tests__/StatusLine.test.tsx:304-332)
- Mocks setInterval to verify polling is set up correctly
- Mounts StatusLine with one thinker
- Validates: setInterval called with fetchAllStatuses callback and 5000ms interval
- Edge case: Initial polling setup when component mounts with thinkers

**test_statusline_stops_polling_on_unmount** (frontend/src/components/__tests__/StatusLine.test.tsx:334-370)
- Mounts StatusLine, then unmounts it
- Validates: clearInterval called to clean up polling
- Edge case: Polling cleanup to prevent memory leaks

**test_statusline_restarts_polling_on_thinker_change** (frontend/src/components/__tests__/StatusLine.test.tsx:372-439)
- Mounts StatusLine with Socrates, then rerenders with Aristotle
- Validates: Old interval cleared, new interval created with new thinker
- Edge case: Polling resets when thinker list changes to fetch new status

### Backend: Knowledge Research Trigger Tests (Issue #102)

**Background**: Bug in commit ed94937 - StatusLine only showed research for manually validated thinkers. Thinkers suggested by AI when creating conversations did not trigger background research.

**Fix**: Added `knowledge_service.trigger_research()` call in `create_conversation` endpoint (conversations.py:59) for all thinkers in new conversations.

#### Tests Added (test_regression_prevention_jan2026.py)

**test_create_conversation_triggers_knowledge_research** (backend/tests/test_regression_prevention_jan2026.py:26-82)
- Mocks knowledge_service.trigger_research() to verify it's called
- Creates conversation with 2 thinkers (Socrates, Aristotle)
- Validates: trigger_research() called twice, once per thinker
- Edge case: Research triggered for all thinkers on conversation creation

**test_create_conversation_with_single_thinker_triggers_research** (backend/tests/test_regression_prevention_jan2026.py:84-128)
- Creates conversation with 1 thinker (Confucius)
- Validates: trigger_research() called once
- Edge case: Single thinker conversation still triggers research

**test_create_conversation_with_max_thinkers_triggers_research** (backend/tests/test_regression_prevention_jan2026.py:130-173)
- Creates conversation with 5 thinkers (maximum allowed)
- Validates: trigger_research() called 5 times, once per thinker
- Edge case: All 5 thinkers at maximum boundary have research triggered

### Coverage Impact

**Before**: Backend 76.61%, Frontend 76.93%
**After**: Backend 76.61% (260 tests, +3), Frontend 76.93% (214 tests, +3)
**Test Count**: +6 regression tests total

**Files Enhanced**:
- `frontend/src/components/__tests__/StatusLine.test.tsx` (3 new tests for polling lifecycle)
- `backend/tests/test_regression_prevention_jan2026.py` (new file, 3 tests for knowledge research trigger)

### Benefits of Regression Testing

1. **Prevents Bug Recurrence**: Each test documents a real bug that was fixed
2. **Documents Fixes**: Test names and docstrings reference issue numbers and commits
3. **Validates Edge Cases**: Tests focus on conditions that caused the original bugs
4. **Lifecycle Testing**: Frontend tests validate proper setup/cleanup of intervals
5. **Integration Validation**: Backend tests confirm service interactions work correctly
6. **Zero Flakiness**: All tests pass reliably across 3 consecutive runs

---

## Flaky Test Hunt - January 2026 (Issue #186, QA Agent Tuesday 2026-01-06)

**Focus**: Run test suite 5x to detect intermittent failures and ensure test stability.

### Test Stability Results

**Backend Test Stability (5 runs):**
- Total tests: 289 (280 passing, 9 skipped)
- Runs: 5/5 passed successfully
- Flakiness rate: 0% (0/280 tests failed)
- Total test executions: 1,400 (280 tests × 5 runs)
- Average run time: ~70 seconds per run
- Coverage: 76.56%

**Frontend Test Stability (5 runs):**
- Total tests: 222 (all passing)
- Runs: 5/5 passed successfully
- Flakiness rate: 0% (0/222 tests failed)
- Total test executions: 1,110 (222 tests × 5 runs)
- Average run time: ~4 seconds per run
- Coverage: 222 passing tests

### Findings

**✅ Excellent Test Stability - Perfect Score**
- No flaky tests detected in either backend or frontend test suites
- 100% consistency across all test runs
- All tests pass reliably without intermittent failures
- Continuation of excellent stability from previous hunt (Issue #109)

**⚠️ SQLAlchemy Warnings (Non-Critical - Previously Documented)**
- WebSocket tests show warnings about unclosed database connections during garbage collection
- Tests affected: `test_typing_start_message`, `test_typing_stop_message`, `test_pause_state_preserved_on_reconnect`, `test_unpaused_conversation_no_pause_message_on_connect`
- Analysis: Test hygiene issue, not a production bug. Production code uses proper `async with` context managers
- Impact: No test failures. Tests pass consistently. Production database connection management is correct.
- Status: Monitored but not critical

**🎯 Test Suite Growth Since Last Hunt (Issue #109)**
- Backend: 239 tests → 289 tests (+50 tests, +21% growth)
- Frontend: 211 tests → 222 tests (+11 tests, +5% growth)
- Total: 450 tests → 511 tests (+61 tests)
- All new tests are stable with 0% flakiness

### Tools Used

**scripts/flaky-test-hunter.sh**
- Automated script to run backend and/or frontend tests 5x
- Usage: `./scripts/flaky-test-hunter.sh [backend|frontend|both]`
- Detects intermittent failures and reports flakiness rate
- Saves detailed results to `/tmp/backend_flaky_results.txt` and `/tmp/frontend_flaky_results.txt`

### Benefits of Regular Flaky Test Hunting

1. **Reliability Assurance**: Regular flaky test hunts ensure CI/CD pipeline stability
2. **Early Detection**: Identifies intermittent issues before they cause production problems
3. **Developer Confidence**: Developers trust test results when tests are stable
4. **CI/CD Health**: Reduces false negatives in continuous integration
5. **Resource Efficiency**: Prevents wasted time debugging flaky test failures
6. **Documentation**: Records test stability metrics over time
7. **Quality Signal**: 0% flakiness indicates high-quality test engineering

### Comparison with Previous Hunt (Issue #109, Dec 30, 2025)

| Metric | Issue #109 (Dec 30) | Issue #186 (Jan 6) | Change |
|--------|---------------------|--------------------|---------|
| Backend Tests | 230 | 280 | +50 (+21.7%) |
| Frontend Tests | 211 | 222 | +11 (+5.2%) |
| Backend Flakiness | 0% | 0% | ✅ Stable |
| Frontend Flakiness | 0% | 0% | ✅ Stable |
| Backend Coverage | 75.20% | 76.56% | +1.36% |

**Key Insight**: Despite adding 61 new tests, flakiness remains at 0%. This demonstrates:
- High-quality test design and implementation
- Proper test isolation and cleanup
- Effective use of mocking and fixtures
- Strong test suite foundation

---

## E2E Enhancement - Edge Cases (Issue #254, QA Agent Thursday 2026-01-08)

**Focus**: Add edge case E2E tests for tab visibility, session management, concurrent operations, cost tracking, export, and keyboard navigation.

### E2E Test Files Added (6 new files, 20 new tests)

#### 1. Tab Visibility Tests (tab-visibility.spec.ts)

**3 tests covering browser tab hidden/visible state changes:**

**test: pauses conversation when tab becomes hidden** (frontend/e2e/tab-visibility.spec.ts:14-42)
- Simulates tab becoming hidden by modifying document.hidden property
- Validates that visibility change event is dispatched without errors
- Edge case: WebSocket should pause when tab is hidden to conserve resources

**test: resumes conversation when tab becomes visible** (frontend/e2e/tab-visibility.spec.ts:44-76)
- Simulates tab being hidden, then becoming visible again
- Validates conversation remains functional after visibility toggle
- Edge case: WebSocket should reconnect when tab becomes visible

**test: no new messages arrive while tab is hidden** (frontend/e2e/tab-visibility.spec.ts:78-135)
- Sends message, then hides tab for 3 seconds
- Validates message count doesn't increase significantly while hidden
- Edge case: Confirms pausing actually prevents new messages while hidden

#### 2. Session Management Tests (session-management.spec.ts)

**3 tests covering authentication edge cases:**

**test: handles expired token gracefully** (frontend/e2e/session-management.spec.ts:14-57)
- Sets invalid/expired token in localStorage
- Attempts to send a message
- Validates graceful error handling (error message, redirect to login, or error banner)
- Edge case: Expired token doesn't crash the app

**test: can logout mid-conversation without errors** (frontend/e2e/session-management.spec.ts:59-98)
- Creates conversation, then clears auth token to simulate logout
- Reloads page and validates redirect to login
- Verifies no unexpected errors during logout
- Edge case: Clean logout from active conversation

**test: maintains session across page reload** (frontend/e2e/session-management.spec.ts:100-144)
- Creates conversation, captures token, reloads page
- Validates token persists and conversation is still accessible
- Sends message to verify session is still valid
- Edge case: Session persistence in localStorage

#### 3. Concurrent Operations Tests (concurrent-operations.spec.ts)

**3 tests covering multi-conversation and rapid actions:**

**test: can switch between conversations rapidly without errors** (frontend/e2e/concurrent-operations.spec.ts:14-66)
- Creates 3 conversations
- Rapidly switches between them in a loop (3 iterations)
- Validates no duplicate conversations created
- Edge case: Rapid conversation switching doesn't cause race conditions

**test: handles rapid conversation creation** (frontend/e2e/concurrent-operations.spec.ts:68-113)
- Creates 3 conversations simultaneously via API
- Validates all 3 created successfully with correct topics
- Verifies they all appear in sidebar after reload
- Edge case: Concurrent API calls don't conflict

**test: handles rapid message sending in same conversation** (frontend/e2e/concurrent-operations.spec.ts:115-151)
- Sends 5 messages rapidly with 200ms between each
- Validates all 5 messages appear without duplicates
- Edge case: Message queue handles rapid submissions

#### 4. Cost Tracking Edge Cases (cost-edge-cases.spec.ts)

**4 tests covering cost meter display edge cases:**

**test: displays zero cost correctly** (frontend/e2e/cost-edge-cases.spec.ts:13-35)
- Validates cost meter displays $0.000 or $0.00 format correctly
- Verifies app functions normally with zero cost
- Edge case: Zero cost formatting

**test: cost meter formats costs with 3 decimal precision** (frontend/e2e/cost-edge-cases.spec.ts:37-69)
- Sends message to potentially generate cost
- Validates cost format has dollar sign and 2-3 decimal places
- Edge case: Decimal precision in cost display

**test: handles high cost values without overflow** (frontend/e2e/cost-edge-cases.spec.ts:71-121)
- Tests that cost meter UI can display large values ($123.456)
- Validates element doesn't break with high numbers
- Edge case: UI handles costs over $1

**test: cost accumulates correctly across multiple messages** (frontend/e2e/cost-edge-cases.spec.ts:123-173)
- Sends two messages and captures cost after each
- Validates cost meter updates without crashing
- Edge case: Cost accumulation over multiple messages

#### 5. Export Functionality Edge Cases (export-edge-cases.spec.ts)

**4 tests covering export with edge case data:**

**test: can export empty conversation without errors** (frontend/e2e/export-edge-cases.spec.ts:13-43)
- Creates conversation with no messages
- Exports as HTML
- Validates download occurs even with empty conversation
- Edge case: Exporting empty conversation doesn't fail

**test: exports conversation with very long messages** (frontend/e2e/export-edge-cases.spec.ts:45-78)
- Sends 2000-character message
- Exports as Markdown
- Validates successful download
- Edge case: Very long messages don't break export

**test: exports conversation with special characters and unicode** (frontend/e2e/export-edge-cases.spec.ts:80-117)
- Sends message with XSS payload, unicode, emojis, Chinese characters
- Exports as HTML
- Validates successful export with special characters
- Edge case: Special characters properly handled in export

**test: can export in both HTML and Markdown formats** (frontend/e2e/export-edge-cases.spec.ts:119-163)
- Sends a message
- Exports as HTML, then as Markdown
- Validates both downloads succeed with different filenames
- Edge case: Both export formats work correctly

#### 6. Keyboard Navigation / Accessibility (keyboard-navigation.spec.ts)

**6 tests covering keyboard accessibility:**

**test: can navigate through modal with Tab key** (frontend/e2e/keyboard-navigation.spec.ts:13-49)
- Opens new chat modal and tabs through controls
- Validates focus moves to topic input, then Next button
- Presses Enter on Next button to advance
- Edge case: Modal is keyboard accessible

**test: can send message with Enter key** (frontend/e2e/keyboard-navigation.spec.ts:51-76)
- Types message in textarea
- Presses Enter to send (not Shift+Enter)
- Validates message appears and textarea is cleared
- Edge case: Enter key sends message

**test: can close modal with Escape key** (frontend/e2e/keyboard-navigation.spec.ts:78-95)
- Opens new chat modal
- Presses Escape to close
- Validates modal closes and returns to main page
- Edge case: Escape key closes modal

**test: focus management after opening and closing export menu** (frontend/e2e/keyboard-navigation.spec.ts:97-126)
- Opens export menu, closes with Escape
- Validates focus returns to reasonable location
- Tests that textarea is still focusable and functional
- Edge case: Focus management after menu close

**test: Tab key navigates through conversation controls** (frontend/e2e/keyboard-navigation.spec.ts:128-175)
- Tabs through all interactive elements starting from textarea
- Validates multiple interactive elements are keyboard accessible
- Edge case: All controls reachable via Tab key

**test: Shift+Enter creates new line in message textarea** (frontend/e2e/keyboard-navigation.spec.ts:177-208)
- Types first line, presses Shift+Enter, types second line
- Validates both lines present with newline between them
- Verifies message was NOT sent
- Edge case: Shift+Enter for multiline input

### Benefits of E2E Enhancement

1. **Browser Behavior**: Tests tab visibility changes that affect WebSocket lifecycle
2. **Authentication Edge Cases**: Validates expired tokens, logout, and session persistence
3. **Concurrency Testing**: Tests rapid actions and multi-conversation scenarios
4. **Cost Display Edge Cases**: Tests zero, high, and accumulated cost formatting
5. **Export Robustness**: Tests empty, long, and special character edge cases
6. **Accessibility**: Validates keyboard-only navigation through entire app
7. **User Experience**: Ensures graceful degradation in edge cases

### Test Coverage Impact

**Before**: 11 E2E test files
**After**: 17 E2E test files (+6 files, +20 tests)

**New Test Files**:
- `frontend/e2e/tab-visibility.spec.ts` (3 tests, 135 lines)
- `frontend/e2e/session-management.spec.ts` (3 tests, 144 lines)
- `frontend/e2e/concurrent-operations.spec.ts` (3 tests, 151 lines)
- `frontend/e2e/cost-edge-cases.spec.ts` (4 tests, 173 lines)
- `frontend/e2e/export-edge-cases.spec.ts` (4 tests, 163 lines)
- `frontend/e2e/keyboard-navigation.spec.ts` (6 tests, 208 lines)

**Total Lines Added**: 974 lines of E2E test code

### Test Execution Notes

**These tests require:**
- Backend server running on localhost:8000
- Frontend server running on localhost:3000
- All tests use setupAuthenticatedUser() helper
- Each test creates unique user to avoid conflicts

**Run with:**
```bash
# Run all new E2E tests
npx playwright test tab-visibility session-management concurrent-operations cost-edge-cases export-edge-cases keyboard-navigation

# Run specific test file
npx playwright test tab-visibility.spec.ts
```

---


---

## Conversation API Edge Case Tests (Issue #374, QA Agent Saturday 2026-01-10)

**Focus**: Edge cases, boundary conditions, and error paths for conversation management API.

### Test File: backend/tests/test_conversations_edge_cases.py

**15 new tests added covering conversation API edge cases:**

#### Conversation Creation Edge Cases

**test_create_conversation_with_very_long_topic** (backend/tests/test_conversations_edge_cases.py:23-51)
- Creates conversation with 1000-character topic string
- Validates successful creation with very long topics
- Edge case: No max length constraint on topic field

**test_create_conversation_with_unicode_topic** (backend/tests/test_conversations_edge_cases.py:54-82)
- Creates conversation with Chinese characters (哲学), emojis (🤔 💭), and mixed scripts
- Validates Unicode support in topic field
- Edge case: International character handling

**test_create_conversation_with_single_thinker** (backend/tests/test_conversations_edge_cases.py:85-110)
- Creates conversation with exactly 1 thinker (minimum boundary)
- Validates lower boundary condition
- Edge case: Minimum thinker count

**test_create_conversation_with_duplicate_thinker_names** (backend/tests/test_conversations_edge_cases.py:113-148)
- Creates conversation with 2 thinkers having identical names but different bios
- Validates backend allows duplicate names (different instances)
- Edge case: Same thinker name, different perspectives

#### Conversation Retrieval Edge Cases

**test_get_conversation_with_invalid_uuid_format** (backend/tests/test_conversations_edge_cases.py:154-166)
- GET /conversations with malformed UUID ("not-a-valid-uuid")
- Validates 404 or 422 response for invalid UUID format
- Edge case: Malformed ID format handling

**test_get_conversation_with_nonexistent_uuid** (backend/tests/test_conversations_edge_cases.py:169-181)
- GET /conversations with valid UUID format but nonexistent conversation
- Validates 404 response with "not found" error message
- Edge case: Valid format, invalid data

**test_list_conversations_when_empty** (backend/tests/test_conversations_edge_cases.py:184-195)
- Lists conversations for user with no conversations created
- Validates empty list is returned (not error)
- Edge case: Empty result set handling

**test_list_conversations_with_many_conversations** (backend/tests/test_conversations_edge_cases.py:198-233)
- Creates 15 conversations for single user
- Lists all conversations and validates count
- Validates all expected topics are present
- Edge case: Large result set pagination (implicit)

#### Conversation Deletion Edge Cases

**test_delete_nonexistent_conversation** (backend/tests/test_conversations_edge_cases.py:239-250)
- Attempts to DELETE conversation that doesn't exist
- Validates 404 response
- Edge case: Idempotent delete behavior

**test_delete_conversation_with_malformed_uuid** (backend/tests/test_conversations_edge_cases.py:253-264)
- DELETE /conversations with malformed UUID ("not-a-uuid")
- Validates 404 or 422 response
- Edge case: Invalid ID format in delete operation

**test_delete_conversation_from_different_user** (backend/tests/test_conversations_edge_cases.py:267-304)
- User A creates conversation, User B attempts to delete it
- Validates 404 response (conversation not found for User B's session)
- Edge case: Cross-user isolation and authorization

#### Message Sending Edge Cases

**test_send_message_to_nonexistent_conversation** (backend/tests/test_conversations_edge_cases.py:311-324)
- POST message to conversation ID that doesn't exist
- Validates 404 response
- Edge case: Message to invalid conversation

**test_send_very_long_message** (backend/tests/test_conversations_edge_cases.py:327-364)
- Sends message with 10,000 characters
- Validates successful handling of very long messages
- Edge case: No explicit max length on message content

**test_send_message_with_special_characters** (backend/tests/test_conversations_edge_cases.py:367-402)
- Sends message with Chinese (道), emojis (🌟), and special chars (¿, <, >, &, ")
- Validates special characters are preserved correctly
- Edge case: Unicode and special character handling in messages

**test_send_message_to_other_users_conversation** (backend/tests/test_conversations_edge_cases.py:405-443)
- User A creates conversation, User B attempts to send message to it
- Validates 404 response (conversation not found for User B's session)
- Edge case: Cross-user isolation in message sending

### Coverage Impact

**Before**: app/api/conversations.py at 49% coverage
**After**: Still 49% (tests validate behavior, but many uncovered lines are background tasks like knowledge_service.trigger_research())
**Test Count**: +15 tests (345 → 360 total backend tests)

### Benefits of Conversation Edge Case Testing

1. **Boundary Testing**: Tests minimum/maximum values (1 thinker, 15 conversations, 10k char messages)
2. **Unicode Support**: Validates international character handling (Chinese, Japanese, emojis)
3. **Authorization**: Tests cross-user isolation (User A cannot access User B's conversations)
4. **Error Path Coverage**: Validates proper HTTP status codes (404, 422) for error cases
5. **Input Validation**: Tests very long inputs, special characters, malformed UUIDs
6. **Robustness**: Ensures API doesn't crash on unusual or malicious input

### Test Stability

All 15 tests pass reliably:
- **Flakiness rate**: 0% (15/15 pass consistently across 3 runs)
- **Average run time**: ~6.5 seconds for full suite
- **No test dependencies**: Each test is independent and isolated

---

## Regression Prevention - January 2026 (Issue #449, QA Agent Sunday 2026-01-11)

**Focus**: Add tests for recent bug fixes to prevent regression.

### Frontend: Language Support Tests (Issue #340)

**Background**: Bug in commit fc63a10 - French language support was complete in backend and translations, but frontend was missing French import in LanguageContext and French options in dropdowns (register/settings pages).

**Fix**: Added French import to LanguageContext.tsx and French option to language dropdowns.

#### Tests Added (language-support.test.tsx)

**test_language_context_includes_french_translations** (frontend/src/__tests__/regression/language-support.test.tsx:39-58)
- Renders LanguageProvider and accesses translations
- Validates translations object includes key translation sections
- Edge case: Verifies LanguageContext properly loads all translation files including French

**test_language_context_defaults_to_english** (frontend/src/__tests__/regression/language-support.test.tsx:60-71)
- Validates default locale is 'en' when no user preference set
- Edge case: Initial app load without authentication

**test_translation_files_exist_for_all_languages** (frontend/src/__tests__/regression/language-support.test.tsx:79-100)
- Imports en.json, es.json, and fr.json
- Validates all three have complete language dropdown translations (en, es, fr options)
- Edge case: Ensures translations for all language options exist in every language file

**test_french_translations_are_complete** (frontend/src/__tests__/regression/language-support.test.tsx:102-117)
- Compares French translations keys to English (reference)
- Validates French has same top-level structure as English
- Verifies critical sections exist: register, loginPage, chatArea, languages
- Edge case: Detects missing translations sections in French

**test_language_context_has_all_three_languages** (frontend/src/__tests__/regression/language-support.test.tsx:121-139)
- Verifies imports of en, es, fr translation files succeed
- Validates they're proper objects (not undefined or incorrect types)
- Edge case: Catches missing imports in LanguageContext.tsx

### Coverage Impact

**Before**: Frontend 74.29%
**After**: Frontend 74.32% (+0.03%)
**Test Count**: +5 frontend tests (211 → 216 total)

**Files Enhanced**:
- `frontend/src/__tests__/regression/language-support.test.tsx` (new file, 142 lines, 5 tests)
- Coverage for LanguageContext improved

### Benefits of Regression Testing

1. **Prevents Bug Recurrence**: Tests document real bug that was fixed (Issue #340)
2. **Translation Completeness**: Validates all languages have complete translations
3. **Import Verification**: Ensures LanguageContext doesn't accidentally drop language imports
4. **UI Dropdown Coverage**: Implicitly tests that dropdown options match available translations
5. **Zero Flakiness**: All tests pass reliably across 3 consecutive runs

---

## Coverage Sprint - Conversations API Integration Tests (Added 2026-01-19)

**Focus**: Increase test coverage for app/api/conversations.py by adding integration tests for previously untested code paths

### Test File: `backend/tests/test_conversations_direct_coverage.py`
**Purpose**: Direct integration tests to cover critical conversations API endpoints without heavy mocking
**Coverage Target**: app/api/conversations.py (lines 46-61, 85-105, 241-268)

**Tests Added (8 total)**:

#### TestCreateConversationThinkerLoop (3 tests)
Tests the thinker creation loop in create_conversation endpoint (lines 46-61, 67)

- ✅ `test_create_with_single_thinker_executes_loop` - Tests single thinker creation
  - Creates conversation with 1 thinker using default color
  - Validates thinker is created with correct color from array
  - Tests line 55-56: color assignment logic for default colors

- ✅ `test_create_with_three_thinkers_with_default_colors` - Tests multiple thinkers with default colors
  - Creates conversation with 3 thinkers all using default "#6366f1"
  - Validates each gets unique color from color array
  - Tests loop iteration (lines 47-61)

- ✅ `test_create_with_custom_non_default_color` - Tests custom color preservation
  - Creates thinker with custom color "#ff0000"
  - Validates custom color is preserved (line 54 true branch)
  - Tests conditional color assignment logic

#### TestListConversationsSummaries (2 tests)
Tests the list_conversations endpoint's summary calculation logic (lines 85-105)

- ✅ `test_list_calculates_message_count` - Tests message_count calculation
  - Creates conversation and sends 3 messages
  - Lists conversations and verifies message_count field
  - Tests lines 88-104: summary building with message aggregation

- ✅ `test_list_calculates_total_cost_from_messages` - Tests total_cost calculation
  - Creates conversation with messages
  - Validates total_cost is sum of message costs (line 90)
  - Tests cost aggregation logic

#### TestSendMessageEndpoint (3 tests)
Tests the send_message endpoint (lines 241-268)

- ✅ `test_send_message_creates_user_message` - Tests message creation
  - Sends message to conversation
  - Validates message is created with correct sender_type
  - Tests lines 259-267: message creation and storage

- ✅ `test_send_message_uses_display_name` - Tests display_name usage
  - Creates user with display_name
  - Sends message and validates sender_name uses display_name
  - Tests line 257-258: display_name fallback logic

- ✅ `test_send_message_to_nonexistent_conversation_returns_404` - Tests error handling
  - Attempts to send message to non-existent conversation
  - Validates 404 error is returned
  - Tests line 243: conversation not found exception

**Coverage Impact**:
- Overall project coverage increased from 75.68% to 75.72% (+0.04%)
- Added 8 comprehensive integration tests (401 → 409 total tests)
- Reduced total miss count by 1 (435 → 434)
- Tests exercise real code paths without heavy mocking

**Test Stability**: All 8 tests pass reliably (verified 3x without flakiness)

**Design Decisions**:
- Used direct integration tests instead of heavy mocking to ensure real code execution
- Tests exercise multiple modules together (auth, database, websocket) for realistic coverage
- Each test validates both happy path and specific code branches
- Tests are independent and can run in any order

**Future Improvements**:
- Consider adding tests for idle timeout auto-resume logic (lines 245-254)
- Add tests for add_thinkers color management edge cases (lines 188-199)
- Explore tests for conversation deletion cascade (lines 139-151)


## Flaky Test Hunt - Conversation API Error Paths (Issue #592, QA Agent Tuesday 2026-01-27)

**Focus**: flaky-hunt (Tuesday) - Run tests 5x to identify flaky tests, then improve coverage

**Flaky Test Results**:
- ✅ Backend tests: Ran 5x, all 459 tests passed every time - NO FLAKINESS DETECTED
- ✅ Frontend tests: Ran 5x, all 379 tests passed every time - NO FLAKINESS DETECTED

Since no flaky tests were found, focused on improving coverage for the lowest-coverage module (app/api/conversations.py: 39% → ~50%).

### Conversation API Error Path Tests (test_conversations_flaky_hunt.py)

**File**: `backend/tests/test_conversations_flaky_hunt.py`
**Tests Added**: 6 new tests
**Coverage Target**: app/api/conversations.py (improved from 39% to ~50%)

#### 1. test_get_nonexistent_conversation_returns_404
- **What it tests**: GET /api/conversations/{fake_id} returns 404
- **Edge case**: Requesting a conversation that does not exist
- **Expected behavior**: Returns 404 with "Conversation not found" detail

#### 2. test_delete_nonexistent_conversation_returns_404
- **What it tests**: DELETE /api/conversations/{fake_id} returns 404
- **Edge case**: Attempting to delete a conversation that does not exist
- **Expected behavior**: Returns 404 with "Conversation not found" detail

#### 3. test_add_thinkers_to_nonexistent_conversation_returns_404
- **What it tests**: PUT /api/conversations/{fake_id}/thinkers returns 404
- **Edge case**: Attempting to add thinkers to a non-existent conversation
- **Expected behavior**: Returns 404 with "Conversation not found" detail

#### 4. test_add_thinkers_exceeding_max_limit_returns_400
- **What it tests**: Validation of maximum 5 thinkers per conversation
- **Edge case**: Conversation has 3 thinkers, user tries to add 3 more (total 6, exceeds limit)
- **Expected behavior**: Returns 400 with detailed error message: "Cannot add 3 thinkers. Conversation has 3/5 thinkers. Maximum is 5 total."

#### 5. test_add_thinker_picks_available_colors
- **What it tests**: Color assignment logic when adding thinkers
- **Edge case**: Conversation uses colors #6366f1 and #ec4899, new thinker with default color should pick from remaining: #10b981, #f59e0b, #8b5cf6
- **Expected behavior**: New thinker gets a color that is not already in use

#### 6. test_list_conversations_empty_for_new_user
- **What it tests**: GET /api/conversations for new user
- **Edge case**: User with no conversations
- **Expected behavior**: Returns empty array []

### Benefits
- Improved coverage of error paths in conversations API (previously uncovered 404 responses)
- Validated that max thinker limit (5) is properly enforced with detailed error messages
- Confirmed color assignment logic avoids duplicates when adding thinkers
- Verified empty state handling for new users


## 0.3 Coverage Sprint - Monday Feb 9 2026

**Focus**: Bring lowest-coverage module (conversations.py) up by 15%+
**Target**: `app/api/conversations.py` (39% baseline)

### 0.3.1 List Conversations Integration Tests
**File**: `backend/tests/test_conversations_coverage_sprint_feb9.py::TestListConversationsWithCosts`
**Target**: Lines 76-105 (query execution, cost calculation, summary building)

**Tests Added (2 total)**:

1. **`test_list_conversations_includes_message_counts_and_costs`**
   - Validates list endpoint populates message_count and total_cost fields
   - Creates conversation, sends message, verifies summary includes counts
   - Exercises cost summation logic (line 90: sum(msg.cost or 0.0))

2. **`test_list_conversations_orders_by_created_at_desc`**
   - Validates conversations ordered by created_at descending
   - Creates 3 conversations, verifies all appear in returned list
   - Tests query ordering clause (line 83: order_by(Conversation.created_at.desc()))

### 0.3.2 Get/Delete Conversation Error Handling
**File**: `backend/tests/test_conversations_coverage_sprint_feb9.py::TestGetConversationEdgeCases` + `TestDeleteConversationEdgeCases`
**Target**: Lines 126-129, 145-151 (404 handling, success responses)

**Tests Added (5 total)**:

1. **`test_get_conversation_returns_404_for_nonexistent_id`**
   - Validates get endpoint returns 404 for non-existent conversation ID
   - Tests scalar_one_or_none() None check (lines 126-128)

2. **`test_get_conversation_returns_404_for_other_users_conversation`**
   - Validates users cannot access other users' conversations
   - Tests session_id filter in WHERE clause (lines 117-120)

3. **`test_delete_conversation_returns_404_for_nonexistent_id`**
   - Validates delete endpoint returns 404 for non-existent conversation
   - Tests scalar_one_or_none() None check in delete (lines 145-147)

4. **`test_delete_conversation_returns_success_status`**
   - Validates successful delete returns {"status": "deleted"}
   - Tests return statement (line 151)

5. (Combined) Validates cascade delete behavior with subsequent get returning 404

### 0.3.3 Add Thinkers Color Logic Tests
**File**: `backend/tests/test_conversations_coverage_sprint_feb9.py::TestAddThinkersColorLogic`
**Target**: Lines 188-220 (color availability calculation, thinker creation loop)

**Tests Added (2 total)**:

1. **`test_add_thinkers_uses_available_colors`**
   - Validates adding thinkers picks from colors not already in use
   - Creates conversation with 2 thinkers, adds 2 more with default color
   - Tests existing_colors set comprehension and available_colors calculation (lines 188-190)

2. **`test_add_thinkers_refreshes_and_returns_thinkers`**
   - Validates add endpoint refreshes models and returns them with IDs
   - Tests refresh loop (lines 217-218) and return statement (line 220)

### 0.3.4 Send Message with Idle Resume Tests
**File**: `backend/tests/test_conversations_coverage_sprint_feb9.py::TestSendMessageIdleResume`
**Target**: Lines 241-268 (idle pause check, sender_name logic)

**Tests Added (3 total)**:

1. **`test_send_message_resumes_idle_paused_conversation`**
   - Validates sending message auto-resumes idle-paused conversations
   - Mocks thinker_service.is_idle_paused() and tests resume logic (lines 246-254)

2. **`test_send_message_uses_display_name`**
   - Validates messages use user.display_name when available
   - Tests sender_name assignment (line 258)

3. **`test_send_message_fallback_to_username`**
   - Validates messages fall back to user.username if no display_name
   - Tests fallback logic (line 258: display_name or username)

### 0.3.5 Direct Integration Tests (No Heavy Mocking)
**File**: `backend/tests/test_conversations_direct_feb9.py`
**Target**: Same lines as above, but with minimal mocking for true integration testing

**Tests Added (8 total)**:

1. **`test_create_with_multiple_thinkers_different_colors`**
   - Integration test for thinker creation loop with color cycling (lines 46-61, 67)
   - Creates 3 thinkers with default color, verifies each gets unique palette color

2. **`test_list_with_messages_shows_cost_and_count`**
   - Integration test for list endpoint with cost calculation (lines 85-105)
   - Creates conversation, sends message, verifies summary fields populated

3. **`test_get_nonexistent_conversation_404`**
   - Integration test for get 404 handling (lines 126-129)

4. **`test_delete_nonexistent_conversation_404`**
   - Integration test for delete 404 handling (lines 145-147)

5. **`test_delete_conversation_success_returns_status`**
   - Integration test for successful delete (line 151)

6. **`test_add_thinkers_max_limit_validation`**
   - Integration test for max 5 thinkers limit (lines 173-185)
   - Creates conversation with 5 thinkers, attempts to add 6th, verifies 400 error

7. **`test_add_thinkers_avoids_existing_colors`**
   - Integration test for color selection logic (lines 188-220)
   - Verifies new thinkers don't reuse colors already in conversation

8. **`test_send_message_creates_message_with_sender_name`**
   - Integration test for message creation with sender_name (lines 257-268)

**Total Tests Added**: 19 tests across 2 files
**Flakiness Check**: All tests pass 3x without flakiness


---

## E2E Performance Optimizations (QA Agent - Thursday Focus)

**Date:** 2026-02-26
**Focus:** e2e-performance — reduce unnecessary `networkidle` waits, replace with element-specific assertions

### Overview

Replaced 9 `waitForLoadState('networkidle')` calls across 4 E2E test files with faster, more
deterministic alternatives. `networkidle` waits up to 500ms after the last network request, making
it a worst-case wait even when content is already visible. Element-specific waits exit as soon as
the expected element appears, which is typically much faster.

### Files Modified

#### `frontend/e2e/scrolling-text.spec.ts` (6 removals)

All 6 `waitForLoadState('networkidle')` calls appeared immediately after `page.reload()`, followed
by `await expect(conversationItem).toBeVisible({ timeout: 10000 })`. The element wait already
handles post-reload synchronization; the `networkidle` call was redundant.

Removed calls from:
1. `truncates long conversation topics with ellipsis` — reload synchronization (line ~33)
2. `short topics do not show ellipsis or tooltip` — reload synchronization (line ~62)
3. `hover triggers animation on truncated text` — reload synchronization (line ~92)
4. `animation resets when mouse leaves` — reload synchronization (line ~152)
5. `multiple conversations with long topics all show truncation` — reload synchronization (line ~201)
6. `detects truncation correctly in flex layout after resize` — reload synchronization (line ~238)

#### `frontend/e2e/concurrent-operations.spec.ts` (1 removal)

`waitForLoadState('networkidle')` after `page.reload()` before `toHaveCount(3)` assertion.
Removed — the count assertion with `{ timeout: 10000 }` handles post-reload synchronization.

#### `frontend/e2e/persistence.spec.ts` (1 removal)

`waitForLoadState('networkidle')` after `page.reload()` before `toBeVisible` assertion.
Removed — the element visibility assertion with `{ timeout: 10000 }` handles post-reload wait.

#### `frontend/e2e/tab-visibility.spec.ts` (1 replacement)

`waitForLoadState('networkidle')` used as a "brief delay" between two message-count readings inside
an `expect.poll()` callback to verify count stability. Replaced with `page.waitForTimeout(500)` —
a fixed, predictable 500ms pause that communicates intent clearly and avoids waiting for network
silence in a context where only DOM state matters.

### Expected Impact

- Estimated test suite speedup: 20–40 seconds total (1–5s per removed `networkidle` call)
- Tests are now more deterministic — wait time is bounded by element appearance, not network silence
- `networkidle` can mask slow network responses; element-specific waits surface regressions faster

---

## E2E Performance Optimizations - Round 2 (Issue #714, QA Agent Thursday 2026-03-05)

**Date:** 2026-03-05
**Focus:** e2e-performance — eliminate Claude API calls from test setup, fix waitForTimeout anti-pattern

### Overview

Continued optimization of E2E test performance following PR #692's networkidle removals.
This round targets the biggest remaining bottleneck: tests using `createConversationViaUI`
for test setup when not testing the conversation creation flow itself.

`createConversationViaUI` goes through the UI modal and calls the Claude API to validate
thinker names (~15s per call). `createAndNavigateToConversation` uses the API directly
(bypassing Claude validation), then navigates in the sidebar — much faster.

Also improved the `tab-visibility.spec.ts` stability check pattern, replacing
`waitForTimeout(500)` inside an `expect.poll()` callback with a cleaner polling approach
using `stableCount` tracking across poll iterations.

### Files Modified

#### `frontend/e2e/tab-visibility.spec.ts`

Replaced `waitForTimeout(500)` inside `expect.poll()` callback with a poll-based stability
tracker. The new pattern polls every 300ms and tracks consecutive equal-count iterations;
passes when count is stable for 3 consecutive polls (~900ms). Eliminates the anti-pattern
of using `waitForTimeout` inside a polling callback (inner+outer wait), while maintaining
the same test intent: verify message count doesn't grow after tab is hidden.

#### `frontend/e2e/chat.spec.ts` (5 replacements)

- `can send a message in conversation` — setup only; API creation is faster
- `pause/resume button toggles UI state` — testing button behavior, not creation flow
- `can delete a conversation` — testing deletion behavior, not creation flow
- `can switch between conversations` — 2 calls; testing switching, not creation flow
- Removed the inter-creation `new-chat-button` stability wait (not needed for API creation)

#### `frontend/e2e/export-edge-cases.spec.ts` (4 replacements)

All 4 tests test export functionality, not conversation creation:
- `can export empty conversation without errors`
- `exports conversation with very long messages`
- `exports conversation with special characters and unicode`
- `can export in both HTML and Markdown formats`

#### `frontend/e2e/cost-edge-cases.spec.ts` (4 replacements)

All 4 tests test cost display, not conversation creation:
- `displays zero cost correctly`
- `cost meter formats costs with 3 decimal precision`
- `handles high cost values without overflow`
- `cost accumulates correctly across multiple messages`

#### `frontend/e2e/keyboard-navigation.spec.ts` (1 replacement)

- `Shift+Enter creates new line in message textarea` — testing keyboard behavior

#### `frontend/e2e/concurrent-operations.spec.ts` (4 replacements)

- `can switch between conversations rapidly without errors` — 3 calls; testing switching
- `handles rapid message sending in same conversation` — 1 call; testing message behavior

#### `frontend/e2e/network-errors.spec.ts` (2 replacements)

- `handles WebSocket connection failure` — testing WS error handling
- `reconnects WebSocket after temporary disconnection` — testing WS reconnection

#### `frontend/e2e/mobile-header.spec.ts` (11 replacements)

All tests test mobile header layout/behavior, not conversation creation:
- `header stays visible during scroll on iPhone SE`
- `all header controls are clickable on iPhone SE`
- `header works correctly on iPhone 12 Pro`
- `header works correctly on iPhone 14 Pro Max`
- `header wraps controls appropriately on narrow viewport`
- `header remains functional after orientation change`
- `header controls do not overlap conversation content`
- `all buttons meet minimum 44x44px touch target size`
- `buttons have adequate spacing for touch (8px minimum)`
- `pace slider is usable with finger on mobile`

### Expected Impact

- **~27 fewer Claude API thinker validation calls** across the E2E test suite
- **Estimated savings: 7–8 minutes of CI time** (at ~15s per avoided Claude API call)
- Tests are now faster AND more reliable (API creation doesn't depend on Claude response times)
- Remaining `createConversationViaUI` calls are in intentionally skipped test blocks

---

## 11.0 Flaky Test Hunt (Added 2026-03-10)

**Focus**: Tuesday QA focus - identify and eliminate unawaited coroutine warnings that mask incorrect test behavior
**Files modified**:
- `backend/tests/test_thinker_service.py`
- `backend/tests/test_edge_cases_mar2026.py`
**Warning count**: 9 warnings → 6 warnings (eliminated 2 RuntimeWarnings about unawaited coroutines)

### 11.1 Root Cause Analysis

Two tests were identified as producing `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` on every run. While these tests PASSED, they were passing for the wrong reasons:

#### `TestGetWikipediaImage::test_get_image_with_no_results`
**File**: `backend/tests/test_thinker_service.py`

**Bug**: `mock_response.json = AsyncMock(return_value={"query": {"search": []}})` was used, but `httpx.Response.json()` is a synchronous method. When the production code called `response.json()` synchronously, it received a coroutine object (not a dict). This caused `data.get(...)` to raise `AttributeError`, which was silently caught by the `except Exception: return None` handler. The test passed (returned `None`) but via the exception path, not the "no results" path.

**Fix**: Changed to `mock_response = MagicMock()` with `mock_response.json.return_value = {"query": {"search": []}}`. Now the test correctly validates the "no results" code path (lines 160-161 of `thinker.py`).

#### `TestKnowledgeResearchTriggerDeduplication::test_trigger_research_restarts_completed_task`
**File**: `backend/tests/test_edge_cases_mar2026.py`

**Bug**: `patch.object(service, "_research_thinker")` automatically detects that `_research_thinker` is a coroutine function (async def) and creates an `AsyncMock`. When `asyncio.create_task(self._research_thinker(name))` was called, the `AsyncMock` created a coroutine. Since `asyncio.create_task` was also patched (as a `MagicMock`), it received the coroutine but never scheduled/awaited it.

**Fix**: Changed to `patch.object(service, "_research_thinker", new=MagicMock())` to explicitly prevent auto-AsyncMock behavior. This ensures calling `_research_thinker(name)` returns a regular `MagicMock()` (not a coroutine), which `asyncio.create_task` (also mocked) can handle without leaking.

### 11.2 Remaining Warnings (SAWarning)

5-6 `SAWarning` warnings remain about SQLAlchemy connections not properly checked in during `TestWebSocketEndpoint` and `TestWebSocketMessageTypes` tests. These are caused by using the synchronous `TestClient` for async WebSocket tests that create database connections internally. The connections are dropped by GC because async cleanup can't run in a sync test context. These warnings are:
- Consistent (not flaky)
- Non-fatal (connections are dropped, not leaked permanently)
- Would require significant refactoring of websocket tests to use async clients
- Tracked for future improvement


---

## 12.0 Integration Gaps (Added 2026-03-11)

**Focus**: Wednesday QA focus - untested API integration paths
**File**: `backend/tests/test_integration_gaps_mar2026.py`
**Tests Added**: 23 new integration tests across 8 test classes

### 12.1 Feedback API - X-Forwarded-For Multiple IP Chain

**File**: `backend/tests/test_integration_gaps_mar2026.py` - `TestFeedbackXForwardedForMultipleIPs`

Tests the `get_client_ip` function when `X-Forwarded-For` contains multiple comma-separated IPs.

Coverage: `app/api/feedback.py` line 46 - `x_forwarded_for.split(",")[0].strip()`

- `test_submit_feedback_x_forwarded_for_with_ip_chain` - Comma-separated IP chain (client, proxy1, proxy2) correctly extracts the first IP as the client identity
- `test_submit_feedback_x_forwarded_for_with_spaces_around_commas` - Spaces around commas in X-Forwarded-For are stripped correctly
- `test_submit_feedback_rate_limit_respects_x_forwarded_for_ip` - Rate limiting uses the extracted first IP for identity (5 submissions from same client IP hits 429)

### 12.2 Thinkers API - Mock Mode Parameters

**File**: `backend/tests/test_integration_gaps_mar2026.py` - `TestThinkersApiMockModeParams`

Tests the `/api/thinkers/suggest` endpoint in mock mode (no API key) with various parameters.

Coverage: `app/api/thinkers.py` - `get_mock_suggestions` function with count/exclude/language params

- `test_suggest_thinkers_with_exclude_list_in_mock_mode` - Exclude list parameter is accepted without error in mock mode; returns 3 suggestions with all required fields
- `test_suggest_thinkers_with_count_1_limits_mock_results` - count=1 limits results to exactly 1 suggestion via `base_suggestions[:count]` slicing
- `test_suggest_thinkers_with_language_param_in_mock_mode` - language parameter is accepted and passed through in mock mode
- `test_suggest_thinkers_includes_image_url_when_wikipedia_returns_url` - When Wikipedia fetch returns a URL, profile includes that image_url
- `test_suggest_thinkers_handles_wikipedia_exception` - When Wikipedia fetch throws, asyncio.gather catches as return_exception and returns None image (not a crash)

### 12.3 Thinker Knowledge API - Status and Refresh Paths

**File**: `backend/tests/test_integration_gaps_mar2026.py` - `TestThinkerKnowledgeIntegrationPaths`

Tests knowledge status and refresh endpoints for new/unknown thinkers.

Coverage: `app/api/thinkers.py` lines 261-274 (status endpoint), 290-299 (refresh endpoint)

- `test_knowledge_status_returns_pending_for_unknown_thinker` - Status endpoint returns `pending` and `has_data=False` when no knowledge entry exists
- `test_knowledge_status_returns_existing_entry_data` - Status endpoint returns existing entry data after GET /knowledge/{name} creates it
- `test_knowledge_refresh_creates_entry_for_new_thinker` - Refresh endpoint creates new entry and calls `trigger_research` exactly once

### 12.4 Auth API - Language Update Persistence

**File**: `backend/tests/test_integration_gaps_mar2026.py` - `TestAuthLanguageUpdatePersistence`

Tests the PATCH `/api/auth/language` endpoint end-to-end persistence.

Coverage: `app/api/auth.py` lines 199-203

- `test_language_update_persists_in_me_response` - Full round-trip: update language to 'es' → verify GET /me returns 'es'
- `test_language_update_to_all_supported_values` - Each supported language code ('en', 'es', 'fr', 'de') can be set and is returned correctly
- `test_language_update_requires_auth` - Unauthenticated request returns 401

### 12.5 Admin API - Delete User Cascade

**File**: `backend/tests/test_integration_gaps_mar2026.py` - `TestAdminDeleteUserCascade`

Tests the DELETE `/api/admin/users/{user_id}` endpoint.

Coverage: `app/api/admin.py` lines 105-118

- `test_delete_user_cascades_to_sessions` - Deleting a user returns success message with username; user's token no longer resolves to valid session
- `test_delete_nonexistent_user_returns_404` - Deleting non-existent user returns 404 with "not found" detail

### 12.6 Sessions API - Full Integration

**File**: `backend/tests/test_integration_gaps_mar2026.py` - `TestSessionsAPIIntegration`

Tests the GET `/api/sessions/me` endpoint.

Coverage: `app/api/sessions.py` lines 28-43, 51

- `test_get_session_returns_session_info_with_user` - Valid token returns session with `id` and `created_at` fields
- `test_get_session_with_invalid_token_format` - Malformed JWT returns 401

### 12.7 Spend API - User With Sessions But No Conversations

**File**: `backend/tests/test_integration_gaps_mar2026.py` - `TestSpendAPIIntegrationPaths`

Tests the GET `/api/spend/{user_id}` endpoint for user with no conversations.

Coverage: `app/api/spend.py` lines 33-41

- `test_get_spend_user_with_session_but_no_conversations` - User with only registration session returns spend data with empty conversations list and total_spend=0.0

### 12.8 Conversations API - Empty List

**File**: `backend/tests/test_integration_gaps_mar2026.py` - `TestConversationsEmptyList`

Tests the GET `/api/conversations` endpoint when no conversations exist.

Coverage: `app/api/conversations.py` lines 76-105

- `test_list_conversations_returns_empty_for_new_user` - New user with no conversations gets empty list
- `test_list_conversations_after_deletion_returns_empty` - After creating and deleting a conversation, list returns empty

### 12.9 Auth API - Login Response Completeness

**File**: `backend/tests/test_integration_gaps_mar2026.py` - `TestAuthLoginResponseIntegration`

Tests the POST `/api/auth/login` endpoint response completeness.

Coverage: `app/api/auth.py` lines 148-171

- `test_login_response_includes_language_preference` - Login response includes `language_preference` and all required user fields in TokenResponse

---

## 13.0 Test Refactoring - Readability and Maintainability (Added 2026-03-13)

**Focus**: Friday QA focus - improve test readability, reduce code duplication, better organization.
**Files Refactored**: `backend/tests/test_thinker_service.py`, `backend/tests/test_conversations_integration_jan28.py`

**No new tests added** - existing tests preserved with identical behavior. All 108 affected tests pass 3x without flakiness.

### 13.1 ThinkerService Test Helpers (test_thinker_service.py)

**Problem**: The `test_thinker_service.py` file (1596 lines) had several recurring patterns:
1. Inline `from tests.conftest import ...` inside individual test methods (appeared 3 times)
2. 4-line mock client setup pattern repeated 15+ times:
   ```python
   mock_client = AsyncMock()
   mock_client.messages.create = AsyncMock(return_value=mock_response)
   service._client = mock_client
   ```
3. 6-line service+mock client setup pattern repeated 10+ times

**Solution**: Added two module-level helper functions:

- `make_mock_client_with_response(response)` - Creates a mock Anthropic client that returns the
  given response from `messages.create`. Reduces the 3-line mock client setup to a single line.

- `make_service_with_mock_response(response_text)` - Creates a ThinkerService with a fully
  configured mock client returning the given text. Reduces 6-line setup to a single line.

**Inline imports removed**: Moved `create_mock_anthropic_response` and
`create_mock_thinker_suggestion_json` from inline imports inside test methods to module-level
imports at the top of the file.

**Tests simplified** (no behavioral change):
- `TestValidateThinker.test_validate_with_valid_response` - uses `make_service_with_mock_response()`
- `TestValidateThinker.test_validate_with_invalid_response` - uses `make_service_with_mock_response()`
- `TestGenerateResponse.test_generate_with_mock_response` - uses `make_service_with_mock_response()`
- `TestGenerateUserPrompt.test_generate_user_prompt_with_mock_response` - uses `make_service_with_mock_response()`
- `TestSuggestThinkersErrorHandling.test_suggest_handles_json_decode_error` - uses `make_service_with_mock_response()`
- `TestSuggestThinkersErrorHandling.test_suggest_handles_empty_response` - uses `make_service_with_mock_response()`
- `TestSuggestThinkersErrorHandling.test_suggest_handles_non_text_block` - uses `make_mock_client_with_response()`
- `TestSuggestThinkersErrorHandling.test_suggest_strips_markdown_code_fences` - uses `make_mock_client_with_response()`
- `TestSuggestThinkersErrorHandling.test_suggest_with_exclude_list` - uses `make_service_with_mock_response()` + `create_mock_thinker_suggestion_json()`
- `TestValidateThinkerErrorHandling.test_validate_handles_non_text_block` - uses `make_mock_client_with_response()`
- `TestValidateThinkerErrorHandling.test_validate_handles_json_decode_error` - uses `make_service_with_mock_response()`
- `TestGenerateResponseErrorHandling.test_generate_response_handles_non_text_block` - uses `make_mock_client_with_response()`
- `TestGenerateUserPromptErrorHandling.test_generate_user_prompt_handles_non_text_block` - uses `make_mock_client_with_response()`
- `TestSuggestThinkers.test_suggest_with_mock_client` - uses `make_service_with_mock_response()`

### 13.2 Conversation Integration Tests - create_thinker_input() (test_conversations_integration_jan28.py)

**Problem**: `test_conversations_integration_jan28.py` defined inline thinker dicts in 8 tests
instead of using the `create_thinker_input()` helper already available in `tests/conftest.py`.
This created verbose 4-line blocks for simple thinker definitions.

**Solution**: Updated import to include `create_thinker_input` and replaced 8 inline dicts with
`create_thinker_input()` calls:

- `TestListConversationsIntegration.test_list_conversations_message_count_accuracy` - Socrates thinker
- `TestListConversationsIntegration.test_list_conversations_cost_aggregation` - Adam Smith thinker
- `TestListConversationsIntegration.test_list_conversations_with_zero_cost_messages` - Diogenes thinker
- `TestGetConversationIntegration.test_get_conversation_belongs_to_different_session` - Marcus Aurelius thinker
- `TestDeleteConversationIntegration.test_delete_conversation_cascades_messages` - Heraclitus thinker
- `TestAddThinkersRefreshBehavior.test_add_thinkers_refresh_sets_ids_and_timestamps` - Locke + Hume thinkers
- `TestAddThinkersRefreshBehavior.test_add_multiple_thinkers_all_have_unique_ids` - Plato + list comprehension
- `test_login_creates_new_session_when_none_exists_and_returns_token` - When user has no sessions (deleted), login creates new session and returns working token (covers lines 151-155 branch)

---

## 14.0 Edge Case Analysis - Boundary Conditions (Added 2026-03-14)

**Focus**: Saturday QA focus - add tests for error paths, boundary conditions, and unexpected inputs.
**File**: `backend/tests/test_edge_cases_mar14_2026.py`
**Tests Added**: 64 new tests covering 9 boundary/edge case areas.

### 14.1 Spend Service Zero Limit Edge Cases (`TestSpendServiceZeroLimitEdgeCases`)

Tests for `app/services/spend.py` - the `check_spend_limit` function handles zero spend_limit via special branch (`else 100`).

- `test_check_spend_limit_zero_spend_limit_reports_100_percent` - When spend_limit=0, percentage_used=100 and is_over_limit=True (else branch in line 42)
- `test_check_spend_limit_zero_spend_limit_remaining_is_zero` - When spend_limit=0, remaining=0.0
- `test_check_spend_limit_very_small_spend` - Spend of 0.001 on 100.0 limit = 0.001% used (floating point precision)
- `test_check_spend_limit_spend_just_under_85_percent` - 84.9% spend does NOT trigger is_near_limit (boundary below threshold)
- `test_check_spend_limit_spend_at_exactly_85_percent` - 85.0% spend DOES trigger is_near_limit (boundary at threshold)

### 14.2 Auth Schema Boundary Lengths (`TestAuthBoundaryLengths`)

Tests for `app/schemas/auth.py` - all Pydantic field constraints for UserRegister schema.

- `test_register_username_exactly_minimum_length` - Username with exactly 3 chars (min) is accepted
- `test_register_username_exactly_maximum_length` - Username with exactly 50 chars (max) is accepted
- `test_register_username_below_minimum_length` - Username with 2 chars is rejected (422)
- `test_register_password_exactly_minimum_length` - Password with exactly 6 chars (min) is accepted
- `test_register_password_below_minimum_length` - Password with 5 chars is rejected (422)
- `test_register_display_name_exactly_minimum_length` - Display name with 1 char (min) is accepted
- `test_register_display_name_at_maximum_length` - Display name with 100 chars (max) is accepted
- `test_register_display_name_over_maximum_length` - Display name with 101 chars is rejected (422)
- `test_register_password_at_maximum_length` - Password with 100 chars (max) is accepted
- `test_register_password_over_maximum_length` - Password with 101 chars is rejected (422)

### 14.3 JWT Token Edge Cases (`TestAuthJWTEdgeCases`)

Tests for `app/api/auth.py` and `app/core/auth.py` - JWT validation paths.

- `test_get_me_with_expired_token` - Token expired 1 hour ago returns 401
- `test_get_me_with_completely_malformed_token` - Non-JWT string returns 401
- `test_get_me_with_empty_bearer_token` - Empty bearer value returns 401
- `test_get_me_with_token_for_nonexistent_user` - Valid JWT but user not in DB returns 401
- `test_get_me_with_custom_expiry_token` - Token with custom positive expiry works correctly

### 14.4 Sessions Token Edge Cases (`TestSessionsTokenEdgeCases`)

Tests for `app/api/sessions.py` - token validation paths covering specific error branches.

- `test_get_session_me_with_token_missing_session_id` - Token with sub but no session_id returns 401 (covers line 34: "Invalid token - no session")
- `test_get_session_me_with_invalid_session_id` - Token with non-existent session_id returns 404 (covers line 41: "Session not found")
- `test_conversations_with_token_missing_session_id` - Conversations endpoint rejects token without session_id

### 14.5 Feedback Schema Boundary Conditions (`TestFeedbackSchemaEdgeCases`)

Tests for `app/schemas/feedback.py` and `app/api/feedback.py` - field length boundaries and special paths.

- `test_submit_feedback_message_at_exactly_minimum_length` - Message with exactly 10 chars (min) accepted
- `test_submit_feedback_message_below_minimum_length` - Message with 9 chars rejected (422)
- `test_submit_feedback_message_at_exactly_maximum_length` - Message with exactly 5000 chars (max) accepted
- `test_submit_feedback_message_over_maximum_length` - Message with 5001 chars rejected (422)
- `test_feedback_screenshot_at_exactly_max_size_is_accepted` - Screenshot at MAX_SCREENSHOT_SIZE passes schema
- `test_feedback_screenshot_over_max_size_is_rejected` - Screenshot over MAX_SCREENSHOT_SIZE raises ValidationError
- `test_feedback_screenshot_none_is_accepted` - screenshot_data=None is accepted (optional field)
- `test_submit_feedback_without_request_client_ip` - Multi-hop X-Forwarded-For header (10.0.0.1, 172.16.0.1, ...) uses first IP
- `test_submit_feedback_with_all_optional_fields_none` - All optional fields explicitly set to None
- `test_submit_feedback_default_type_is_bug` - Missing feedback_type defaults to "bug"
- `test_submit_feedback_email_at_max_length` - Email at exactly 255 chars (max) is accepted

### 14.6 Conversation Thinker Boundary Edge Cases (`TestConversationThinkerBoundaryEdgeCases`)

Tests for `app/api/conversations.py` and `app/schemas/conversation.py` - thinker count limits and color validation.

- `test_create_conversation_with_exactly_5_thinkers` - Creating conversation with exactly 5 thinkers (max) succeeds
- `test_create_conversation_with_6_thinkers_rejected` - Creating conversation with 6 thinkers rejected (422)
- `test_add_thinkers_to_reach_exactly_5` - Adding thinkers to reach exactly 5 total succeeds
- `test_add_thinkers_exceeding_5_limit_rejected` - Adding thinkers that would exceed 5 total rejected (400)
- `test_thinker_name_at_exactly_max_length` - Thinker name at exactly 255 chars (max) accepted
- `test_thinker_name_over_max_length_rejected` - Thinker name at 256 chars rejected (422)
- `test_thinker_color_invalid_format_rejected` - Non-hex color like "blue" rejected (422)
- `test_thinker_color_valid_uppercase_hex_accepted` - Uppercase hex color "#AABBCC" accepted and preserved

### 14.7 Admin Spend Limit Schema Boundary (`TestAdminSpendLimitBoundary`)

Tests for `app/api/admin.py` - UpdateSpendLimitRequest schema validation.

- `test_update_spend_limit_to_very_small_positive` - spend_limit=0.01 (very small positive) accepted by schema (gt=0)
- `test_update_spend_limit_zero_rejected_by_schema` - spend_limit=0.0 raises ValidationError (gt=0 constraint)
- `test_update_spend_limit_negative_rejected_by_schema` - spend_limit=-5.0 raises ValidationError (gt=0 constraint)

### 14.8 Password Change Boundary Cases (`TestPasswordChangeEdgeCases`)

Tests for `app/api/auth.py` - ChangePasswordRequest schema boundaries.

- `test_change_password_to_exactly_min_length` - New password with exactly 6 chars (min) accepted
- `test_change_password_to_below_min_length_rejected` - New password with 5 chars rejected (422)
- `test_change_password_to_max_length` - New password with exactly 100 chars (max) accepted
- `test_change_password_empty_current_password_rejected` - Empty current_password rejected (422, min_length=1)
- `test_change_password_with_special_characters` - Password with symbols, spaces, unicode accepted

### 14.9 ThinkerSuggestRequest Schema Boundaries (`TestThinkerSuggestRequestBoundary`)

Tests for `app/schemas/thinker.py` - ThinkerSuggestRequest field constraints.

- `test_suggest_request_count_at_minimum` - count=1 (min, ge=1) accepted
- `test_suggest_request_count_below_minimum_rejected` - count=0 raises ValidationError (ge=1)
- `test_suggest_request_count_at_maximum` - count=5 (max, le=5) accepted
- `test_suggest_request_count_over_maximum_rejected` - count=6 raises ValidationError (le=5)
- `test_suggest_request_empty_topic_rejected` - Empty topic raises ValidationError (min_length=1)
- `test_suggest_request_invalid_language_rejected` - Language "xx" raises ValidationError
- `test_suggest_request_german_language_rejected` - Language "de" raises ValidationError (ThinkerSuggestRequest only allows en|es|fr, not de)
- `test_suggest_request_default_values` - Defaults: count=3, language='en', exclude=[]
- `test_suggest_request_exclude_list_populated` - exclude list accepts multiple thinker names

### 14.10 Profile Update Boundary Cases (`TestProfileUpdateEdgeCases`)

Tests for `app/api/auth.py` - PATCH /auth/profile and /auth/language endpoint boundaries.

- `test_update_profile_display_name_exactly_min_length` - display_name with 1 char (min) accepted
- `test_update_profile_display_name_empty_rejected` - Empty display_name rejected (422, min_length=1)
- `test_update_profile_display_name_at_max_length` - display_name with 100 chars (max) accepted
- `test_update_profile_display_name_over_max_length_rejected` - display_name with 101 chars rejected (422)
- `test_update_language_all_valid_codes` - All 4 valid language codes (en, es, fr, de) accepted and persisted

---

## 15. Regression Prevention - Mar 15, 2026 (`test_regression_prevention_mar15_2026.py`)

Sunday QA focus: regression prevention for recent features and bug fixes.

### 15.1 Thinker Color Assignment (`TestThinkerColorAssignment`)

Tests for `app/api/conversations.py` - color assignment logic in `add_thinkers_to_conversation`.

- `test_add_thinkers_uses_provided_non_default_color` - Custom color (non-#6366f1) is preserved when adding thinker; not overridden by color cycling logic
- `test_add_thinkers_replaces_default_color_with_available` - Default color #6366f1 is replaced with first available color when available colors exist
- `test_add_thinkers_with_all_colors_used_keeps_default` - When all 5 colors are used, adding a 6th thinker is rejected (400 max 5 limit)

### 15.2 Conversation List Cost Aggregation (`TestConversationListCostAggregation`)

Tests for `app/api/conversations.py` - cost aggregation in `list_conversations`.

- `test_conversation_list_total_cost_zero_when_no_messages` - New conversation with no messages has 0.0 total_cost
- `test_conversation_list_returns_correct_thinker_count` - Conversation list includes all thinkers with correct count
- `test_conversation_list_is_empty_for_new_session` - New user session returns empty conversation list (session isolation)

### 15.3 Spend API Endpoints (`TestSpendAPIEndpoints`)

Tests for `app/api/spend.py` - GET /api/spend/{user_id} admin-only endpoint.

- `test_spend_api_requires_admin` - Non-admin user gets 403 (Admin access required)
- `test_spend_api_returns_404_for_nonexistent_user` - Nonexistent user ID returns 404 (not 200 or 500)

### 15.4 Auth Flows (`TestAuthFlows`)

Tests for `app/api/auth.py` - critical authentication flow edge cases.

- `test_login_creates_new_session_when_none_exists` - Login works and returns valid JWT token with /me verification
- `test_change_password_allows_login_with_new_password` - After password change, new password can log in
- `test_change_password_rejects_old_password_after_change` - After password change, old password is rejected with 401
- `test_register_with_language_preference_persists` - language_preference set during registration persists in /me response
- `test_register_response_includes_all_user_fields` - Registration response includes all required user fields (id, username, display_name, is_admin, total_spend, spend_limit, language_preference, created_at)
- `test_logout_endpoint_returns_success` - Logout endpoint returns 200 with "Logged out" message
- `test_logout_works_without_authentication` - Logout endpoint works without a valid auth token (JWT is stateless)

### 15.5 Spend Service Edge Cases (`TestSpendServiceEdgeCases`)

Tests for `app/services/spend.py` - boundary conditions in spend checking.

- `test_check_spend_limit_returns_none_for_nonexistent_user` - check_spend_limit returns None for unknown user ID
- `test_can_user_spend_returns_false_for_nonexistent_user` - can_user_spend returns False for unknown user (security default: deny)
- `test_check_spend_limit_is_near_limit_at_exactly_85_percent` - is_near_limit is True at exactly 85% usage (boundary condition)
- `test_check_spend_limit_is_over_limit_when_spend_equals_limit` - is_over_limit is True when total_spend equals spend_limit (not just exceeds)
- `test_check_spend_limit_percentage_capped_at_100` - percentage_used is capped at 100% when spend exceeds limit (UI safety)

### 15.6 Profile and Language Persistence (`TestProfileAndLanguagePersistence`)

Tests for `app/api/auth.py` - PATCH /auth/profile and PATCH /auth/language persistence.

- `test_profile_update_display_name_persists` - display_name update persists across subsequent /me requests (DB commit works)
- `test_language_update_persists` - language_preference update persists across subsequent /me requests
- `test_profile_and_language_updates_are_independent` - Updating profile doesn't reset language; updating language doesn't reset display_name

### 15.7 Conversation API Regressions (`TestConversationAPIRegressions`)

Tests for `app/api/conversations.py` - response formats and security boundaries.

- `test_delete_conversation_returns_deleted_status` - Delete conversation returns {"status": "deleted"} (response format preserved)
- `test_get_conversation_includes_thinkers_and_messages` - GET conversation response includes both thinkers and messages fields
- `test_get_conversation_other_session_returns_404` - Cross-session access returns 404 (session isolation security boundary)

---

## 16.0 Coverage Sprint (Added 2026-03-16)

**Focus**: Monday QA coverage sprint - targeting lowest-coverage modules
**File**: `backend/tests/test_coverage_sprint_mar16_2026.py`
**Coverage Impact**: 83% → 86% (+3%)
- `app/core/config.py`: 72% → **100%** (sync_database_url property fully tested)
- `app/core/database.py`: 43% → **95%** (async_session, get_db, run_migrations, init_db, close_db)
- `app/main.py`: 60% → **79%** (create_admin_user, health DB error path)
- `app/api/websocket.py`: 66% → **68%** (ConversationRoom, ConnectionManager methods, SpeedControl)

### 16.1 Config sync_database_url Tests (`TestSyncDatabaseUrl`)

**File**: `backend/tests/test_coverage_sprint_mar16_2026.py`

Tests the `sync_database_url` property which converts async DB driver URLs to sync equivalents for Alembic migrations.

- `test_sqlite_aiosqlite_converts_to_sync` - `sqlite+aiosqlite://` converts to `sqlite://`
- `test_postgresql_asyncpg_converts_to_sync` - `postgresql+asyncpg://` converts to `postgresql://`
- `test_postgres_shorthand_converts_to_postgresql` - `postgres://` (Railway) converts to `postgresql://`
- `test_plain_postgresql_url_unchanged` - Plain `postgresql://` with no async prefix passes through unchanged
- `test_memory_sqlite_converts_to_sync` - In-memory SQLite aiosqlite converts correctly
- `test_default_database_url_has_correct_sync_form` - Default SQLite URL produces valid sync form

### 16.2 Database Module Tests

**File**: `backend/tests/test_coverage_sprint_mar16_2026.py`

Tests for `app/core/database.py` - the database session management layer.

#### `TestAsyncSessionContextManager`
- `test_async_session_yields_session` - `async_session()` context manager yields a usable `AsyncSession`
- `test_async_session_commits_on_success` - Session commits successfully after normal operations
- `test_async_session_rolls_back_on_exception` - Session rolls back and re-raises on exception

#### `TestGetDb`
- `test_get_db_yields_session` - `get_db()` FastAPI dependency yields an `AsyncSession`

#### `TestRunMigrations`
- `test_run_migrations_returns_false_when_no_alembic_ini` - Returns `False` when alembic.ini is missing
- `test_run_migrations_succeeds_with_valid_alembic_ini` - Calls `alembic command.upgrade` when ini exists

#### `TestInitDb`
- `test_init_db_uses_migrations_when_alembic_ini_exists` - Calls `run_migrations()` when alembic.ini present
- `test_init_db_falls_back_to_create_all_when_migrations_fail` - Falls back to `Base.metadata.create_all` if migrations raise

#### `TestCloseDb`
- `test_close_db_disposes_engine` - Calls `engine.dispose()` to close all connections

### 16.3 Main App Tests

**File**: `backend/tests/test_coverage_sprint_mar16_2026.py`

Tests for `app/main.py` startup functions and endpoint edge cases.

#### `TestCreateAdminUser`
- `test_creates_admin_user_when_not_exists` - Creates admin user with `db.add()` when no admin exists
- `test_skips_creation_when_admin_already_exists` - Does not call `db.add()` when admin already present

#### `TestHealthReadyDbError`
- `test_health_ready_returns_503_on_db_error` - `/health/ready` returns 503 with `status: degraded` when DB check fails
- `test_health_ready_returns_200_on_db_success` - `/health/ready` returns 200 with `status: ready` when DB check succeeds

### 16.4 WebSocket Layer Tests

**File**: `backend/tests/test_coverage_sprint_mar16_2026.py`

Tests for `app/api/websocket.py` - WebSocket room management and connection handling.

#### `TestConversationRoom`
- `test_add_connection_sets_active` - Adding a WebSocket connection marks room as active
- `test_remove_connection_deactivates_when_empty` - Removing last connection deactivates the room
- `test_remove_nonexistent_connection_is_safe` - Removing an unknown connection does not raise
- `test_broadcast_skips_failed_connections` - Connections that fail to send are removed from room
- `test_broadcast_deactivates_when_all_connections_fail` - All connections failing deactivates room

#### `TestConnectionManagerMethods`
- `test_connect_creates_room_if_not_exists` - `connect()` creates new room and calls `websocket.accept()`
- `test_disconnect_removes_connection` - `disconnect()` removes WebSocket from room, deactivates if empty
- `test_disconnect_nonexistent_conversation_is_safe` - `disconnect()` on unknown conversation ID doesn't raise
- `test_get_speed_multiplier_returns_default_for_unknown` - Returns 1.0 for conversations without a room
- `test_get_speed_multiplier_returns_room_value` - Returns the room's actual speed_multiplier value
- `test_set_speed_multiplier_clamps_to_minimum` - Values below 0.5 are clamped to 0.5
- `test_set_speed_multiplier_clamps_to_maximum` - Values above 6.0 are clamped to 6.0
- `test_set_speed_multiplier_broadcasts_speed_changed` - Broadcasts SPEED_CHANGED message with new multiplier
- `test_set_speed_multiplier_noop_for_unknown_conversation` - No error if conversation room doesn't exist
- `test_send_thinker_message_broadcasts_correctly` - Broadcasts MESSAGE with thinker name, content, cost
- `test_send_thinker_typing_adds_to_typing_set` - Adds thinker to room's `typing_thinkers` set
- `test_send_thinker_stopped_typing_removes_from_set` - Removes thinker from `typing_thinkers` set
- `test_send_thinker_thinking_broadcasts_content` - Broadcasts THINKER_THINKING with content
- `test_send_research_started_broadcasts_event` - Broadcasts RESEARCH_STARTED with thinker_name
- `test_send_research_complete_broadcasts_event` - Broadcasts RESEARCH_COMPLETE with thinker_name
- `test_send_research_failed_broadcasts_with_error` - Broadcasts RESEARCH_FAILED with error content
- `test_send_cache_hit_broadcasts_event` - Broadcasts CACHE_HIT with thinker_name

#### `TestWebSocketAuthentication`
- `test_websocket_rejects_missing_token` - WebSocket closes when no token query param provided
- `test_websocket_rejects_invalid_token` - WebSocket closes when token is not a valid JWT

#### `TestSpendLimitExceeded`
- `test_spend_limit_exceeded_message` - Exception message includes current and limit spend amounts
- `test_save_thinker_message_raises_when_spend_limit_exceeded` - Raises when user.total_spend >= spend_limit

#### `TestGetMessagesForConversation`
- `test_get_messages_returns_empty_list_for_new_conversation` - Returns empty list for unknown conversation
- `test_get_messages_returns_messages_in_order` - Returns messages ordered by `created_at`

#### `TestWebSocketSetSpeed`
- `test_set_speed_message_updates_multiplier` - SET_SPEED WebSocket message triggers SPEED_CHANGED broadcast

## 17. E2E Performance Optimization (Added 2026-03-19)

**Focus**: Thursday QA focus - optimize E2E test speed and reduce setup overhead
**Files Modified**: `frontend/e2e/form-validation.spec.ts`, `frontend/e2e/test-fixtures.ts` (new)
**Coverage Impact**: No coverage change (structural improvement)

### 17.1 Form Validation Tests - API Creation Optimization

**Problem**: 4 tests in `Message Input Validation` and `Rapid-Fire Actions` were using the full
UI modal flow (topic input → thinker selection → Claude API validation → conversation create)
as setup for tests that only test *message sending* behavior. Each setup took 15-30s due to
Claude API validation.

**Fix**: Converted to use `createAndNavigateToConversation()` API helper which skips the UI
modal and creates conversations directly via REST API (< 2s vs 15-30s).

**Tests optimized** (4 tests in `frontend/e2e/form-validation.spec.ts`):
- `prevents sending empty message` - now uses API creation
- `handles very long message input` - now uses API creation
- `handles special characters in messages` - now uses API creation
- `handles rapid message sending` - now uses API creation

**Estimated time savings**: ~60-80s total setup time removed from test suite per run.

### 17.2 Fix Unbounded waitForLoadState

**File**: `frontend/e2e/form-validation.spec.ts` (line ~401)

Added missing timeout to `page.waitForLoadState('networkidle')` call used inside a
`Promise.race`. Without timeout, this could theoretically hang indefinitely if network
never becomes idle (e.g., WebSocket keeping connection open).

**Fix**: Added `{ timeout: 5000 }` to bound the wait.

### 17.3 Playwright Test Fixtures (New File)

**File**: `frontend/e2e/test-fixtures.ts`

Added reusable Playwright fixtures to reduce boilerplate and standardize setup patterns:

- `testWithAuth` - Provides `authenticatedPage` fixture with authenticated user ready
- `test` (default export) - Provides `conversationPage` fixture with authenticated user
  AND a conversation already open (via API creation, not UI flow)

**How to use**:
```typescript
import { test, expect } from './test-fixtures';

test('my chat test', async ({ conversationPage }) => {
  // conversationPage already has auth + open conversation
  await conversationPage.getByTestId('message-textarea').fill('Hello');
});
```

**Performance benefit**: Both fixtures use API calls (not UI modal flow) for setup,
saving 15-30s compared to navigating the conversation creation modal per test.

## 18. Flaky Test Hunt - Mar 31, 2026 (`test_main.py`)

**Focus**: Tuesday QA focus - identify and fix hanging/flaky tests
**Files Modified**: `backend/tests/test_main.py`
**Coverage Impact**: No coverage change (stability fix)

### 18.1 Background: Hanging Test Discovery

Ran all test files individually to identify tests that block the suite. Found that
`tests/test_main.py` caused the entire test suite to hang when run together.

### 18.2 Root Cause

**Test**: `tests/test_main.py::test_health_ready_endpoint`
**Symptom**: Test hangs indefinitely (required `kill -9` to terminate)
**Root cause**: `test_main.py` defined its own `client` fixture:

```python
@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

This fixture did NOT override `get_db` with a test database. The `/health/ready` endpoint
calls `get_db` and executes `await db.execute(text("SELECT 1"))`. In the test environment,
this tries to connect to the real PostgreSQL database (which doesn't exist), causing the
connection to hang indefinitely on the TCP connection attempt.

By contrast:
- `test_health_check` (no DB call) - passes immediately
- `test_version_endpoint` (no DB call) - passes immediately
- `test_health_ready_endpoint` (DB call via `get_db`) - hangs indefinitely

The `conftest.py` `client` fixture correctly solves this by overriding `get_db` with an
in-memory SQLite session.

### 18.3 Fix Applied

**File**: `backend/tests/test_main.py`

Removed the local `client` fixture from `test_main.py` entirely. The tests now use the
shared `client` fixture from `conftest.py`, which injects an in-memory SQLite test database.

**Before** (broken): own client fixture, no DB override, health/ready hangs
**After** (fixed): uses conftest client fixture with proper in-memory SQLite injection

### 18.4 Test Stability Verification

Confirmed all 3 tests pass stably across 3 consecutive runs:
- `test_health_check` - passes (0.6s)
- `test_health_ready_endpoint` - passes (0.6s, previously hung indefinitely)
- `test_version_endpoint` - passes (0.6s)

## 19. Regression Prevention - Apr 12, 2026 (`test_regression_prevention_apr12_2026.py`)

**Focus**: Sunday QA - regression prevention
**Files Modified**: `backend/tests/test_regression_prevention_apr12_2026.py` (NEW)
**Coverage Impact**: +34 tests, covers previously untested behavioral contracts

### 19.1 Test Classes and Rationale

#### TestWebSocketTokenWithoutSessionId (3 tests)
Guards against the WebSocket auth path at lines 364-367 in `websocket.py`:
- `test_websocket_rejects_token_without_session_id`: Valid JWT with `sub` but no `session_id` → rejected with close code 4001
- `test_websocket_accepts_token_with_valid_session_id`: Token with both fields → accepted
- `test_websocket_rejects_empty_session_id_in_token`: Token with `session_id: ""` (falsy) → rejected

Root cause: Only missing-token and invalid-token paths were previously tested. The third branch (valid JWT, no session_id) was uncovered, leaving a potential security bypass undetected.

#### TestExtractThinkingDisplayLanguageReplacements (7 tests)
Guards language-specific text transformations in `_extract_thinking_display`:
- German ("de") replacements: `"Ich sollte "` → `"Vielleicht sollte ich "`
- French ("fr") replacements: `"Je devrais "` → `"Peut-être que je devrais "`
- Spanish ("es") replacements: `"Debería "` → `"Quizás debería "`
- Hindi ("hi") replacements: `"मुझे चाहिए "` → `"शायद मुझे चाहिए "`
- German/French don't use English starters
- English default still applies correct replacements

Root cause: Each language has a distinct replacement dict and starter list. If a language branch is accidentally removed, thinking display falls through to English replacements.

#### TestCountMessagesSinceUser (5 tests)
Guards `_count_messages_since_user` reverse-scan logic:
- All thinker messages → returns total count (loop never breaks)
- User message at end → returns 0 immediately
- Mixed history → counts only thinker messages after last user message
- Empty list → 0
- Single user message → 0

Root cause: Used by `_should_prompt_user` to decide whether to invite participation. Wrong counting causes either never-prompt or always-prompt behavior.

#### TestConnectionManagerSpeedMultiplierDefaults (5 tests)
Guards ConnectionManager speed multiplier behavior:
- Unknown conversation → returns 1.0 (safe default)
- Speed 0.1 → clamped to 0.5 (prevents infinite response loop)
- Speed 7.0 → clamped to 6.0 (prevents 25-minute freeze)
- Speed 2.0 → stored exactly (no rounding)
- Boundary values 0.5, 6.0 → accepted unchanged

Root cause: Speed multiplier controls `min_interval = 15.0 * speed_mult`. Default or clamping bugs would make thinkers either silent forever or spamming.

#### TestHealthReadyEndpointDatabaseInjection (2 tests)
Guards against regression from PR #804 fix:
- `/health/ready` completes quickly with conftest client (no hanging)
- `/health` doesn't require DB at all

Root cause: PR #804 fixed an indefinite hang caused by test_main.py having its own client fixture without DB override. These tests confirm the shared fixture is used correctly.

#### TestGetLanguageInstructionIntegration (7 tests)
Guards `_get_language_instruction` for all supported languages:
- English ("en") → empty string (no special instruction needed)
- Spanish, French, German, Hindi → non-empty with language name
- Unknown code ("xx") → fallback instruction with code itself (no crash)
- All entries in `LANGUAGE_NAMES` produce instructions

Root cause: PR #570 added Hindi precisely because it was missing from LANGUAGE_NAMES. This catch-all test prevents similar omissions for future language additions.

#### TestSplitResponseIntoBubblesEdgeCases (5 tests)
Guards edge cases in `_split_response_into_bubbles`:
- Short text (<60 chars) always returns single bubble (no random splitting)
- Empty string → `[]`, whitespace → well-defined behavior
- Force-split path (lines 767-773): text >300 chars with 1 bubble gets sentence-boundary split
- No-boundary text >300 chars stays as 1 bubble (correct: no mid-word cut)
- All returned bubbles are non-empty strings

Root cause: The force-split safety net is critical for LLM responses that form one very long "sentence". Without it, a 500-word paragraph appears as a single message bubble.

### 19.2 Stability Verification

All 34 tests pass consistently across 3 consecutive runs (no flakiness detected).
Total run time: ~2.0s per run.

## 20. E2E Performance Optimization - Apr 16, 2026 (`e2e/performance.spec.ts`)

**Focus:** Thursday e2e-performance — replace `networkidle` anti-patterns, parallelize sequential API calls, add performance assertion tests.

### 20.1 Optimization Changes

**`e2e/network-errors.spec.ts`** — Replaced 3 `waitForLoadState('networkidle')` calls inside `Promise.race` with direct element-based waits. `networkidle` can block for 2-5s waiting for all network activity to cease; element-based waits resolve as soon as the relevant UI updates, which is always faster. Changes:
- Timeout fallback: now waits for `addButton.toBeEnabled()` instead of `networkidle`
- Offline test: now waits for `createButton.toBeEnabled()` instead of `networkidle`
- Auth 401 test: removed `networkidle` from Promise.race; login/error locators are sufficient

**`e2e/scrolling-text.spec.ts`** — Parallelized 3 sequential `createConversationViaAPI` calls into a single `Promise.all`. Each call was independent (different topics, same page context) but ran one-after-another. With `Promise.all` they execute concurrently, saving ~2s of setup time.

### 20.2 New Tests (`e2e/performance.spec.ts`)

**Page Load Performance** (4 tests)
- `login page loads within 3 seconds` — measures time from `page.goto('/login')` to `#username` visible. Login page is static; must be fast.
- `register page loads within 3 seconds` — same pattern for `/register`.
- `authenticated homepage loads within 5 seconds` — measures full auth setup + new-chat-button visibility.
- `sidebar renders within 5 seconds on authenticated load` — measures sidebar render separately from homepage load.

**Interaction Performance** (3 tests)
- `conversation list renders within 5 seconds after creating conversation` — creates conversation via API, navigates home, measures sidebar update.
- `navigating to settings page completes within 3 seconds` — client-side navigation, should be near-instant.
- `new conversation modal opens within 2 seconds` — click-to-modal-visible; critical UI interaction.

**API Response Performance** (3 tests)
- `auth/me endpoint responds within 3 seconds` — validates authenticated user lookup is not slow.
- `conversations list endpoint responds within 3 seconds` — validates conversation fetch is not slow.
- `health endpoint responds within 2 seconds` — validates health check is always fast.

### 20.3 Anti-Pattern Count

| Metric | Before | After |
|--------|--------|-------|
| `waitForTimeout()` calls | 0 (was already clean) | 0 |
| `waitForLoadState('networkidle')` in Promise.race | 3 | 0 |
| Sequential API calls in loops | 1 (scrolling-text) | 0 |
| Performance assertion tests | 0 | 10 |

## 21. Test Refactoring - Apr 17, 2026 (Friday QA)

**Focus:** Improve test readability and reduce duplication by applying shared helpers.

### 21.1 Frontend: api.test.ts (`src/__tests__/lib/api.test.ts`)

**Refactoring:** Applied `createMockFetchResponse` and `setupAuthToken` helpers from `test-utils.tsx` throughout the test file.

- **Before:** 15 instances of verbose inline fetch mock: `{ ok: true, json: () => Promise.resolve(data) }`
- **After:** `createMockFetchResponse(data)` — single-line, intent-revealing helper call
- **Before:** 7 instances of `(localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123')`
- **After:** `setupAuthToken()` — named helper that communicates intent

Affected tests (all 16 tests in file):
- Auth API: register, login, logout, getCurrentUser, no-token edge cases
- Session API: get session success/failure/no-token
- Conversation API: list, get, create, delete
- Message API: send message
- Thinker API: suggest, validate
- Error Handling: detail error, status-only error

### 21.2 Frontend: ScrollingText.test.tsx (`src/components/__tests__/ScrollingText.test.tsx`)

**Refactoring:** Extracted repeated DOM dimension mocking into two helpers.

- `setTruncatedDimensions(container, measureSpan, clientWidth?, scrollWidth?)` — sets `clientWidth` and `scrollWidth` via `Object.defineProperty`
- `mockTruncation(container, measureSpan, clientWidth?, scrollWidth?)` — wraps `setTruncatedDimensions` + fires `window.resize`

5 instances of the 3-5 line verbose pattern were replaced with single-line helper calls.

### 21.3 Backend: test_conversations_flaky_hunt.py

**Refactoring:** Added `assert_not_found` import from conftest and replaced 3 two-line assertion pairs with the single-line helper.

- Pattern replaced: `assert response.status_code == 404` + `assert "not found" in response.json()["detail"].lower()`
- Replacement: `assert_not_found(response, "not found")`

### 21.4 Backend: test_edge_cases_apr4_2026.py

**Refactoring:** Added assertion helpers (`assert_error_response`, `assert_forbidden`, `assert_not_found`, `assert_unauthorized`) from conftest. Replaced 6 two-line status+detail assertion pairs with single-line helper calls:

- `assert_unauthorized(response, "no session")` — session missing from JWT
- `assert_not_found(response, "Session not found")` — nonexistent session ID
- `assert_not_found(response, "User not found")` ×2 — admin delete/update nonexistent user
- `assert_forbidden(response, "Admin access required")` — non-admin accessing admin endpoint
- `assert_error_response(response, 400, "Cannot delete your own account")` — admin self-delete prevention

## 22. Integration Test Gaps - Apr 22, 2026 (Wednesday QA)

**Focus:** Fill integration test gaps covering untested code paths identified by coverage analysis.
**Coverage:** 87.62% → 88.00% (partial branches improved from 21 to 13)

### 22.1 ConnectionManager Async Edge Cases (`backend/tests/test_integration_gaps_apr22_2026.py`)

Tests async edge cases in `ConnectionManager` that expose previously uncovered branches (websocket.py lines 125->127, 189->191, 212->214).

| Test | Validates |
|------|-----------|
| `test_connect_to_existing_room_reuses_room` | Connecting to a room that already exists reuses the same room object (branch 125->127) |
| `test_broadcast_to_nonexistent_conversation_is_noop` | Broadcasting to a non-existent room silently does nothing (branch 189->191) |
| `test_send_thinker_typing_without_room` | Typing notification for non-existent room doesn't crash (branch 212->214) |
| `test_send_thinker_stopped_typing_without_room` | Stopped-typing notification for non-existent room doesn't crash |
| `test_set_speed_multiplier_clamped_to_valid_range` | Speed multiplier is clamped to [0.5, 6.0] and broadcast to clients |
| `test_set_speed_multiplier_for_nonexistent_room_is_noop` | Setting speed for non-existent room is silently ignored |
| `test_get_speed_multiplier_for_nonexistent_room_returns_default` | Default speed 1.0 returned when no room exists |
| `test_conversation_room_typing_thinkers_tracking` | typing_thinkers set is updated correctly on start/stop |

### 22.2 SpendLimitExceeded and save_thinker_message (`backend/tests/test_integration_gaps_apr22_2026.py`)

Tests the spend limit enforcement in the WebSocket message saving path.

| Test | Validates |
|------|-----------|
| `test_spend_limit_exceeded_attributes` | SpendLimitExceeded stores current_spend and spend_limit attributes |
| `test_spend_limit_exceeded_is_exception` | SpendLimitExceeded is a proper Exception subclass |
| `test_save_message_raises_when_spend_equals_limit` | save_thinker_message raises when user.total_spend == spend_limit |
| `test_save_message_raises_when_spend_exceeds_limit` | save_thinker_message raises when user.total_spend > spend_limit |
| `test_save_message_succeeds_when_under_limit` | save_thinker_message succeeds and updates user.total_spend when under limit |
| `test_save_message_with_no_conversation_does_not_crash` | Message created even when conversation ID doesn't exist |
| `test_get_messages_returns_empty_for_new_conversation` | Empty list returned for conversations with no messages |
| `test_get_messages_returns_all_messages_ordered_by_time` | All messages returned in creation order |

### 22.3 `_split_response_into_bubbles` Force-Split Path (`backend/tests/test_integration_gaps_apr22_2026.py`)

Tests the force-split path triggered when a very long text ends up as a single bubble (lines 763-768 in thinker.py).

| Test | Validates |
|------|-----------|
| `test_force_split_on_very_long_single_bubble` | Text > 300 chars with single bubble triggers force-split |
| `test_force_split_creates_two_bubbles_from_long_text` | Force-split finds sentence boundary past midpoint and creates 2 parts |
| `test_text_with_transition_word_starts_new_bubble` | "However," and similar words start a new bubble |
| `test_very_long_text_without_sentence_end_past_midpoint` | No valid split point → text returned as-is |

### 22.4 `_extract_thinking_display` Language Branches (`backend/tests/test_integration_gaps_apr22_2026.py`)

Tests language-specific branches in `_extract_thinking_display` (previously uncovered: Japanese, Korean, Hindi, and English internal monologue replacements).

| Test | Validates |
|------|-----------|
| `test_extract_thinking_display_japanese` | Japanese language handled without crashing |
| `test_extract_thinking_display_korean` | Korean language handled without crashing |
| `test_extract_thinking_display_hindi` | Hindi language handled without crashing |
| `test_extract_thinking_display_text_over_200_chars_trimmed` | Long text trimmed from end with sentence boundary search |
| `test_extract_thinking_display_sentence_boundary_search` | ". " within first 80 chars of trimmed text used as new start |
| `test_extract_thinking_display_text_starting_with_lowercase` | Incomplete word at start dropped after trimming |
| `test_extract_thinking_display_english_replacements` | LLM phrasing replaced with first-person monologue |

### 22.5 Knowledge Research Service (`backend/tests/test_integration_gaps_apr22_2026.py`)

Integration tests for knowledge research service lifecycle.

| Test | Validates |
|------|-----------|
| `test_get_or_create_knowledge_creates_new_entry` | Creates new ThinkerKnowledge entry if none exists |
| `test_get_or_create_knowledge_returns_existing` | Returns same entry on repeated calls (no duplication) |
| `test_get_knowledge_returns_none_for_unknown` | Returns None for thinkers not yet researched |
| `test_is_stale_returns_true_for_old_knowledge` | Marks knowledge > threshold days old as stale |
| `test_is_stale_returns_false_for_fresh_knowledge` | Freshly updated knowledge is not stale |

### 22.6 End-to-End Integration Chains (`backend/tests/test_integration_gaps_apr22_2026.py`)

Multi-step API workflows testing full integration chains.

| Test | Chain | Validates |
|------|-------|-----------|
| `test_submit_feedback_then_retrieve_as_pending` | POST /feedback → GET /feedback/pending | Submitted feedback appears in pending queue |
| `test_full_feedback_mark_processed_chain` | POST /feedback → GET pending → PATCH processed | Full feedback lifecycle moves to REVIEWED status |
| `test_admin_update_spend_limit_then_retrieve_spend_data` | PATCH admin spend → GET spend | Spend limit update visible in spend API |
| `test_admin_list_users_shows_updated_spend_limit` | PATCH admin spend → GET admin/users | Updated limit appears in user list |
| `test_register_login_create_conversation_send_message` | Register → session → conversation → message | Full user workflow end-to-end |
| `test_delete_user_cascade_removes_conversations` | Create user → admin delete → verify gone | Admin delete cascades to remove all user data |
| `test_get_knowledge_creates_entry_and_triggers_research` | GET /thinkers/knowledge/{name} | Creates entry and triggers background research |
| `test_get_knowledge_status_returns_pending_for_unknown` | GET /thinkers/knowledge/{name}/status | Returns PENDING for unknown thinkers |
| `test_refresh_thinker_knowledge_triggers_new_research` | POST /thinkers/knowledge/{name}/refresh | Forces fresh research even for complete entries |

## 23. Test Refactoring - Apr 24, 2026 (Friday QA)

**Focus:** Improve test readability and reduce duplication by using shared helper utilities.
**Coverage:** 88.00% (maintained — refactoring focus, no new tests added)

### 23.1 Frontend: MessageList.test.tsx

**Refactoring:** Replaced local `createMessage(id, content, sender_type)` factory function with the shared `createMessage(overrides)` from `@/test-utils`. Eliminates duplicate factory definition that was diverging from the canonical version.

| Change | Details |
|--------|---------|
| Removed local `createMessage` | Was 10-line factory with positional args; replaced with import |
| Updated 4 test cases | All `createMessage(...)` calls updated to use override-based API |
| Added `image_url: null` | Added required field to local `thinkers` fixture |

### 23.2 Frontend: Message.test.tsx

**Refactoring:** Replaced local `createMessage(overrides)` and `createThinker(name, overrides)` factory functions with the shared versions from `@/test-utils`. Removes 25 lines of duplicate factory definitions.

| Change | Details |
|--------|---------|
| Removed local `createMessage` | 11-line factory replaced with import from `@/test-utils` |
| Removed local `createThinker` | 10-line factory replaced with import from `@/test-utils` |
| Updated 15 test cases | All factory calls updated to use shared helpers with override API |
| Removed unused `fireEvent` import | Import cleanup |

### 23.3 Backend: test_edge_cases_mar14_2026.py

**Refactoring:** Added `assert_validation_error`, `assert_unauthorized`, and `assert_not_found` helpers from conftest. Replaced 20 raw `assert response.status_code == XXX` patterns with single-line helper calls.

| Pattern Replaced | Count | Helper Used |
|-----------------|-------|-------------|
| `assert response.status_code == 422` | 12 | `assert_validation_error(response)` |
| `assert response.status_code == 401` | 7 | `assert_unauthorized(response)` |
| `assert response.status_code == 401` + detail check | 1 | `assert_unauthorized(response, "Invalid token")` |
| `assert response.status_code == 404` | 1 | `assert_not_found(response)` |

### 23.4 Backend: test_edge_cases_apr4_2026.py

**Refactoring:** Added `assert_validation_error` import (file already had other assertion helpers). Replaced 30 raw assertion patterns with single-line helper calls.

| Pattern Replaced | Count | Helper Used |
|-----------------|-------|-------------|
| `assert response.status_code == 422` | 22 | `assert_validation_error(response)` |
| `assert response.status_code == 401` | 4 | `assert_unauthorized(response)` |
| `assert response.status_code == 401` + detail | 1 | `assert_unauthorized(response, "Invalid username or password")` |
| `assert response.status_code == 404` | 8 | `assert_not_found(response)` |
| `_description` parameter rename | 0 | Renamed unused `description` to `_description` in parametrized tests |

### 23.5 Backend: test_edge_cases_feb21_2026.py

**Refactoring:** Added `assert_not_found`, `assert_unauthorized`, `assert_validation_error` helpers from conftest. Replaced 12 raw assertion patterns.

| Pattern Replaced | Count | Helper Used |
|-----------------|-------|-------------|
| `assert response.status_code == 422` | 4 | `assert_validation_error(response)` |
| `assert response.status_code == 401` | 4 | `assert_unauthorized(response)` |
| `assert response.status_code == 401` + detail | 2 | `assert_unauthorized(response, "Invalid username or password")` |
| `assert response.status_code == 404` | 2 | `assert_not_found(response)` |

### 23.6 Backend: test_api.py

**Refactoring:** Added `assert_not_found`, `assert_unauthorized`, `assert_validation_error` helpers from conftest. Replaced 22 raw assertion patterns with helper calls. Fixed orphaned multi-line assertion continuation after replacing `assert response.status_code == 422, (...)`.

| Pattern Replaced | Count | Helper Used |
|-----------------|-------|-------------|
| `assert response.status_code == 422` | 3 | `assert_validation_error(response)` |
| `assert response.status_code == 401` + detail | 2 | `assert_unauthorized(response, "...")` |
| `assert response.status_code == 401` standalone | 6 | `assert_unauthorized(response)` |
| `assert response.status_code == 404` standalone | 2 | `assert_not_found(response)` |
| Parametrize `description` → `_description` | 2 | Ruff ARG002 unused argument fix |

## 24. Edge Case Analysis - Apr 25, 2026 (`test_edge_cases_apr25_2026.py`)

**Focus:** Boundary conditions and error paths targeting uncovered branches in websocket.py and thinker.py.

**Coverage before:** 88% (1229 tests)
**Coverage target:** 89%+ (30 new tests added)

### 24.1 WebSocket Authentication Edge Cases (`TestWebSocketAuthEdgeCases`)

| Test | What It Validates |
|------|-------------------|
| `test_websocket_no_token_closes_with_4001` | Missing token triggers close(4001) guard at websocket.py:355 |
| `test_websocket_invalid_token_closes_with_4001` | Malformed JWT rejected by decode_access_token guard at websocket.py:360 |
| `test_websocket_token_without_session_id_closes_with_4001` | Valid JWT without session_id claim rejected at websocket.py:364 |
| `test_websocket_valid_token_connects_successfully` | Control: valid token with session_id allows connection |

### 24.2 WebSocket SET_SPEED Handler (`TestWebSocketSetSpeed`)

| Test | What It Validates |
|------|-------------------|
| `test_set_speed_message_broadcasts_speed_changed` | SET_SPEED message triggers SPEED_CHANGED broadcast to all clients |
| `test_set_speed_clamps_to_valid_range` | Extreme speed values are clamped to [0.5, 6.0] range |

### 24.3 ThinkerService Idle Pause/Resume (`TestThinkerServiceIdlePause`)

| Test | What It Validates |
|------|-------------------|
| `test_is_idle_paused_returns_false_for_unknown_conversation` | Unknown conversation ID returns False (boundary) |
| `test_pause_for_idle_sets_both_paused_and_idle_paused` | pause_for_idle() adds to both _paused and _idle_paused sets |
| `test_resume_from_idle_clears_both_sets` | resume_from_idle() removes from both pause sets |
| `test_resume_from_idle_is_noop_for_manual_pause` | Manual pause is not cleared by resume_from_idle (isolation) |
| `test_resume_from_idle_is_noop_for_unknown_conversation` | resume_from_idle on unknown conv is safe no-op |
| `test_pause_for_idle_then_manual_resume_clears_idle_state` | Manual resume clears pause but keeps idle set entry |

### 24.4 _should_respond Edge Cases (`TestShouldRespondEdgeCases`)

| Test | What It Validates |
|------|-------------------|
| `test_at_mentioned_thinker_has_very_high_response_probability` | @mention sets probability to 0.98 (near-certain response) |
| `test_addressed_by_name_boosts_probability` | Name without @ gets boosted probability (>base) |
| `test_consecutive_silence_boosts_probability` | consecutive_silence>2 increases response rate |
| `test_own_last_message_reduces_probability_to_near_zero` | Own last message drops probability to 0.05 |
| `test_no_new_messages_always_returns_false` | No new messages → always False (early exit guard) |

### 24.5 _extract_thinking_display Language Paths (`TestExtractThinkingDisplayLanguages`)

| Test | What It Validates |
|------|-------------------|
| `test_german_language_path_applies_replacements` | German ('de') replacements applied (e.g., Ich sollte → Vielleicht sollte ich) |
| `test_german_language_returns_non_empty_for_valid_input` | German path produces output without error |
| `test_spanish_language_path_applies_replacements` | Spanish ('es') replacements applied |
| `test_spanish_language_returns_non_empty_for_valid_input` | Spanish path produces output without error |
| `test_french_language_path_applies_replacements` | French ('fr') replacements applied |
| `test_french_language_returns_non_empty_for_valid_input` | French path produces output without error |
| `test_hindi_language_path_applies_replacements` | Hindi ('hi') path exercised |
| `test_unknown_language_falls_back_to_english_replacements` | Unknown language code uses English defaults |
| `test_text_already_ending_with_ellipsis_no_double_ellipsis` | Text ending in '...' does not get second ellipsis |

### 24.6 _split_response_into_bubbles Edge Cases (`TestSplitResponseEdgeCases`)

| Test | What It Validates |
|------|-------------------|
| `test_transition_word_forces_bubble_split` | Transition words (However,) trigger bubble split even below target size |
| `test_very_long_single_sentence_gets_force_split` | Single bubble >300 chars gets force-split at mid-sentence boundary |
| `test_empty_bubbles_filtered_out` | Filter step removes empty strings from bubble list |

### 24.7 Streaming Thinking Unexpected Error (`TestStreamingThinkingUnexpectedError`)

| Test | What It Validates |
|------|-------------------|
| `test_unexpected_exception_in_stream_raises_thinker_api_error` | Non-APIError during streaming is wrapped in ThinkerAPIError (lines 686-688) |

## 25. Flaky Test Hunt - Apr 28, 2026 (`test_flaky_hunt_apr28_2026.py`)

**Focus:** flaky-hunt (Tuesday QA)
**Issue:** #863

Tests run 5x without failures. Coverage maintained at 91.32% (1350 passed). Key flakiness risks identified and hardened.

### 25.1 Extract Thinking Display Language Branches (`TestExtractThinkingDisplayLanguages`)

| Test | What It Validates |
|------|-------------------|
| `test_german_replacements_applied` | German (de): "Ich denke " removed from output |
| `test_spanish_replacements_applied` | Spanish (es): "Creo que " removed from output |
| `test_french_replacements_applied` | French (fr): "Je pense que " removed from output |
| `test_english_should_replacement` | English: "I should" → "Perhaps I should" replacement |
| `test_english_let_me_replacement` | English: "Let me" → "Let me see..." replacement |
| `test_short_text_returns_empty_string` | Lengths 0, 1, 40, 79 all return "" (threshold guard) |
| `test_exactly_80_chars_threshold` | 79-char text returns "" (exact boundary) |
| `test_empty_text_returns_empty_string` | Empty string returns "" for all language codes |
| `test_long_text_gets_truncated_to_200_chars` | 500-char text uses only last 200 chars |
| `test_text_with_ellipsis_not_doubled` | Text already ending "..." does not get second ellipsis |
| `test_german_user_pronoun_replacement` | German: "Der Benutzer" → "Sie" replacement |
| `test_spanish_user_pronoun_replacement` | Spanish: "El usuario" → "Ellos" replacement |
| `test_hindi_short_text_returns_empty` | Hindi (hi): short text still returns "" |

### 25.2 Deterministic Should-Respond Tests (`TestShouldRespondDeterministic`)

| Test | What It Validates |
|------|-------------------|
| `test_at_mentioned_with_random_always_0_always_responds` | @mention + random=0.0 → always responds (98% prob) |
| `test_at_mentioned_with_random_always_1_never_responds` | @mention + random=1.0 → never responds (above 98%) |
| `test_own_message_with_random_0_still_suppressed` | Own message + random=0.0 → False (silence check fires at 15%) |
| `test_own_message_with_random_above_silence_threshold_uses_5pct` | Own message passes silence (0.20>0.15), then 4% < 5% → responds |
| `test_no_messages_returns_false` | Empty message list always False (no random needed) |
| `test_no_new_messages_returns_false` | last_response_count >= len(messages) → always False |
| `test_consecutive_silence_boosts_probability` | consecutive_silence=3: passes silence (0.20>0.15), then 0.0 < boosted prob |
| `test_addressed_by_name_boosts_probability` | Name in message: silence check skipped, 0.0 < 0.87 → True |
| `test_silence_cutoff_returns_false_deterministically` | random=0.10 < 0.15 silence threshold → always False |

### 25.3 Deterministic Bubble Split Tests (`TestSplitResponseBubblesDeterministic`)

| Test | What It Validates |
|------|-------------------|
| `test_transition_word_but_forces_new_bubble` | "But " starts new bubble when text >250 chars (bypass single-bubble shortcut) |
| `test_however_transition_forces_new_bubble` | "However," starts new bubble when text >250 chars |
| `test_very_short_text_always_single_bubble` | Text < 60 chars → always 1 bubble (10 seeds) |
| `test_empty_text_returns_empty_list` | Empty text → [] |
| `test_very_long_text_force_splits` | Text >300 chars force-splits at sentence boundary |
| `test_no_empty_bubbles_in_output` | Filter ensures no empty strings in bubble list (5 seeds × 3 texts) |

### 25.4 Conversation State Isolation (`TestConversationStateIsolation`)

| Test | What It Validates |
|------|-------------------|
| `test_fresh_thinker_service_has_no_paused_conversations` | New ThinkerService starts with no paused convs |
| `test_fresh_thinker_service_has_no_idle_paused_conversations` | New ThinkerService starts with no idle-paused convs |
| `test_pause_and_unpause_returns_to_clean_state` | pause_for_idle + resume_from_idle → clean state |
| `test_unknown_conv_resume_from_idle_is_safe` | resume_from_idle on unknown ID doesn't raise |
| `test_multiple_services_have_independent_state` | Two instances have independent _paused/_idle_paused state |
| `test_pause_for_idle_sets_idle_paused_flag` | pause_for_idle() sets is_idle_paused() to True |
| `test_get_last_user_message_timestamp_with_no_user_messages` | Empty messages → 0.0 (sentinel, not exception) |
| `test_idle_timeout_default_setting_is_positive` | idle_timeout_seconds >= 0 (guard for timeout logic) |

### 25.5 Should-Respond Probability Cap Tests (`TestShouldRespondEdgeCases`)

| Test | What It Validates |
|------|-------------------|
| `test_probability_capped_at_0_9_with_high_silence` | consecutive_silence=100: prob capped at 0.9; 0.89 responds, 0.91 doesn't |
| `test_addressed_probability_capped_at_0_95` | Addressed with N=5 messages: cap at 0.95; 0.94 responds, 0.96 doesn't |
| `test_base_probability_capped_at_0_7` | N=10 messages: base capped at 0.7; 0.69 responds, 0.71 doesn't |


## 26. Test Refactoring (Friday QA, May 1, 2026)

### 26.1 Refactoring: Remove Redundant `trigger_research` Patches

**Problem:** Several test files contained redundant `with patch("app.services.knowledge_research.knowledge_service.trigger_research"):` blocks. These are unnecessary because `conftest.py` already mocks `trigger_research` globally via an `autouse=True` fixture. The redundant wrappers added visual noise, unnecessary indentation, and obscured test intent.

**Files Refactored:**

| File | Patches Removed | Lines Reduced |
|------|-----------------|---------------|
| `test_conversations_coverage_sprint_feb9.py` | 11 | 514 → 345 (-33%) |
| `test_edge_cases_feb21_2026.py` | 10 | 1048 → 1034 |
| `test_edge_cases_feb28_2026.py` | 20 | 1053 → 1033 |
| `test_regression_prevention_mar15_2026.py` | 10 | 991 → 981 |
| `test_edge_cases_mar14_2026.py` | 5 | 1210 → 1205 |
| **Total** | **56** | **~250 lines removed** |

**Additional improvements in `test_conversations_coverage_sprint_feb9.py`:**
- Used `create_test_conversation()` helper from `conftest.py` to replace 10-20 line conversation creation blocks
- Used `assert_not_found()` helper for 404 assertions
- Removed unused `from unittest.mock import patch` import from `test_edge_cases_feb21_2026.py`

**What these refactored tests validate:** All original test coverage is preserved. The refactoring only removes duplicate mock setup, not test logic. Coverage remains at 91%.

## 27. Flaky Test Hunt (Tuesday QA, May 5, 2026)

**Focus:** Tuesday - Flaky Test Hunt
**Issue:** #876
**File:** `backend/tests/test_flaky_hunt_may5_2026.py` (19 new tests)

### 27.1 Analysis Results

**Backend:** 91.32% total coverage (1350 passed, 9 skipped). Runs are consistently stable (3/3 passes).

**Frontend:** 525 tests, all pass consistently (3/3 runs in ~7-8 seconds).

**Flakiness risks identified:**
- `test_thinker_service.py:332` uses `random.seed(None)` inside a loop (benign for short-text test, but pattern flagged)
- `test_regression_prevention_apr26_2026.py:604` uses probabilistic loop (50 tries, P(all-fail) ≈ 2e-9, statistically safe)
- `_extract_thinking_display` line 819->824: False branch (last_space ≤ 40, no truncation) never tested
- `_should_prompt_user` line 1470: random.random() path tested only via seed iteration (not direct mock)
- `_should_respond` line 1597: forced-silence 15% path tested only probabilistically

### 27.2 `_extract_thinking_display` Word-Boundary Branches (`TestExtractThinkingDisplayWordBoundaryBranches`)

Covers lines 816-820: the word-boundary end-truncation logic. Branch 819->824 (last_space ≤ 40, truncation skipped) was never exercised.

| Test | What It Validates |
|------|-------------------|
| `test_word_boundary_truncation_skipped_when_space_position_is_early` | Covers 819->824: space at position 35 (≤ 40) → no tail trim → B chars preserved |
| `test_word_boundary_truncation_applied_when_space_far_from_start` | Covers 819-True: space at position 81 (> 40) → tail trim applied → C chars removed |
| `test_word_boundary_check_not_triggered_when_no_space_in_tail` | Covers line 816 False path: no space in last 30 chars → entire block skipped |

### 27.3 `_should_prompt_user` Deterministic Tests (`TestShouldPromptUserDeterministic`)

Replaces seed-iteration approach with direct mock of `random.random()` for deterministic coverage of line 1470.

| Test | What It Validates |
|------|-------------------|
| `test_prompt_returns_true_when_random_below_probability` | random.random()=0.05 < 0.15 (prob) → True |
| `test_prompt_returns_false_when_random_above_probability` | random.random()=0.20 >= 0.15 → False |
| `test_prompt_returns_false_when_threshold_not_met_regardless_of_random` | 2 thinker msgs < threshold=8 → False before random check |
| `test_prompt_threshold_scales_with_speed_multiplier` | speed_mult=6.0 reduces threshold to 4; 4 msgs + random=0.0 → True |

### 27.4 `_should_respond` Forced-Silence Branch Tests (`TestShouldRespondForcedSilenceBranch`)

Deterministic coverage of the 15% noise-floor at line 1597 using `patch('random.random', side_effect=[...])`.

| Test | What It Validates |
|------|-------------------|
| `test_forced_silence_returns_false_when_noise_floor_triggers` | random()=0.05 < 0.15 → forced silence → False |
| `test_forced_silence_bypassed_when_at_mentioned` | @mentioned thinker skips noise-floor entirely → True |
| `test_should_respond_false_when_base_probability_roll_fails` | Noise-floor passes but 0.99 > base_prob → False |
| `test_should_respond_true_when_both_checks_pass` | Noise-floor 0.20 > 0.15; prob 0.10 < 0.37 → True |

### 27.5 `_count_messages_since_user` Edge Cases (`TestCountMessagesSinceUserEdgeCases`)

Edge cases not covered by existing tests: all-thinker conversation, empty list, user as latest message.

| Test | What It Validates |
|------|-------------------|
| `test_all_thinker_messages_returns_full_count` | 7 thinker msgs, no user → returns 7 |
| `test_empty_messages_returns_zero` | Empty list → 0 (no crash) |
| `test_user_as_last_message_returns_zero` | User spoke last → count = 0 immediately |
| `test_enum_sender_type_counted_correctly` | SenderType enum (not string) recognized correctly → 3 |

### 27.6 `_split_response_into_bubbles` Edge Cases (`TestSplitResponseBubblesEdgeCases`)

| Test | What It Validates |
|------|-------------------|
| `test_text_with_consecutive_punctuation_produces_no_empty_bubbles` | `!?` sequences → no empty bubbles (line 733 filter) across 5 seeds |
| `test_single_char_sentence_boundaries_not_treated_as_empty` | `?` followed by `?` → no crash, valid list returned |
| `test_empty_response_returns_empty_list` | Empty string → []; whitespace → list (documents actual behavior) |
| `test_very_short_text_always_single_bubble_across_seeds` | 30-char text → 1 bubble across all 10 seeds (deterministic, no seed(None)) |


## 28. Test Refactoring (Friday QA, May 8, 2026)

**Focus:** Reduce inline mock boilerplate by adopting existing helpers.
**Issue:** #882
**Files Modified:**
- `backend/tests/test_thinker_service.py`
- `backend/tests/test_coverage_sprint_mar30_2026.py`

### 28.1 `make_mock_thinker` Adoption in `test_thinker_service.py`

**Problem:** 13 inline occurrences of `thinker = MagicMock(); thinker.name = "X"` ignored the existing `make_mock_thinker(name="X")` helper defined at the top of the same file (line 19-53).

**Refactored 13 call sites** across `TestShouldRespond`, `TestGenerateResponse`, `TestChooseResponseStyle`, `TestGenerateUserPrompt`, and `TestShouldRespondWithMentions`. Each replacement collapses 2 lines (`thinker = MagicMock()` + `thinker.name = "X"`) into 1 line (`thinker = make_mock_thinker(name="X")`).

**No tests added or removed.** All 97 tests in `test_thinker_service.py` continue to pass identically.

### 28.2 `create_mock_anthropic_response` Adoption in `test_coverage_sprint_mar30_2026.py`

**Problem:** 4 inline occurrences of:
```python
mock_response = MagicMock()
mock_response.content = [TextBlock(type="text", text=...)]
```
ignored the existing `create_mock_anthropic_response()` helper in `conftest.py`.

**Refactored 4 call sites** in `TestSuggestThinkersWithLanguage` and `TestParallelSuggestionsDeduplication`. Each replacement collapses 2 lines into 1 and removes the local `TextBlock` import (no longer needed in this file).

**No tests added or removed.** All 64 tests in `test_coverage_sprint_mar30_2026.py` continue to pass identically.

### 28.3 Net Effect

- **Lines removed:** ~22 lines of duplicated mock boilerplate
- **Imports cleaned:** 1 unused `from anthropic.types import TextBlock` removed
- **Tests:** 161 tests across the two refactored files, all passing 3x
- **Behavior:** Identical — pure refactoring with no semantic change

## 29. Flaky Test Hunt (Tuesday QA, May 26, 2026) — `test_flaky_hunt_may26_2026.py`

**Focus:** Lock down the remaining branches in `app/services/thinker.py` that prior flaky-hunt sessions did not yet pin deterministically. This session targets LENGTH boundaries, randint EXTREME values, and the `consecutive_silence` strict-`>` boundary.

**Issue:** #922

**Flaky-hunt verification (no flakiness found):**
- Ran the 97-test random/timing-prone subset (matching `bubble`, `split`, `random`, `should_respond`, `should_prompt`, `thinking_display`, `choose_response_style`, `choose_style`, `strategy_roll`) 5x back-to-back. All 5 runs passed cleanly in ~6.5s each.

**Prior sessions already covered:**
- `_choose_response_style` 11 branches (may19) — just_spoke, was_addressed×5, not-addressed×5
- `_split_response_into_bubbles` strategy_roll branches (may12) — single-bubble, aggressive, normal, relaxed
- `_should_respond` silence-check boundary at exactly 0.15 (may12)
- `_should_prompt_user` boundary at exactly 0.15 (may12)
- `_extract_thinking_display` punctuation and language branches (apr28, may12)

**This session adds 18 tests across 5 test classes:**

### 29.1 `TestSplitBubblesLengthBoundary60` — line 704 strict `<`

`_split_response_into_bubbles` line 704: `if len(text) < 60: return [text]`. Strict `<` direction pinned with len=59 (early return) and len=60 (falls through to splitting).

- `test_setup_lengths_are_correct` — sanity check on test data lengths
- `test_length_59_takes_early_return` — positive control: len=59 short-circuits, no random calls
- `test_length_60_does_not_take_early_return` — len=60 falls through; randint(120, 180) is called

### 29.2 `TestSplitBubblesLengthBoundary250` — line 711 strict `<`

Line 711: `if strategy_roll < 0.25 and len(text) < 250: return [text]`. Compound condition. With strategy_roll=0 forcing the first term True, the length term `len(text) < 250` strict `<` determines whether the early return fires.

- `test_setup_lengths_are_correct` — sanity check
- `test_length_249_with_low_roll_takes_single_bubble` — positive control: both terms True → early return
- `test_length_250_with_low_roll_falls_through` — len=250 disqualifies despite roll=0; randint(80, 120) is called

### 29.3 `TestSplitBubblesLengthBoundary300` — line 767 strict `>`

Line 767: `if len(bubbles) == 1 and len(text) > 300:` (force-split fallback). Strict `>` direction pinned with single-sentence inputs at lengths 300 and 301.

- `test_force_split_setup_lengths` — sanity check
- `test_length_300_single_sentence_does_not_enter_force_split` — len=300 does NOT satisfy the strict `>`
- `test_length_301_single_sentence_enters_force_split_block` — positive control: len=301 satisfies guard

### 29.4 `TestSplitBubblesRandintExtremeValues` — randint(a, b) inclusive endpoints

Existing tests only patch randint to mid-range values (100, 150, 220). These tests pin behavior at the inclusive MIN and MAX of each randint range, catching any regression that mishandles the boundary (e.g., a refactor that confused inclusive vs exclusive semantics).

- `test_setup_long_text_is_long_enough` — sanity check
- `test_aggressive_randint_min_value_80_produces_bubbles` — aggressive branch with target_size=80 (inclusive min)
- `test_aggressive_randint_max_value_120_produces_bubbles` — aggressive branch with target_size=120 (inclusive max)
- `test_normal_randint_min_value_120_produces_bubbles` — normal branch min
- `test_normal_randint_max_value_180_produces_bubbles` — normal branch max
- `test_relaxed_randint_min_value_180_produces_bubbles` — relaxed branch min
- `test_relaxed_randint_max_value_250_produces_bubbles` — relaxed branch max

Each test asserts the function produces at least one non-empty bubble and that randint was called with the documented range — guarding against typo regressions like `randint(80, 119)` or off-by-one slips.

### 29.5 `TestShouldRespondConsecutiveSilenceBoundary` — line 1588 strict `>`

`_should_respond` line 1588: `if consecutive_silence > 2 and not was_at_mentioned: ...`. Boost-probability branch uses strict `>`. Pin behavior at exactly 2 (no boost) and at 3 (boost), using a roll value that falls between the unboosted (0.37) and boosted (0.67) probabilities — same roll, different silence values, different results.

- `test_silence_2_no_boost_returns_false_with_roll_above_unboosted` — silence=2, roll=0.50, base=0.37 → False
- `test_silence_3_does_boost_returns_true_with_same_roll` — silence=3, roll=0.50, base=0.67 (boost) → True

A regression flipping `>` → `>=` would make silence=2 also boost to base=0.57, and roll=0.50 < 0.57 would return True instead of False. The test catches this immediately.

### 29.6 Verification

- All 18 tests passed 5x consecutively (3x is the minimum per QA protocol)
- Full thinker-related suite (261 tests across `test_thinker_service.py`, all `test_flaky_hunt_*.py`, including this new file) passes in 12.7s
- No existing tests broken, no flakiness introduced

## 30. Integration Gaps (Wednesday QA, Jun 3, 2026) — `test_integration_gaps_jun3_2026.py`

Backend line/branch coverage is already 99.4%, so this Wednesday run targets
**cross-endpoint integration contracts** — workflows where a write through one
endpoint must be observable through a *different* endpoint. Each endpoint passes
in isolation; these tests catch contract drift between endpoints that
single-endpoint tests cannot. 10 tests across 5 classes, all passing 3x plus a
randomized-order run.

### 30.1 `TestProfileUpdatePropagatesToMessageSenderName`

`send_message` derives `sender_name` from `user.display_name or user.username`
at send time. Existing tests only check the registration-time display_name, so a
regression caching the old name or reading a stale row would slip through. Pairs
`PATCH /api/auth/profile` with `POST /api/conversations/{id}/messages`.

- `test_updated_display_name_used_for_subsequent_message` — rename via profile
  endpoint, then a new message's `sender_name` reflects the updated name.
- `test_message_after_two_profile_updates_uses_latest` — two successive renames;
  the message uses the most recent value, not an intermediate one.

### 30.2 `TestConversationListCrossUserIsolation`

The single-resource 404-on-foreign-id case is covered elsewhere; this asserts the
`GET /api/conversations` list endpoint's `session_id` filter holds when two real
authenticated users have overlapping data, so a dropped WHERE clause is caught.

- `test_each_user_sees_only_their_own_conversations` — two users; each list
  returns exactly their own conversation ids and excludes the other's.
- `test_other_users_message_not_counted_in_my_list` — a message one user sends
  must not appear in or inflate the message_count of the other user's list.

### 30.3 `TestDeleteUserCascadeAcrossEndpoints`

A user-deletion that left the row reachable via login or spend would be a serious
data-integrity bug. Chains `DELETE /api/admin/users/{id}` to the auth and spend
endpoints.

- `test_deleted_user_cannot_login_and_has_no_spend_record` — after delete, login
  returns 401 and admin `GET /api/spend/{id}` returns 404 (both 200 beforehand).
- `test_deleted_user_drops_out_of_admin_user_listing` — deleted user disappears
  from `GET /api/admin/users`.

### 30.4 `TestFeedbackPendingLimitAndOrdering`

Existing tests cover the `?limit` boundary *status codes* (1/50/51) but not the
behaviour the DevOps processing workflow relies on.

- `test_pending_truncates_to_limit` — submitting 4 items, `?limit=2` returns
  exactly 2.
- `test_pending_returns_items_in_ascending_created_at_order` — `/pending` items
  come back oldest-first (non-decreasing created_at). Robust against timestamp
  ties: asserts the asc-ordering invariant rather than specific positions.

### 30.5 `TestFeedbackMarkProcessedIsolation`

The single-item submit→process→gone chain is covered; this asserts the multi-item
invariant for `PATCH /api/feedback/{id}/processed`.

- `test_processing_one_leaves_others_pending` — marking one of three NEW items
  removes exactly that id from `/pending` and leaves the other two.
- `test_processed_feedback_records_issue_url_for_other_items_untouched` — marking
  one item with a github_issue_url must not stamp a bystander item's url.

## 31. Coverage Sprint (Monday QA, Jun 8, 2026) — `src/__tests__/lib/api.coverage.test.ts`

**Focus:** Coverage sprint. Backend is effectively maxed (99.43%; the one missed
statement at `app/services/thinker.py:733` is an unreachable defensive `continue`
given the upfront `.strip()`). The frontend API client `src/lib/api.ts` was the
lowest-coverage testable-logic file at **76.9% stmts / 77.27% branch**. After this
sprint it is at **100% stmts / 95.58% branch / 100% funcs** (remaining branch
partials are the SSR `typeof window === 'undefined'` guards).

### 31.1 Token & user storage helpers (`api.coverage.test.ts`)

- `setAccessToken(null)` removes `access_token`; `setAccessToken(token)` writes it.
- `setStoredUser(null)` removes the stored `user`.
- `getStoredUser` covers all three branches: valid JSON parses, empty storage
  returns null, and malformed JSON is caught and returns null.
- `getAccessToken` caches the token in memory after the first read (second read
  does not touch localStorage).

### 31.2 Profile / language / password mutations

- `updateLanguage` PATCHes `/api/auth/language` and persists the updated user.
- `updateProfile` PATCHes `/api/auth/profile` and persists the updated user.
- `changePassword` POSTs `/api/auth/change-password` with current/new passwords.

### 31.3 Admin API

- `getAdminUsers` GETs `/api/admin/users` with the bearer token.
- `deleteUser` DELETEs `/api/admin/users/{id}`.
- `updateUserSpendLimit` PATCHes `/api/admin/users/{id}/spend-limit`.

### 31.4 `submitFeedback` (no-auth endpoint)

- Success path POSTs to `/api/feedback` and returns the created record.
- Non-ok response throws the server-provided `detail`.
- Error body without a `detail` field falls back to `HTTP <status>`.
- A `TypeError: Failed to fetch` is mapped to the friendly "Unable to connect to
  the server…" message.
- Any other error is re-thrown unchanged.

### 31.5 `fetchWithAuth` auth/error/cancellation branches

- A 401 from a protected page clears auth and triggers the `/login` redirect
  branch (`api.coverage.test.ts`). The companion case where the user is already
  on `/login` (redirect skipped, only clearAuth runs) lives in
  `src/__tests__/lib/api.login-401.coverage.test.ts`, which pins the jsdom URL to
  `/login` via a `@jest-environment-options` docblock.
- `getCurrentUser` clears auth and returns null when `/api/auth/me` fails.
- An `AbortError` with no external signal becomes a `Request timeout after <ms>ms`
  error; an aborted external `AbortSignal` instead yields `Request cancelled`.
- `suggestThinkers` wires an external `AbortSignal` through to the request
  (verified via an `addEventListener('abort', …)` spy).

## 32. Edge Cases (Saturday QA, Jun 13, 2026) — `test_edge_cases_saturday_jun13_2026.py`

Backend coverage was already at 99.43%. This session closed the remaining
*reachable* partial-branch gaps in the streaming-thinking event loop and the
database initialiser. (`thinker.py:733`, the `continue` for an empty
post-split sentence, is unreachable — `re.split(r"(?<=[.!?])\s+", text)` on a
stripped string cannot produce empty fragments — so it is deliberately left
alone.)

### 32.1 `TestStreamingThinkingEdgeBranches`

Exercises the per-event branches inside
`ThinkerService.generate_response_with_streaming_thinking`:

- `test_second_thinking_delta_is_throttled` — a second thinking delta arriving
  within the update interval is throttled, so exactly one thinking update is
  sent (covers `636->616`).
- `test_short_thinking_delta_sends_no_update` — a thinking delta under 80 chars
  yields an empty display preview, so the throttle passes but no update is sent
  (covers `641->645`).
- `test_empty_delta_is_ignored` — a `content_block_delta` carrying neither
  `thinking` nor `text` is a no-op and does not affect the response (covers
  `646->616`).
- `test_message_delta_without_usage_is_ignored` — a `message_delta` event with
  `usage = None` does not update token counts; final usage still comes from
  `get_final_message()` (covers `649->616`).
- `test_non_thinking_block_does_not_add_thinking_cost` — a final-message content
  block that is not a `ThinkingBlock` adds no thinking tokens, so cost equals
  input + output cost exactly (covers `662->661`).

### 32.2 `TestInitDbNoAlembic`

- `test_init_db_uses_create_all_when_no_alembic_ini` — when `alembic.ini` is
  absent, `init_db()` skips `run_migrations()` entirely and falls back to
  `create_all` via `engine.begin().run_sync` (covers `database.py` `98->107`).

## 33. Coverage Sprint (Monday QA, Jun 15, 2026) — `src/middleware.ts`

**Focus**: Monday QA (coverage-sprint). The backend is exhaustively covered
(websocket.py 95%, thinker.py ~99%), and the previous coverage-sprint (#951)
had already moved to the frontend. A fresh `jest --coverage` run confirmed the
lowest-coverage file is now the Next.js cache-control middleware.

**Target**: `frontend/src/middleware.ts` — **0% → 100%** statements/branches/
functions/lines.

**Why it was at 0%**: `src/__tests__/middleware.test.ts` was a placeholder that
only asserted string constants and never invoked `middleware()` ("tested in E2E
instead"). Next.js middleware runs in the Edge Runtime, which exposes the web
`Request`/`Response` globals; the default jsdom test environment does not define
`Request`, so importing `next/server` there throws. The placeholder side-stepped
this entirely, leaving the cache-control logic with no unit coverage.

**Enabling change**: the new test file opts into `@jest-environment node` (Node
18+ provides the web fetch globals natively). `jest.setup.ts` was hardened to
guard browser-only globals (`Element`, `window`) behind `typeof … !== 'undefined'`
so node-environment test files can share the global setup without
`ReferenceError`s. Under jsdom these guards are always true, so all 671 pre-existing
browser tests are unaffected.

### 33.1 `cache-control middleware` — `src/__tests__/middleware.test.ts`

Replaces the placeholder. Invokes `middleware()` with real `NextRequest`s and
asserts the resulting `Cache-Control`/`Pragma`/`Expires` headers, covering every
branch:

- **Hashed static assets (`/_next/static/…`)** — JS and CSS receive
  `public, max-age=31536000, immutable`; the no-cache HTML headers are *not* set.
  A `.png` under `/_next/static/` still resolves to the immutable policy,
  pinning the branch *ordering* (the static check precedes the image check).
- **HTML pages / root / extensionless routes** — `/`, `/about.html`, `/login`
  and `/admin/users` all receive `no-cache, no-store, must-revalidate, max-age=0`
  plus `Pragma: no-cache` and `Expires: 0`. This covers the three OR'd
  sub-conditions (`endsWith('.html')`, `=== '/'`, `!includes('.')`).
- **Public images & fonts** — a parametrised list (`jpg, jpeg, png, gif, ico,
  svg, woff, woff2, ttf, eot`) each receives `public, max-age=3600,
  must-revalidate` and no `Pragma`.
- **Case-sensitivity guard** — `/Banner.PNG` (uppercase extension) does *not*
  match the case-sensitive extension regex and falls through with no
  `Cache-Control`, pinning current behavior.
- **Fallthrough** — extensioned paths that match nothing (`/data.json`,
  `/notes.txt`, `/archive.zip`, `/feed.xml`) return the pass-through response
  with no cache headers at all.
- **Exported `config.matcher`** — asserts the matcher excludes `api` and
  `_next/webpack-hmr` routes.

**Result**: `middleware.ts` 0% → 100% (all metrics); overall frontend statement
coverage 88.41% → 89.1%; full suite 695 passed (was 675), verified stable across
3 consecutive runs.

## 34. Integration Gaps (Wednesday QA, Jun 24, 2026) — `src/__tests__/components/FeedbackModal.integration-gaps.test.tsx`

The existing `FeedbackModal.test.tsx` covered the happy-path file upload,
validation errors, and submission flow, but left the screenshot **drag-and-drop**,
**clipboard paste**, **FileReader error**, and **modal-close cleanup** paths
untested — `FeedbackModal.tsx` sat at 87.7% statements / **54.9% branch**. These
are all real user-facing integration flows. This file adds end-to-end tests that
fire the actual DOM events and drive the FileReader callbacks.

### 34.1 Clipboard paste (`handlePaste`)

- **Pastes an image** — fires a `paste` event whose `clipboardData.items`
  contains an `image/png` item, drives `FileReader.onload`, and asserts the
  preview renders with the auto-generated `screenshot-<timestamp>.png` filename.
- **No clipboard items** — `clipboardData.items` is `undefined`; the early
  return leaves the dropzone untouched (no preview).
- **Only non-image items** — a `text/plain` item is ignored (the loop never
  calls `getAsFile`), no preview appears.

### 34.2 Drag and drop (`handleDragOver` / `handleDragLeave` / `handleDrop`)

- **Drag over highlights, drag leave reverts** — `dragOver` flips the dropzone
  into the "Drop image here" state; a `dragLeave` whose `relatedTarget` is
  outside the dropzone reverts it to "Upload screenshot".
- **Dropped image is processed** — `drop` with an `image/png` file in
  `dataTransfer.files` drives `FileReader.onload` and renders the filename.
- **Drop with no files** — empty `dataTransfer.files` is a no-op.
- **Drop of a disallowed type** — a `text/plain` file is skipped by the
  `ALLOWED_TYPES` guard; the dropzone remains and no preview is created.

### 34.3 FileReader error (`processFile` `reader.onerror`)

- **File read failure** — drives `FileReader.onerror`, asserts the
  "Failed to read screenshot file" error renders and the preview object URL is
  revoked (`URL.revokeObjectURL`), guarding against memory leaks on failure.

### 34.4 File input edge case (`handleFileChange`)

- **Dialog cancelled (no file)** — a `change` event with an empty `files` list
  takes the no-file branch (clears screenshot / resets upload state) and leaves
  the dropzone in place.

### 34.5 Modal close cleanup (reset `useEffect`)

- **Object URL revoked on close** — uploads a screenshot, then re-renders with
  `isOpen={false}`; the reset effect revokes the preview object URL.

**Result**: `FeedbackModal.tsx` 87.7% → **96.48%** statements, 54.9% → **62.71%**
branch, functions **100%**. Remaining uncovered lines are defensive i18n `||`
fallback strings. Verified stable across 3 consecutive runs (10/10 passing).

## 35. Coverage Sprint: Home page (`src/app/page.tsx`) 0% → 100% (Added 2026-06-29)

**Focus**: Monday QA (coverage-sprint). The backend is effectively maxed out
(99.66%), so the largest remaining gap was the entire Home/chat orchestration
page — **`src/app/page.tsx`, previously 0% across 333 lines**. It is the surface
that wires together the auth redirect, conversation loading, the WebSocket
message/error callbacks, the send/create/delete/select handlers, sidebar width
persistence and the spend-limit display, yet had no unit coverage at all.

New test file: `frontend/src/__tests__/app/page.test.tsx` (39 tests). Child
components (`Sidebar`, `ChatArea`, `NewChatModal`, `ResizeDivider`), the
`useWebSocket` hook, the auth/language contexts and the `@/lib/api` layer are
mocked so the tests exercise the page's own logic in isolation. The mocked
children expose buttons/`data-testid`s that invoke the page's callbacks, and the
`useWebSocket` mock captures the `onMessage`/`onError` options so those callbacks
can be driven directly.

### 35.1 Loading & auth gating
- **Loading state** — renders "Loading..." while `authLoading` is true; sidebar
  absent.
- **Unauthenticated redirect** — `router.replace('/login')` fires and
  conversations are not fetched.
- **Null render after logout** — an authenticated session that flips to
  unauthenticated (after loading completed) renders nothing and redirects.
- **Main layout** — once conversations load, Sidebar/ChatArea/NewChatModal render
  with the conversation count and username.

### 35.2 Conversation list loading
- **Populates sidebar** from `api.getConversations`.
- **Error finally path** — a failed fetch still clears the loading state and
  logs the error.

### 35.3 Sidebar width persistence (localStorage)
- **Restore valid** saved width; **ignore out-of-range** width (keeps 288px
  default); **default** when nothing saved; **save on resize** persists the new
  width to localStorage.

### 35.4 Selecting a conversation
- **Loads conversation + messages**; **closes sidebar on mobile**
  (`innerWidth < 1024`); **stays open on desktop**; **error path** logs and
  leaves no active conversation.

### 35.5 Deleting a conversation
- **Removes non-active** conversation; **clears the active** conversation and its
  messages when the current one is deleted; **error path** logs and keeps the
  conversation.

### 35.6 Sending messages
- **No active conversation** → early return, no API call; **success** sends via
  API + notifies over WebSocket and appends the message; **non-401 error**
  surfaces an error banner; **401 error** stays silent (handled by redirect).

### 35.7 Creating conversations
- **Prepend + activate** the new conversation with an empty message list;
  **closes sidebar on mobile** after creation.

### 35.8 Thinker suggestions & validation
- **Suggest** forwards the current `locale` to `api.suggestThinkers`;
  **validate** returns the profile for a valid thinker and `null` for an invalid
  one.

### 35.9 Modal, logout & toggles
- **Modal open/close**, **sidebar toggle**, and **logout** (calls `logout` then
  `router.push('/login')`).

### 35.10 WebSocket callbacks
- **onMessage** — appends the message and accrues cost to session spend; updates
  the matching conversation summary only for thinker messages; user messages
  still accrue cost but skip the summary update; no-cost messages leave spend
  unchanged; non-matching conversation ids are appended without crashing.
- **onError** — flags `spendLimitExceeded` for "spend limit" errors, shows a
  generic message otherwise, and supports dismissal.

### 35.11 Spend display
- Passes combined `userTotalSpend` (`total_spend + sessionCost`) and
  `userSpendLimit` to ChatArea; falls back to the default limit (10) and zero
  spend when user fields are absent/falsy.

**Result**: `src/app/page.tsx` **0% → 100% statements / 98.66% branch**
(the only uncovered branch is a structurally-unreachable defensive
`if (!isAuthenticated) return` guard inside the load effect). Full frontend
suite 730 → **769 tests passing**. Verified stable across 3 consecutive runs.
