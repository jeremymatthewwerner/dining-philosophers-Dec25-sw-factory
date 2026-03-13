# Test Plan - Dining Philosophers

This document outlines all features requiring testing, their test cases, and edge conditions.

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
