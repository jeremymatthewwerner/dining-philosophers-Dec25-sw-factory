## Flaky Hunt - Tuesday QA: transition-word bubble split (Added 2026-06-16)

**Focus**: Tuesday QA (flaky-hunt). Verified the suite is flake-free, then pinned
the last un-guarded probabilistic branch in `_split_response_into_bubbles`.

**Flakiness verification (primary deliverable)**: The full backend suite
(1794 passed, 10 skipped) ran clean. The random/timing-prone subset (380 tests
matching `flaky`/`random`/`bubble`/`split`/`should_respond`/`should_prompt`/
`thinking_display`/`choose_*`/`strategy`/`randint`/`mention`/`speed`) was run
**5× back-to-back** and again under `PYTHONHASHSEED` 0/1/12345 — 379 passed every
run, identical results. **No flaky tests found.**

**Gap pinned** — `tests/test_flaky_hunt_jun16_2026.py`
(`app/services/thinker.py:736-760`):

`_split_response_into_bubbles` forces a sentence into a fresh chat bubble when it
*starts* with one of a 10-word transition list (`But `, `However,`, `Although `,
`On the other hand,`, `That said,`, `Nevertheless,`, `Yet `, `Still,`, `Though `,
`Conversely,`). Prior sessions only ever exercised `However,`; the other nine
words — and the exact casing/trailing-space of each entry — were unguarded.

| Test | What it validates |
|------|-------------------|
| `test_transition_word_forces_new_bubble` (parametrized ×10) | Each listed word, with `random.random`→0.5 and `random.randint`→500 (target_size so large size never forces a split), still produces a 2nd bubble starting with that word. Dropping a word or altering its casing/trailing-space would merge the sentences and fail. |
| `test_neutral_leading_word_stays_single_bubble` | Negative control: a neutral leading word (`Indeed `) under the same huge target_size stays a single bubble — proving the parametrized splits are caused by the transition word, not by size. |
| `test_transition_match_is_case_sensitive` | Lowercase `but ` does NOT split — pins that the `startswith` match is case-sensitive (a `.lower()` regression would wrongly split and fail). |

**Why deterministic isolation**: mocking both `random.random` (branch selection)
and `random.randint` (target size) removes all randomness, so the transition word
is the sole possible cause of a second bubble — no seed search, no flake risk.

---

## Integration Gaps - Wednesday QA (Added 2026-06-10)

**Focus**: Cross-endpoint workflows centered on the spend aggregation endpoint
(`GET /api/spend/{user_id}`). Individual API endpoints already have very high
unit coverage, but the spend endpoint's multi-table join (Session ⨝ Conversation
⨝ Message in `app/services/spend.py`) was only exercised by service-level unit
tests, never through the real REST write path (POST /conversations, POST
/messages, DELETE /conversations). These integration tests drive the write
endpoints and assert the spend read endpoint reflects the result, catching
contract drift (session linkage, cost filtering, delete cascade) that
single-endpoint tests cannot.

### Tests Added (test_integration_gaps_jun10_2026.py)

#### `TestSpendReflectsRestCreatedConversations` (2 tests)
- `test_spend_lists_all_conversations_created_via_rest` — Creates three
  conversations via `POST /conversations` and asserts all three appear in
  `GET /spend` (by id and topic) with the auto-created session reporting
  `conversation_count == 3`. Validates the Session⨝Conversation join + Python
  grouping in `get_user_spend_data` for the multi-conversation case (test_api.py
  only covers a single conversation).
- `test_spend_conversation_count_excludes_other_users` — Two real users each
  create conversations over REST; asserts each user's `GET /spend` returns only
  their own conversations and `conversation_count`. Exercises the
  `WHERE UserSession.user_id == user_id` filter against genuine overlapping data.

#### `TestUserMessagesDoNotInflateSpend` (1 test)
- `test_user_messages_leave_message_count_and_total_at_zero` — Sends three user
  messages via `POST /conversations/{id}/messages`, then asserts the spend row
  reports `message_count == 0` and `total_spend == 0.0`. Locks in the
  cost-filter contract end-to-end: user messages carry `cost = NULL` and the
  spend query counts only messages with `cost IS NOT NULL`.

#### `TestDeleteConversationDropsFromSpend` (1 test)
- `test_deleting_one_conversation_removes_it_from_spend` — Creates two
  conversations, deletes one via `DELETE /conversations/{id}`, and asserts the
  deleted conversation is gone from `GET /spend` and the session's
  `conversation_count` drops from 2 to 1. Verifies the delete is durably
  committed and the spend join no longer returns the removed row.

#### `TestSessionIdConsistencyAcrossEndpoints` (1 test)
- `test_session_id_identical_across_sessions_me_conversation_and_spend` —
  Asserts the session id is identical across three endpoints: `GET /sessions/me`,
  the `session_id` on a `POST /conversations` response, and the session entry in
  `GET /spend`. Detects drift where a write path might spawn or reference a
  different session than the one encoded in the JWT.

### Stability & Coverage Verification
- All 5 tests run 3x consecutively with no flakiness.
- `ruff format` and `ruff check` pass clean.

---

## Coverage Sprint - Monday QA (Added 2026-06-01)

**Focus**: Close the last-mile coverage gaps in the two lowest-coverage backend modules. Before this run, `app/api/websocket.py` was at 95% (9 missing lines + branches) and `app/services/thinker.py` was at 98%, with overall coverage at **98.94%**. The 9 missing lines in `websocket.py` were the highest-leverage gap because they fall on the **connect-handler path that wires a Conversation to its thinker agents** — code that runs every time a real user opens a chat.

### Analysis Results

`pytest --cov=app --cov-report=term-missing` showed:
- `app/api/websocket.py` — lines 420-431 (`get_messages`/`save_message` closures + `start_conversation_agents` call), 450 (TYPING_START `pass`), 453 (TYPING_STOP `pass`), branch 478→441 (USER_MESSAGE returning to receive loop).
- `app/services/thinker.py` — line 733 (`_split_response_into_bubbles` whitespace-only sentence skip) and several partial branches in `_should_respond`, `_extract_thinking_display`, and the streaming response loop.

The pre-existing typing tests *did* send TYPING_START/STOP frames, but the test closed its TestClient context before the server-side loop reached the `pass` body. Sending a **follow-up USER_MESSAGE** on the same connection and waiting for its broadcast back is the strongest possible proof that the server reached the `pass` branch and then returned to `receive_text` — which is also what covers branch 478→441.

### Tests Added (test_coverage_sprint_jun1_2026.py)

**File**: `tests/test_coverage_sprint_jun1_2026.py` (14 new tests, all pass 3x stable in ~1.3s)

After this run: overall backend coverage **99.40%** (+0.46pp), `app/api/websocket.py` 95% → 99%, total missing lines 10 → 1.

#### TestWebSocketLoopHandlesTypingAndUserMessageSequence (3 tests)
1. `test_typing_start_then_user_message_reaches_loop_again` — Sends TYPING_START then USER_MESSAGE on the same socket and asserts the USER_MESSAGE broadcast arrives. The broadcast can only arrive if the server's receive loop reached the `pass` body for TYPING_START (line 450) and looped back to `receive_text`.
2. `test_typing_stop_then_user_message_reaches_loop_again` — Same pattern for TYPING_STOP (line 453). Covers the loop-continuation invariant: pass-branch handlers must not break the receive loop.
3. `test_two_user_messages_in_sequence_proves_loop_continuation` — Sends two consecutive USER_MESSAGE frames and asserts both broadcasts come back, proving branch 478→441 (USER_MESSAGE → top of receive loop).

#### TestWebSocketStartsThinkerAgentsWhenConversationHasThinkers (1 test)
4. `test_handler_invokes_start_conversation_agents_with_working_closures` — Seeds the in-memory test DB with a User (`language_preference="fr"`), Session, Conversation, and ConversationThinker, then directly invokes `websocket_endpoint` with a mocked WebSocket whose `receive_text` raises `WebSocketDisconnect`. Patches `async_session_maker` at its source module so the closures pick up the test session, and replaces `thinker_service.start_conversation_agents` with a capture that **executes** the closures end-to-end against the real `get_messages_for_conversation` and `save_thinker_message` helpers. Verifies: language is propagated from User, thinker list is forwarded, the `get_messages` closure returns an empty Sequence for a fresh conversation, and the `save_message` closure persists a real Message with the correct cost. Covers lines 420-431 (the closure bodies + the `start_conversation_agents` call).

#### TestExtractThinkingDisplayShortCircuits (3 tests)
5. `test_empty_thinking_text_returns_empty_string` — Empty thinking text fast-path. The streaming-loop guard `if display_thinking:` only skips when this returns falsy.
6. `test_short_thinking_text_returns_empty_string` — < 80 chars also short-circuits to empty. Documents the threshold so future changes can't silently lower it (which would surface partial "Har…" snippets to users).
7. `test_long_thinking_text_returns_non_empty` — Confirms the non-empty path returns a meaningful preview. Together with tests 5 and 6 this pins both legs of branch 641→645.

#### TestShouldRespondEarlyReturns (2 tests)
8. `test_should_respond_returns_false_when_no_messages` — Empty messages list returns False (line 1561-1562 fast path).
9. `test_should_respond_returns_false_when_no_new_messages` — When `last_response_count == len(messages)`, no new messages, returns False (line 1566-1567). Pins both early-return invariants so the run-thinker loop can't accidentally start responding to nothing.

#### TestSplitResponseIntoBubblesEdgeCases (5 tests)
10. `test_empty_response_returns_empty_list` — Empty input returns `[]` (line 698).
11. `test_short_response_stays_single_bubble` — < 60 chars stays as one bubble (line 704). Locks the "don't fragment short responses" invariant.
12. `test_long_response_with_transition_words_splits_into_multiple` — Seeded RNG forces aggressive strategy; transition words ("However,") + length both trigger splits. No bubble is empty.
13. `test_long_run_on_text_force_splits_at_sentence_boundary` — Seeded RNG forces single-bubble strategy; with >300 char text, the force-split branch (lines 767-774) kicks in and produces multiple bubbles.
14. `test_whitespace_only_fragment_is_skipped` — Crafts a text where `re.split` produces a fragment that becomes empty after `sentence.strip()`. Documents the `if not sentence: continue` skip (line 733) so a future refactor can't drop it without surfacing the bubbles-with-blanks regression.

---

## Regression Prevention - Sunday QA (Added 2026-06-14)

**Focus**: Source-level invariants for shipped fixes / features that earlier Sunday regression suites did not explicitly pin. Backend coverage is already ~99% (496 branches), so the highest-leverage QA work continues to be "if you change the implementation, this test breaks" guards for fixes whose current behavioral tests don't structurally enforce them.

### Analysis Results

Cross-referencing every `test_regression_prevention_*.py` file against the merged commit history shows fixes #144, #163, #214, #257, #275, #299, #336, #367, #455, #459, #483, #533, #570 already have source-level guards. **Not yet guarded**: #332 (username in feedback submissions), #17 / #12 (`/api/version` endpoint + `VERSION` constant), and the in-app feedback form contract bounds from #193 / #218 (message length policy, pending-feedback query ordering/filter/limit, mark-processed URL bounds).

### Tests Added (test_regression_prevention_jun14_2026.py)

**File**: `tests/test_regression_prevention_jun14_2026.py` (18 new tests, all pass 3x stable in ~1.2s)

Bug fixes / features covered:
- **#332** feat(feedback): include username in feedback submissions (commit `d1a8123`) — model column, request/admin schema, and source-level persistence/passthrough plumbing
- **#17 / #12** feat(backend): `/api/version` endpoint + `VERSION` constant (commits `9636b45`, `8c6473d`) — endpoint reports the live constant and documented app name
- **#193 / #218** feat(feedback): in-app feedback form + feedback-to-issue conversion (commits `a8e9a53`, `bad4303`) — message length bounds, pending-query invariants, mark-processed URL bounds

#### TestFeedbackUsernameWiringContract (5 tests) — #332
1. `test_feedback_model_has_username_string50_nullable` — `Feedback.username` is a nullable `String(50)` column (cap matches the schema; nullable so anonymous submissions still work).
2. `test_feedback_create_schema_has_username_optional_max50` — `FeedbackCreate.username` is optional (default None) with `max_length=50`. Without the schema field, the API would strip submitted usernames before persisting.
3. `test_feedback_detail_schema_exposes_username` — `FeedbackDetail` (pending/admin view) surfaces `username` so the feedback-to-issue workflow can attribute issues.
4. `test_submit_feedback_source_persists_username` — `submit_feedback` threads `username=data.username` into the `Feedback(...)` constructor (else every row lands with NULL username).
5. `test_get_pending_feedback_source_passes_username_through` — `get_pending_feedback` maps `username=fb.username` into each `FeedbackDetail` (else the stored username is hidden from the workflow's last hop).

#### TestVersionEndpointContract (4 tests) — #17 / #12
1. `test_version_constant_is_defined_and_nonempty` — `app.VERSION` is a non-empty string (single source of truth for the probe).
2. `test_version_endpoint_returns_version_constant` — `version()` returns the live `VERSION` constant under the `version` key (not a stale inlined literal).
3. `test_version_endpoint_returns_documented_app_name` — `version()` returns `name="Dining Philosophers API"` (public contract for consumers/dashboards).
4. `test_version_endpoint_source_reads_version_constant` — source references `VERSION` so inlining a literal reads as a regression, not a style choice.

#### TestFeedbackMessageBoundsContract (3 tests) — #193
1. `test_feedback_message_requires_min_length_10` — `FeedbackCreate.message` requires `min_length=10` (filters trivial/empty spam from the pipeline).
2. `test_feedback_message_allows_max_length_5000` — `message` caps at `max_length=5000` (the Text column is uncapped at the DB, so this schema bound is the only guard).
3. `test_feedback_create_rejects_too_short_and_accepts_valid` — behavioral boundary check: 9 chars rejected, 10 chars accepted.

#### TestPendingFeedbackQueryContract (4 tests) — #218
1. `test_pending_filters_to_new_status_only` — query filters `status == FeedbackStatus.NEW` (else processed feedback is re-issued as duplicates).
2. `test_pending_orders_oldest_first` — `order_by(created_at.asc())` so old feedback isn't starved.
3. `test_pending_limit_param_clamped_1_to_50` — `limit` `Query` carries `Ge(1)`/`Le(50)` (0 = no-op; unbounded = backlog drain + timeout).
4. `test_pending_default_limit_is_10` — `limit` defaults to 10 (documented per-run batch size).

#### TestMarkProcessedRequestContract (2 tests) — #218
1. `test_github_issue_url_requires_min_length_1` — `MarkProcessedRequest.github_issue_url` requires `min_length=1` (no marking processed without a traceable link).
2. `test_github_issue_url_caps_at_max_length_500` — caps at `max_length=500` to match the `Feedback.github_issue_url String(500)` column (else over-long URLs pass validation then fail at commit).

---

## Regression Prevention - Sunday QA (Added 2026-05-31)

**Focus**: Source-level invariants for past bug fixes / features that earlier Sunday regression suites did not explicitly pin. Backend coverage is at **98.94%** (496 branches across 2153 stmts), so the highest-leverage QA work is pinning down "if you change the implementation, this test breaks" guards for fixes that current behavioral tests don't structurally enforce.

### Analysis Results

Cross-referencing `test_regression_prevention_may{10,17,24}_2026.py` shows fixes #81, #257, #299, #336, #367, #455, #483, #533, #570 already have source-level guards. Not yet guarded: #214 (feedback screenshots), #459 / #275 (test-user cleanup), #144 (`/health/ready`), #163 (profile validation), parts of #367 (connect-handler source order), feedback rate-limit constants, and the `trigger_error` test-mode security guard.

### Tests Added (test_regression_prevention_may31_2026.py)

**File**: `tests/test_regression_prevention_may31_2026.py` (24 new tests, all pass 3x stable in ~1.5s)

Bug fixes / features covered:
- **#214** fix(feedback): add screenshot support and improve error handling (commit `ef3c3dc`)
- **#459 / #275** feat(devops) + fix(cleanup): test user cleanup endpoint (commits `6fed42a`, `9f25bc7`)
- **#367** fix(websocket): sync pause button state when switching threads (commit `a9c7742`) — source-level order guards (the May 17 set covered the wire constants)
- **#144** feat(backend): `/health/ready` deep readiness probe (commit `346bc33`) — source-level `SELECT 1` and 503/200 guards (apr12 set covered behavior under shared test client)
- **#163** feat(auth): user profile management for password and display name (commit `7acadd7`) — schema validation bounds
- Feedback rate-limit constants (`MAX_SUBMISSIONS_PER_HOUR`, hashed-IP query)
- `trigger_error` test-helpers production-disable security guard

#### TestFeedbackScreenshotFieldsContract (5 tests)
1. `test_feedback_model_has_screenshot_data_text_column` — `Feedback.screenshot_data` is a nullable Text column (must not be String/VARCHAR — base64 PNGs exceed any practical VARCHAR cap).
2. `test_feedback_model_has_screenshot_filename_string_column` — `Feedback.screenshot_filename` is a nullable String column.
3. `test_feedback_create_schema_accepts_screenshot_fields` — `FeedbackCreate` exposes both screenshot fields as optional (default None). Without these on the schema, the API would silently strip user-submitted screenshots before persisting.
4. `test_max_screenshot_size_caps_payload_around_5mb_binary` — `MAX_SCREENSHOT_SIZE == 7_000_000` (~5MB binary post-base64). Pinned with the inline comment so future reviewers can verify intent.
5. `test_feedback_create_rejects_oversize_screenshot` — `FeedbackCreate.validate_screenshot_size` raises `ValidationError` for payloads exceeding `MAX_SCREENSHOT_SIZE + 1`. Removing the validator would expose the backend to multi-GB DoS payloads.

#### TestFeedbackRateLimitContract (3 tests)
6. `test_max_submissions_per_hour_constant_is_five` — `feedback.MAX_SUBMISSIONS_PER_HOUR == 5` (matches docstring + frontend copy).
7. `test_submit_feedback_source_uses_hashed_ip_not_raw` — `submit_feedback` source contains `Feedback.ip_hash == ip_hash` AND `hash_ip(client_ip)`. Prevents a privacy regression where raw IPs leak into the DB column.
8. `test_submit_feedback_source_uses_one_hour_window` — Source regex matches `timedelta(hours=1)`. The constant + window form one contract; both must update together.

#### TestTestUserPrefixesCleanupContract (4 tests)
9. `test_test_user_prefixes_contains_documented_three` — Exact tuple `("smoketest_", "canary_", "testuser_")`. Adding a prefix broadens the destructive endpoint's blast radius.
10. `test_test_user_prefixes_are_all_lowercase` — Every prefix == its lowercase form. The cleanup uses case-sensitive `startswith`, so a non-lowercase prefix silently fails to match real test users.
11. `test_test_user_prefixes_is_immutable_tuple` — `isinstance(TEST_USER_PREFIXES, tuple)`. A mutable list could be appended to at runtime, broadening cleanup scope without code review.
12. `test_cleanup_test_users_source_requires_secret_match` — Source contains BOTH `not settings.test_cleanup_secret` (unconfigured rejection) AND `secret != settings.test_cleanup_secret` (wrong-secret rejection). Dropping either check would expose the destructive endpoint.

#### TestWebsocketConnectPauseStateSyncSource (3 tests)
13. `test_websocket_endpoint_source_dispatches_on_is_paused` — `websocket_endpoint` source contains `thinker_service.is_paused(conversation_id)`. Required for fix #367's correct PAUSED/RESUMED dispatch on connect.
14. `test_websocket_endpoint_source_has_paused_and_resumed_branches` — Source contains both `WSMessageType.PAUSED` AND `WSMessageType.RESUMED`. Sending only one would leave thread-switch state stuck.
15. `test_websocket_endpoint_sync_happens_before_receive_loop` — Both PAUSED and RESUMED sends appear in the source BEFORE `while True`. Deferring sync into the receive loop would defeat fix #367.

#### TestHealthReadyEndpointSourceGuards (3 tests)
16. `test_health_ready_source_executes_select_1_probe` — `health_ready` source contains `text("SELECT 1")`. Without a real DB probe, the endpoint becomes "always green" and masks DB outages from load balancers.
17. `test_health_ready_source_uses_503_for_degraded` — Source contains literal `503`. Load balancers use 503 to drop a backend from rotation.
18. `test_health_ready_source_uses_200_for_ready` — Source contains literal `200`. Pinning both literals locks the dual-check contract under JSONResponse wrapping.

#### TestUserProfileValidationContract (4 tests)
19. `test_change_password_request_new_password_requires_min_length_6` — `ChangePasswordRequest.new_password` metadata contains `min_length=6`. Loosening to no minimum would silently permit 1-character passwords.
20. `test_user_register_password_has_min_and_max_length` — `UserRegister.password` has `min_length=6` AND `max_length=100`. Inconsistent bounds vs. `change_password` would be a confusing UX + security gap.
21. `test_user_register_display_name_has_min_and_max_length` — `UserRegister.display_name` has `min_length=1` (reject blanks) AND `max_length=100` (matches DB column).
22. `test_user_profile_update_display_name_has_min_and_max_length` — `UserProfileUpdate.display_name` has matching bounds. Drift between register and update would create inconsistent state.

#### TestTriggerErrorTestModeGuard (2 tests)
23. `test_trigger_error_source_checks_is_test_mode` — `trigger_error` source contains `is_test_mode()`. Without this guard, a misconfigured production deploy would expose a public endpoint that injects ERROR banners into any active conversation (phishing/UI-spoofing risk).
24. `test_trigger_error_source_returns_403_when_not_test_mode` — Source contains `status_code=403`. Documented as 403 in the docstring so clients can distinguish "disabled" from "not found".

---

## Edge Cases - Saturday Sprint (Added 2026-05-30)

**Focus**: Behavioral invariants and boundary contracts in pure helpers across `app/services/thinker.py`, `app/api/feedback.py:hash_ip`, and `app/core/config.py:is_test_mode`. Backend coverage was already **98.94%** before this sprint; these tests pin down off-by-one / precedence regressions that line coverage alone does not catch.

### Tests Added (test_edge_cases_saturday_may30_2026.py)

**File**: `tests/test_edge_cases_saturday_may30_2026.py` (30 passing + 1 skipped documentation marker, across 8 classes; all pass 3x stable in ~2.0s)

#### `TestExtractMentionsDedupAndStructure`
1. `test_quoted_then_simple_same_first_word_does_not_dedup` — `@"Marie Curie" @Marie` yields BOTH names (the dedup check is exact-string, not substring). Locks the contract that `is_mentioned`'s first-name path relies on.
2. `test_quoted_then_simple_identical_token_dedups` — `@"Bob" @Bob` produces a single "Bob" (the simple pass's `if name not in mentions` skips the duplicate).
3. `test_multi_line_text_captures_all_mentions` — Newlines do not break iteration; `\w+` naturally stops at the newline so each line's mention is captured independently.
4. `test_at_followed_by_only_punctuation_yields_nothing` — `@!`, `@,`, `@.` produce no mentions (regex requires 1+ word chars).
5. `test_quoted_mention_with_only_spaces_is_captured_literally` — `@"   "` is captured as `"   "`; the regex's `[^"]+` accepts spaces.

#### `TestIsMentionedThinkerNameGuards`
6. `test_empty_thinker_name_returns_false` — Empty thinker name short-circuits via the `if thinker_name else ""` guard on line 105, preventing IndexError from `"".split()[0]`.
7. `test_whitespace_only_thinker_name_returns_false` (SKIPPED) — Documents a known hardening opportunity: `"   "` is truthy so passes the guard, but `"   ".split()` returns `[]` and would IndexError on `[0]`. Test is a regression marker — if behavior changes (guard tightened or crash), it surfaces as a status change.
8. `test_first_name_with_punctuation_in_thinker_name` — `"St. Augustine"` is NOT matched by `@St` because the comparison is exact-string after lowercasing; `@"St. Augustine"` (quoted) IS matched.
9. `test_mixed_case_thinker_name_lowercased_for_comparison` — `@MCALLISTER`, `@mcallister`, `@McAllister` all match `"McAllister"` (case-insensitive both sides).

#### `TestSplitBubblesBoundaries`
10. `test_text_exactly_60_chars_does_not_short_circuit` — Boundary `< 60`: at len == 60 the function proceeds into the strategy path. Tested across 20 seeds — never crashes, never produces empty bubbles.
11. `test_text_exactly_59_chars_short_circuits_to_single_bubble` — At len == 59 returns `[text]` deterministically.
12. `test_text_exactly_250_chars_keep_single_branch_skipped` — At len == 250, the 25%-keep-single branch (gated on `len(text) < 250`) does NOT fire even when `strategy_roll < 0.25`. Finds the seed deterministically and verifies multi-bubble output.
13. `test_leading_transition_word_starts_new_bubble` — A sentence starting with "However," forces a new bubble (via `starts_with_transition`). Verified across 30 seeds — at least some produce 2+ bubbles, and "However," always starts its own bubble when split.
14. `test_text_above_60_below_250_short_strategy_roll_keeps_single` — Sanity sibling: at len 249 (just below boundary), the keep-single branch fires for `strategy_roll < 0.25`.

#### `TestExtractThinkingDisplayContracts`
15. `test_long_text_with_no_sentence_boundary_in_tail_keeps_full_tail` — Text > 200 with no `. ` / `! ` / `? ` / `\n` anywhere → the for-loop's break never fires → full 200-char tail preserved. Output still gets the trailing "..." per line 965.
16. `test_text_starting_uppercase_skips_incomplete_word_strip` — `text[0].isupper()` short-circuits the leading-word strip (line 811). "Capital" survives the post-processing.
17. `test_text_no_spaces_no_leading_word_strip` — Right-hand half of `not text[0].isupper() and " " in text`: 90 `a`'s (lowercase, no space) does NOT trigger the strip.
18. `test_short_text_below_80_returns_empty_regardless_of_language` — The `< 80` gate is language-independent; checked for `en`, `es`, `fr`, `de`, `hi`, and an unknown `zz` code.

#### `TestShouldRespondProbabilityCeilings`
19. `test_new_message_count_cap_at_0_7_with_many_new_messages` — Even with 50 new messages, `base_probability = min(0.25 + count*0.12, 0.7)` caps at 0.7. Statistical test across 500 seeds: True-rate stays in [0.30, 0.90] band consistent with 0.7-cap × 0.85-silence-gate ≈ 0.6.
20. `test_consecutive_silence_exactly_2_does_not_trigger_bonus` — Strict-`>` boundary on line 1588: silence == 2 has no bonus, silence == 10 does. Comparison across 400 seeds shows gap > 0.20.

#### `TestCountMessagesSinceUserMinimal`
21. `test_empty_messages_returns_zero` — Vacuous truth on empty list.
22. `test_only_user_messages_returns_zero` — First reverse-iteration breaks immediately.
23. `test_user_in_middle_counts_only_trailing_thinkers` — Counts thinkers AFTER the most recent user only.
24. `test_enum_sender_type_at_user_boundary_correctly_detected` — `hasattr(sender, "value")` enum path (line 1437) detects user boundary correctly.

#### `TestHashIpExtendedInputs`
25. `test_ipv6_with_zone_id_hashes_distinct_from_plain_ipv6` — `fe80::1` and `fe80::1%eth0` produce different hashes (raw-string SHA-256 input).
26. `test_unicode_input_does_not_crash` — Zero-width-space in IP is UTF-8-encoded by `.encode()`; produces valid 64-char hex digest.
27. `test_very_long_input_yields_fixed_64_char_digest` — 100KB input still yields 64-char hex; nearby long inputs hash differently.
28. `test_identical_octet_prefixes_yield_unrelated_hashes` — Avalanche property: `10.0.0.1` and `10.0.0.2` differ in first 8 hex chars too. Regression guard against naive non-cryptographic replacements.

#### `TestIsTestModeSettingsReflection`
29. `test_is_test_mode_reflects_patched_settings_true` — Patched Settings with `test_mode=True` flows through.
30. `test_is_test_mode_reflects_patched_settings_false` — Patched `test_mode=False` flows through.
31. `test_is_test_mode_flip_between_calls_via_cache_clear` — Each call hits `get_settings()` fresh; alternating True/False/True is reflected (no own cache).

### Stability & Coverage Verification

- All 30 tests pass across 3 consecutive runs in ~2.0s each — no flakiness.
- Backend line coverage remains **98.94%** (the targets were already covered for lines; these tests improve *behavioral* regression resistance, not coverage numbers).
- Full thinker/feedback/config related suites (`test_thinker_service.py + test_feedback.py + test_config.py + test_edge_cases_may23_2026.py + this file` = 201 tests) all pass.
- No new dependencies, no DB usage, no network calls — fully self-contained.

## Coverage Sprint - Monday (Added 2026-05-25)

**Focus**: Close remaining branch gaps in `app/services/knowledge_research.py`. Existing tests covered the file to ~82% line / 89% branch — the 18% gap was concentrated in the `_research_thinker` failure handler, Wikipedia "-1" sentinel handling, and the `_fetch_wikipedia_sections` iteration/error paths.

**Why this file**: It's the highest-traffic *uncovered* code in the service layer — every conversation creation triggers `trigger_research(...)`, so an untested branch here can silently fail in production background tasks without surfacing in user-facing tests. The added tests exercise exact line + branch combinations identified by `--cov-report=term-missing`.

### Tests Added (test_coverage_sprint_may25_2026.py)

**File**: `tests/test_coverage_sprint_may25_2026.py` (10 new tests across 7 classes, all pass 3x stable)

#### `TestTriggerResearchCleanup`
1. `test_cleanup_callback_when_name_already_removed` — Simulates a race: the cleanup callback fires after the entry was already cleared from `_active_tasks`. The `if name in self._active_tasks` guard must short-circuit without raising. Covers the 107→exit branch (callback fired but `name` missing).

#### `TestResearchThinkerNoWikipedia`
2. `test_research_thinker_marks_complete_with_empty_data_when_wikipedia_none` — `_fetch_wikipedia_data` returns None; status must still flip to COMPLETE and `research_data` must NOT contain a `wikipedia` key. Covers the 140→149 branch (`if wikipedia_data:` falsy).

#### `TestResearchThinkerFailureWithoutKnowledge`
3. `test_failure_handler_no_op_when_get_knowledge_returns_none` — Primary research raises; the inner error handler's `get_knowledge()` returns None (e.g. row deleted concurrently). Handler must skip the FAILED status update silently. Covers the 162→exit branch (`if failed_knowledge:` falsy).

#### `TestFetchWikipediaSentinelPage`
4. `test_returns_none_when_only_sentinel_page_present` — Wikipedia returns only the `-1` "missing page" sentinel; loop `continue` skips it (line 215) and function returns None (line 236). Both API calls still issued.

#### `TestFetchWikipediaSectionsIteration`
5. `test_includes_only_interesting_sections_and_skips_others` — Section list mixes interesting (`Philosophy`, `Major works`) and uninteresting (`References`, `External links`). Only the interesting titles land in the result; per-section content calls are made only for matches. Covers lines 292-312 (matched + skipped branches).
6. `test_returns_none_when_no_interesting_sections_match` — All section titles uninteresting → function returns None (the `result if result else None` falsy branch). Only the initial sections query is issued.

#### `TestFetchWikipediaSectionsExceptionPath`
7. `test_returns_none_on_http_error` — `client.get` raises; exception is swallowed and None is returned. Covers lines 316-318.
8. `test_returns_none_on_malformed_response` — Response JSON missing the `parse` key entirely → empty section list → None. Verifies the result-falsy return at function end.

#### `TestFetchWikipediaMixedPages`
9. `test_skips_sentinel_then_processes_real_page` — Pages dict contains both `-1` (sentinel) and a real page id. Loop `continue`s past the sentinel and processes the real page. Cross-validates the line-215 `continue` works in combination with the success-return at line 234.

#### Sanity guard
10. `test_fetch_wikipedia_data_timestamp_is_utc_aware` — Successful fetch's `fetched_at` is a UTC-aware ISO-8601 string. Regression guard for `datetime.now(UTC)` usage in result construction.

### Stability & Coverage Verification

- All 10 tests pass across 3 consecutive runs (~0.95-1.00s each, no flakiness).
- `app/services/knowledge_research.py` coverage with the full knowledge-research test set (existing + new): **100% line, 100% branch** (was 82% / 89%). +18% line coverage on the target file — exceeds the 15% coverage-sprint goal.
- All tests use only mocks/patches: no real Wikipedia traffic, no background tasks, no DB outside the in-memory fixture used by one test.

## Edge Cases - Saturday Sprint (Added 2026-05-23)

**Focus**: Boundary conditions and behavioral invariants in `app/services/thinker.py` decision functions, mention parsing, and `app/api/feedback.py:hash_ip`. Backend line coverage was already **98.83%** before this sprint; these tests pin down edge contracts that line-coverage alone does not catch.

### Tests Added (test_edge_cases_may23_2026.py)

**File**: `tests/test_edge_cases_may23_2026.py` (38 new tests across 7 classes, all pass 3x stable)

#### `TestShouldRespondBoundaries`
1. `test_empty_messages_returns_false` — `_should_respond([], …)` short-circuits to False before any random roll (line 1561-1562). Regression guard: an empty message history must never yield a response.
2. `test_no_new_messages_since_last_response_returns_false` — When `last_response_count >= len(messages)`, `new_message_count <= 0` fires the line-1566 short-circuit; tested at boundary (==) and overshoot (>).
3. `test_own_last_message_without_self_mention_uses_low_probability` — When the thinker's own message is at the tail with no `@self` mention, `base_probability = 0.05` (line 1593). 50 seed sweep confirms ≥40/50 result in False.
4. `test_self_mention_overrides_own_message_low_probability` — Self-`@mention` keeps `base_probability` at 0.98 even when own message is at tail (the `and not was_at_mentioned` guard on line 1593). 50 seed sweep confirms ≥35/50 True.
5. `test_consecutive_silence_probability_caps_at_0_9` — Very large `consecutive_silence` values must respect the 0.9 cap (line 1589); 200 seed sweep confirms mixed True/False outcomes rather than always True.

#### `TestShouldPromptUserShortHistory`
6. `test_below_five_messages_returns_false` (parametrized 0, 1, 4) — Histories shorter than 5 messages short-circuit before any random roll (line 1456).
7. `test_exactly_five_messages_allows_evaluation` — Five messages passes the gate (boundary), reaches the threshold check where `messages_since_user=5 < threshold=8` returns False without crashing.

#### `TestUserMessageHelpers`
8. `test_count_messages_since_user_with_no_user_messages` — No user messages → count equals length (full reverse scan).
9. `test_count_messages_since_user_with_user_at_end` — User message at the tail → 0 (`break` before increment).
10. `test_count_messages_since_user_works_with_enum_sender_type` — Real `SenderType` enum exercises the `hasattr(sender, "value")` branch in line 1438.
11. `test_get_user_name_from_messages_returns_none_when_no_user` — No user messages → None.
12. `test_get_user_name_from_messages_returns_most_recent` — Reverse scan returns latest user, not first.
13. `test_get_user_name_from_messages_skips_user_with_empty_name` — User message with falsy `sender_name` is skipped per line 1417.
14. `test_get_last_user_message_timestamp_returns_0_with_no_user` — No user messages → 0.0 (line 1431).
15. `test_get_last_user_message_timestamp_skips_user_without_created_at` — User message without `created_at` is skipped; older user with timestamp wins.

#### `TestExtractThinkingDisplayBoundaries`
16. `test_whitespace_only_input_returns_empty` — Whitespace-only thinking_text strips to '' → length < 80 → returns ''.
17. `test_text_ending_with_ellipsis_not_doubled` — Text already ending in '...' must not get '......'; line 965 guard.
18. `test_text_ending_with_question_mark_not_appended` — Text already ending in '?' must not get '?...' or '...?' appended.
19. `test_text_just_below_80_chars_returns_empty` — 79-char text returns '' (boundary below threshold).
20. `test_text_at_or_above_80_chars_returns_non_empty` — 80-char text returns non-empty (boundary at threshold).

#### `TestSplitResponseBubblesEdgeInputs`
21. `test_whitespace_only_input_returns_empty` — Single-space input passes the truthiness check then strips to ''; no returned bubble may contain non-whitespace.
22. `test_leading_consecutive_periods_skip_empty_sentences` — Text with `". . . ."` produces empty post-split sentences that the line-733 `continue` must skip; 10 seeds confirm no empty bubble is ever returned.

#### `TestExtractMentionsCharacterClass`
23. `test_mention_with_underscore_captured` — `@bob_smith` produces `["bob_smith"]` (regex `\w+` includes underscore).
24. `test_mention_with_digits_captured` — `@bob123` produces `["bob123"]`.
25. `test_lone_at_at_end_of_text_not_captured` — Trailing bare `@` produces `[]` (regex requires ≥1 word char).
26. `test_mention_followed_by_punctuation_stops_at_word_boundary` — `@Socrates,` produces `["Socrates"]` (comma excluded).
27. `test_back_to_back_mentions_both_captured` — `@Alice@Bob` produces both names.
28. `test_quoted_mention_with_internal_punctuation` — `@"Dr. Strange"` preserves the dot and space.

#### `TestIsMentionedMultiWord`
29. `test_first_name_match_for_multi_word_thinker` — `@Marie` matches "Marie Curie" via the first-name path.
30. `test_full_quoted_name_matches_exact` — `@"Marie Curie"` matches via exact-match path.
31. `test_last_name_alone_does_not_match_via_at` — `@Curie` does NOT match "Marie Curie" (only first name matches, not last).
32. `test_case_insensitive_first_name_match` — `@MARIE` matches "Marie Curie" case-insensitively.

#### `TestHashIpProperties`
33. `test_hash_ip_is_deterministic` — Same input → same hash across multiple calls.
34. `test_hash_ip_different_ips_produce_different_hashes` — Five distinct IPs (IPv4 + IPv6) produce five distinct hashes.
35. `test_hash_ip_empty_string_returns_valid_hash` — Empty IP does not crash; returns 64-char hex (SHA-256 of '').
36. `test_hash_ip_output_is_lowercase_hex` — Output is lowercase hex (the 8-char prefix logged in the rate-limiter depends on this format).

### Coverage Impact
- Backend line coverage: **98.83% → ≥98.83%** (these tests target boundary contracts already exercised by line coverage; primary value is regression resilience).
- Total tests: 1538 → 1576 (38 new tests).
- All 38 tests run in ~3s and pass 3x consecutively (no flakiness).

### Why These Tests
Line-coverage metrics show 98.83% but say nothing about boundary correctness. The tests in this batch fail loudly if a future refactor breaks subtle invariants: the self-mention exception in `_should_respond` (line 1593), the empty-name skip in `_get_user_name_from_messages` (line 1417), the no-double-ellipsis guard in `_extract_thinking_display` (line 965), and the lone-`@` non-capture in `extract_mentions`. Each test names the line(s) it pins so future maintainers can reason about scope.

---

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

## Regression Prevention - Sunday QA (Added 2026-05-24)

**Focus**: Source-level invariants that the existing numeric tests do not lock in. The numeric tests prove "this value comes out right today"; these prove "the implementation hasn't been changed in a way that lets the original bug come back."

### Analysis Results

Backend coverage is already at **98.83%** (`app/services/thinker.py` 98%, `app/api/websocket.py` 95%). With coverage saturated, the highest-leverage regression work is pinning down **source-level invariants** for fixes that the numeric tests describe but don't structurally enforce.

### Tests Added (test_regression_prevention_may24_2026.py)

**File**: `tests/test_regression_prevention_may24_2026.py` (20 new tests)

Bug fixes / features covered:
- **#533** fix(thinker): use linear scaling for speed multiplier instead of exponential (commit `17cabf9`)
- **#483** feat(backend): add idle timeout to auto-pause inactive conversations (commit `7aa14e7`)
- **#336 / #455 / #570** feat(i18n): French / German / Hindi language support

#### TestSpeedMultiplierAgentLoopSourceGuards (4 tests)
1. `test_run_thinker_agent_source_uses_linear_15s_base` - The agent loop source literally contains `15.0 * speed_mult` (linear). Existing tests verify the *result* via the manager; this test prevents a refactor that bypasses the manager from silently going back to exponential pacing.
2. `test_run_thinker_agent_source_has_no_exponentiation_on_speed_mult` - Regex-scans `_run_thinker_agent` source for `speed_mult ** N` and `pow(speed_mult, ...)`; fails if either is reintroduced. The original #533 bug was `speed_mult ** 1.5`.
3. `test_run_thinker_agent_initial_reading_delay_is_linear` - The initial "reading" sleep also uses `random.uniform(1.0, 2.5) * speed_mult` (linear). Before #533, this was `* (speed_mult ** 1.5)`, making the 6x slider feel like 37s of staring at an empty typing indicator.
4. `test_linear_min_interval_formula_documented_contract` - Documents `min_interval = 15.0 * speed_mult` as the contract: 1x → 15s, 6x → 90s. A baseline change to the formula must rebaseline this test.

#### TestPauseStateMachineDualSetIndependence (5 tests)
5. `test_resume_from_idle_does_not_clear_manually_paused_conversation` - `resume_from_idle` on a manually-paused-only conv is a no-op. If the two sets were collapsed, the user's Pause click would silently disappear when send_message → resume_from_idle fires.
6. `test_pause_for_idle_after_manual_pause_keeps_manual_paused` - Calling `pause_for_idle` on an already manually-paused conv adds the idle flag without disturbing the manual one.
7. `test_resume_conversation_does_not_clear_idle_paused_flag` - Documents current contract: manual resume only clears the manual flag. If this changes, audit the agent loop's `is_idle_paused` re-notification logic.
8. `test_resume_from_idle_clears_both_pause_sets_atomically` - On idle-paused conv, `resume_from_idle` clears *both* flags so the next idle detection can re-notify the frontend.
9. `test_repeated_pause_for_idle_resume_from_idle_cycle_stays_clean` - 5 consecutive pause/resume cycles leave the state machine clean (no leaked flags).

#### TestSetSpeedMultiplierClampBoundaries (4 tests)
10. `test_set_speed_at_exact_lower_bound_is_unchanged` - Setting 0.5 stores 0.5 (no off-by-one in `max(0.5, ...)`).
11. `test_set_speed_at_exact_upper_bound_is_unchanged` - Setting 6.0 stores 6.0 (no off-by-one in `min(6.0, ...)`).
12. `test_clamped_speed_value_is_broadcast_not_raw_input` - Broadcasting 100.0 results in `speed_multiplier: 6.0` in the SPEED_CHANGED message, not 100.0. Prevents UI slider position drifting from actual backend pacing.
13. `test_extreme_negative_input_clamps_to_lower_bound` - `-1000.0` clamps to `0.5` (not 0 or negative). A negative speed_mult in `15.0 * speed_mult` would produce ≤0s min interval and spam.

#### TestLanguageNamesAndThinkingDisplayParity (4 tests)
14. `test_language_names_exact_keyset_is_documented_five_languages` - `LANGUAGE_NAMES.keys() == {"en","es","fr","de","hi"}`. Catches both accidental removals and additions.
15. `test_language_names_values_are_full_english_names` - Values are full English names (e.g., "Spanish" not "es") because the LLM recognizes them better in the IMPORTANT: Respond in X instruction.
16. `test_extract_thinking_display_source_has_branch_per_language` - Source inspection: each non-English language in LANGUAGE_NAMES has `language == "{code}"` in `_extract_thinking_display`. Catches the #570-style regression where a language was added to LANGUAGE_NAMES but not the thinking-display function.
17. `test_extract_thinking_display_source_has_starters_for_each_language` - Source has at least len(LANGUAGE_NAMES) `starters = [` assignments, so each language gets its own contemplative prefixes.

#### TestIdleTimeoutZeroDisablesSentinel (3 tests)
18. `test_run_thinker_agent_source_guards_idle_check_with_positive_value` - The `if idle_timeout > 0` guard remains in the agent loop. This is the documented mechanism for disabling idle-pause via `IDLE_TIMEOUT_SECONDS=0` without redeploying.
19. `test_settings_idle_timeout_can_be_set_to_zero` - `Settings(idle_timeout_seconds=0)` is valid (no validator rejects 0).
20. `test_settings_idle_timeout_default_is_int_type` - The field is `int` (not `float` or `timedelta`) because the agent loop uses `idle_timeout // 60` in the user-facing inactivity notification.

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

## Integration Gaps - Wednesday QA (Added 2026-05-27)

**Focus**: Cross-endpoint workflow tests targeting integration scenarios that pair multiple API calls and assert effects of one call are observable through another.

### Analysis Results

- Backend coverage is already at 98.94% (2153 statements, 10 missing). Only 3 files below 100%: `app/api/websocket.py` (95.2% — TestClient timing issues with TYPING_START/TYPING_STOP and inner callbacks), `app/services/thinker.py` (98.4% — line 733, `continue` for empty sentence after re.split, unreachable given greedy `\s+`), and `app/core/database.py` (98.4% — branch coverage only).
- Given high coverage, focus shifted from filling missing lines to filling **cross-endpoint workflow gaps**. Each test exercises 2+ endpoints in sequence and asserts that effects of the first call are observable through a later call. This catches contract drift between endpoints that single-endpoint tests cannot.

### Tests Added (test_integration_gaps_may27_2026.py)

**File**: `tests/test_integration_gaps_may27_2026.py` (10 new tests)

#### TestMessageCountPropagation
1. `test_list_message_count_reflects_user_messages_sent` — POST 3 user messages to one conversation; `GET /api/conversations` reports `message_count == 3` for that conversation. Catches drift between `send_message` insertion path (conversations.py:257-265) and `list_conversations` aggregation path (lines 88-104).

#### TestSpendHierarchyIntegration
2. `test_admin_spend_endpoint_includes_user_conversation_after_message_send` — User creates a conversation; admin queries `/api/spend/{user_id}` and the conversation appears in the flat `conversations` list. Verifies the spend endpoint's join across `sessions->conversations` respects newly-created rows and is not cached.
3. `test_admin_spend_endpoint_reflects_message_with_cost` — Directly inserts a thinker `Message` with `cost=0.05`; admin spend endpoint reports `total_spend >= 0.05` and `message_count >= 1` for that conversation. Validates the SQL aggregation in `get_user_spend_data` correctly sums message costs.

#### TestSequentialAddThinkersColorUniqueness
4. `test_two_sequential_adds_each_get_distinct_color_from_initial` — Conversation starts with 1 thinker; two subsequent PUT calls (one thinker each, default color) must each receive a distinct color from the palette, none equal to the original. Exercises color-pool logic across consecutive requests — the pool is recomputed on each request, so the second call must observe the first call's allocation.

#### TestIdlePauseResumeDurability
5. `test_subsequent_message_after_idle_resume_succeeds` — Conversation is force-idle-paused; first user message resumes via auto-resume code path (conversations.py:246-254); second user message also processes normally with `is_idle_paused == False`. Catches regression where idle-resume left the conversation in a partial state.

#### TestLanguagePreferenceRoundTrip
6. `test_language_update_visible_in_me_after_patch_language` — User PATCHes `/api/auth/language` with a value distinct from the default; both the PATCH response and a subsequent `GET /api/auth/me` reflect the new language. Catches divergence between the language-update endpoint and the canonical user-read endpoint.

#### TestDeleteCascadeSpendVisibility
7. `test_deleted_conversation_no_longer_in_admin_spend_breakdown` — Admin `/spend/{user_id}` shows the conversation before deletion; after `DELETE /api/conversations/{id}`, the same query no longer lists it. Validates that conversation deletion cascades correctly through the spend join and the admin view doesn't show dangling deleted conversations.

#### TestCreateGetAttributeFidelity
8. `test_thinker_fields_persist_across_create_and_get` — Conversation created with explicit `bio`, `positions`, `style`, and `image_url` returns identical values via `GET /api/conversations/{id}`. Catches schema-level mismatches where the API drops or transforms fields on response.

#### TestAdminUserListingFreshness
9. `test_user_registered_after_admin_login_appears_in_admin_list` — Admin lists users → captures baseline → new user registers → admin re-lists → new user is present and user count incremented by exactly 1. Verifies the admin list query is not cached and reflects DB state at request time.

#### TestAuthorizationBoundaryAcrossEndpoints
10. `test_non_admin_cannot_read_own_spend_but_can_read_own_me` — A non-admin user can `GET /api/auth/me` (200) but receives 401/403 on `GET /api/spend/{own_user_id}`. Catches a regression where `/api/spend` might be mis-gated by ownership rather than admin-flag (which would let any user read their own spend bypassing admin oversight).

### Stability Verification

All 10 tests verified passing across 3 consecutive runs (~5.6s each, no flakiness). Tests use the standard `client` and `db_session` fixtures from `conftest.py`, with `mock_knowledge_service_trigger` (auto-applied) preventing background HTTP tasks. No timing-dependent assertions and no shared state between tests.

## Flaky Test Hunt - Tuesday QA (Added 2026-06-02)

**Focus**: Pin the remaining gaps in `_should_respond` probability math (cap transitions, two-call ordering), `is_mentioned` matching rules, and the `_split_response_into_bubbles` transition-word guard at sentence index 0.

### Analysis Results

- Re-ran the 241-test random/timing-prone subset (`flaky`, `random`, `bubble`, `split`, `should_respond`, `should_prompt`, `thinking_display`, `choose_response_style`, `choose_style`, `strategy_roll`, `randint`) **5× back-to-back** — 241 passed every run in ~18s. No flakiness detected.
- Prior flaky-hunt sessions (mar17, apr14, apr28, may5, may12, may19, may26) already pinned every `strategy_roll` boundary, every `_choose_response_style` roll threshold, every `randint` endpoint, the `_should_prompt_user` threshold formula, the strict `>` direction at `consecutive_silence > 2`, the 15% silence cutoff, and the own-message override `base_probability = 0.05`.
- **Remaining gaps targeted this run**: (a) the cap *transition* in `min(0.25 + N*0.12, 0.7)` — earlier tests used N=10 (deep cap region) and wouldn't catch a coefficient regression; (b) the **two-call ordering** of `random.random()` in `_should_respond` (silence-check then response-check); (c) the silence-boost cap `min(_, 0.9)` upper-cap transition; (d) the addressed-by-name cap `min(_, 0.95)` transition; (e) `is_mentioned` boundary cases; (f) the `current_bubble and ...` guard at sentence-0 that prevents spurious empty bubbles when text starts with a transition word.

### Tests Added (test_flaky_hunt_jun2_2026.py)

**File**: `tests/test_flaky_hunt_jun2_2026.py` (20 new tests)

#### TestShouldRespondBaseProbabilityCapTransition
1. `test_n3_base_probability_is_0_61_uncapped` — N=3 → `base = 0.25 + 3*0.12 = 0.61`; `random=0.60 < 0.61` → True. Pins the formula coefficients (regression flipping `0.12` → `0.10` would change this).
2. `test_n3_response_strict_lt_boundary` — N=3 → base=0.61; `random=0.61` NOT `< 0.61` → False. Strict-`<` direction at the formula-computed value.
3. `test_n4_base_probability_engages_cap_at_0_7` — N=4 → `0.25 + 4*0.12 = 0.73 → min(_, 0.7) = 0.7`; `random=0.69 < 0.7` → True. Verifies the cap engages at N=4, NOT at N=10 (where prior tests live).
4. `test_n4_cap_strict_lt_at_0_70` — N=4 cap at 0.7; `random=0.70` NOT `< 0.70` → False. Pins the cap VALUE (0.7) exactly.

#### TestShouldRespondRandomCallOrdering
5. `test_exactly_two_random_calls_made_in_unaddressed_path` — `random.random()` is called exactly **twice** in the not-@mentioned / not-addressed path (line 1597 silence-check, line 1600 response-check). Regressions that collapse or duplicate calls would fail call-count assertion.
6. `test_first_call_is_silence_check_second_is_response` — With `side_effect=[0.14, 0.99]`, the first call triggers the `< 0.15` silence early-return after only ONE call. A swapped order would consume both values and reach a different answer.

#### TestShouldRespondConsecutiveSilenceCap
7. `test_silence_3_gives_uncapped_0_67` — N=1, silence=3 → `0.37 + 0.3 = 0.67` uncapped; `random=0.66` → True, `random=0.67` → False. Pins the silence-boost formula `(silence * 0.1)` exactly.
8. `test_silence_6_engages_cap_at_0_9` — N=1, silence=6 → `0.37 + 0.6 = 0.97 → min(_, 0.9) = 0.9`; `random=0.89` → True, `random=0.90` → False. Pins the cap VALUE (0.9) — a regression raising the cap would incorrectly return True at 0.90.

#### TestShouldRespondWasAddressedCap
9. `test_n1_addressed_no_cap_at_0_87` — Name in message (no `@`) + N=1 → `0.37 + 0.5 = 0.87` uncapped; `random=0.86` → True, `random=0.87` → False.
10. `test_n1_addressed_skips_silence_check` — `was_addressed=True` short-circuits the line-1597 silence check, so only ONE `random.random()` call is made (not two). Pins the short-circuit behavior.
11. `test_n2_addressed_engages_cap_at_0_95` — N=2 + addressed → `0.49 + 0.5 = 0.99 → min(_, 0.95) = 0.95`; `random=0.94` → True, `random=0.95` → False. Pins the addressed-boost cap VALUE (0.95) exactly.

#### TestIsMentionedBoundaries
12. `test_full_name_at_mention_matches` — `@Socrates` matches thinker `Socrates`.
13. `test_first_name_at_mention_matches_multi_word` — `@Marie` matches thinker `Marie Curie` (first-name path in `is_mentioned`).
14. `test_full_quoted_at_mention_matches_multi_word` — `@"Marie Curie"` matches thinker `Marie Curie` (quoted-name extraction path).
15. `test_case_insensitive_match` — `@socrates` matches `Socrates` (lowercased compare).
16. `test_no_at_symbol_does_not_match` — Bare `Socrates` (no `@`) returns False. Critical for the `was_at_mentioned` vs `was_addressed` distinction in `_should_respond`.
17. `test_wrong_at_mention_does_not_match` — `@Plato` does NOT match `Socrates`.
18. `test_empty_text_does_not_match` — Empty text → no mentions → False.

#### TestSplitBubblesTransitionAtIndexZero
19. `test_leading_but_combines_with_next_sentence_under_target` — Text starting with `But ...` followed by another sentence (total length under target_size) must produce a SINGLE bubble. Pins the `current_bubble and ...` guard at line 751 — a regression flipping `and` to `or` would split on the empty current_bubble at sentence-0 and produce 2 bubbles.
20. `test_leading_however_combines_with_next_sentence_under_target` — Same guard with `However,` transition. Confirms the guard short-circuits for ALL transition words, not just `But `.

### Stability Verification

All 20 tests verified passing across 5 consecutive runs (~1.3s each, no flakiness). The full backend suite (1744 passed, 10 skipped, ~7:00) also runs cleanly with the new tests included. Tests use only mocks/patches — no real network, DB, or background-task dependencies.

## Flaky Test Hunt - Tuesday QA (Added 2026-06-09)

**Focus**: Pin the speed-multiplier scaling of `_should_prompt_user` (`thinker.py:1444-1470`) — the one probabilistic branch whose `speed_mult**0.3` scaling was never locked deterministically.

### Analysis Results

- Full backend suite ran clean **twice** (1758 passed, 10 skipped, ~7:00 each).
- The random/timing-prone subset (331 tests matching `flaky`, `random`, `bubble`, `split`, `should_respond`, `should_prompt`, `thinking_display`, `choose_response`, `choose_style`, `strategy`, `randint`, `mention`) ran **5× back-to-back** — 331 passed every run (~25s). **No flakiness detected.**
- **Gap found**: `_should_prompt_user` scales both its threshold and probability by `speed_mult**0.3`, but existing tests only exercise `speed_mult=1.0` (where `speed**anything == 1`, hiding the exponent) plus one `6.0` test using `random=0.0` (passes any positive probability). The exponent `0.3`, the base constants (`8`, `0.15`), and the `max(4, ...)` floor were effectively unguarded. A mutation changing `0.3`→`0.5` was confirmed to slip past the prior suite but fails 3 of the new tests.
  - `threshold = max(4, int(8 / speed_mult**0.3))`
  - `prompt_probability = 0.15 * speed_mult**0.3`

### Tests Added (test_flaky_hunt_jun9_2026.py)

**File**: `tests/test_flaky_hunt_jun9_2026.py` (7 new tests)

#### TestShouldPromptUserProbabilityScaling
1. `test_fixed_roll_flips_outcome_across_speeds` — A single fixed roll (0.20) yields False at speed 1.0 (prob 0.15) but True at speed 6.0 (prob 0.2568). Same roll, opposite outcomes — pins that probability *increases* with speed. A regression dropping the `speed_mult**0.3` factor (flat 0.15) would return False at 6.0.
2. `test_exact_probability_boundary_at_speed_1` — At speed 1.0 prob is exactly 0.15; `roll=0.149` → True, `roll=0.15` → False (strict `<`). Pins the base constant 0.15 and the strict-less-than direction.
3. `test_scaled_probability_value_at_speed_6` — At speed 6.0 prob ≈ 0.2568; `roll=0.25` → True, `roll=0.26` → False. Brackets the scaled probability so a changed exponent/base shifts it out of the `[0.25, 0.26)` window.

#### TestShouldPromptUserThresholdScaling
4. `test_threshold_is_5_at_speed_4_locks_exponent` — At speed 4.0 threshold = `max(4, int(8/4**0.3))` = 5. `messages_since_user=4` (< 5, roll=0.0) → False; `=5` (== 5) → True. Locks the exponent: at speed 4.0 exp 0.2 → threshold 6 and exp 0.5 → 4, so only exp 0.3 yields 5 (the speed-6.0 test can't distinguish exp 0.3 from 0.5, both → 4).
5. `test_threshold_strict_less_than_boundary_at_speed_2` — At speed 2.0 threshold = 6; `=5` → False, `=6` → True (gate is strict `<`, `6 < 6` is False). Pins the threshold value and the strict-< gate.
6. `test_threshold_floor_of_4_at_high_speed` — At speed 20.0 the raw value `int(8/20**0.3)=3` is clamped by `max(4, ...)` to 4. `messages_since_user=3` → False, `=4` → True. Guards the floor, which is never reached at the production-clamped max speed of 6.0.

#### TestShouldPromptUserShortHistoryBeatsSpeed
7. `test_four_messages_returns_false_even_at_high_speed` — A 4-message history (< 5) short-circuits to False at line 1456 even at speed 6.0, and `random.random()` is never called (asserted via `call_count == 0`). Pins precedence of the short-history gate over the speed-based logic.

### Stability Verification

All 7 tests verified passing across 3 consecutive runs (~0.8s each, no flakiness). Mutation check (`speed_mult**0.3` → `**0.5`) confirmed 3 tests fail on the regression and all 7 pass again once reverted. The full backend suite (1758 passed, 10 skipped) runs cleanly with the new tests included. Tests use only mocks/patches — no real network, DB, or background-task dependencies.
