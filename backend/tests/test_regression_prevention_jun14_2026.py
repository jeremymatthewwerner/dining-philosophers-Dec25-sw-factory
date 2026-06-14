"""Regression prevention tests for Sunday QA (June 14, 2026).

Focus: pin down behavioral and source-level invariants for shipped fixes /
features that earlier regression suites have not yet explicitly guarded.

Each prior Sunday's regression set picked up the fixes that were freshest at
the time. By cross-referencing every existing `test_regression_prevention_*.py`
file against the merged commit history, the following fixes/features still
lack dedicated source-level guards — the kind of "reviewer aid" that fails
when a refactor silently reintroduces the original bug while every behavioral
test stays green:

- feat(feedback) #332 (commit d1a8123): include username in feedback submissions.
  Adds `username` to the `Feedback` model (String(50), nullable), the
  `FeedbackCreate` request schema, and the `FeedbackDetail` admin schema.
  `submit_feedback` persists it and `get_pending_feedback` passes it through.
  The May 17 / Apr 19 suites cover the enum wiring and the processor-secret
  flow but never pin the username plumbing. If a future cleanup dropped the
  column or stopped persisting it, feedback from logged-in users would
  silently lose the one field that ties it back to an account — and no
  existing test would fail.

- feat(backend) #17 / #12 (commits 9636b45, 8c6473d): the `/api/version`
  endpoint and the `VERSION` constant. No existing regression suite pins that
  the endpoint returns the `VERSION` constant (not a hard-coded literal) plus
  the documented app name. A refactor that inlined a stale literal would make
  the public version probe lie about the deployed build.

- feat(feedback) #193 / #218 (commits a8e9a53, bad4303): the in-app feedback
  form contract. The `FeedbackCreate.message` bounds (min_length=10,
  max_length=5000) are the documented submission policy; the
  `get_pending_feedback` query invariants (oldest-first ordering, NEW-only
  filter, limit clamped to 1-50); and the `MarkProcessedRequest.github_issue_url`
  bounds (min 1 / max 500). Apr 19 pins the 503/403 secret behavior but not
  these contract bounds — a loosening would silently change documented
  request validation.

Test groups (this file, 18 tests total):
- TestFeedbackUsernameWiringContract (5): feat #332 username plumbing
- TestVersionEndpointContract (4): feat #17 / #12 version endpoint
- TestFeedbackMessageBoundsContract (3): feat #193 message length policy
- TestPendingFeedbackQueryContract (4): feat #218 ordering / filter / limit
- TestMarkProcessedRequestContract (2): feat #218 issue-url bounds
"""

import inspect

import pytest
from pydantic import ValidationError
from sqlalchemy import String

from app import VERSION
from app.api import feedback as feedback_api
from app.main import version as version_endpoint
from app.models.feedback import Feedback
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackDetail,
    MarkProcessedRequest,
)

# ===========================================================================
# TestFeedbackUsernameWiringContract
# Regression guard for feat #332 (commit d1a8123).
#
# Logged-in users submitting feedback have their Dining Philosophers username
# attached so the software factory can tie feedback back to an account. The
# field flows model <-> request schema <-> admin schema <-> persistence. If
# any link in that chain is dropped, the username is silently discarded — a
# "data quietly lost" failure mode that black-box tests miss because the
# submit endpoint returns only an id + thank-you message.
# ===========================================================================


class TestFeedbackUsernameWiringContract:
    """Regression guards: Feedback username wired model<->schema<->persist."""

    def test_feedback_model_has_username_string50_nullable(self) -> None:
        """Feedback.username is a nullable String(50) column.

        Regression guard for feat #332: usernames are short, so String(50)
        is the documented cap (matches FeedbackCreate.username max_length=50).
        It must stay nullable because anonymous (logged-out) users submit
        feedback with no username — a NOT NULL column would reject every
        anonymous submission, which is the primary use case of the form.
        """
        column = Feedback.__table__.c.username
        assert isinstance(column.type, String), (
            f"Feedback.username must be a String type (got {type(column.type).__name__})."
        )
        assert column.type.length == 50, (
            f"Feedback.username must be String(50) to match "
            f"FeedbackCreate.username max_length=50. Got length="
            f"{column.type.length}. A mismatch would let the schema accept "
            f"a 50-char username the DB column then truncates or rejects."
        )
        assert column.nullable is True, (
            "Feedback.username must be nullable — anonymous (logged-out) "
            "users submit feedback with no username. A NOT NULL column "
            "would reject the form's primary use case (feat #332)."
        )

    def test_feedback_create_schema_has_username_optional_max50(self) -> None:
        """FeedbackCreate.username is optional with max_length=50.

        Regression guard for feat #332: if the schema field were removed
        while the model kept the column, the API would strip every
        submitted username before persistence (logged-in feedback would
        look anonymous). The default must be None so the field stays
        optional for logged-out users.
        """
        fields = FeedbackCreate.model_fields
        assert "username" in fields, (
            "FeedbackCreate must expose `username` so the API persists the "
            "logged-in user's name with their feedback (feat #332)."
        )
        username_field = fields["username"]
        assert username_field.default is None, (
            "FeedbackCreate.username must default to None — logged-out "
            "users submit feedback without a username."
        )
        max_lengths = [getattr(c, "max_length", None) for c in username_field.metadata]
        assert 50 in max_lengths, (
            f"FeedbackCreate.username must cap at max_length=50 to match the "
            f"Feedback.username String(50) DB column. Got {max_lengths}."
        )

    def test_feedback_detail_schema_exposes_username(self) -> None:
        """FeedbackDetail (admin/pending view) includes the username field.

        Regression guard for feat #332: the pending-feedback view used by
        the feedback-to-issue workflow must surface the username so issues
        can be attributed. Dropping it from FeedbackDetail would make the
        username unrecoverable from the processing pipeline even though it
        is stored in the DB.
        """
        assert "username" in FeedbackDetail.model_fields, (
            "FeedbackDetail must expose `username` so the feedback-to-issue "
            "workflow can attribute issues to logged-in users (feat #332)."
        )

    def test_submit_feedback_source_persists_username(self) -> None:
        """submit_feedback constructs Feedback with username=data.username.

        Regression guard for feat #332: the column and schema field can both
        exist while the persistence step silently omits the mapping. The
        Feedback(...) constructor call must thread `username=data.username`
        through, or every submission lands with username=NULL regardless of
        what the client sent.
        """
        source = inspect.getsource(feedback_api.submit_feedback)
        assert "username=data.username" in source, (
            "submit_feedback must persist `username=data.username` when "
            "constructing the Feedback row. Without it, logged-in feedback "
            "is stored anonymously even though the schema accepts the field "
            "(feat #332)."
        )

    def test_get_pending_feedback_source_passes_username_through(self) -> None:
        """get_pending_feedback maps fb.username into each FeedbackDetail.

        Regression guard for feat #332: the pending endpoint builds
        FeedbackDetail objects field-by-field. If the username mapping is
        omitted here, the feedback-to-issue workflow can never see the
        username even though it is persisted — breaking attribution at the
        last hop.
        """
        source = inspect.getsource(feedback_api.get_pending_feedback)
        assert "username=fb.username" in source, (
            "get_pending_feedback must map `username=fb.username` into each "
            "FeedbackDetail. Dropping it hides the stored username from the "
            "feedback-to-issue workflow (feat #332)."
        )


# ===========================================================================
# TestVersionEndpointContract
# Regression guard for feat #17 (commit 9636b45) and feat #12 (commit 8c6473d).
#
# `/api/version` is a public, unauthenticated probe used to confirm which
# build is deployed. It MUST report the live `VERSION` constant (not a
# hard-coded literal that drifts at release time) and the documented app
# name. The endpoint is async and returns a plain dict.
# ===========================================================================


class TestVersionEndpointContract:
    """Regression guards: /api/version reports the VERSION constant + name."""

    def test_version_constant_is_defined_and_nonempty(self) -> None:
        """app.VERSION is a non-empty string.

        Regression guard for feat #12: the VERSION constant is the single
        source of truth the /api/version endpoint reads. If it were removed
        or blanked, the version probe would report an empty build id and the
        endpoint import would fail.
        """
        assert isinstance(VERSION, str) and VERSION, (
            f"app.VERSION must be a non-empty string (the single source of "
            f"truth for /api/version). Got {VERSION!r}."
        )

    @pytest.mark.asyncio
    async def test_version_endpoint_returns_version_constant(self) -> None:
        """version() returns the live VERSION constant under the 'version' key.

        Regression guard for feat #17: the endpoint must reflect the actual
        VERSION constant, not a stale inlined literal. Pinning the equality
        to the imported constant means a refactor that hard-codes a literal
        (which then drifts from VERSION at release time) fails this test.
        """
        result = await version_endpoint()
        assert result["version"] == VERSION, (
            f"/api/version must return the live VERSION constant "
            f"({VERSION!r}) under the 'version' key, not a hard-coded "
            f"literal. Got {result.get('version')!r}."
        )

    @pytest.mark.asyncio
    async def test_version_endpoint_returns_documented_app_name(self) -> None:
        """version() returns 'Dining Philosophers API' under the 'name' key.

        Regression guard for feat #17: the documented app name is part of
        the public contract. A rename that isn't coordinated with API
        consumers (dashboards, status pages) would silently break them.
        """
        result = await version_endpoint()
        assert result["name"] == "Dining Philosophers API", (
            f"/api/version must return name='Dining Philosophers API'. Got "
            f"{result.get('name')!r}. The app name is a public contract; a "
            f"rename must be coordinated with consumers."
        )

    def test_version_endpoint_source_reads_version_constant(self) -> None:
        """version() source references the VERSION constant (not a literal).

        Regression guard for feat #17: belt-and-suspenders with the runtime
        check above — pinning the source-level use of `VERSION` makes the
        intent explicit so a reviewer immediately sees that inlining a
        version string is a regression, not a stylistic choice.
        """
        source = inspect.getsource(version_endpoint)
        assert "VERSION" in source, (
            "version() must read the VERSION constant. Inlining a literal "
            "version string would let the reported version drift from the "
            "actual build at release time (feat #17)."
        )


# ===========================================================================
# TestFeedbackMessageBoundsContract
# Regression guard for feat #193 (commit a8e9a53).
#
# The in-app feedback form's message field carries the documented submission
# policy: at least 10 characters (reject empty / "asdf" spam) and at most
# 5000 (prevent unbounded payloads). These bounds are exposed via the
# OpenAPI schema and enforced on every request. A loosening would silently
# change what the form accepts without breaking any behavioral test.
# ===========================================================================


class TestFeedbackMessageBoundsContract:
    """Regression guards: FeedbackCreate.message length policy."""

    def test_feedback_message_requires_min_length_10(self) -> None:
        """FeedbackCreate.message requires min_length=10.

        Regression guard for feat #193: the 10-char minimum filters out
        empty and trivial ("ok", "asdf") submissions that create noise in
        the feedback-to-issue pipeline. Dropping the minimum would flood
        the pipeline with low-signal entries.
        """
        fields = FeedbackCreate.model_fields
        min_lengths = [getattr(c, "min_length", None) for c in fields["message"].metadata]
        assert 10 in min_lengths, (
            f"FeedbackCreate.message must require min_length=10 to reject "
            f"trivial submissions. Got min_length values: {min_lengths}."
        )

    def test_feedback_message_allows_max_length_5000(self) -> None:
        """FeedbackCreate.message caps at max_length=5000.

        Regression guard for feat #193: the 5000-char cap bounds the payload
        so a single submission can't store an unbounded blob. The message
        column is Text (no DB cap), so the schema bound is the only guard.
        """
        fields = FeedbackCreate.model_fields
        max_lengths = [getattr(c, "max_length", None) for c in fields["message"].metadata]
        assert 5000 in max_lengths, (
            f"FeedbackCreate.message must cap at max_length=5000. Got "
            f"max_length values: {max_lengths}. The message column is Text "
            f"(uncapped at the DB), so this schema bound is the only guard."
        )

    def test_feedback_create_rejects_too_short_and_accepts_valid(self) -> None:
        """FeedbackCreate enforces the 10-char minimum at validation time.

        Regression guard for feat #193: a behavioral check that a 9-char
        message is rejected and a 10-char message is accepted. This catches
        a regression even if the constraint were moved off the field
        metadata (e.g., into a custom validator that was later deleted).
        """
        with pytest.raises(ValidationError):
            FeedbackCreate(message="x" * 9)
        # Exactly 10 chars is the boundary and must be accepted.
        ok = FeedbackCreate(message="x" * 10)
        assert ok.message == "x" * 10


# ===========================================================================
# TestPendingFeedbackQueryContract
# Regression guard for feat #218 (commit bad4303).
#
# get_pending_feedback feeds the feedback-to-issue workflow. Its query has
# three load-bearing invariants:
#   1. NEW-only filter — already-processed feedback must not be re-issued.
#   2. Oldest-first ordering — fairness, so old feedback isn't starved.
#   3. limit clamped to 1-50 — bounds the workflow's batch size.
# Apr 19 pins the 503/403 secret behavior but not these query invariants;
# a refactor could reverse the ordering or widen the limit unnoticed.
# ===========================================================================


class TestPendingFeedbackQueryContract:
    """Regression guards: get_pending_feedback query invariants."""

    def test_pending_filters_to_new_status_only(self) -> None:
        """get_pending_feedback filters where status == FeedbackStatus.NEW.

        Regression guard for feat #218: without the NEW-only filter the
        workflow would re-fetch already-processed feedback and create
        duplicate GitHub issues on every run.
        """
        source = inspect.getsource(feedback_api.get_pending_feedback)
        assert "Feedback.status == FeedbackStatus.NEW" in source, (
            "get_pending_feedback must filter `Feedback.status == "
            "FeedbackStatus.NEW`. Without it, processed feedback is re-fetched "
            "and duplicate issues are created (feat #218)."
        )

    def test_pending_orders_oldest_first(self) -> None:
        """get_pending_feedback orders by created_at ascending (oldest first).

        Regression guard for feat #218: oldest-first ordering ensures old
        feedback isn't starved behind a steady stream of new submissions.
        A flip to descending would let fresh feedback perpetually jump the
        queue.
        """
        source = inspect.getsource(feedback_api.get_pending_feedback)
        assert "Feedback.created_at.asc()" in source, (
            "get_pending_feedback must order by `Feedback.created_at.asc()` "
            "(oldest first) so old feedback is not starved (feat #218)."
        )

    def test_pending_limit_param_clamped_1_to_50(self) -> None:
        """The `limit` query param is clamped to ge=1, le=50.

        Regression guard for feat #218: the limit bounds the workflow batch
        size. Allowing 0 would make every call a no-op; allowing an
        unbounded value would let a single call pull the entire backlog and
        time out the workflow.
        """
        sig = inspect.signature(feedback_api.get_pending_feedback)
        limit_default = sig.parameters["limit"].default
        # FastAPI Query(...) stores numeric constraints as annotated-types
        # Ge/Le objects in .metadata (e.g. [Ge(ge=1), Le(le=50)]).
        ge_values = [getattr(c, "ge", None) for c in limit_default.metadata]
        le_values = [getattr(c, "le", None) for c in limit_default.metadata]
        assert 1 in ge_values, (
            f"get_pending_feedback `limit` must enforce ge=1 (0 would make "
            f"every call a no-op). Got ge values: {ge_values}."
        )
        assert 50 in le_values, (
            f"get_pending_feedback `limit` must enforce le=50 (an unbounded "
            f"limit would let one call drain the whole backlog and time out). "
            f"Got le values: {le_values}."
        )

    def test_pending_default_limit_is_10(self) -> None:
        """The `limit` query param defaults to 10.

        Regression guard for feat #218: 10 is the documented default batch
        size for the feedback-to-issue workflow. A silent change would alter
        how many issues the workflow opens per run.
        """
        sig = inspect.signature(feedback_api.get_pending_feedback)
        limit_default = sig.parameters["limit"].default
        assert getattr(limit_default, "default", None) == 10, (
            "get_pending_feedback `limit` must default to 10 — the documented "
            "per-run batch size for the feedback-to-issue workflow (feat #218)."
        )


# ===========================================================================
# TestMarkProcessedRequestContract
# Regression guard for feat #218 (commit bad4303).
#
# After the workflow creates a GitHub issue it PATCHes the feedback as
# processed with the issue URL. The MarkProcessedRequest schema requires a
# non-empty URL (min 1) capped at the DB column width (max 500). An empty
# URL would mark feedback processed with no traceable issue link.
# ===========================================================================


class TestMarkProcessedRequestContract:
    """Regression guards: MarkProcessedRequest.github_issue_url bounds."""

    def test_github_issue_url_requires_min_length_1(self) -> None:
        """MarkProcessedRequest.github_issue_url requires min_length=1.

        Regression guard for feat #218: an empty URL would mark feedback
        as processed with no traceable issue, breaking the audit trail
        between user feedback and the GitHub issue it became.
        """
        fields = MarkProcessedRequest.model_fields
        min_lengths = [getattr(c, "min_length", None) for c in fields["github_issue_url"].metadata]
        assert 1 in min_lengths, (
            f"MarkProcessedRequest.github_issue_url must require min_length=1 "
            f"so feedback is never marked processed with an empty issue link. "
            f"Got {min_lengths}."
        )

    def test_github_issue_url_caps_at_max_length_500(self) -> None:
        """MarkProcessedRequest.github_issue_url caps at max_length=500.

        Regression guard for feat #218: the cap matches the
        Feedback.github_issue_url String(500) column. A schema that accepted
        a longer URL than the column holds would raise a DB error at commit
        time on an otherwise-valid request.
        """
        fields = MarkProcessedRequest.model_fields
        max_lengths = [getattr(c, "max_length", None) for c in fields["github_issue_url"].metadata]
        assert 500 in max_lengths, (
            f"MarkProcessedRequest.github_issue_url must cap at max_length=500 "
            f"to match the Feedback.github_issue_url String(500) column. Got "
            f"{max_lengths}. A looser schema bound would let an over-long URL "
            f"pass validation and then fail at DB commit."
        )
