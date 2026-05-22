## Integration Gaps - Wednesday (Added 2026-05-20)

**Focus**: Multi-endpoint workflows that traverse the public API surface. Each test exercises 2+ endpoints in sequence and asserts that effects of the first call are observable through a later call — the kind of contract mismatch that single-endpoint tests cannot catch.

Line coverage was already at **98.83%** before this sprint, with every endpoint at 100%. The gap targeted here is **behavioral / integration**, not line-coverage.

### Tests Added (test_integration_gaps_may20_2026.py)

**File**: `tests/test_integration_gaps_may20_2026.py` (10 new tests across 5 classes, all pass 3x stable)

#### `TestConversationLifecycleIntegration`
1. `test_create_then_list_then_get_then_delete_then_list_again` — Full CRUD path: create returns id, list contains it, get returns the same conversation, delete removes it, subsequent list excludes it, and follow-up GET on the deleted id returns 404. Validates that every conversations.py endpoint observes the same underlying DB state.
2. `test_list_returns_all_created_conversations_with_full_summary_fields` — Creates 3 conversations and validates the list endpoint returns every one with the full `ConversationSummary` schema populated (topic, thinkers, message_count=0, total_cost=0.0). Cross-endpoint contract between create_conversation and list_conversations.
3. `test_send_message_to_deleted_conversation_returns_404` — DELETE /conversations/{id} → POST /messages on that id returns 404. Validates that DELETE is observable by send_message (the row is actually gone, not orphaned).

#### `TestAddThinkersConstraintIntegration`
4. `test_add_thinkers_rejected_when_total_exceeds_five_and_state_unchanged` — Create with 4 thinkers, PUT 2 more (would be 6), expect 400 with "Maximum is 5 total", then GET to verify the conversation still has exactly 4 thinkers and neither "Extra1" nor "Extra2" was partially written. Validates the limit-check fires *before* any db.add commits.
5. `test_add_thinkers_assigns_unique_colors_when_default_color_provided` — Create 1 thinker, PUT 2 more with default color → GET to verify all 3 thinkers have distinct colors (the color-dedup logic in add_thinkers_to_conversation is observable in the persisted state).

#### `TestKnowledgeResearchWorkflowIntegration`
6. `test_validate_mock_thinker_triggers_research_and_knowledge_endpoint_works` — POST /thinkers/validate with mock thinker "Socrates" → asserts `trigger_research` was called once → subsequent GET /thinkers/knowledge/Socrates returns 200 with the thinker name. Cross-endpoint contract: validate's side-effect must be observable to the knowledge endpoint.
7. `test_refresh_on_never_seen_thinker_creates_entry_then_status_reflects_it` — On a never-seen name, GET /status returns pending+has_data=false, then POST /refresh (which calls `get_or_create_knowledge`) creates the entry and fires research; subsequent GET /status finds the entry. Validates the get-or-create-on-refresh path is observable via status.
8. `test_get_knowledge_for_new_thinker_creates_entry_and_subsequent_status_finds_it` — GET /knowledge/{name} on a new name creates the entry via `get_or_create_knowledge`; the next GET /status finds it. Coverage: the create-on-miss path in `get_thinker_knowledge` is observable downstream.

#### `TestLanguagePreferenceCrossFlowIntegration`
9. `test_register_with_custom_lang_login_returns_same_then_patch_updates_everywhere` — Register with `language_preference="fr"` → /me returns fr → fresh login still returns fr → PATCH /language to "es" → /me reflects es → another fresh login returns es. Validates the contract between auth.register, auth.login, auth.update_language, and auth.get_me.

#### `TestAdminSpendLimitVisibilityIntegration`
10. `test_admin_patches_spend_limit_user_me_and_admin_user_list_both_reflect` — Admin PATCH /admin/users/{id}/spend-limit → user GET /auth/me reflects the new limit → admin GET /admin/users list shows the matching limit on that user → admin GET /spend/{user_id} returns spend data with the correct user_id and username. Cross-endpoint contract among admin.update_spend_limit, auth.get_me, admin.list_users, and spend.get_spend.

### Coverage Impact
- Backend line coverage: **98.83% → ≥98.83%** (these are integration tests; the lines they hit were already covered by unit tests, but they pin down cross-endpoint contracts).
- Total tests: 1547 → 1557 (10 new tests).
- All 10 tests run in <5s and pass 3x consecutively (no flakiness).

### Why These Tests
Single-endpoint unit tests verify each endpoint in isolation. Integration tests catch a different class of bugs: schema drift between create/read, missing cascades, lazy-load pitfalls, observable-state contracts. Each test in this batch is selected to fail loudly if a future refactor accidentally breaks the contract between two endpoints (e.g. if delete_conversation stops cascading, or if update_language stops persisting before login is called again).

---

## Coverage Sprint - Monday (Added 2026-05-18)

**Focus**: Cover the post-generation **bubble-sending path** inside `_run_thinker_agent` — the largest contiguous uncovered region in `app/services/thinker.py` (lines 1269-1336) plus the min-interval gating branch (1184-1187) and the user-prompt branch (line 1258).

### Coverage Impact
- Backend total: **96.83% → 98.75%** (+1.92%)
- `app/services/thinker.py`: **92% → 98%** (35 missed statements → 2)
- Total tests: 1494 → 1503 (9 new tests, all pass 3x stable)
- The previous Monday sprint (may11) covered the streaming-thinking event loop and exception handlers; this sprint completes the agent loop's success path.

### Tests Added (test_thinker_coverage_sprint_may18_2026.py)

**File**: `tests/test_thinker_coverage_sprint_may18_2026.py` (9 new tests, single class `TestRunThinkerAgentBubblePath`)

All tests drive `_run_thinker_agent` for one or two iterations using the "cancel iter N via CancelledError from `is_conversation_active`" pattern from `test_thinker_coverage_sprint_may11_2026.py`, with `asyncio.sleep` patched to a no-op so the event loop time barely advances.

1. `test_happy_path_single_bubble_sends_message` - Generate→split→save→send: a single-bubble response is persisted via `save_message` and broadcast via `manager.send_thinker_message` exactly once, validating the bubble-loop happy path (lines 1273-1312, 1322-1323) and `last_message_time` update.
2. `test_multi_bubble_response_sends_each_with_typing_between` - Three-bubble response causes three `send_thinker_message` awaits and at least 3 `send_thinker_typing` awaits (the inter-bubble "show typing for next bubble" path on lines 1315-1320 fires `n-1` times).
3. `test_pause_after_generation_skips_bubble_send` - When `is_paused` flips True between `generate_response_with_streaming_thinking` and the bubble loop, no `save_message`/`send_thinker_message` is emitted but `send_thinker_stopped_typing` is awaited to flush the indicator (lines 1269-1271).
4. `test_pause_inside_bubble_loop_breaks_iteration` - Pause flipping True at the top of the first bubble iteration breaks the loop before any save runs (lines 1283-1287); no save_message and no send_thinker_message.
5. `test_pause_between_save_and_send_breaks_iteration` - Pause flipping True between `save_message` and `send_thinker_message` results in exactly one save_message but zero send_thinker_message — the loop broke mid-iteration (lines 1298-1302).
6. `test_empty_response_text_stops_typing` - Generate returning `("", 0.0)` skips the bubble loop entirely and only emits `send_thinker_stopped_typing` (lines 1324-1325). No save, no send.
7. `test_should_prompt_user_calls_generate_user_prompt` - `_should_prompt_user=True` + `_get_user_name_from_messages="Alice"` routes through `generate_user_prompt` instead of `generate_response_with_streaming_thinking` (line 1258); validates the user-name argument is passed through.
8. `test_min_interval_gating_after_successful_response` - After one successful iteration, `last_message_time > 0` and `elapsed < min_interval` (since `asyncio.sleep` is no-op), so iteration 2 short-circuits via `await asyncio.sleep(min_interval - elapsed); continue` without reaching `_should_respond` (lines 1183-1187). Asserted via call count on `_should_respond`.
9. `test_consecutive_silence_exceeds_threshold_uses_quiet_wait` - 5 silent iterations (`_should_respond=False`) drive `consecutive_silence` past the threshold of 3, exercising the `wait_time = random.uniform(10.0, 20.0) * speed_mult` quiet-conversation branch on line 1332.

### Branches Now Covered
- `1184-1187` - min-interval gating sleep+continue ✓
- `1258` - `should_prompt and user_name` → call `generate_user_prompt` ✓
- `1269-1271` - pause flips True between generate and bubble loop ✓
- `1281-1287` - pause check at start of bubble iteration (break) ✓
- `1289-1296` - happy-path `save_message` + first-bubble send ✓
- `1298-1302` - pause between `save_message` and `send_thinker_message` ✓
- `1305-1322` - full bubble send + `last_message_time` update ✓
- `1315-1320` - multi-bubble case: sleep + typing for next bubble ✓
- `1324-1325` - empty `response_text` → stop typing only ✓
- `1332-1336` - `consecutive_silence > 3` quiet-wait branch ✓

### Remaining Gaps (≤2% in thinker.py)
- `272` - `_suggest_single_batch` no-client early return
- `733`, `763->767` - micro-branches inside `_split_response_into_bubbles` (force-split when single bubble exceeds 300 chars and a sentence boundary is found exactly mid-text)
- `1185->1190`, `1194->1230`, `1198->1230`, `1200->1226` - partial branches inside the idle-timeout block (already covered for the True path by may11 tests)

These are partial-branch edge cases worth deferring to a future flaky-hunt or edge-case sprint.

---

## Regression Prevention - Sunday Sprint (Added 2026-05-17)

**Focus**: Pin down behavioral contracts from recent bug fixes that lack explicit regression guards.

### Analysis Results

Backend coverage is already at **96.83%** with very few missing lines. Existing regression-prevention test files (mar29, apr12, apr19, apr26, may10) cover most invariants. Remaining gaps are in **wire-protocol constants** and **cross-state contracts** that are easy to break silently in refactors.

### Tests Added (test_regression_prevention_may17_2026.py)

**File**: `tests/test_regression_prevention_may17_2026.py` (34 new tests)

Bug fixes covered:
- **#299** fix(feedback): use enum values instead of names for PostgreSQL (commit 451a962)
- **#483** feat(backend): add idle timeout to auto-pause inactive conversations (commit 7aa14e7)
- **#367** fix(websocket): sync pause button state when switching threads (commit a9c7742)
- **#257** feat(thinker): add @mention support for addressing specific thinkers (commit 363f0e7)
- **#81** fix: persist language preference to database (commit 6fb8b6c)

#### TestFeedbackEnumValuesCallable (6 tests)
1. `test_feedback_type_column_has_values_callable` - SQLAlchemy Enum column produces lowercase labels `["bug","feature","other"]` matching the PostgreSQL `feedbacktype` enum.
2. `test_feedback_status_column_has_values_callable` - Same guard for `feedbackstatus` enum: labels are lowercase values, not uppercase names.
3. `test_feedback_type_enum_values_are_lowercase` - `FeedbackType.BUG.value == "bug"` (the values_callable depends on this).
4. `test_feedback_status_enum_values_are_lowercase` - `FeedbackStatus.NEW.value == "new"`.
5. `test_feedback_type_postgres_enum_name` - Column uses explicit `name="feedbacktype"` for predictable migrations.
6. `test_feedback_status_postgres_enum_name` - Column uses explicit `name="feedbackstatus"`.

#### TestFeedbackTablenameContract (2 tests)
7. `test_feedback_tablename_is_plural` - `Feedback.__tablename__ == "feedbacks"` (singular rename would orphan production data).
8. `test_feedback_table_object_matches_tablename` - Metadata table name matches `__tablename__` (no drift).

#### TestWSMessageTypeConstants (6 tests)
9. `test_idle_timeout_value_is_snake_case` - `WSMessageType.IDLE_TIMEOUT.value == "idle_timeout"` (wire protocol guard for #483).
10. `test_paused_value_is_snake_case` - `PAUSED.value == "paused"` (used by pause sync fix #367).
11. `test_resumed_value_is_snake_case` - `RESUMED.value == "resumed"` (sent on every connect post-#367).
12. `test_speed_changed_value_is_snake_case` - `SPEED_CHANGED.value == "speed_changed"`.
13. `test_cache_hit_value_is_snake_case` - `CACHE_HIT.value == "cache_hit"`.
14. `test_wsmessagetype_is_string_enum` - `WSMessageType` inherits from `str`; refactor to plain Enum would break JSON serialization.

#### TestIdlePauseCrossStateContract (5 tests)
15. `test_manual_pause_does_not_set_idle_paused` - `pause_conversation()` must NOT add to `_idle_paused_conversations` (otherwise user messages would auto-resume manually paused convs).
16. `test_is_paused_returns_true_when_only_idle_paused` - Idle-paused conversations are also reported as `is_paused == True` (cross-set invariant required by agent loop).
17. `test_pause_for_idle_is_idempotent` - Calling `pause_for_idle()` twice does not error or double-add.
18. `test_resume_from_idle_unknown_conversation_is_noop` - `resume_from_idle()` for unknown conv is a safe no-op (called on every user message).
19. `test_idle_timeout_seconds_default_is_300` - Config default for `idle_timeout_seconds` is 300 (5 minutes); changing to 0 disables auto-pause silently.

#### TestExtractMentionsBasicContract (5 tests)
20. `test_empty_text_returns_empty_list` - `extract_mentions("") == []` (downstream `is_mentioned` iterates the result).
21. `test_plain_text_without_at_sign_returns_empty` - Plain text produces no mentions; regression guard for the `@` regex anchor.
22. `test_email_addresses_not_treated_as_mentions` - Documents current behavior: `user@example.com` captures `"example"` (no email-aware filtering yet).
23. `test_at_with_no_following_word_is_skipped` - Bare `@` without a following word produces no mention.
24. `test_multiple_distinct_mentions_preserved_in_order` - Mentions returned in encounter order (downstream may rely on first-mention-is-primary).

#### TestIsMentionedCaseInsensitivity (3 tests)
25. `test_lowercase_mention_matches_capitalized_thinker` - `@socrates` matches thinker "Socrates" (common user typing case).
26. `test_uppercase_mention_matches_capitalized_thinker` - `@SOCRATES` matches "Socrates" (both folded to lowercase).
27. `test_lowercase_first_name_matches_multi_word_thinker` - `@marie` matches "Marie Curie" via first-name path, case-insensitive.

#### TestLanguageInstructionEnglishBypass (3 tests)
28. `test_english_returns_empty_string` - `_get_language_instruction("en") == ""` (token-saver bypass that must be preserved).
29. `test_non_english_returns_non_empty_string` - es/fr/de/hi all produce `"\n\nIMPORTANT: Respond in X."` (regression guard for the language directive).
30. `test_unknown_language_falls_back_to_raw_code` - Unknown code (e.g., "xx") uses the code as the language name, doesn't crash.

#### TestSplitBubblesEmptyAndShort (4 tests)
31. `test_empty_string_returns_empty_list` - `_split_response_into_bubbles("") == []` (not `[""]`); otherwise broadcast would emit blank message.
32. `test_whitespace_only_returns_at_most_one_empty_bubble` - Documents current behavior of the short-text fast path for whitespace input.
33. `test_short_text_returns_single_bubble` - Text < 60 chars always returns one bubble (line 705 guard).
34. `test_borderline_60_char_text_does_not_crash` - 59/60/61 char inputs all produce at least one non-empty bubble (off-by-one guard).

### Coverage Impact
- Coverage stays at 96.83% (target was *contract pinning*, not coverage increase)
- 34 new regression tests added, all pass 3x stable
- Total tests: 1460 → 1494 passed
- Each test class is justified by a specific bug fix (with commit SHA + issue number)

---

## Edge Cases - Saturday Sprint (Added 2026-03-07)

**Focus**: Add tests for error paths and boundary conditions in low-coverage modules.

### Analysis Results

Coverage before: 80.45% (496 missed branches), coverage after: 82.03% (33 missed branches).
Key improvements: `app/api/websocket.py` 47% → 66%, total tests: 687 → 734 passed.

### Tests Added (test_edge_cases_mar2026.py)

**File**: `tests/test_edge_cases_mar2026.py` (47 new tests)

#### TestConversationRoomBroadcastEdgeCases
1. `test_broadcast_removes_disconnected_client` - Verifies ConversationRoom.broadcast() removes clients that throw exceptions during send, simulating dropped connections.
2. `test_broadcast_sets_inactive_when_all_disconnect` - Verifies room becomes inactive (is_active=False) when all connections fail during broadcast.
3. `test_broadcast_empty_room_is_noop` - Validates broadcasting to a room with no connections doesn't raise.
4. `test_add_connection_sets_active` - Tests ConversationRoom.add_connection() sets is_active=True.
5. `test_remove_connection_sets_inactive_when_empty` - Tests removing last connection sets is_active=False.
6. `test_remove_connection_stays_active_with_remaining_connections` - Tests room stays active when connections remain after one removal.

#### TestConnectionManagerEdgeCases
7. `test_set_speed_multiplier_no_room_is_noop` - Boundary: speed change for conversation without a room is a no-op.
8. `test_set_speed_multiplier_clamps_below_minimum` - Boundary: speed < 0.5 gets clamped to 0.5.
9. `test_set_speed_multiplier_clamps_above_maximum` - Boundary: speed > 6.0 gets clamped to 6.0.
10. `test_get_speed_multiplier_nonexistent_room_returns_default` - Boundary: non-existent conversation returns 1.0 default.
11. `test_send_thinker_typing_adds_to_typing_thinkers` - Tests typing set membership tracking.
12. `test_send_thinker_stopped_typing_removes_from_typing_thinkers` - Tests typing set cleanup.
13. `test_send_thinker_thinking_broadcasts_message` - Tests thinking content broadcast with correct type/sender_name/content.
14. `test_send_research_started_broadcasts_to_room` - Tests research_started event includes thinker_name and timestamp.
15. `test_send_research_complete_broadcasts_to_room` - Tests research_complete event includes thinker_name.
16. `test_send_research_failed_with_error_message` - Tests research_failed event includes error content.
17. `test_send_research_failed_without_error_message` - Boundary: research_failed with no error has None content.
18. `test_send_cache_hit_broadcasts_to_room` - Tests cache_hit event includes thinker_name.
19. `test_send_thinker_message_with_cost` - Tests thinker message broadcast includes cost.
20. `test_send_thinker_message_without_cost` - Boundary: thinker message with None cost.

#### TestSpendLimitExceededException
21. `test_spend_limit_exceeded_attributes` - Verifies SpendLimitExceeded stores current_spend and spend_limit.
22. `test_spend_limit_exceeded_message_format` - Verifies error message includes the dollar amounts.
23. `test_spend_limit_exceeded_is_exception` - Verifies it's a proper Exception subclass.

#### TestSaveThinkerMessageEdgeCases
24. `test_save_message_raises_when_spend_limit_exceeded` - Error path: user at spend limit raises SpendLimitExceeded before saving message.
25. `test_save_message_updates_user_spend` - Happy path: save_thinker_message increments user.total_spend.
26. `test_save_message_no_conversation_still_saves` - Boundary: non-existent conversation creates message without spend tracking.

#### TestKnowledgeResearchIsStale
27. `test_is_stale_pending_returns_true` - PENDING status is always stale (needs research).
28. `test_is_stale_failed_returns_true` - FAILED status is always stale (needs retry).
29. `test_is_stale_in_progress_returns_true` - IN_PROGRESS status is always stale.
30. `test_is_stale_complete_old_returns_true` - COMPLETE with 60-day-old timestamp is stale.
31. `test_is_stale_complete_recent_returns_false` - COMPLETE with 1-day-old timestamp is fresh.

#### TestKnowledgeResearchTriggerDeduplication
32. `test_trigger_research_deduplicates_in_progress` - Boundary: trigger_research skips if task already running.
33. `test_trigger_research_restarts_completed_task` - Boundary: trigger_research starts new task if previous is done.

#### TestKnowledgeResearchFetchWikipedia
34. `test_fetch_wikipedia_no_results_returns_none` - Error path: empty search results returns None.
35. `test_fetch_wikipedia_http_error_returns_none` - Error path: HTTP error returns None gracefully.

#### TestExtractMentionsEdgeCases
36. `test_extract_mentions_empty_text` - Boundary: empty string returns empty list.
37. `test_extract_mentions_no_mentions` - No @mentions returns empty list.
38. `test_extract_mentions_quoted_name_with_spaces` - Handles @"Marie Curie" format.
39. `test_extract_mentions_simple_name` - Handles @Socrates format.
40. `test_extract_mentions_multiple_thinkers` - Multiple @mentions in one message.
41. `test_extract_mentions_quoted_prevents_duplicate` - Quoted names don't appear twice.

#### TestGetLanguageInstructionEdgeCases
42. `test_english_returns_empty_string` - English (default) returns empty string (no instruction).
43. `test_spanish_returns_instruction` - Spanish returns "Respond in Spanish".
44. `test_french_returns_instruction` - French returns instruction with "French".
45. `test_unknown_language_code_uses_code_as_name` - Unknown code "zh" uses the code as language name.
46. `test_german_returns_instruction` - German returns instruction with "German".
47. `test_hindi_returns_instruction` - Hindi returns instruction with "Hindi".

### Coverage Impact
- Coverage: 80.45% → 82.03%
- websocket.py: 47% → 66% (+19%)
- knowledge_research.py: 73% (unchanged - existing tests cover those branches)
- thinker.py: 71% (unchanged - agent loop lines require async integration tests)
- New tests: 47 added, 0 skipped
- All 734 tests pass (verified 3x, stable)

---

## Flaky Hunt - Tuesday Sprint (Added 2026-03-03)

**Focus**: Run test suite 5x, identify flaky tests, and fix skipped tests with fixable bugs.

### Analysis Results

Ran backend test suite 5 times consecutively. Results were consistent: 683 passed, 13 skipped (before fixes).
No flaky tests found - all 683 tests passed on every run.

**Skipped tests identified (13 total):**
- 9 in `test_billing_error_integration.py`: Waiting for unimplemented features (#114, #123, #124) - left as-is
- 4 in `test_integration_gaps_feb18.py`: Had fixable bugs in the test code itself

### Tests Fixed (test_integration_gaps_feb18.py)

**File**: `tests/test_integration_gaps_feb18.py`
**Tests Fixed**: 4 previously-skipped tests now run and pass

#### TestConversationsIntegration
1. `test_add_thinkers_with_color_pool_exhaustion_integration` - **Bug fix**: `positions` field was a list `["pos4"]` but the API schema expects a string. Fixed to use string value. Now validates that adding 2 thinkers to a 3-thinker conversation gets unique colors from the remaining palette.
2. `test_create_conversation_triggers_knowledge_research_integration` - **Bug fix**: Used `mocker` fixture from `pytest-mock` which isn't installed. Rewritten with `unittest.mock.patch` (standard library). Also fixed `positions` fields from lists to strings. Now verifies `trigger_research` is called for each thinker when creating a conversation.

#### TestAdminIntegration
3. `test_admin_delete_user_cascades_all_related_data` - **Rewrite**: Original test used `async_session` to create data then verified cascade at DB level, but SQLite doesn't enforce FK cascade with raw SQL DELETE. Rewritten to test the admin API behavior: creates admin+user via direct DB session, uses admin API to delete user, then verifies user no longer appears in admin user list.

#### TestDevOpsIntegration
4. `test_devops_cleanup_with_concurrent_user_activity` - **Bug fix**: Two issues fixed:
   - Wrong query parameter name: `hours_threshold` corrected to `older_than_hours` (matching API)
   - Unused variable `active_session_id` removed after refactoring to use dry_run approach
   Now creates stale session (72h old) and active session, runs cleanup in dry_run mode to verify count, then executes actual cleanup.

### Coverage Impact
- Tests fixed: 4 previously-skipped tests now run (reduced skipped from 13 to 9)
- Suite results after fixes: 687 passed, 9 skipped (verified 3x, stable)
- Coverage: 80.45% (unchanged - the fixed tests cover already-covered paths)
- No flaky tests found in 5 runs

### Remaining Skipped Tests
9 tests in `test_billing_error_integration.py` remain skipped pending:
- Issue #114: BillingError exception class
- Issue #123: FastAPI exception handler for BillingError
- Issue #124: GitHub issue filing background task integration

---

## Integration Gaps - Wednesday Sprint (Added 2026-02-25)

**Focus**: Fill coverage gaps in API modules by testing untested integration paths.

### Root Cause Discovered
`knowledge_service.trigger_research()` spawns `asyncio.create_task()` background tasks
that call the Anthropic API. Existing tests without mocking this method cause slow/hanging
tests, resulting in missing coverage for the thinker creation loop in `conversations.py`.
Fix: patch `app.services.knowledge_research.knowledge_service.trigger_research`.

### Tests Added (test_integration_gaps_feb25_2026.py)

**File**: `tests/test_integration_gaps_feb25_2026.py`
**Tests Added**: 27 integration tests across 3 test classes

#### TestConversationsWithMockedKnowledge (14 tests)
1. `test_create_conversation_with_thinkers_covers_loop` - Create conversation with thinkers, verifies trigger_research called 2x (covers lines 46-61)
2. `test_create_conversation_color_assignment_in_loop` - Colors assigned from pool during thinker loop execution
3. `test_create_conversation_with_custom_thinker_color` - Custom color preserved, not overridden by pool
4. `test_list_conversations_with_message_counts` - list_conversations calculates message_count and total_cost (lines 85-105)
5. `test_list_conversations_none_cost_treated_as_zero` - None-cost messages treated as 0.0
6. `test_get_conversation_not_found_returns_404` - 404 path in get_conversation (line 128)
7. `test_delete_conversation_not_found_returns_404` - 404 path in delete_conversation (lines 145-147)
8. `test_delete_conversation_success` - Successful delete returns status and verifies gone (line 151)
9. `test_add_thinkers_conversation_not_found_404` - 404 when conversation missing (lines 173-175)
10. `test_add_thinkers_exceeds_max_limit_400` - 400 when would exceed 5 thinkers (lines 179-185)
11. `test_add_thinkers_success_with_colors` - Successful thinker addition with color assignment (lines 189-220)
12. `test_send_message_conversation_not_found_404` - 404 when conversation missing (lines 241-243)
13. `test_send_message_creates_message_with_correct_sender` - Message created with correct sender_name (lines 256-268)
14. `test_send_message_cross_session_unauthorized` - Cross-session access returns 404

#### TestFeedbackIntegrationPaths (8 tests)
15. `test_submit_feedback_with_x_forwarded_for_header` - X-Forwarded-For branch in get_client_ip (line 46)
16. `test_submit_feedback_full_data_creates_record` - Full feedback record creation (lines 84-114)
17. `test_submit_feedback_other_type` - 'other' type maps to correct enum
18. `test_submit_feedback_rate_limit_triggers_429` - Rate limit enforcement (lines 77-82)
19. `test_get_pending_feedback_returns_submitted_items` - get_pending returns items (lines 160-182)
20. `test_get_pending_feedback_with_limit_parameter` - Limit parameter respected
21. `test_mark_feedback_processed_success` - Successful processing with GitHub URL (lines 201-220)
22. `test_mark_feedback_processed_not_found_404` - 404 for non-existent feedback (lines 203-207)

#### TestAdminIntegrationPaths (5 tests)
23. `test_list_users_builds_correct_stats_response` - UserWithStats building (lines 35-53)
24. `test_update_spend_limit_user_not_found_404` - 404 for missing user (lines 79-85)
25. `test_update_spend_limit_success_commits_to_db` - Successful update returns full response (lines 87-94)
26. `test_delete_user_not_found_returns_404` - 404 for missing user (lines 113-116)
27. `test_delete_user_returns_success_message` - Success message includes username (line 125)

### Coverage Impact
- All 27 tests pass consistently (verified 3x, ~8.4s per run)
- Coverage improvements in: conversations.py, feedback.py, admin.py
- Root cause fix prevents future test hangs from background API tasks

---

## Edge Case Analysis - Saturday Sprint (Added 2026-02-21)

**Focus**: Add tests for error paths and boundary conditions (Saturday QA focus)

### Tests Added (test_edge_cases_feb21_2026.py)

**File**: `tests/test_edge_cases_feb21_2026.py`
**Tests Added**: 40 edge case tests across 8 test classes

#### TestAuthLogoutEndpoint (2 tests)
1. `test_logout_succeeds_without_auth` - Logout endpoint works without authentication (stateless JWT)
2. `test_logout_succeeds_with_valid_auth` - Logout with valid auth token still succeeds

#### TestRequireAdminEdgeCases (2 tests)
3. `test_admin_endpoint_rejects_non_admin_user` - Non-admin users get 403 from admin endpoints
4. `test_admin_endpoint_rejects_no_auth` - Unauthenticated requests get 401/403 from admin endpoints

#### TestLoginSessionCreation (3 tests)
5. `test_login_creates_session_when_none_exists` - Login creates new session when all sessions deleted
6. `test_login_wrong_password_returns_401` - Invalid password returns 401 with correct message
7. `test_login_nonexistent_user_returns_401` - Non-existent username returns 401

#### TestAuthUpdateEndpoints (4 tests)
8. `test_update_language_returns_user_response` - PATCH /auth/language returns full user object
9. `test_update_profile_returns_user_with_new_name` - PATCH /auth/profile returns updated display name
10. `test_change_password_returns_success_message` - Password change returns success message
11. `test_change_password_wrong_current_password` - Wrong current password returns 400

#### TestRegisterEdgeCases (2 tests)
12. `test_register_duplicate_username_returns_400` - Duplicate username returns 400 with "already taken"
13. `test_register_with_display_name_none` - Registration without display_name field

#### TestAdminSpendLimitEdgeCases (3 tests)
14. `test_update_spend_limit_for_nonexistent_user` - Updating spend limit for non-existent user returns 404
15. `test_delete_nonexistent_user_returns_404` - Deleting non-existent user returns 404
16. `test_update_spend_limit_success_returns_response` - Successful update returns proper response with message

#### TestFeedbackEdgeCases (9 tests)
17. `test_submit_feedback_minimum_valid_message` - Exactly 10 char message (min_length boundary)
18. `test_submit_feedback_maximum_valid_message` - Exactly 5000 char message (max_length boundary)
19. `test_submit_feedback_message_too_short` - 5 char message fails validation
20. `test_submit_feedback_message_too_long` - 5001 char message fails validation
21. `test_submit_feedback_feature_type` - Feedback type "feature" is accepted
22. `test_submit_feedback_with_invalid_type` - Invalid feedback type fails validation
23. `test_get_pending_feedback_no_secret_configured` - Pending endpoint returns 503 when no secret configured
24. `test_submit_feedback_with_all_optional_fields` - All optional fields populated in submission
25. `test_submit_feedback_oversized_screenshot` - Screenshot >7MB fails validation
26. `test_submit_feedback_rate_limiting` - 6th submission in an hour returns 429

#### TestConversationMaxThinkersEdgeCases (5 tests)
27. `test_create_conversation_with_exactly_5_thinkers` - Max 5 thinkers creates successfully
28. `test_create_conversation_with_6_thinkers_rejected` - 6 thinkers in creation fails with 422
29. `test_add_thinkers_when_at_capacity_returns_400` - Adding thinker to full (5) conversation returns 400
30. `test_add_thinkers_to_nonexistent_conversation_returns_404` - Add thinkers to missing conversation
31. `test_add_thinkers_too_many_at_once_returns_400` - Adding batch that exceeds 5 total returns 400

#### TestUnicodeAndSpecialCharacters (4 tests)
32. `test_create_conversation_with_unicode_topic` - Japanese/CJK unicode topic preserved correctly
33. `test_create_conversation_with_arabic_topic` - Arabic RTL text topic preserved correctly
34. `test_create_conversation_with_special_chars_in_thinker_name` - Special chars in thinker name/bio
35. `test_send_message_with_unicode_content` - Chinese unicode message stored and retrieved correctly

#### TestMessageBoundaryConditions (3 tests)
36. `test_send_message_to_nonexistent_conversation` - Message to missing conversation returns 404
37. `test_send_message_to_other_users_conversation` - Cross-user message isolation returns 404
38. `test_get_conversation_with_messages_returns_cost` - Conversation with messages includes total_cost

#### TestConversationListEdgeCases (2 tests)
39. `test_list_conversations_empty_for_new_user` - New user gets empty list
40. `test_list_conversations_includes_zero_cost_messages` - New conversation shows 0 cost and 0 messages

### Coverage Impact
- All 40 tests pass consistently (verified 3x)
- Tests cover error paths in: auth.py, admin.py, feedback.py, conversations.py
- Key edge cases: rate limiting, capacity limits, unicode handling, cross-user isolation, boundary conditions

---

## Flaky Test Hunt - Tuesday Sprint (Added 2026-02-17)

**Focus**: Run full test suite 5 times to identify and fix flaky tests (Tuesday QA focus)

### Test Stability Analysis

**Test Runs**: 5 complete runs of 552 tests each
- **Run 1**: 552 passed, 9 skipped (153.75s)
- **Run 2**: 552 passed, 9 skipped (147.91s)
- **Run 3**: 552 passed, 9 skipped (147.81s)
- **Run 4**: 552 passed, 9 skipped (148.35s)
- **Run 5**: 552 passed, 9 skipped (152.70s)

**Result**: ✅ **NO FLAKY TESTS DETECTED!** All tests passed consistently across 5 runs with identical results.

### Warning Fixes Applied

**Fixed 4 warnings in this session:**

1. **Unawaited Coroutine Warning** - `test_conversations_coverage_sprint_feb9.py:420`
   - **Issue**: `resume_from_idle` was mocked as `AsyncMock` but actual implementation is synchronous
   - **Fix**: Changed mock from `AsyncMock()` to `MagicMock()` to match actual function signature
   - **File**: `tests/test_conversations_coverage_sprint_feb9.py`
   - **Line**: 420

2. **Deprecated HTTP Status Code (3 occurrences)** - `test_regression_prevention_feb2026.py`
   - **Issue**: `HTTP_422_UNPROCESSABLE_ENTITY` is deprecated in Starlette, replaced by `HTTP_422_UNPROCESSABLE_CONTENT`
   - **Fix**: Replaced all 3 usages with the new constant name
   - **Files**: `tests/test_regression_prevention_feb2026.py` lines 129, 310, 320
   - **Impact**: Eliminates deprecation warnings, future-proofs for Starlette updates

### Remaining Warnings (8 total)

**SQLAlchemy Connection Warnings (8 occurrences)** - WebSocket tests
- **Issue**: Database connections not properly closed in WebSocket tests, triggering garbage collector cleanup warnings
- **Affected Tests**:
  - `test_websocket.py::TestWebSocketEndpoint::test_websocket_connect`
  - `test_websocket.py::TestWebSocketEndpoint::test_multiple_clients_receive_messages`
  - `test_websocket.py::TestWebSocketMessageTypes::test_typing_start_message`
  - `test_websocket.py::TestWebSocketMessageTypes::test_typing_stop_message`
  - `test_websocket.py::TestWebSocketMessageTypes::test_pause_state_preserved_on_reconnect` (2x)
  - `test_websocket.py::TestWebSocketMessageTypes::test_unpaused_conversation_sends_resumed_on_connect` (2x)
- **Root Cause**: WebSocket test fixtures don't properly clean up database connections before garbage collection
- **Impact**: Low - warnings only, tests pass successfully
- **Recommendation**: Add explicit connection cleanup in `tests/conftest.py:38` fixture teardown

**Passlib Crypt Deprecation (1 occurrence)**
- **Issue**: Python 3.13 will remove the `crypt` module, which passlib currently uses
- **Impact**: Low - Python 3.13 is future release, passlib will need to update
- **Recommendation**: Monitor passlib updates, no action needed from test suite

### Test Quality Metrics

- **Total Tests**: 552 passing, 9 skipped
- **Flaky Tests**: 0 detected ✅
- **Warnings Fixed**: 4 (from 12 to 8)
- **Test Stability**: 100% consistent across 5 runs
- **Average Run Time**: 149.97s (~2.5 minutes)

### Tests Modified in This Session

1. **test_conversations_coverage_sprint_feb9.py**
   - Fixed `TestSendMessageIdleResume::test_send_message_resumes_idle_paused_conversation`
   - Changed mock from `AsyncMock()` to `MagicMock()` for synchronous `resume_from_idle`
   - Test now runs without RuntimeWarning

2. **test_regression_prevention_feb2026.py**
   - Updated 3 tests to use `HTTP_422_UNPROCESSABLE_CONTENT` instead of deprecated `HTTP_422_UNPROCESSABLE_ENTITY`
   - Tests: `test_feedback_validation_error_returns_422`, `test_empty_message_rejected`, `test_message_content_required`
   - All tests verified passing 3x after changes

## Integration Test Gaps - Wednesday Sprint (Added 2026-02-04)

**Focus**: Add integration tests for untested API endpoints (Wednesday QA focus)

### Conversation API Integration Tests Added (test_conversations_api_integration_feb4.py)

**File**: `tests/test_conversations_api_integration_feb4.py`
**Tests Added**: 18 comprehensive integration tests
**Coverage Impact**: Significantly improved coverage for conversations.py API endpoints (39% baseline)

### List Conversations Tests (4 tests)

1. **test_list_conversations_empty**
   - **What**: GET /api/conversations returns empty array when no conversations exist
   - **Validates**: Empty state handling, proper response structure
   - **Lines Covered**: app/api/conversations.py lines 70-105

2. **test_list_conversations_with_data**
   - **What**: List returns all conversations for session with proper structure
   - **Validates**: Multi-conversation listing, response includes thinkers, message_count, total_cost
   - **Lines Covered**: app/api/conversations.py conversation aggregation logic

3. **test_list_conversations_with_messages_shows_count**
   - **What**: Message count accurately reflects number of messages
   - **Validates**: Message counting aggregation
   - **Lines Covered**: app/api/conversations.py message count calculation

4. **test_list_conversations_ordered_by_created_at_desc**
   - **What**: Conversations ordered newest first
   - **Validates**: Ordering logic, created_at timestamps
   - **Lines Covered**: app/api/conversations.py ordering query

### Get Conversation Tests (3 tests)

5. **test_get_conversation_success**
   - **What**: GET /api/conversations/{id} returns full conversation with messages and thinkers
   - **Validates**: Single conversation retrieval with relationships
   - **Lines Covered**: app/api/conversations.py lines 108-129

6. **test_get_conversation_not_found**
   - **What**: Returns 404 for non-existent conversation
   - **Validates**: Error handling for missing resources
   - **Lines Covered**: app/api/conversations.py error path

7. **test_get_conversation_different_session_not_authorized**
   - **What**: Returns 404 when accessing another session's conversation (not 403 to avoid info leak)
   - **Validates**: Authorization enforcement
   - **Lines Covered**: app/api/conversations.py session ownership check

### Delete Conversation Tests (3 tests)

8. **test_delete_conversation_success**
   - **What**: DELETE /api/conversations/{id} removes conversation
   - **Validates**: Deletion operation, status response
   - **Lines Covered**: app/api/conversations.py lines 132-151

9. **test_delete_conversation_not_found**
   - **What**: Returns 404 for non-existent conversation
   - **Validates**: Deletion error handling
   - **Lines Covered**: app/api/conversations.py deletion error path

10. **test_delete_conversation_cascades_to_messages**
    - **What**: Deleting conversation also deletes all messages
    - **Validates**: CASCADE DELETE behavior
    - **Lines Covered**: Database cascade constraints validation

### Update Thinkers Tests (4 tests)

11. **test_add_thinkers_success**
    - **What**: PUT /api/conversations/{id}/thinkers adds new thinkers
    - **Validates**: Thinker addition, response includes new thinkers
    - **Lines Covered**: app/api/conversations.py lines 154-220

12. **test_add_thinkers_exceeds_max_limit**
    - **What**: Returns 400 when adding would exceed 5 thinker limit
    - **Validates**: Business rule enforcement (max 5 thinkers)
    - **Lines Covered**: app/api/conversations.py max thinker validation

13. **test_add_thinkers_assigns_unique_colors**
    - **What**: New thinkers get colors from available pool
    - **Validates**: Color assignment algorithm avoids duplicates
    - **Lines Covered**: app/api/conversations.py color allocation logic

14. **test_add_thinkers_conversation_not_found**
    - **What**: Returns 404 for non-existent conversation
    - **Validates**: Error handling for thinker addition
    - **Lines Covered**: app/api/conversations.py error path

### Send Message Tests (4 tests)

15. **test_send_message_success**
    - **What**: POST /api/conversations/{id}/messages creates user message
    - **Validates**: Message creation, proper response format
    - **Lines Covered**: app/api/conversations.py lines 223-268

16. **test_send_message_empty_content**
    - **What**: Empty message content rejected with 422
    - **Validates**: Schema validation for required content
    - **Lines Covered**: Pydantic schema validation

17. **test_send_message_conversation_not_found**
    - **What**: Returns 404 for non-existent conversation
    - **Validates**: Error handling for message sending
    - **Lines Covered**: app/api/conversations.py send message error path

18. **test_send_message_uses_display_name**
    - **What**: Message sender_name uses user's display_name if set
    - **Validates**: Display name preference in messages
    - **Lines Covered**: app/api/conversations.py sender name logic

### Test Quality Metrics

- **Test Stability**: All 18 tests pass consistently (verified 3x runs)
- **Integration Coverage**: Tests real API contracts, not mocked responses
- **Error Path Testing**: Comprehensive 404, 422, 400 error scenarios
- **Authorization Testing**: Cross-session access prevention validated
- **Business Logic**: Max thinker limit, color assignment, cascade delete validated

## Edge Case Analysis - Saturday Sprint (Added 2026-01-24)

**Focus**: Test error paths, boundary conditions, and security edge cases (Saturday QA focus)

### Edge Case Tests Added (test_edge_cases_admin_auth_feedback.py)

**File**: `tests/test_edge_cases_admin_auth_feedback.py`
**Tests Added**: 15 comprehensive edge case tests
**Coverage Impact**: Improved error path coverage for admin, auth, feedback, and conversations APIs

### Admin API Edge Cases (5 tests)

1. **test_update_spend_limit_with_negative_value**
   - **What**: Validates that negative spend limits are rejected with 422
   - **Edge Case**: Boundary validation - negative monetary values
   - **Lines Covered**: app/api/admin.py validation logic

2. **test_update_spend_limit_with_zero**
   - **What**: Validates that zero spend limits are rejected (must be > 0)
   - **Edge Case**: Boundary validation - zero value edge case
   - **Lines Covered**: Pydantic validation constraints

3. **test_update_spend_limit_with_extremely_large_value**
   - **What**: Confirms API accepts very large spend limits (>$1M)
   - **Edge Case**: Upper boundary - $10M spend limit handling
   - **Lines Covered**: app/api/admin.py update logic with extreme values

4. **test_list_users_when_no_users_exist**
   - **What**: Tests user listing when only admin exists (minimal dataset)
   - **Edge Case**: Empty result set handling
   - **Lines Covered**: app/api/admin.py lines 35-53 (user list aggregation)

5. **test_admin_cannot_delete_own_account**
   - **What**: Verifies admin cannot self-delete (returns 400)
   - **Edge Case**: Self-referential operation prevention
   - **Lines Covered**: app/api/admin.py lines 104-109 (self-deletion check)

### Auth API Edge Cases (4 tests)

6. **test_register_with_empty_password**
   - **What**: Empty passwords are rejected with validation error
   - **Edge Case**: Boundary validation - empty required fields
   - **Lines Covered**: app/api/auth.py password validation

7. **test_register_with_extremely_long_username**
   - **What**: 500+ character usernames handled (likely rejected by DB constraints)
   - **Edge Case**: Upper boundary - very long string inputs
   - **Lines Covered**: app/api/auth.py registration error paths

8. **test_login_with_username_containing_null_bytes**
   - **What**: Null bytes in username return 401, don't crash server
   - **Edge Case**: Special character handling - null byte injection
   - **Lines Covered**: app/api/auth.py login error handling

9. **test_register_with_whitespace_only_username**
   - **What**: Whitespace-only usernames currently accepted (documents behavior)
   - **Edge Case**: Invalid input - whitespace only
   - **Lines Covered**: app/api/auth.py registration flow

### Feedback API Edge Cases (3 tests)

10. **test_submit_feedback_with_extremely_long_text**
    - **What**: 50,000 character feedback accepted or rejected gracefully
    - **Edge Case**: Very large input handling
    - **Lines Covered**: app/api/feedback.py submission logic

11. **test_submit_feedback_with_special_characters**
    - **What**: Unicode, emojis, HTML tags, quotes preserved
    - **Edge Case**: Special character handling (XSS attempts documented)
    - **Lines Covered**: app/api/feedback.py text processing

12. **test_submit_feedback_with_only_whitespace**
    - **What**: Whitespace-only feedback handling (documents behavior)
    - **Edge Case**: Empty/meaningless input
    - **Lines Covered**: app/api/feedback.py validation

### Conversation API Edge Cases (3 tests)

13. **test_create_conversation_with_empty_topic**
    - **What**: Empty string topics handled (documents behavior)
    - **Edge Case**: Empty required field
    - **Lines Covered**: app/api/conversations.py creation validation

14. **test_list_conversations_cost_calculation_with_null_costs**
    - **What**: Cost aggregation handles null/zero message costs correctly
    - **Edge Case**: Null value aggregation edge case
    - **Lines Covered**: app/api/conversations.py lines 88-105 (cost calculation)

15. **test_add_thinkers_with_all_default_colors**
    - **What**: Color assignment algorithm when all thinkers use default color
    - **Edge Case**: Algorithm behavior with uniform inputs
    - **Lines Covered**: app/api/conversations.py lines 46-61 (color assignment)

### Test Quality Metrics

- **Test Stability**: All 15 tests pass consistently (verified 3x runs)
- **Error Path Coverage**: Significantly improved for admin, auth, feedback APIs
- **Boundary Testing**: Added validation for negative, zero, and extremely large values
- **Security Testing**: XSS attempts, null byte injection, SQL injection documented
- **Edge Case Documentation**: Tests document actual API behavior (accept vs reject)

### API Behavior Insights Discovered

1. **Whitespace usernames**: Currently accepted (potential improvement area)
2. **Large spend limits**: Accepted without upper bound (working as designed)
3. **Null bytes in feedback**: Rejected by API validation
4. **Special characters**: Preserved in feedback (XSS sanitization needed on render)
5. **Empty topics**: Accepted for conversations (flexible design)

### Files Modified

- **Created**: `backend/tests/test_edge_cases_admin_auth_feedback.py` (530 lines)
- **Coverage Impact**: +15 tests covering error paths and boundary conditions

---

---

## Test Refactoring - Friday Sprint (Added 2026-05-22)

**Focus**: Eliminate inline admin-user setup boilerplate across three dated test files; use existing `conftest.py` helpers.

### Refactoring Summary
**Files Refactored**: 3 test files
**Patterns Eliminated**: 9 inline admin-user setups + ~6 inline thinker/error-assertion blocks
**Tests**: 90 tests in scope, all still passing (verified 3x)

**Improvements Made**:
- Replaced 9 instances of manual "register → `update(User).is_admin=True` → (optionally re-login) → build headers" with single-line `create_admin_headers()` calls
- Replaced `assert response.status_code == 401/404` patterns with `assert_unauthorized()` / `assert_not_found()` for clearer intent and consistent error-detail checks
- Replaced inline `{"name": ..., "bio": ..., "positions": ..., "style": ...}` thinker dict with `make_simple_thinker_list()`
- Removed now-unused `sqlalchemy.update` and `app.models.User` imports
- Identified an anti-pattern in `test_edge_cases_feb21_2026.py`: tests were performing an unnecessary `/api/auth/login` re-login after setting `is_admin=True`. Because `require_admin` re-reads `is_admin` from the DB at request time, the original registration token already works — removed 3 redundant login round-trips.

**Refactoring Patterns Applied**:
1. **Admin setup consolidation**: ~15 lines → 1 line (`create_admin_headers(client, db_session, username, password)`)
2. **Error assertion helpers**: `assert response.status_code == 4xx` + manual detail check → `assert_not_found(response, "...")` / `assert_unauthorized(response)`
3. **Thinker dict consolidation**: inline dict → `make_simple_thinker_list(name=..., bio=..., positions=..., style=...)`

### Refactored Files

**File**: `tests/test_integration_gaps_mar2026.py`
**Refactorings**: 3 admin setups, 2 `assert_unauthorized`, 1 `assert_not_found`, 1 thinker list
**Impact**: ~55 lines of boilerplate removed; reads as intent rather than DB plumbing

**File**: `tests/test_integration_gaps_feb25_2026.py`
**Refactorings**: 5 admin setups, 2 `assert_not_found`
**Impact**: ~70 lines of boilerplate removed; centralizes a previously-duplicated DB update pattern

**File**: `tests/test_edge_cases_feb21_2026.py`
**Refactorings**: 3 admin setups (each had a redundant re-login step that is now removed)
**Impact**: ~30 lines removed; removes a misleading pattern that suggested admin promotion required re-login

### Test Coverage Maintained

**Before Refactoring**: 1538 tests passing, 98.83% coverage
**After Refactoring**: 1538 tests passing, 98.83% coverage (verified across 3 sequential runs)
**Test Stability**: 100% — no behavior changes, no new tests, no removed tests

**Benefits**:
- Removes ~155 lines of boilerplate
- Eliminates 3 unnecessary HTTP round-trips per session (the redundant re-login pattern)
- Makes the test intent obvious: "I need admin headers" instead of 15 lines of DB plumbing
- New test authors are more likely to discover and reuse the helpers
- Coverage and behavior unchanged

---

## Test Refactoring - Friday Sprint (Added 2026-01-23)

**Focus**: Improve test maintainability by consolidating duplicate test setup code

### Refactoring Summary
**Files Refactored**: 2 test files
**Patterns Eliminated**: ~45 instances of duplication

**Improvements Made**:
- Replaced ~25 instances of manual auth header creation with `get_auth_headers()` helper
- Replaced ~18 instances of manual thinker dict creation with `create_thinker_input()` helper
- Reduced code duplication and improved test readability

**Refactoring Patterns Applied**:
1. **Auth header consolidation**: `{"Authorization": f"Bearer {data['access_token']}"}` → `get_auth_headers(client, username, password)`
2. **Thinker dict consolidation**: `{"name": "X", "bio": "Y", ...}` → `create_thinker_input("X", "Y", ...)`
3. **Leveraged existing conftest.py helpers** instead of inline duplication

### Refactored Files

**File**: `tests/test_conversations_edge_cases.py`
**Refactorings**: ~25 auth headers + ~15 thinker dicts
**Impact**: Improved readability, easier maintenance, consistent test patterns

**File**: `tests/test_conversations_coverage_sprint.py`
**Refactorings**: ~3 thinker dicts with default color
**Impact**: More concise test setup, clearer test intent

### Test Coverage Maintained

**Before Refactoring**: 421 tests passing
**After Refactoring**: 421 tests passing
**Test Stability**: 100% - all tests pass consistently

**Benefits**:
- Reduced lines of code without changing behavior
- Easier to update test patterns across the suite
- More consistent use of conftest.py helpers
- Better adherence to DRY principle
- No coverage loss or test failures

---

## Integration Test Gaps - Conversation API (Issue #551, QA Agent Wednesday 2026-01-21)

**Focus**: Add integration tests for untested conversation API endpoints covering idle-pause auto-resume, color assignment, and display name fallback.

### Conversation API Integration Tests (test_conversations_integration_gaps.py)

**8 new tests added covering previously untested integration flows:**

#### Idle-Pause Auto-Resume (lines 245-254 in conversations.py)

**test_idle_pause_auto_resume_on_user_message** (test_conversations_integration_gaps.py:13-53)
- Integration: When user sends message to idle-paused conversation, it should auto-resume
- Validates thinker_service.pause_for_idle() correctly pauses conversation
- Validates sending user message clears idle-pause state
- Edge case: Distinguishes idle-pause from manual pause

**test_regular_pause_not_affected_by_auto_resume** (test_conversations_integration_gaps.py:55-93)
- Edge case: Manual pause (not idle-pause) should NOT auto-resume on user messages
- Validates thinker_service.pause_conversation() remains active after message
- Ensures auto-resume only affects idle-paused conversations

#### Add Thinkers Color Pool (lines 188-198 in conversations.py)

**test_add_thinkers_uses_available_colors_from_pool** (test_conversations_integration_gaps.py:99-157)
- Integration: Adding thinkers with default color picks from available pool
- Validates color assignment avoids duplicates
- Tests PUT /api/conversations/{id}/thinkers endpoint
- Ensures new thinker gets color not in existing_colors set

**test_add_thinkers_respects_custom_color** (test_conversations_integration_gaps.py:159-206)
- Edge case: Custom colors (non-default) are preserved when adding thinkers
- Validates custom color bypasses pool assignment logic
- Tests explicit color specification in thinker creation

**test_add_thinkers_color_pool_exhaustion** (test_conversations_integration_gaps.py:208-253)
- Edge case: When color pool is exhausted (all 5 colors used), adding thinker still works
- Validates graceful handling of empty available_colors list
- Tests maximum capacity scenario (5 thinkers)

#### Display Name Fallback (lines 257-265 in conversations.py)

**test_send_message_uses_display_name_when_set** (test_conversations_integration_gaps.py:259-298)
- Happy path: Messages use user's display_name if set
- Validates PATCH /api/auth/profile updates display name
- Validates POST /api/conversations/{id}/messages uses updated display_name
- Tests sender_name field in message response

**test_send_message_falls_back_to_username_when_no_display_name** (test_conversations_integration_gaps.py:300-334)
- Edge case: Messages use username as fallback when display_name is None
- Validates default behavior for users without display name
- Tests sender_name field defaults correctly

**test_send_message_updates_sender_name_after_profile_change** (test_conversations_integration_gaps.py:336-386)
- Integration: Messages reflect current display_name, not cached value
- Validates real-time name updates across multiple messages
- Tests: First message (username), update profile, second message (display_name)
- Ensures no stale cached user data affects message creation

### Coverage Impact

**Before**: Backend 75% (409 tests)
**After**: Backend ~76% (417 tests)
**Improvement**: +1% coverage, +8 tests

**Files Enhanced**:
- test_conversations_integration_gaps.py (new file, 386 lines)
- conversations.py coverage increased (idle-pause, color pool, display name now tested)
- Integration with thinker_service validated

### Benefits of Conversation API Integration Tests

1. **Idle-Pause Auto-Resume**: Validates conversation auto-resumes when user returns after idle timeout
2. **Color Assignment**: Ensures thinkers get unique colors without conflicts or pool exhaustion issues
3. **Display Name**: Validates user identity is correctly displayed in messages with proper fallback
4. **Real Integration**: Tests actual API endpoints with database, not just mocked services
5. **Edge Cases**: Covers color pool exhaustion, profile updates, idle vs manual pause distinction

---

## Integration Test Gaps - Thinker Knowledge API (Issue #115, QA Agent Wednesday 2025-12-31)

**Focus**: Add integration tests for untested thinker knowledge research API endpoints.

### Thinker Knowledge API Integration Tests (test_thinker_knowledge_integration.py)

**13 new tests added covering the full knowledge research lifecycle:**

#### GET /api/thinkers/knowledge/{name}

**test_get_existing_knowledge_success** (test_thinker_knowledge_integration.py:69-99)
- Happy path: Fetch existing completed knowledge from database
- Validates complete knowledge with research_data is returned correctly
- Edge case: Returns research_data JSON object with bio and works

**test_get_knowledge_triggers_research_for_new_thinker** (test_thinker_knowledge_integration.py:101-133)
- Edge case: First request for new thinker triggers background research
- Creates PENDING knowledge entry in database
- Validates trigger_research() is called to start background job
- Returns pending status while research is queued

**test_get_knowledge_refreshes_stale_data** (test_thinker_knowledge_integration.py:135-167)
- Edge case: Stale completed knowledge triggers background refresh
- Returns existing stale data immediately (non-blocking)
- Validates is_stale() check and refresh trigger
- Ensures users get data while refresh happens in background

**test_get_knowledge_returns_failed_research** (test_thinker_knowledge_integration.py:169-198)
- Edge case: Failed research returns error_message
- Validates FAILED status with descriptive error
- Empty research_data for failed lookups

#### GET /api/thinkers/knowledge/{name}/status

**test_get_status_for_completed_research** (test_thinker_knowledge_integration.py:204-233)
- Happy path: Check status of completed research
- Validates has_data=true and updated_at timestamp
- Lightweight endpoint for polling without fetching full data

**test_get_status_for_pending_research** (test_thinker_knowledge_integration.py:235-262)
- Edge case: PENDING research shows has_data=false
- Used to poll before data is ready

**test_get_status_for_nonexistent_thinker** (test_thinker_knowledge_integration.py:264-283)
- Edge case: Nonexistent thinker returns PENDING status
- Does NOT create database entry (read-only check)
- updated_at is None when no entry exists

**test_get_status_for_in_progress_research** (test_thinker_knowledge_integration.py:285-311)
- Edge case: IN_PROGRESS status during active research
- Distinguishes between PENDING (queued) and IN_PROGRESS (actively running)

#### POST /api/thinkers/knowledge/{name}/refresh

**test_refresh_existing_knowledge** (test_thinker_knowledge_integration.py:317-348)
- Happy path: Force refresh of existing completed knowledge
- Re-triggers research even if data is recent
- Returns current status while refresh queues

**test_refresh_creates_entry_for_new_thinker** (test_thinker_knowledge_integration.py:350-380)
- Edge case: Refresh on new thinker creates database entry
- get_or_create_knowledge() ensures entry exists before trigger
- Validates both entry creation and research trigger

**test_refresh_retriggers_failed_research** (test_thinker_knowledge_integration.py:382-412)
- Edge case: Refresh can retry previously failed research
- Allows manual retry of failures without waiting for automatic retry
- Returns FAILED status but queues new research attempt

#### Full Lifecycle Integration Tests

**test_full_lifecycle_trigger_poll_retrieve** (test_thinker_knowledge_integration.py:418-475)
- Integration: Complete knowledge research lifecycle
- Step 1: GET triggers research for new thinker (PENDING)
- Step 2: Poll /status shows IN_PROGRESS during research
- Step 3: GET retrieves completed knowledge with full data
- Validates: Database state transitions through entire flow

**test_refresh_updates_stale_completed_knowledge** (test_thinker_knowledge_integration.py:477-516)
- Integration: Refresh endpoint updates stale data
- Creates stale completed knowledge
- Forces refresh via POST /refresh
- Simulates research completion with new data
- Validates: New data replaces old data after refresh

### Coverage Impact

**Before**: Backend 75.15% (230 tests)
**After**: Backend 75.84% (243 tests)
**Improvement**: +0.69% coverage, +13 tests

**Files Enhanced**:
- test_thinker_knowledge_integration.py (new file, 516 lines)
- thinkers.py coverage increased (knowledge endpoints now tested)
- knowledge_research.py integration validated

### Benefits of Knowledge API Integration Tests

1. **API Contract Validation**: Ensures knowledge endpoints return correct schemas
2. **Lifecycle Coverage**: Tests full flow from trigger → poll → retrieve
3. **Edge Case Handling**: Validates pending, in-progress, failed, and stale states
4. **Background Research**: Confirms non-blocking research triggers work correctly
5. **Polling Patterns**: Documents lightweight /status endpoint for UI polling
6. **Refresh Mechanism**: Tests manual refresh for stale or failed data
7. **Database Integration**: Validates state transitions in real database

**Key Integration Patterns Tested:**
- Non-blocking research triggers (trigger_research doesn't block API response)
- Polling-based status checks (lightweight /status for UI updates)
- Graceful degradation (returns stale data while refreshing)
- Retry mechanisms (refresh endpoint for failed research)
- State machine transitions (PENDING → IN_PROGRESS → COMPLETE/FAILED)

## Coverage Sprint - Conversation API Edge Cases (Issue #589, QA Agent Monday 2026-01-26)

**Focus**: Target lowest coverage file (app/api/conversations.py at 39%) with edge case tests for error paths, validation, and state management.

**Coverage Impact**: Added explicit edge case tests for error handling, validation, and state management in conversations API.

**File**: `tests/test_conversations_coverage_sprint_jan26.py`

### List Conversations Edge Cases (2 tests)

**test_list_conversations_when_empty** (test_conversations_coverage_sprint_jan26.py:20-31)
- **Lines Covered**: app/api/conversations.py lines 76-85 (list endpoint when no conversations exist)
- Validates that GET /api/conversations returns empty array when user has no conversations
- Edge case: New user with no conversation history
- Expected behavior: Returns 200 with empty list `[]`

**test_list_conversations_with_null_costs** (test_conversations_coverage_sprint_jan26.py:33-72)
- **Lines Covered**: app/api/conversations.py lines 88-104 (cost calculation with null values)
- Validates that list_conversations handles messages with null cost values gracefully
- Edge case: Messages created before cost tracking was implemented or user messages with no cost
- Tests `sum(msg.cost or 0.0 for msg in conv.messages)` logic
- Expected behavior: Null costs treated as 0.0, no exceptions raised

### Get Conversation Error Paths (1 test)

**test_get_conversation_returns_404_for_nonexistent** (test_conversations_coverage_sprint_jan26.py:78-88)
- **Lines Covered**: app/api/conversations.py lines 126-129 (404 error path)
- Validates that GET /api/conversations/{invalid_uuid} returns 404
- Edge case: User requests conversation that doesn't exist
- Expected behavior: Returns 404 with "Conversation not found" detail

### Delete Conversation Error Paths (2 tests)

**test_delete_conversation_returns_404_for_nonexistent** (test_conversations_coverage_sprint_jan26.py:94-106)
- **Lines Covered**: app/api/conversations.py lines 145-147 (404 error path)
- Validates that DELETE /api/conversations/{invalid_uuid} returns 404
- Edge case: User tries to delete nonexistent conversation
- Expected behavior: Returns 404 with "Conversation not found" detail

**test_delete_conversation_returns_success_response** (test_conversations_coverage_sprint_jan26.py:108-150)
- **Lines Covered**: app/api/conversations.py line 151 (success response)
- Validates that DELETE /api/conversations/{valid_id} returns success object
- Tests successful delete operation returns `{"status": "deleted"}`
- Expected behavior: Returns 200 with status object, conversation removed from database

### Add Thinkers Validation (2 tests)

**test_add_thinkers_when_at_max_limit** (test_conversations_coverage_sprint_jan26.py:156-213)
- **Lines Covered**: app/api/conversations.py lines 173-185 (max thinker validation)
- Validates that PUT /api/conversations/{id}/thinkers rejects additions when at 5 thinker limit
- Edge case: Conversation already has 5 thinkers (max), user tries to add more
- Tests validation error message includes useful context: "Cannot add X thinkers. Conversation has 5/5 thinkers. Maximum is 5 total."
- Expected behavior: Returns 400 with descriptive error message

**test_add_thinkers_when_color_pool_exhausted** (test_conversations_coverage_sprint_jan26.py:215-269)
- **Lines Covered**: app/api/conversations.py lines 188-199, 217-220 (color pool management)
- Validates that adding thinkers when all 5 default colors are in use still works
- Edge case: 4 thinkers with explicit colors, adding 5th with default color
- Tests color assignment from available pool: `available_colors = [c for c in all_colors if c not in existing_colors]`
- Expected behavior: 5th thinker gets last available color from pool

### Send Message Idle Pause (1 test)

**test_send_message_auto_resumes_from_idle_pause** (test_conversations_coverage_sprint_jan26.py:275-328)
- **Lines Covered**: app/api/conversations.py lines 245-254 (idle pause auto-resume)
- Validates that sending message to idle-paused conversation auto-resumes it
- Integration: Mocks thinker_service.is_idle_paused() and resume_from_idle()
- Tests auto-resume flow: check if idle → resume → broadcast RESUMED message
- Expected behavior: Conversation resumes, RESUMED WebSocket message sent to clients

## Saturday Edge Case Analysis Sprint (Added 2026-01-31)

**Focus**: Add comprehensive edge case tests for error paths, boundary conditions, and security validation

### Conversation Edge Case Tests
**File**: `backend/tests/test_conversations_edge_cases.py`
**Purpose**: Test error paths, boundary conditions, and security edge cases for conversation management
**Lines Covered**: app/api/conversations.py - error handling, validation, authorization

**Tests Added (13 total)**:

#### Conversation Creation Edge Cases (5 tests)
- ✅ `test_create_conversation_with_no_thinkers` - Empty thinkers list rejected with 422
  - Edge case: Required list field validation
  - Validates that conversations require at least one thinker
  - Tests Pydantic min_items constraint

- ✅ `test_create_conversation_with_too_many_thinkers` - Max thinkers boundary (11 thinkers)
  - Edge case: Upper boundary for list size
  - Tests max_items validation (if defined)
  - System currently allows unlimited thinkers, test verifies graceful handling

- ✅ `test_create_conversation_with_duplicate_thinker_names` - Duplicate thinker names allowed
  - Edge case: Duplicate entries in list
  - Validates system handles duplicates without crashing
  - Tests that color assignment still works with duplicates

- ✅ `test_create_conversation_with_very_long_topic` - Topic with 5000+ characters
  - Edge case: Large text input validation
  - Tests max_length constraint on topic field
  - System currently allows long topics, test verifies no crashes

- ✅ `test_create_conversation_with_special_characters_in_thinker_fields` - XSS/Unicode handling
  - Edge case: Special characters, emojis, HTML, script tags
  - Tests: `<script>alert('xss')</script>`, `🎉`, `你好`, `"quotes"`, `&<>` symbols
  - Validates backend preserves content without sanitization (frontend's job)
  - Security: No SQL injection, no crashes from special chars

#### Conversation Retrieval Edge Cases (3 tests)
- ✅ `test_get_nonexistent_conversation_different_user` - Cross-user authorization
  - Edge case: Authorization boundary - session isolation
  - User2 attempts to access User1's conversation
  - Returns 404 (not 403) to prevent information disclosure
  - Security: Conversation ID existence not leaked

- ✅ `test_list_conversations_when_session_has_none` - Empty result set
  - Edge case: No conversations exist for session
  - Tests endpoint returns empty list (not error)
  - Validates empty state handling

- ✅ `test_get_conversation_after_session_expired` - Invalid/expired token
  - Edge case: Token expiration, malformed JWT
  - Tests with invalid Bearer token
  - Returns 401 (unauthorized) not crash

#### Conversation Deletion Edge Cases (2 tests)
- ✅ `test_delete_nonexistent_conversation` - Delete non-existent resource
  - Edge case: Idempotency check
  - DELETE on fake UUID returns 404
  - Tests error handling for missing resources

- ✅ `test_delete_conversation_with_many_messages` - Cascade deletion
  - Edge case: Foreign key cascade performance
  - Creates conversation, deletes it, verifies cascade
  - Tests database CASCADE constraints work correctly
  - Validates 200 OK response with {"status": "deleted"}

#### Message Creation Edge Cases (3 tests)
- ✅ `test_create_message_with_empty_content` - Empty message content
  - Edge case: Required field validation
  - POST with empty string content rejected with 422
  - Tests min_length validation on message content

- ✅ `test_create_message_with_extremely_long_content` - 100k character message
  - Edge case: Large input validation
  - Tests max_length constraint (if defined)
  - System currently allows, test verifies no memory issues

- ✅ `test_create_message_in_nonexistent_conversation` - Invalid foreign key
  - Edge case: Referential integrity
  - POST to fake conversation UUID returns 404
  - Tests foreign key constraint handling

**Coverage Impact**:
- app/api/conversations.py: Error paths now covered (previously 39%, targeting 60%)
- Improved validation testing for all endpoints
- Security edge cases (XSS, SQL injection attempts, authorization leaks) now tested
- Boundary conditions (empty lists, very long strings, special chars) covered

**Edge Case Categories Covered**:
1. **Validation**: Empty/missing/too-long fields
2. **Security**: XSS, authorization boundaries, information disclosure
3. **Boundary Conditions**: Min/max values, special characters, Unicode
4. **Error Paths**: 404s, 401s, 422s
5. **Idempotency**: DELETE non-existent, double operations
6. **Data Integrity**: Foreign keys, cascade deletes, session isolation

## 0.3 Integration Gaps - Wednesday (Added 2026-02-11)

**Focus**: Add integration tests for untested API endpoints to improve coverage

### 0.3.1 Admin API Integration Tests
**File**: `backend/tests/test_integration_gaps_wednesday.py::TestAdminIntegration`
**Target**: `app/api/admin.py` (60% → 75% coverage)
**Purpose**: Test admin user management endpoints with various scenarios

**Tests Added (3 total)**:

1. **`test_list_users_with_multiple_users_and_conversations`**
   - Validates GET /api/admin/users returns users with correct conversation counts
   - Creates 2 users: one with 2 conversations, one with 0
   - Verifies conversation_count field calculated correctly via SQL join
   - Coverage: Lines 35-53 (list users query with aggregation)

2. **`test_list_users_when_no_conversations_exist`**
   - Validates GET /api/admin/users when no conversations exist for any user
   - All users should have conversation_count = 0
   - Edge case: Ensures LEFT JOIN doesn't break when right side is empty
   - Coverage: Lines 35-53 (handles zero conversation case)

3. **`test_delete_nonexistent_user_returns_404`**
   - Validates DELETE /api/admin/users/{id} with nonexistent user ID
   - Verifies proper 404 error response
   - Coverage: Lines 113-116 (user not found error path)

**Coverage Impact**: Brings admin.py from 60% to ~75%

### 0.3.2 DevOps API Integration Tests
**File**: `backend/tests/test_integration_gaps_wednesday.py::TestDevOpsIntegration`
**Target**: `app/api/devops.py` (62% → 75% coverage)
**Purpose**: Test DevOps maintenance endpoints with edge cases

**Tests Added (3 total)**:

1. **`test_cleanup_stale_sessions_when_no_sessions`**
   - Validates DELETE /api/devops/cleanup/stale-sessions with no stale sessions
   - Verifies deleted_count = 0 when nothing to delete
   - Tests proper secret authentication with patched settings
   - Coverage: Lines 139-145 (cleanup with zero results)

2. **`test_cleanup_orphans_when_no_orphans`**
   - Validates DELETE /api/devops/cleanup/orphans with no orphaned records
   - Verifies details dict structure: {orphan_conversations: 0, orphan_messages: 0}
   - Tests edge case of cleanup operations returning empty results
   - Coverage: Lines 186-196 (orphan cleanup with zero results)

3. **`test_devops_health_endpoint`**
   - Validates GET /api/devops/health returns 200 with status="ok"
   - Tests DevOps API authentication flow
   - Uses mock settings to inject test secret
   - Coverage: Lines 274 (health endpoint)

**Coverage Impact**: Brings devops.py from 62% to ~75%

### 0.3.3 Limitations & Future Work

**Omitted Tests (due to Claude API call timeouts)**:
- Conversation API tests (would trigger real Anthropic API calls)
- Feedback API tests (model schema mismatch discovered - needs refactoring)

These will be added in future QA iterations with proper API mocking.

**Test Stability**: All 6 tests verified passing with 3 consecutive runs (no flakiness)

### 0.3.4 Summary

**Files Modified**:
- `backend/tests/test_integration_gaps_wednesday.py` - Added 6 new integration tests

**Total Impact**:
- 6 integration tests added (3 admin + 3 devops)
- Improved admin.py coverage: 60% → ~75%
- Improved devops.py coverage: 62% → ~75%
- Tests use proper mocking patterns (patch for settings, get_password_hash for users)

**Technical Patterns Demonstrated**:
- `patch("app.api.devops.get_settings")` for testing authenticated endpoints
- `get_password_hash()` for creating test users with hashed passwords
- `assert_success_response()` / `assert_error_response()` helpers from conftest.py
- Direct database setup via SQLAlchemy models for complex test scenarios



---

## Regression Prevention - Sunday QA (Added 2026-05-10)

**Focus**: Pin down behavioral invariants in core services that lack explicit regression guards. Since recent commits in the window have been test-only, these tests guard subtle branches and boundary semantics that, if changed inadvertently, would cause silent product regressions.

### Analysis Results

Coverage before: 91.36% (1389 tests pass), coverage after: 91.36% (1419 tests pass).
The new tests do not raise coverage but harden existing code paths against silent regressions.

### Tests Added (test_regression_prevention_may10_2026.py)

**File**: `tests/test_regression_prevention_may10_2026.py` (30 new tests)

#### TestShouldRespondSelfFollowupSuppression
1. `test_self_followup_suppressed_to_low_probability` - When the last message is from the same thinker AND no @mention, base_probability drops to 0.05. Guards against runaway monologues if the suppression branch is removed.
2. `test_at_mentioning_self_bypasses_self_followup_suppression` - Self @mention bypasses the 0.05 floor (the `not was_at_mentioned` clause). Guards the dual-condition logic intact.

#### TestShouldRespondProbabilityCaps
3. `test_at_mention_does_not_exceed_0_98` - @mention sets base_probability to 0.98 (not 1.0). Statistically detects regression to 1.0.
4. `test_consecutive_silence_boost_capped_at_0_9` - Consecutive-silence boost is hard-capped at 0.9 — preserves the silent-skip branch and natural variability.

#### TestIsMentionedEmptyThinkerName
5. `test_empty_thinker_name_does_not_raise` - Defensive guard: empty thinker_name does not trigger IndexError on `.split()[0]` (line 105 fallback).
6. `test_empty_thinker_name_with_empty_text_does_not_raise` - Companion: both inputs empty also does not raise.

#### TestExtractThinkingDisplayStarterDedup
7. `test_text_starting_with_hmm_does_not_get_double_prefix` - The `if not text.lower().startswith(starter_prefixes)` check prevents "Hmm... Hmm, ..." double-prefix output.
8. `test_text_starting_with_let_me_does_not_get_double_prefix` - Companion test for the "Let me" starter prefix.

#### TestExtractMentionsQuotedDedup
9. `test_quoted_name_followed_by_bare_first_word_does_not_duplicate` - The dedup check (`if name not in mentions`) prevents the simple_pattern from double-listing names already captured by the quoted_pattern.
10. `test_simple_pattern_alone_works_for_punctuation_terminator` - `@Plato!` (with trailing punctuation) extracts cleanly as `["Plato"]` — pins down the regex contract.

#### TestGetUserNameSkipsUnnamedUsers
11. `test_user_message_without_sender_name_is_skipped` - Truthiness check on sender_name (line 1417) means user messages with sender_name=None are skipped.
12. `test_user_message_with_empty_string_sender_name_is_skipped` - Empty string sender_name (also falsy) is skipped — protects against "None" prompts.

#### TestConversationRoomBroadcastDeactivation
13. `test_broadcast_deactivates_room_when_all_clients_fail` - When every WebSocket fails during broadcast, all are purged and is_active flips to False — preserves the agent-pause-on-empty-room contract.
14. `test_broadcast_to_empty_room_does_not_raise` - Broadcasting to a room with zero connections is a silent no-op.

#### TestConnectionManagerLifecycle
15. `test_connect_creates_room_for_new_conversation` - First connect() creates the ConversationRoom entry (not the defaultdict sentinel).
16. `test_disconnect_is_noop_for_unknown_conversation` - disconnect for an unknown conversation_id does not raise and does not auto-create a phantom room.

#### TestThinkerServicePauseIdempotency
17. `test_pause_conversation_called_twice_is_idempotent` - Set semantics ensure duplicate pause events from clients do not corrupt state.
18. `test_resume_unpaused_conversation_is_safe` - Uses set.discard() (not remove()) so resuming a never-paused conversation does not raise KeyError.

#### TestSpendStatusBoundaries
19. `test_is_near_limit_true_at_exactly_85_percent` - is_near_limit threshold is `>=` 85%, not `>`. UI yellow-flag preserved at the boundary.
20. `test_is_near_limit_false_at_84_99_percent` - Just below 85% does not trigger the warning — guards against threshold drift.
21. `test_zero_spend_limit_treats_user_as_at_100_percent` - When spend_limit=0, percentage falls back to 100 (no division-by-zero crash).
22. `test_can_user_spend_returns_false_for_unknown_user` - Unknown user denied by default — protects against forged JWTs for deleted users.
23. `test_spend_status_dataclass_clamps_percentage_to_100` - percentage_used clamped to 100 even when actual usage exceeds limit (UI progress bar safety).

#### TestKnowledgeRefreshNoStaleEntries
24. `test_refresh_stale_returns_zero_for_only_fresh_entries` - WHERE clause filtering on (status==COMPLETE AND old timestamp) preserves fresh data and avoids re-refreshing FAILED entries.

#### TestKnowledgeIsStaleNaiveAware
25. `test_is_stale_with_naive_recent_timestamp` - The .replace(tzinfo=UTC) call lets is_stale work uniformly with SQLite (naive) and PostgreSQL (aware) datetimes.
26. `test_is_stale_with_naive_old_timestamp` - Companion: confirms the 30-day threshold still triggers correctly for old naive timestamps.

#### TestLanguageInstructionMappingGap
27. `test_hindi_maps_to_full_name_in_thinker_service` - LANGUAGE_NAMES["hi"] mapping (added in fix(i18n) #570) produces "Respond in Hindi.", not "Respond in hi.".
28. `test_unknown_language_code_falls_back_to_code_itself` - Defensive fallback: unknown codes use the code as the language name.
29. `test_english_returns_empty_instruction` - English path returns empty string (saves prompt tokens for the default case).
30. `test_auth_api_still_rejects_hindi` - Documents the auth/service language gap — auth schema rejects `hi` while ThinkerService supports it. When the gap is closed, this test will fail and prompt the developer to update the all-valid-codes test.

### Stability Verification

All 30 tests verified passing across 3 consecutive runs (no flakiness). Probability-based tests use enough trials (200-500) to be statistically reliable across random seeds.

---

## Flaky Test Hunt - Tuesday QA (Added 2026-05-12)

**Focus**: Lock down flakiness-prone branches in `app/services/thinker.py` with fully deterministic mocks — no seed-based luck, no real wall-clock dependency. Close branch coverage gap 965->968 (already-ends-in-punctuation case in `_extract_thinking_display`).

### Analysis Results

- Full backend suite (1433 passed, 9 skipped) executed cleanly before adding the new file.
- Probabilistic / timing subset (63 tests matching `bubble`, `split`, `random`, `should_respond`, `should_prompt`, `thinking_display`) was run **5 times in a row** — all green every run. No flakiness detected.
- Coverage before: 96.34% (27 partial branches). Coverage after: 96.38% (26 partial branches). Branch 965->968 closed.

### Tests Added (test_flaky_hunt_may12_2026.py)

**File**: `tests/test_flaky_hunt_may12_2026.py` (16 new tests)

#### TestSplitBubblesStrategyBranchesDeterministic
1. `test_strategy_single_bubble_when_roll_below_025_and_text_under_250` - With `random.random()` mocked to 0.0 and a 100-char text, the single-bubble early-return at line 711-712 fires deterministically — no seed lottery.
2. `test_strategy_single_bubble_skipped_when_text_at_least_250_chars` - The compound condition at line 711 requires BOTH `roll<0.25` AND `len<250`. With a 358-char text and roll=0.0, the early return is skipped and the function falls through to aggressive splitting.
3. `test_strategy_aggressive_uses_randint_80_120` - `0.25 <= roll < 0.45` exercises the aggressive branch (line 718). Verified by asserting `random.randint` was called with exactly `(80, 120)`.
4. `test_strategy_normal_uses_randint_120_180` - `0.45 <= roll < 0.80` exercises the normal branch (line 720). Verified by asserting `random.randint` was called with exactly `(120, 180)`.
5. `test_strategy_relaxed_uses_randint_180_250` - `roll >= 0.80` exercises the relaxed branch (line 722). Verified by asserting `random.randint` was called with exactly `(180, 250)`.
6. `test_strategy_boundary_at_025_does_not_take_single_bubble` - At exactly `roll==0.25` the strict `<` comparison must NOT fire single-bubble; locks down inequality direction so a refactor to `<=` is caught.
7. `test_strategy_boundary_at_045_does_not_take_aggressive` - At exactly `roll==0.45` the strict `<` must NOT fire aggressive; normal `(120, 180)` is chosen instead.
8. `test_strategy_boundary_at_080_does_not_take_normal` - At exactly `roll==0.80` the strict `<` must NOT fire normal; relaxed `(180, 250)` is chosen instead.

#### TestExtractThinkingDisplayPunctuationBranch
9. `test_text_ending_in_period_does_not_get_ellipsis` - When the cleaned text already ends with `.`, line 965 False branch (965->968) fires and no extra `...` is appended. Engineered so the final 30 chars are a single space-free word, bypassing the word-boundary truncation (lines 816-820).
10. `test_text_ending_in_exclamation_does_not_get_ellipsis` - Same branch for `!` terminator.
11. `test_text_ending_in_question_does_not_get_ellipsis` - Same branch for `?` terminator.
12. `test_text_ending_in_triple_dot_does_not_get_ellipsis` - Same branch for existing `...` — verifies no double-`......` produced.
13. `test_text_not_ending_in_punctuation_gets_ellipsis_appended` - Positive control: text ending in a letter triggers the True branch (965->966) and `...` is appended. Paired with the False-branch tests so a flipped condition is caught by BOTH branches in this file.

#### TestRandomBoundaryStrictnessRegression
14. `test_should_respond_silence_check_strict_at_exactly_015` - `random.random()==0.15` at line 1597 must NOT trigger the 15% silence cutoff (strict `<`). Verified by asserting BOTH random calls happen (silence check + response probability) and the final result is True.
15. `test_should_prompt_user_strict_at_threshold_returns_false` - `random.random()==prompt_probability` (both 0.15 at speed_mult=1.0) must NOT trigger the prompt at line 1470 (strict `<`).
16. `test_should_prompt_user_below_threshold_returns_true` - Positive control: `random.random()==0.0` is strictly below the 0.15 prompt_probability, so the prompt fires. Paired with the boundary-equality test to lock down direction.

### Stability Verification

All 16 tests verified passing across 3 consecutive runs (no flakiness). The full backend suite (1449 passed, 9 skipped) also runs cleanly with the new tests included.

## Edge Cases - Saturday Sprint (Added 2026-05-16)

**Focus**: Hard-to-hit error/edge branches surfaced by full-suite coverage (96.38% baseline).

### Analysis Results

The full suite already covers happy paths well; remaining gaps clustered around defensive error-handlers, fallback branches, and small helper edge values. New tests target lines that only execute on unusual or failure inputs.

### Tests Added (test_edge_cases_may16_2026.py)

**File**: `tests/test_edge_cases_may16_2026.py` (11 new tests)

#### TestGetDbRollbackPath
1. `test_get_db_rolls_back_on_exception` — Drives `app/core/database.py:get_db` through its `except`/`rollback`/`raise` branch (lines 55-57) by injecting an exception via `athrow` into the dependency generator. Verifies `rollback` is awaited and `commit` is not.
2. `test_get_db_commits_on_clean_exit` — Companion happy-path that confirms the normal exit takes the `commit` branch on line 54.

#### TestLifespanStartupFailure
3. `test_lifespan_reraises_init_db_error` — Patches `init_db` to raise during application startup and asserts the `lifespan` context manager (`app/main.py` lines 63-65) logs `Startup failed` with `exc_info=True` and re-raises. Also confirms `create_admin_user` is NOT called when init fails (early-exit invariant).

#### TestKnowledgeResearchEdgeCases
4. `test_fetch_wikipedia_data_includes_sections` — Mocks the Wikipedia search + content API responses and the `_fetch_wikipedia_sections` helper to return data, exercising the `sections` merge branch at `knowledge_research.py:231-232`.
5. `test_research_thinker_swallows_nested_error_during_failure_update` — Forces the outer research to raise via `get_or_create_knowledge`, then makes the inner `async_session()` reopen also raise, hitting the nested `except` on lines 166-167. Asserts `_research_thinker` returns without propagating either error.

#### TestThinkerHelperEdgeCases
6. `test_get_last_user_message_timestamp_no_user_messages` — Returns 0.0 when only thinker messages exist (`thinker.py:1431` fallback).
7. `test_get_last_user_message_timestamp_returns_latest_user_msg` — Happy-path companion: returns the *most recent* user message's timestamp.
8. `test_should_prompt_user_below_threshold_returns_false` — With a recent user message, the `messages_since_user < threshold` guard at `thinker.py:1465` short-circuits to False.
9. `test_should_prompt_user_too_few_messages_returns_false` — Conversations with fewer than 5 messages are never eligible (line 1457 guard).
10. `test_should_prompt_user_threshold_met_respects_random` — Locks both sides of the random gate by patching `random.random()` to 0.0 and 0.99, asserting True/False respectively when the threshold is met.
11. `test_count_messages_since_user_counts_trailing_thinkers` — Supporting helper test: counts only thinker messages after the *last* user turn.

### Stability Verification

All 11 tests verified passing across 3 consecutive runs (no flakiness). Tests use only mocks/patches — no real network, DB, or background-task dependencies — so they are also very fast (~1.4s total).



## Flaky Test Hunt - Tuesday QA (Added 2026-05-19)

**Focus**: Lock down `_choose_response_style` branches and the no-client guard in `_suggest_single_batch` with fully deterministic mocks — no seed-based luck. Closes the last fully-uncovered line in `app/services/thinker.py` (line 272).

### Analysis Results

- Full backend suite (1503 passed, 9 skipped) ran cleanly on the baseline at 98.75% coverage. No spurious failures across the full run.
- Only `app/services/thinker.py` uses `random.*` for branch selection. The `_split_response_into_bubbles` / `_should_respond` / `_should_prompt_user` random branches were locked down in earlier flaky-hunt sessions (apr28_2026, may5_2026, may12_2026).
- `_choose_response_style` still had ONLY seed-based tests (`test_thinker_service.py::TestChooseResponseStyle`, `test_flaky_hunt_mar17_2026.py::test_choose_response_style_always_returns_valid_values`) which assert distributional properties. A refactor that breaks a single branch or flips one `<` to `<=` would slip past those checks.
- Coverage before: 98.75% (22 partial branches, 11 missing lines). Coverage after: 98.83% (21 partial branches, 10 missing lines). Line 272 closed.

### Tests Added (test_flaky_hunt_may19_2026.py)

**File**: `tests/test_flaky_hunt_may19_2026.py` (25 new tests)

#### TestChooseResponseStyleAddressedBranchesDeterministic
1. `test_addressed_roll_0_00_returns_30_tokens` — `random.random()` mocked to 0.0 with a name-addressed message → 30-token "2-5 words" branch.
2. `test_addressed_roll_0_14_returns_30_tokens` — roll=0.14 (just under 0.15) still returns 30 tokens.
3. `test_addressed_roll_0_15_boundary_returns_60_tokens` — At exactly `roll==0.15` the strict `<` must NOT take the 30-token branch; locks down inequality direction.
4. `test_addressed_roll_0_34_returns_60_tokens` — roll=0.34 (just under 0.35) returns 60 tokens.
5. `test_addressed_roll_0_35_boundary_returns_120_tokens` — Boundary at 0.35: must take 120-token branch (strict `<`).
6. `test_addressed_roll_0_54_returns_120_tokens` — roll=0.54 (just under 0.55) returns 120 tokens.
7. `test_addressed_roll_0_55_boundary_returns_200_tokens` — Boundary at 0.55: must take 200-token branch (strict `<`).
8. `test_addressed_roll_0_79_returns_200_tokens` — roll=0.79 (just under 0.80) returns 200 tokens.
9. `test_addressed_roll_0_80_boundary_returns_350_tokens` — Boundary at 0.80: must take terminal else (350-token "fuller response" branch).
10. `test_addressed_roll_0_99_returns_350_tokens` — roll=0.99 hits the terminal else branch and asserts the style contains "exploring" or "fuller" so a swap of the two largest branches is caught.

#### TestChooseResponseStyleNotAddressedBranchesDeterministic
11. `test_not_addressed_roll_0_00_returns_30_tokens` — roll=0.0 + generic content (no name mention) → 30-token "very brief reaction" branch.
12. `test_not_addressed_roll_0_19_returns_30_tokens` — roll=0.19 (just under 0.20) still returns 30 tokens.
13. `test_not_addressed_roll_0_20_boundary_returns_60_tokens` — Boundary at 0.20: must take 60-token branch (strict `<`).
14. `test_not_addressed_roll_0_39_returns_60_tokens` — roll=0.39 (just under 0.40) returns 60 tokens.
15. `test_not_addressed_roll_0_40_boundary_returns_120_tokens` — Boundary at 0.40: must take 120-token branch.
16. `test_not_addressed_roll_0_59_returns_120_tokens` — roll=0.59 (just under 0.60) returns 120 tokens.
17. `test_not_addressed_roll_0_60_boundary_returns_200_tokens` — Boundary at 0.60: must take 200-token branch.
18. `test_not_addressed_roll_0_79_returns_200_tokens` — roll=0.79 (just under 0.80) returns 200 tokens.
19. `test_not_addressed_roll_0_80_boundary_returns_300_tokens` — Boundary at 0.80: must take terminal else (300 tokens — NOT 350; the not-addressed cap is intentionally smaller than the addressed cap, and this test pins that distinction).

#### TestChooseResponseStyleJustSpokeFollowUp
20. `test_just_spoke_roll_0_00_returns_follow_up` — Last sender == thinker name + roll=0.00 → 50-token "VERY brief follow-up" branch.
21. `test_just_spoke_roll_0_39_returns_follow_up` — roll=0.39 (just under 0.40) still returns 50-token follow-up.
22. `test_just_spoke_roll_0_40_boundary_falls_through` — Boundary at 0.40 with just_spoke=True must NOT take the follow-up branch (strict `<`). Falls through to the not-addressed roll=0.40 branch (120 tokens) since the message content does not mention the thinker by name.
23. `test_just_spoke_false_with_low_roll_does_not_return_follow_up` — When `just_spoke=False` (last sender is User), even roll=0.05 must NOT trigger the follow-up branch. Verifies the `just_spoke and ...` short-circuit guards the entire follow-up path.

#### TestSuggestSingleBatchNoClientGuard
24. `test_suggest_single_batch_returns_empty_when_client_is_none` — Direct call with `client` property mocked to None returns `[]` (closes line 272). The public `suggest_thinkers` caller short-circuits earlier so this inner guard was previously unreachable; locking it down means a refactor that drops the guard (and later assumes `client` is non-None) will fail loudly.
25. `test_suggest_single_batch_returns_empty_with_exclude_when_client_is_none` — Same guard with all optional arguments populated (`perspective_hint`, `exclude`, `language`); verifies the guard fires regardless of the other args.

### Stability Verification

All 25 tests verified passing across 3 consecutive runs (~1.9s each, no flakiness). The full backend suite (1528 passed, 9 skipped, ~6:43) also runs cleanly with the new tests included. Tests use only mocks/patches — no real network, DB, or background-task dependencies.
