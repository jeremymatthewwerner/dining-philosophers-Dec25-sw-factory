"""Edge case tests for Saturday QA focus (May 9, 2026).

Targets uncovered branches and boundary conditions across:
- app/main.py: /health/ready returning 503 when database probe raises
- app/api/devops.py: cleanup endpoints when there is nothing to delete
- app/services/spend.py: check_spend_limit with zero spend_limit and 85% boundary
- app/api/admin.py: update_spend_limit input validation boundaries
- app/api/feedback.py: pending-feedback limit boundaries and processed 404
- app/api/conversations.py: add_thinkers preserves custom non-default colors
- app/api/auth.py: register / change_password validation boundaries

Relates to #884
"""

from typing import TYPE_CHECKING

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from tests.conftest import (
    create_admin_headers,
    create_conversation_with_thinker,
    get_auth_headers,
    register_and_get_token,
)

if TYPE_CHECKING:
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# /health/ready degraded path (app/main.py lines 155-157)
# ---------------------------------------------------------------------------


class TestHealthReadyDegraded:
    """Tests for /health/ready when the database probe raises."""

    async def test_health_ready_returns_503_when_db_raises(self, client: "AsyncClient") -> None:
        """`/health/ready` must return 503 with degraded status when SELECT 1 fails.

        Edge case: a SQLAlchemy OperationalError surfaces from the DB probe. The
        endpoint should catch it (lines 155-157 of app/main.py), label the
        database check as ``error: <ExcType>``, and respond with HTTP 503 +
        ``status: degraded``.
        """
        from app.core.database import get_db
        from app.main import app

        class _BrokenSession:
            async def execute(self, *_a: object, **_k: object) -> None:
                raise OperationalError("SELECT 1", {}, Exception("simulated db failure"))

            async def commit(self) -> None:
                return None

            async def rollback(self) -> None:
                return None

        async def _broken_get_db():  # type: ignore[no-untyped-def]
            yield _BrokenSession()

        original = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = _broken_get_db
        try:
            response = await client.get("/health/ready")
        finally:
            if original is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = original

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert "database" in body["checks"]
        assert body["checks"]["database"].startswith("error:")


# ---------------------------------------------------------------------------
# DevOps cleanup endpoints with zero matching rows
# ---------------------------------------------------------------------------


class TestDevOpsCleanupNoMatches:
    """DevOps cleanup endpoints must succeed when there is nothing to delete."""

    async def test_cleanup_stale_sessions_zero_count_skips_delete(
        self,
        client: "AsyncClient",
        monkeypatch,  # type: ignore[no-untyped-def]
    ) -> None:
        """count == 0 path: endpoint should return 0 and not run DELETE.

        Edge case: branch ``app/api/devops.py 145->150`` only fires when the
        cutoff filter matches no sessions. We choose ``older_than_hours=99999``
        to ensure no sessions are old enough to qualify.
        """
        # Configure a known DEVOPS_API_SECRET for this test
        from app.core.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("DEVOPS_API_SECRET", "test-devops-secret")

        response = await client.delete(
            "/api/devops/cleanup/stale-sessions?older_than_hours=99999",
            headers={"X-DevOps-Secret": "test-devops-secret"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["deleted_count"] == 0
        assert body["dry_run"] is False

        get_settings.cache_clear()

    async def test_cleanup_orphans_returns_zero_when_database_clean(
        self,
        client: "AsyncClient",
        monkeypatch,  # type: ignore[no-untyped-def]
    ) -> None:
        """Empty DB: cleanup_orphans returns 0 with detail counts of 0.

        Edge case: orphan-cleanup walks both messages and conversations. With
        no orphans, the totals are 0, ``details`` reports 0/0, and DELETE
        statements are skipped (lines 196 and 204 branches not taken).
        """
        from app.core.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("DEVOPS_API_SECRET", "test-devops-secret")

        response = await client.delete(
            "/api/devops/cleanup/orphans",
            headers={"X-DevOps-Secret": "test-devops-secret"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["deleted_count"] == 0
        assert body["details"] == {"orphan_conversations": 0, "orphan_messages": 0}
        assert body["dry_run"] is False

        get_settings.cache_clear()

    async def test_cleanup_test_users_dry_run_with_no_matches(
        self,
        client: "AsyncClient",
        monkeypatch,  # type: ignore[no-untyped-def]
    ) -> None:
        """No smoketest_/canary_ users exist: dry-run reports zero matches.

        Edge case: the endpoint logs ``[DRY RUN] Would delete 0 test users``
        and returns ``dry_run=True`` with empty username list, exercising the
        dry-run branch when there is nothing to enumerate.
        """
        from app.core.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("DEVOPS_API_SECRET", "test-devops-secret")

        response = await client.delete(
            "/api/devops/cleanup/test-users?dry_run=true",
            headers={"X-DevOps-Secret": "test-devops-secret"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["deleted_count"] == 0
        assert body["usernames"] == []
        assert body["dry_run"] is True

        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Spend service boundary conditions (app/services/spend.py)
# ---------------------------------------------------------------------------


class TestSpendServiceBoundaries:
    """Boundary conditions for ``check_spend_limit``."""

    async def test_check_spend_limit_with_zero_limit_uses_100_percent(
        self, db_session: AsyncSession
    ) -> None:
        """spend_limit == 0 must avoid division by zero and report 100% used.

        Edge case: line 42 of spend.py uses a ternary to short-circuit when
        ``spend_limit <= 0``. The ``percentage`` is set to 100 directly, and
        the user is treated as over the limit (current >= limit when limit=0).
        """
        from app.services.spend import check_spend_limit

        user = User(
            username="zerolimit",
            password_hash="hash",
            total_spend=0.0,
            spend_limit=0.0,
        )
        db_session.add(user)
        await db_session.commit()

        result = await check_spend_limit(db_session, user.id)

        assert result is not None
        assert result.spend_limit == 0.0
        assert result.percentage_used == 100.0
        # 0 >= 0 -> over limit
        assert result.is_over_limit is True
        assert result.is_near_limit is True
        assert result.remaining == 0.0

    async def test_check_spend_limit_exactly_at_85_percent_is_near_limit(
        self, db_session: AsyncSession
    ) -> None:
        """percentage == 85 must set is_near_limit=True (boundary inclusive).

        Edge case: ``is_near_limit`` is ``percentage >= 85``. A user at exactly
        85% must trip the warning. Verifies the boundary is inclusive.
        """
        from app.services.spend import check_spend_limit

        user = User(
            username="boundaryuser",
            password_hash="hash",
            total_spend=8.5,
            spend_limit=10.0,
        )
        db_session.add(user)
        await db_session.commit()

        result = await check_spend_limit(db_session, user.id)

        assert result is not None
        assert result.percentage_used == 85.0
        assert result.is_near_limit is True
        assert result.is_over_limit is False
        assert result.remaining == 1.5

    async def test_check_spend_limit_just_below_85_percent_is_not_near_limit(
        self, db_session: AsyncSession
    ) -> None:
        """percentage < 85 must NOT set is_near_limit (boundary exclusive below).

        Edge case: paired with the 85% test above, ensures we don't incorrectly
        warn at 84.99%.
        """
        from app.services.spend import check_spend_limit

        user = User(
            username="belowboundary",
            password_hash="hash",
            total_spend=8.4999,
            spend_limit=10.0,
        )
        db_session.add(user)
        await db_session.commit()

        result = await check_spend_limit(db_session, user.id)

        assert result is not None
        assert result.percentage_used < 85.0
        assert result.is_near_limit is False
        assert result.is_over_limit is False


# ---------------------------------------------------------------------------
# Admin spend-limit update boundary validation (app/api/admin.py)
# ---------------------------------------------------------------------------


class TestAdminSpendLimitBoundaries:
    """Boundary validation tests for PATCH /api/admin/users/{id}/spend-limit."""

    async def test_update_spend_limit_zero_rejected(
        self,
        client: "AsyncClient",
        db_session: AsyncSession,
    ) -> None:
        """spend_limit=0 must be rejected by Field(gt=0) validation.

        Edge case: the schema enforces ``gt=0`` so 0 produces 422.
        """
        admin_headers = await create_admin_headers(client, db_session)

        # Need a target user (the admin themselves count, but spec forbids self-mod
        # via delete; spend-limit update on self is allowed though).
        target = await register_and_get_token(client, "targetzero", "password123")

        response = await client.patch(
            f"/api/admin/users/{target['user']['id']}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": 0},
        )
        assert response.status_code == 422

    async def test_update_spend_limit_negative_rejected(
        self,
        client: "AsyncClient",
        db_session: AsyncSession,
    ) -> None:
        """Negative spend_limit must be rejected by Field(gt=0).

        Edge case: ``-1.0`` fails the ``gt=0`` constraint with 422.
        """
        admin_headers = await create_admin_headers(client, db_session)
        target = await register_and_get_token(client, "targetneg", "password123")

        response = await client.patch(
            f"/api/admin/users/{target['user']['id']}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": -1.0},
        )
        assert response.status_code == 422

    async def test_update_spend_limit_very_large_value_accepted(
        self,
        client: "AsyncClient",
        db_session: AsyncSession,
    ) -> None:
        """Very large positive spend_limit (e.g. 1e9) must be accepted.

        Edge case: there is no upper bound; the endpoint should persist the
        value as-is and report it back in the formatted message.
        """
        admin_headers = await create_admin_headers(client, db_session)
        target = await register_and_get_token(client, "targetbig", "password123")

        response = await client.patch(
            f"/api/admin/users/{target['user']['id']}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": 1_000_000_000.0},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["spend_limit"] == 1_000_000_000.0
        assert "1000000000.00" in body["message"]


# ---------------------------------------------------------------------------
# Feedback API boundary conditions (app/api/feedback.py)
# ---------------------------------------------------------------------------


class TestFeedbackPendingLimitBoundaries:
    """Limit-parameter boundaries for GET /api/feedback/pending."""

    async def test_get_pending_feedback_limit_one_returns_at_most_one(
        self,
        client: "AsyncClient",
        monkeypatch,  # type: ignore[no-untyped-def]
    ) -> None:
        """limit=1 must return at most one item even when more pending.

        Edge case: lower bound of the Query(ge=1) constraint. Submit two
        pieces of feedback then request limit=1 — only one is returned.
        """
        from app.core.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("FEEDBACK_PROCESSOR_SECRET", "test-feedback-secret")

        for i in range(2):
            r = await client.post(
                "/api/feedback",
                json={
                    "feedback_type": "bug",
                    "message": f"limit boundary feedback {i} for one-item check",
                },
            )
            assert r.status_code == 201

        response = await client.get("/api/feedback/pending?secret=test-feedback-secret&limit=1")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert len(body["feedbacks"]) == 1

        get_settings.cache_clear()

    async def test_get_pending_feedback_limit_above_max_rejected(
        self,
        client: "AsyncClient",
        monkeypatch,  # type: ignore[no-untyped-def]
    ) -> None:
        """limit > 50 must be rejected by Query(le=50) with 422.

        Edge case: upper bound of the Query constraint.
        """
        from app.core.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("FEEDBACK_PROCESSOR_SECRET", "test-feedback-secret")

        response = await client.get("/api/feedback/pending?secret=test-feedback-secret&limit=51")
        assert response.status_code == 422

        get_settings.cache_clear()

    async def test_get_pending_feedback_limit_below_min_rejected(
        self,
        client: "AsyncClient",
        monkeypatch,  # type: ignore[no-untyped-def]
    ) -> None:
        """limit=0 must be rejected by Query(ge=1) with 422.

        Edge case: lower-bound rejection.
        """
        from app.core.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("FEEDBACK_PROCESSOR_SECRET", "test-feedback-secret")

        response = await client.get("/api/feedback/pending?secret=test-feedback-secret&limit=0")
        assert response.status_code == 422

        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Conversation custom color preservation (app/api/conversations.py)
# ---------------------------------------------------------------------------


class TestConversationCustomColors:
    """add_thinkers_to_conversation must preserve user-supplied non-default colors."""

    async def test_add_thinkers_preserves_custom_non_default_color(
        self, client: "AsyncClient"
    ) -> None:
        """A custom color (not the default ``#6366f1``) must be persisted as-is.

        Edge case: the assignment branch ``color == "#6366f1"`` decides whether
        to auto-pick from the palette. A custom color like ``#abcdef`` must
        bypass the auto-pick and survive into the response.
        """
        headers = await get_auth_headers(client, "colorkeeper", "password123")
        conv_id = await create_conversation_with_thinker(client, headers, "Color test")

        custom_color = "#abcdef"
        response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "ExtraThinker",
                    "bio": "Bio",
                    "positions": "Positions",
                    "style": "Style",
                    "color": custom_color,
                }
            ],
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["color"] == custom_color


# ---------------------------------------------------------------------------
# Auth password / username validation boundaries (app/api/auth.py)
# ---------------------------------------------------------------------------


class TestAuthValidationBoundaries:
    """Field constraint boundaries for register and change-password."""

    async def test_register_password_too_short_rejected(self, client: "AsyncClient") -> None:
        """Password of 5 chars (one below min_length=6) returns 422.

        Edge case: lower-bound rejection of password length.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "shortpw",
                "display_name": "Short PW",
                "password": "abcde",
            },
        )
        assert response.status_code == 422

    async def test_register_username_too_short_rejected(self, client: "AsyncClient") -> None:
        """Username of 2 chars (one below min_length=3) returns 422.

        Edge case: lower-bound rejection of username length.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "ab",
                "display_name": "Short Username",
                "password": "validpass",
            },
        )
        assert response.status_code == 422

    async def test_register_username_at_max_length_accepted(self, client: "AsyncClient") -> None:
        """Username of exactly 50 chars (max_length=50) registers successfully.

        Edge case: max-length boundary is inclusive.
        """
        max_username = "u" * 50
        response = await client.post(
            "/api/auth/register",
            json={
                "username": max_username,
                "display_name": "MaxLen",
                "password": "validpass",
            },
        )
        assert response.status_code == 200
        assert response.json()["user"]["username"] == max_username

    async def test_change_password_new_too_short_rejected(self, client: "AsyncClient") -> None:
        """new_password < 6 chars returns 422 from Field validation.

        Edge case: ChangePasswordRequest.new_password has min_length=6, so
        ``"abc"`` is rejected before the endpoint runs.
        """
        headers = await get_auth_headers(client, "pwchanger", "password123")
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={"current_password": "password123", "new_password": "abc"},
        )
        assert response.status_code == 422
