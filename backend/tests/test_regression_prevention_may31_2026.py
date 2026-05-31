"""Regression prevention tests for Sunday QA (May 31, 2026).

Focus: pin down behavioral and source-level invariants for bug fixes /
features that earlier regression suites have not explicitly guarded.

Each prior Sunday's regression set picked up the fixes that were freshest at
the time. By cross-referencing the existing `test_regression_prevention_*.py`
files, the following fixes/features still lack dedicated source-level guards
(i.e., the kind of "reviewer aid" that fails when a refactor silently
reintroduces the original bug):

- fix(feedback) #214 (commit ef3c3dc): screenshot upload support
  Adds `screenshot_data` / `screenshot_filename` to the `Feedback` model and
  the `FeedbackCreate` schema, plus a `MAX_SCREENSHOT_SIZE` field validator.
  Without these wired up correctly a future cleanup could drop the columns
  silently — leaving the API accepting a field that is never persisted.

- feedback rate-limit invariants (feedback.py constants)
  The MAX_SUBMISSIONS_PER_HOUR = 5 contract and the use of *hashed* IPs (not
  raw IPs) for rate limiting. Existing tests verify behavior end-to-end but
  do not pin the numeric constant or the privacy-preserving hash usage.

- feat(devops) #459 / fix(cleanup) #275 (commits 6fed42a, 9f25bc7): test-user
  cleanup endpoint. The TEST_USER_PREFIXES tuple is *load-bearing*: only
  usernames starting with one of the listed prefixes can be deleted via the
  admin-style endpoint. Adding a prefix here implicitly enlarges the
  endpoint's destructive blast radius. Removing one would silently leave
  the corresponding CI workflow unable to clean up after itself.

- fix(websocket) #367 (commit a9c7742): connect handler always sends current
  pause state. The earlier May 17 / May 24 regression sets cover the
  WSMessageType wire constants and the dual-pause-set contracts, but they
  do not pin the *source-level* invariant that the connect handler dispatches
  on `is_paused` before entering the receive loop. A refactor that moves the
  sync into the receive loop would break the documented thread-switch fix.

- feat(backend) #144 (commit 346bc33): /health/ready deep readiness probe.
  Probes the database with `SELECT 1` and returns 503 when degraded. The
  apr12 file pins the *behavior* (endpoint responds quickly with a shared
  test client) but does not pin the source-level invariants (uses SELECT 1,
  uses 503 for degraded).

- feat(auth) #163 (commit 7acadd7): password change + display-name update.
  The schema validation bounds (min_length=6 for passwords, max_length=100
  for display names) are exposed via the API contract. The mar15 / apr19
  files cover the *behavior* (wrong password rejected, etc.) but not the
  *schema bounds* — a refactor that loosens min_length=6 to no minimum
  would let users set 1-character passwords and not break existing tests.

- test_helpers security: the `trigger_error` endpoint MUST refuse requests
  in production via `is_test_mode()`. This is a security-critical guard
  (raising errors over WebSockets without auth could be abused) and is not
  pinned at the source level by any existing test.

Test groups (this file, 24 tests total):
- TestFeedbackScreenshotFieldsContract (5): fix #214 screenshot wiring
- TestFeedbackRateLimitContract (3): MAX_SUBMISSIONS_PER_HOUR + hashed IP
- TestTestUserPrefixesCleanupContract (4): feat #459 / fix #275 prefix tuple
- TestWebsocketConnectPauseStateSyncSource (3): fix #367 connect-handler
- TestHealthReadyEndpointSourceGuards (3): feat #144 deep-readiness probe
- TestUserProfileValidationContract (4): feat #163 schema bounds
- TestTriggerErrorTestModeGuard (2): test_helpers security guard
"""

import inspect
import re

from sqlalchemy import String, Text

from app.api import feedback as feedback_api
from app.api import test_helpers
from app.api import websocket as websocket_module
from app.main import health_ready
from app.models import Feedback
from app.schemas.auth import (
    ChangePasswordRequest,
    UserProfileUpdate,
    UserRegister,
)
from app.schemas.feedback import MAX_SCREENSHOT_SIZE, FeedbackCreate

# ===========================================================================
# TestFeedbackScreenshotFieldsContract
# Regression guard for fix #214 (commit ef3c3dc).
#
# The screenshot feature stores a base64-encoded image and an optional
# filename. If either column is silently dropped (e.g., a column rename
# without a migration), the API would still happily accept screenshots
# from clients but never persist them — a "data quietly dropped" failure
# mode that's hard to catch from black-box testing.
#
# The field validator enforces MAX_SCREENSHOT_SIZE so that a single user
# cannot DoS the backend by submitting multi-gigabyte payloads.
# ===========================================================================


class TestFeedbackScreenshotFieldsContract:
    """Regression guards: Feedback screenshot fields wired model<->schema<->API."""

    def test_feedback_model_has_screenshot_data_text_column(self) -> None:
        """Feedback.screenshot_data is a nullable Text column.

        Regression guard for fix #214: the column must be Text (not VARCHAR)
        because base64-encoded screenshots can exceed the default 255-char
        VARCHAR limit by orders of magnitude. A naive refactor that changes
        Text to String(...) would truncate every screenshot at submit time.
        """
        column = Feedback.__table__.c.screenshot_data
        assert isinstance(column.type, Text), (
            f"screenshot_data must be Text (got {type(column.type).__name__}). "
            f"Base64 PNG screenshots routinely exceed any practical VARCHAR cap."
        )
        assert column.nullable is True, (
            "screenshot_data must be nullable — most feedback submissions "
            "won't include a screenshot, and a NOT NULL column would break "
            "every text-only feedback submission."
        )

    def test_feedback_model_has_screenshot_filename_string_column(self) -> None:
        """Feedback.screenshot_filename is a nullable String(255) column.

        Regression guard for fix #214: filenames are short (~1-100 chars)
        so a String column with a sensible cap is fine — but it must remain
        nullable, since the Feedback model is only optionally a screenshot.
        """
        column = Feedback.__table__.c.screenshot_filename
        assert isinstance(column.type, String), (
            f"screenshot_filename must be a String type (got {type(column.type).__name__})."
        )
        assert column.nullable is True, (
            "screenshot_filename must be nullable — feedback without a "
            "screenshot has no associated filename."
        )

    def test_feedback_create_schema_accepts_screenshot_fields(self) -> None:
        """FeedbackCreate has screenshot_data and screenshot_filename fields.

        Regression guard for fix #214: if a future refactor removes these
        from the schema while leaving them on the model, the API would
        silently strip user-submitted screenshots before persisting.
        """
        fields = FeedbackCreate.model_fields
        assert "screenshot_data" in fields, (
            "FeedbackCreate must expose screenshot_data so the API persists it."
        )
        assert "screenshot_filename" in fields, (
            "FeedbackCreate must expose screenshot_filename so the API persists it."
        )
        # Both should be optional (default None) — most feedback has no screenshot.
        assert fields["screenshot_data"].default is None
        assert fields["screenshot_filename"].default is None

    def test_max_screenshot_size_caps_payload_around_5mb_binary(self) -> None:
        """MAX_SCREENSHOT_SIZE is 7_000_000 bytes (~5MB binary post-base64).

        Regression guard: this constant is documented to be 7MB to cover
        a ~5MB binary image after base64 encoding (33% overhead). If the
        constant is changed without updating the inline comment / docs,
        a future reviewer can't tell whether the change was intentional.
        """
        assert MAX_SCREENSHOT_SIZE == 7_000_000, (
            f"MAX_SCREENSHOT_SIZE expected 7_000_000 (~5MB binary after "
            f"base64), got {MAX_SCREENSHOT_SIZE}. If you intend to raise "
            f"or lower the screenshot cap, update both the constant and "
            f"the inline comment that documents the 5MB binary limit."
        )

    def test_feedback_create_rejects_oversize_screenshot(self) -> None:
        """FeedbackCreate.validate_screenshot_size raises when payload exceeds limit.

        Regression guard for fix #214: the validator is what prevents a
        client from DoS-ing the backend with a multi-GB payload. If the
        validator were removed, the API would happily try to persist a
        gigabyte of base64 into a single row.
        """
        import pytest
        from pydantic import ValidationError

        oversize = "x" * (MAX_SCREENSHOT_SIZE + 1)
        with pytest.raises(ValidationError):
            FeedbackCreate(message="x" * 20, screenshot_data=oversize)


# ===========================================================================
# TestFeedbackRateLimitContract
# Regression guards for the feedback rate-limit constants and the
# privacy-preserving hashed-IP lookup.
#
# Both invariants are user-visible (rate-limit threshold) or privacy-relevant
# (raw vs. hashed IP) and would be silently regression-able in a cleanup
# refactor without these tests.
# ===========================================================================


class TestFeedbackRateLimitContract:
    """Regression guards: rate-limit constants and hashed-IP lookup."""

    def test_max_submissions_per_hour_constant_is_five(self) -> None:
        """MAX_SUBMISSIONS_PER_HOUR == 5 (documented public contract).

        Regression guard: the limit is documented in the submit_feedback
        docstring ("Maximum 5 submissions per hour per IP"). If this
        constant drifts from the docstring, frontend error messages and
        user-facing rate-limit copy can desync from backend behavior.
        """
        assert feedback_api.MAX_SUBMISSIONS_PER_HOUR == 5, (
            f"MAX_SUBMISSIONS_PER_HOUR must be 5 (matches docstring). "
            f"Got {feedback_api.MAX_SUBMISSIONS_PER_HOUR}. If you intend to "
            f"change the rate limit, also update the submit_feedback "
            f"docstring and any frontend copy that mentions '5 per hour'."
        )

    def test_submit_feedback_source_uses_hashed_ip_not_raw(self) -> None:
        """submit_feedback's rate-limit lookup uses hash_ip(client_ip).

        Regression guard: storing raw IPs in the Feedback.ip_hash column
        would defeat the privacy-preserving design — a database leak would
        expose every submitter's IP. The hashing happens client-side of
        the DB lookup so the rate-limit query MUST use the hashed value.
        """
        source = inspect.getsource(feedback_api.submit_feedback)
        # The rate-limit query must filter by ip_hash, not raw IP.
        assert "Feedback.ip_hash == ip_hash" in source, (
            "submit_feedback's rate-limit query must filter by `ip_hash` "
            "(the SHA-256-hashed client IP), not raw IP. Storing or querying "
            "by raw IP would expose submitter IPs on any DB leak."
        )
        # And ip_hash must come from hash_ip(client_ip) — not from the raw IP.
        assert "hash_ip(client_ip)" in source, (
            "submit_feedback must call hash_ip(client_ip) to produce the "
            "rate-limit key. A bare `client_ip` would leak raw IPs into "
            "the ip_hash column."
        )

    def test_submit_feedback_source_uses_one_hour_window(self) -> None:
        """The rate-limit window is exactly 1 hour (matches MAX_SUBMISSIONS_PER_HOUR).

        Regression guard: the window length and the count threshold form
        a single contract ("5 submissions per HOUR"). A drift in either
        (e.g., changing to timedelta(hours=24)) without updating the
        constant would silently change the documented rate-limit policy.
        """
        source = inspect.getsource(feedback_api.submit_feedback)
        # Match `timedelta(hours=1)` with optional whitespace.
        assert re.search(r"timedelta\s*\(\s*hours\s*=\s*1\s*\)", source), (
            "submit_feedback must use `timedelta(hours=1)` as the rate-limit "
            "window. The constant MAX_SUBMISSIONS_PER_HOUR=5 and this "
            "1-hour window form a single contract; both must update together."
        )


# ===========================================================================
# TestTestUserPrefixesCleanupContract
# Regression guards for feat #459 / fix #275.
#
# The cleanup-test-users endpoint is destructive (DELETE). The TEST_USER_PREFIXES
# tuple is the *only* safety mechanism keeping it from being able to delete
# real users. Specifically:
#
#   - Every prefix must be lowercase (case-sensitive match — a "Testuser_"
#     user would NOT be matched, but more importantly a "TestUser..." real
#     user must not be matched either).
#   - The tuple shape (not list) is intentional — tuples are immutable, so
#     a typo in a single place doesn't open the door to additional prefixes.
# ===========================================================================


class TestTestUserPrefixesCleanupContract:
    """Regression guards: cleanup endpoint's prefix-allowlist contract."""

    def test_test_user_prefixes_contains_documented_three(self) -> None:
        """TEST_USER_PREFIXES contains exactly ('smoketest_', 'canary_', 'testuser_').

        Regression guard for feat #459 / fix #275: these three prefixes are
        the documented allowlist for the cleanup endpoint. Adding a prefix
        here implicitly broadens the endpoint's destructive blast radius;
        removing one breaks the corresponding CI workflow.
        """
        assert test_helpers.TEST_USER_PREFIXES == (
            "smoketest_",
            "canary_",
            "testuser_",
        ), (
            f"TEST_USER_PREFIXES changed. Expected exactly "
            f"('smoketest_', 'canary_', 'testuser_'), got "
            f"{test_helpers.TEST_USER_PREFIXES!r}. If you intend to add or "
            f"remove a prefix, audit the corresponding CI workflows AND "
            f"update this test."
        )

    def test_test_user_prefixes_are_all_lowercase(self) -> None:
        """Every TEST_USER_PREFIXES entry is lowercase.

        Regression guard: the cleanup query uses `username.startswith(prefix)`
        which is case-sensitive. If a prefix were ever uppercased (e.g.,
        "SmokeTest_"), it would silently fail to match any real
        smoketest user — the cleanup would become a no-op.
        """
        for prefix in test_helpers.TEST_USER_PREFIXES:
            assert prefix == prefix.lower(), (
                f"Prefix {prefix!r} must be lowercase. The cleanup query "
                f"uses case-sensitive startswith, so a non-lowercase prefix "
                f"silently fails to match any real test users."
            )

    def test_test_user_prefixes_is_immutable_tuple(self) -> None:
        """TEST_USER_PREFIXES is a tuple, not a list (immutability guard).

        Regression guard: a mutable list could be appended to at runtime
        (e.g., by a poorly-written debug helper) and that would broaden
        the endpoint's destructive surface without any code review.
        """
        assert isinstance(test_helpers.TEST_USER_PREFIXES, tuple), (
            f"TEST_USER_PREFIXES must be a tuple (immutable). Got "
            f"{type(test_helpers.TEST_USER_PREFIXES).__name__}. A mutable "
            f"list could be appended at runtime, broadening the cleanup "
            f"endpoint's destructive scope without any code review."
        )

    def test_cleanup_test_users_source_requires_secret_match(self) -> None:
        """cleanup_test_users source contains both 'not configured' and 'Invalid' checks.

        Regression guard for fix #275: the endpoint must reject BOTH
        missing-secret (settings.test_cleanup_secret == "") AND
        wrong-secret (secret != settings.test_cleanup_secret) cases.
        Dropping either check would expose the destructive endpoint either
        when secrets are misconfigured or to anyone who omits the param.
        """
        source = inspect.getsource(test_helpers.cleanup_test_users)
        # Must check both: unconfigured AND wrong secret.
        assert "not settings.test_cleanup_secret" in source, (
            "cleanup_test_users must reject the unconfigured-secret case "
            "(empty TEST_CLEANUP_SECRET). Otherwise an env-var typo would "
            "silently expose the destructive endpoint."
        )
        assert "secret != settings.test_cleanup_secret" in source, (
            "cleanup_test_users must reject the wrong-secret case. "
            "Without this check, any caller could trigger destructive "
            "cleanup by guessing the endpoint path."
        )


# ===========================================================================
# TestWebsocketConnectPauseStateSyncSource
# Regression guard for fix #367 (commit a9c7742).
#
# Bug: when a user switched threads, the frontend pause button stuck in
# the wrong state because the new WebSocket connection didn't receive a
# fresh PAUSED/RESUMED message. Fix: the connect handler always sends
# the current pause state (PAUSED or RESUMED) immediately after accepting
# the connection, before entering the message receive loop.
#
# This MUST happen on every connect, not "only if state changed" — that
# was the original bug.
# ===========================================================================


class TestWebsocketConnectPauseStateSyncSource:
    """Regression guards: websocket_endpoint always sends pause state on connect."""

    def test_websocket_endpoint_source_dispatches_on_is_paused(self) -> None:
        """websocket_endpoint source contains `thinker_service.is_paused`.

        Regression guard for fix #367: the connect handler must check
        `thinker_service.is_paused(conversation_id)` so it can send the
        correct PAUSED vs RESUMED sync message. A refactor that drops
        this check would leave the frontend with stale pause state on
        thread switch.
        """
        source = inspect.getsource(websocket_module.websocket_endpoint)
        assert "thinker_service.is_paused(conversation_id)" in source, (
            "websocket_endpoint must call `thinker_service.is_paused"
            "(conversation_id)` on connect to determine which sync "
            "message to send. Without this, the frontend pause button "
            "sticks in stale state after thread switches (fix #367)."
        )

    def test_websocket_endpoint_source_has_paused_and_resumed_branches(self) -> None:
        """websocket_endpoint source contains both PAUSED and RESUMED sync sends.

        Regression guard for fix #367: the sync MUST cover BOTH states.
        An "only send PAUSED when paused" optimization would leave the
        frontend stuck in PAUSED state when switching to an unpaused
        conversation — the exact bug fix #367 corrected.
        """
        source = inspect.getsource(websocket_module.websocket_endpoint)
        # Both PAUSED and RESUMED must be sent based on is_paused result.
        assert "WSMessageType.PAUSED" in source, (
            "Connect handler must send WSMessageType.PAUSED for paused conversations (fix #367)."
        )
        assert "WSMessageType.RESUMED" in source, (
            "Connect handler must send WSMessageType.RESUMED for "
            "unpaused conversations on every connect — this is the "
            "core of fix #367. Otherwise switching FROM a paused thread "
            "TO an unpaused one leaves the UI stuck in 'paused'."
        )

    def test_websocket_endpoint_sync_happens_before_receive_loop(self) -> None:
        """The pause-state sync is dispatched BEFORE the `while True` receive loop.

        Regression guard for fix #367: the sync must be unconditional and
        early. If it were deferred into the message-handling loop (e.g.,
        triggered only by a JOIN message), a client that connects and
        immediately receives a thinker message would still see stale
        pause state until they happened to send anything.
        """
        source = inspect.getsource(websocket_module.websocket_endpoint)
        # Find the positions of the sync send and the receive loop.
        paused_pos = source.find("WSMessageType.PAUSED")
        resumed_pos = source.find("WSMessageType.RESUMED")
        # The receive loop is `while True` — find it.
        loop_pos = source.find("while True")
        assert loop_pos > 0, "websocket_endpoint must contain a `while True` receive loop."
        assert paused_pos > 0, "Connect handler must reference WSMessageType.PAUSED."
        assert resumed_pos > 0, "Connect handler must reference WSMessageType.RESUMED."
        assert paused_pos < loop_pos, (
            "PAUSED sync must be sent BEFORE the receive loop "
            "(fix #367 requires unconditional sync on connect)."
        )
        assert resumed_pos < loop_pos, (
            "RESUMED sync must be sent BEFORE the receive loop "
            "(fix #367 requires unconditional sync on connect)."
        )


# ===========================================================================
# TestHealthReadyEndpointSourceGuards
# Regression guard for feat #144 (commit 346bc33).
#
# The /health/ready endpoint is a deep readiness probe used by load balancers
# to decide whether the service should receive traffic. It MUST:
#
#   1. Actually probe the database (not just return 200 unconditionally).
#   2. Return 503 when the DB check fails.
#   3. Return 200 when all checks pass.
#
# Existing tests (apr12) verify the endpoint responds quickly under the
# shared test client. These tests pin the source-level contract: a future
# refactor that "simplifies" the endpoint to always return 200 wouldn't
# break the apr12 test but WOULD break production traffic management.
# ===========================================================================


class TestHealthReadyEndpointSourceGuards:
    """Regression guards: /health/ready actually probes the database."""

    def test_health_ready_source_executes_select_1_probe(self) -> None:
        """health_ready source contains a `SELECT 1` database probe.

        Regression guard for feat #144: the readiness probe must execute
        a real DB query. A refactor that replaced this with `db is not None`
        would pass type checks and unit tests but would mask DB outages
        from load balancers — the worst kind of "always-green" health check.
        """
        source = inspect.getsource(health_ready)
        assert 'text("SELECT 1")' in source, (
            'health_ready must execute `text("SELECT 1")` to verify DB '
            "connectivity. A trivial pass-through (e.g., just returning "
            '`{"status": "ready"}`) would falsely report a downed DB as '
            "ready, causing traffic to route to a broken instance."
        )

    def test_health_ready_source_uses_503_for_degraded(self) -> None:
        """health_ready source contains the literal `503` for degraded status.

        Regression guard for feat #144: load balancers (and Railway's
        own routing) interpret 503 as "do not send traffic here". If the
        endpoint returned 200 on degradation, broken instances would
        continue receiving traffic.
        """
        source = inspect.getsource(health_ready)
        # The endpoint computes status_code = 200 if all_ok else 503.
        assert "503" in source, (
            "health_ready must return HTTP 503 when checks fail. Load "
            "balancers use 503 to drop a backend from rotation; 200 "
            "would keep broken instances receiving traffic."
        )

    def test_health_ready_source_uses_200_for_ready(self) -> None:
        """health_ready source contains the literal `200` for ready status.

        Regression guard for feat #144: dual-check (200 on success, 503
        on failure) is the documented contract. A refactor that drops the
        explicit `200` (e.g., relies on FastAPI's default) is fine in
        practice, but combined with a wrapped JSONResponse the default
        may not apply — pinning both literals locks the contract.
        """
        source = inspect.getsource(health_ready)
        assert "200" in source, (
            "health_ready must explicitly return HTTP 200 when ready. "
            "Relying on FastAPI defaults breaks when the response is "
            "wrapped in a JSONResponse with an explicit status_code."
        )


# ===========================================================================
# TestUserProfileValidationContract
# Regression guards for feat #163 (commit 7acadd7).
#
# The user-profile-management feature exposes password and display-name
# updates. The Pydantic schemas carry validation bounds that ARE the API
# contract — exposing them via the OpenAPI schema and enforcing them on
# every request. A loosening (e.g., min_length=6 → no minimum) would
# silently permit 1-character passwords without breaking any existing test.
# ===========================================================================


class TestUserProfileValidationContract:
    """Regression guards: profile-management schema bounds remain documented."""

    def test_change_password_request_new_password_requires_min_length_6(self) -> None:
        """ChangePasswordRequest.new_password requires min_length=6.

        Regression guard for feat #163: the 6-character minimum is the
        documented password policy. Dropping it (or lowering to 1) would
        weaken security without breaking any existing behavioral test.
        """
        fields = ChangePasswordRequest.model_fields
        new_password_field = fields["new_password"]
        # Extract the min_length constraint.
        constraints = new_password_field.metadata
        min_lengths = [c for c in constraints if hasattr(c, "min_length")]
        assert any(getattr(c, "min_length", None) == 6 for c in min_lengths), (
            f"ChangePasswordRequest.new_password must require min_length=6. "
            f"Constraints: {constraints}. The 6-character minimum is the "
            f"documented password policy; weakening it would silently "
            f"permit 1-character passwords."
        )

    def test_user_register_password_has_min_and_max_length(self) -> None:
        """UserRegister.password requires min_length=6 and max_length=100.

        Regression guard for feat #163: matching the change_password
        validator. Inconsistent bounds (e.g., register allows length-1
        passwords but change_password requires 6+) is a confusing UX
        and a security gap.
        """
        fields = UserRegister.model_fields
        password_field = fields["password"]
        constraints = password_field.metadata
        min_lengths = [getattr(c, "min_length", None) for c in constraints]
        max_lengths = [getattr(c, "max_length", None) for c in constraints]
        assert 6 in min_lengths, (
            f"UserRegister.password must require min_length=6. Got "
            f"min_length values: {min_lengths}. Must match the "
            f"change_password 6-character minimum."
        )
        assert 100 in max_lengths, (
            f"UserRegister.password must allow max_length=100. Got "
            f"max_length values: {max_lengths}. 100 chars is the "
            f"documented upper bound."
        )

    def test_user_register_display_name_has_min_and_max_length(self) -> None:
        """UserRegister.display_name requires min_length=1 and max_length=100.

        Regression guard for feat #163: empty display names should be
        rejected (otherwise the chat UI shows blank usernames). The
        max_length=100 cap matches the DB column bound.
        """
        fields = UserRegister.model_fields
        display_field = fields["display_name"]
        constraints = display_field.metadata
        min_lengths = [getattr(c, "min_length", None) for c in constraints]
        max_lengths = [getattr(c, "max_length", None) for c in constraints]
        assert 1 in min_lengths, (
            "UserRegister.display_name must require min_length=1 so empty "
            "display names cannot be submitted (would show blank usernames)."
        )
        assert 100 in max_lengths, (
            "UserRegister.display_name must allow max_length=100, matching "
            "the DB column bound in User.display_name."
        )

    def test_user_profile_update_display_name_has_min_and_max_length(self) -> None:
        """UserProfileUpdate.display_name requires min_length=1 and max_length=100.

        Regression guard for feat #163: profile-update validation must
        match registration validation. If they differ, a user could
        register with a valid display name and then update to an invalid
        one (or vice versa), creating inconsistent state.
        """
        fields = UserProfileUpdate.model_fields
        display_field = fields["display_name"]
        constraints = display_field.metadata
        min_lengths = [getattr(c, "min_length", None) for c in constraints]
        max_lengths = [getattr(c, "max_length", None) for c in constraints]
        assert 1 in min_lengths, (
            "UserProfileUpdate.display_name must require min_length=1 "
            "(matches UserRegister so users can't update to empty)."
        )
        assert 100 in max_lengths, (
            "UserProfileUpdate.display_name must allow max_length=100 "
            "(matches UserRegister and the DB column bound)."
        )


# ===========================================================================
# TestTriggerErrorTestModeGuard
# Regression guard for the test_helpers security contract.
#
# The /api/test/trigger-error endpoint can broadcast arbitrary error
# messages over WebSockets to active conversations. In production, this
# could be abused (visible to users as "your API has failed!") and must
# be locked behind the TEST_MODE environment variable.
#
# This guard ensures the production-disable check remains in the source.
# ===========================================================================


class TestTriggerErrorTestModeGuard:
    """Regression guards: trigger_error blocked in production."""

    def test_trigger_error_source_checks_is_test_mode(self) -> None:
        """trigger_error source calls is_test_mode() before broadcasting.

        Regression guard: this endpoint can broadcast arbitrary error
        messages over WebSockets to active conversations. Without the
        TEST_MODE check, a misconfigured production deploy would expose
        a public endpoint that any client could use to inject error
        banners into other users' chat sessions.
        """
        source = inspect.getsource(test_helpers.trigger_error)
        assert "is_test_mode()" in source, (
            "trigger_error must guard with `is_test_mode()` so it is "
            "disabled in production. Without this guard, a public "
            "endpoint could inject ERROR banners into any active "
            "conversation, potentially abusable for phishing/UI spoofing."
        )

    def test_trigger_error_source_returns_403_when_not_test_mode(self) -> None:
        """trigger_error returns HTTP 403 when TEST_MODE is not enabled.

        Regression guard: the documented response is 403 Forbidden so
        clients can distinguish "endpoint disabled" from "endpoint not
        found" (404). Changing the status code to 404 would mask the
        endpoint's existence — fine for security through obscurity,
        but inconsistent with the documented behavior.
        """
        source = inspect.getsource(test_helpers.trigger_error)
        # The HTTPException must have status_code=403.
        assert "status_code=403" in source, (
            "trigger_error must raise HTTPException(status_code=403) when "
            "TEST_MODE is not enabled. The docstring documents 403 as the "
            "expected response; drift from this contract is a documented "
            "API change that must be coordinated with API consumers."
        )
