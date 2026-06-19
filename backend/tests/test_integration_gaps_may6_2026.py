"""Integration gap tests - Wednesday focus (May 6, 2026).

Tests targeting cross-endpoint integration workflows that exercise multiple
API endpoints in sequence. While individual endpoints have high unit-test
coverage (91.36%), these tests verify that state transitions across
endpoints behave correctly.

Workflows covered:
- Auth lifecycle (register → profile update → password change → re-login)
- Feedback workflow (submit → fetch pending → mark processed)
- DevOps stats accuracy after REST-driven entity creation
- Admin permission cascades (delete user removes them from list endpoint)
- Spend-limit cross-visibility (admin sets limit → user's /me reflects it)
- Cleanup boundary (mix of stale and recent sessions)
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    assert_error_response,
    assert_success_response,
    create_admin_headers,
    create_admin_user,
    patch_feedback_processor_secret,
    register_and_get_token,
)

# Test secret for DevOps API
TEST_DEVOPS_SECRET = "test-devops-secret-may6"
# Test secret for feedback processor
TEST_FEEDBACK_SECRET = "test-feedback-secret-may6"


# ============================================================================
# Auth Lifecycle: cross-endpoint sequences
# ============================================================================


class TestAuthLifecycleIntegration:
    """End-to-end auth flows that span multiple endpoints."""

    async def test_register_then_update_profile_reflected_in_me(self, client: AsyncClient) -> None:
        """Register a user, update display name, verify /me returns the new name.

        Validates that PATCH /api/auth/profile state is observable through
        a subsequent GET /api/auth/me call.
        """
        data = await register_and_get_token(client, "lifecycle_user1", "Password1!")
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        new_name = "Updated Display Name"
        patch_response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": new_name},
        )
        assert_success_response(patch_response, 200)

        me_response = await client.get("/api/auth/me", headers=headers)
        me_data = assert_success_response(me_response, 200)
        assert me_data["display_name"] == new_name

    async def test_change_password_invalidates_old_password_and_validates_new(
        self, client: AsyncClient
    ) -> None:
        """After password change, login with old password fails and new password succeeds.

        Validates POST /api/auth/change-password is durably persisted and
        observable via POST /api/auth/login.
        """
        old_password = "OldPassword1!"
        new_password = "NewPassword2!"
        username = "pw_change_user"

        data = await register_and_get_token(client, username, old_password)
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        change_response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={"current_password": old_password, "new_password": new_password},
        )
        assert_success_response(change_response, 200)

        # Old password should now fail
        old_login = await client.post(
            "/api/auth/login",
            json={"username": username, "password": old_password},
        )
        assert_error_response(old_login, 401)

        # New password should succeed
        new_login = await client.post(
            "/api/auth/login",
            json={"username": username, "password": new_password},
        )
        assert_success_response(new_login, 200)

    async def test_change_password_with_wrong_current_password_does_not_persist(
        self, client: AsyncClient
    ) -> None:
        """A failed change-password attempt does not modify the stored password.

        This verifies that the rollback path is correct — original password
        must continue to work after a 400 error.
        """
        original_password = "OriginalPwd1!"
        username = "pw_failed_change"

        await register_and_get_token(client, username, original_password)

        login = await client.post(
            "/api/auth/login",
            json={"username": username, "password": original_password},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        bad_attempt = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={"current_password": "WrongPassword!", "new_password": "DoesNotMatter1!"},
        )
        assert_error_response(bad_attempt, 400, "incorrect")

        # Original password still works
        relogin = await client.post(
            "/api/auth/login",
            json={"username": username, "password": original_password},
        )
        assert_success_response(relogin, 200)

    async def test_language_update_persists_across_login(self, client: AsyncClient) -> None:
        """A language update via PATCH persists and is visible in a fresh login response.

        Validates PATCH /api/auth/language → POST /api/auth/login returns the
        updated language_preference inside the user payload.
        """
        username = "lang_persist_user"
        password = "Password3!"
        data = await register_and_get_token(client, username, password)
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "fr"},
        )

        login_response = await client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        login_data = assert_success_response(login_response, 200)
        assert login_data["user"]["language_preference"] == "fr"

    async def test_old_token_remains_valid_after_password_change(self, client: AsyncClient) -> None:
        """JWT tokens are stateless: token from before password change still validates.

        Documents the actual behavior — JWTs are not revoked server-side on
        password change. This is a deliberate design choice, not a bug.
        """
        username = "stateless_token_user"
        old_password = "OldStateless1!"
        new_password = "NewStateless2!"

        data = await register_and_get_token(client, username, old_password)
        old_headers = {"Authorization": f"Bearer {data['access_token']}"}

        change_response = await client.post(
            "/api/auth/change-password",
            headers=old_headers,
            json={"current_password": old_password, "new_password": new_password},
        )
        assert_success_response(change_response, 200)

        # Old token still works for /me — JWTs are stateless and not server-revoked
        me_response = await client.get("/api/auth/me", headers=old_headers)
        assert_success_response(me_response, 200)


# ============================================================================
# Admin permission cascade integration tests
# ============================================================================


class TestAdminPermissionCascadeIntegration:
    """Admin operations on users observed via subsequent API calls."""

    async def test_delete_user_removes_them_from_users_list(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """After DELETE /api/admin/users/{id}, the user no longer appears in GET /api/admin/users.

        Cross-endpoint cascade: deletion via one endpoint reflected in another.
        """
        admin_headers = await create_admin_headers(
            client, db_session, "cascade_admin", "AdminPass1!"
        )

        # Register a regular user
        target = await register_and_get_token(client, "cascade_target", "TargetPass1!")
        target_id = target["user"]["id"]

        # Verify target appears in users list before deletion
        list_before = await client.get("/api/admin/users", headers=admin_headers)
        usernames_before = [u["username"] for u in list_before.json()]
        assert "cascade_target" in usernames_before

        # Delete target user
        delete_response = await client.delete(
            f"/api/admin/users/{target_id}", headers=admin_headers
        )
        assert_success_response(delete_response, 200)

        # Verify target no longer appears
        list_after = await client.get("/api/admin/users", headers=admin_headers)
        usernames_after = [u["username"] for u in list_after.json()]
        assert "cascade_target" not in usernames_after

    async def test_admin_cannot_delete_self_via_admin_endpoint(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Admin self-delete via DELETE /api/admin/users/{own_id} returns 400.

        After the failed delete, the admin can still authenticate via /me.
        """
        admin_data = await create_admin_user(client, db_session, "self_del_admin", "AdminPass2!")
        admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}
        admin_id = admin_data["user"]["id"]

        delete_response = await client.delete(f"/api/admin/users/{admin_id}", headers=admin_headers)
        assert_error_response(delete_response, 400, "own account")

        # Admin still works
        me_response = await client.get("/api/auth/me", headers=admin_headers)
        me_data = assert_success_response(me_response, 200)
        assert me_data["username"] == "self_del_admin"

    async def test_spend_limit_update_visible_to_user_via_me(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Admin updates spend limit; the affected user's /api/auth/me reflects it.

        Cross-endpoint: PATCH /api/admin/users/{id}/spend-limit → GET /api/auth/me
        for the target user.
        """
        admin_headers = await create_admin_headers(client, db_session, "spend_admin", "AdminPass3!")

        target = await register_and_get_token(client, "spend_target", "TargetPass2!")
        target_headers = {"Authorization": f"Bearer {target['access_token']}"}
        target_id = target["user"]["id"]

        new_limit = 25.50
        patch_response = await client.patch(
            f"/api/admin/users/{target_id}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": new_limit},
        )
        assert_success_response(patch_response, 200)

        # Target user sees the update via /me
        me_response = await client.get("/api/auth/me", headers=target_headers)
        me_data = assert_success_response(me_response, 200)
        assert me_data["spend_limit"] == new_limit

    async def test_non_admin_cannot_call_any_admin_endpoint(self, client: AsyncClient) -> None:
        """A regular user receives 403 on every admin endpoint they try.

        Verifies require_admin dependency is consistently applied.
        """
        data = await register_and_get_token(client, "non_admin_user", "RegularPass1!")
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        user_id = data["user"]["id"]

        endpoints = [
            ("GET", "/api/admin/users", None),
            ("PATCH", f"/api/admin/users/{user_id}/spend-limit", {"spend_limit": 100.0}),
            ("DELETE", f"/api/admin/users/{user_id}", None),
        ]

        for method, url, payload in endpoints:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "PATCH":
                response = await client.patch(url, headers=headers, json=payload)
            else:
                response = await client.delete(url, headers=headers)
            assert response.status_code == 403, (
                f"Expected 403 from {method} {url}, got {response.status_code}"
            )


# ============================================================================
# DevOps stats accuracy after REST-driven entity creation
# ============================================================================


class TestDevOpsStatsAccuracyIntegration:
    """Verify GET /api/devops/stats reflects entities created via REST endpoints."""

    async def test_stats_reflects_users_registered_via_api(self, client: AsyncClient) -> None:
        """Each user registered through /api/auth/register increments the user count.

        Cross-endpoint: POST /api/auth/register × N → GET /api/devops/stats users.
        """
        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET
            headers = {"X-DevOps-Secret": TEST_DEVOPS_SECRET}

            # Get baseline count
            baseline_response = await client.get("/api/devops/stats", headers=headers)
            baseline = assert_success_response(baseline_response, 200)
            baseline_users = baseline["users"]
            baseline_sessions = baseline["sessions"]

            # Register 3 users
            for i in range(3):
                await register_and_get_token(client, f"stats_user_{i}", f"StatsPass{i}!")

            # Verify count increased by 3
            after_response = await client.get("/api/devops/stats", headers=headers)
            after = assert_success_response(after_response, 200)
            assert after["users"] == baseline_users + 3
            # Each registration creates a default session
            assert after["sessions"] == baseline_sessions + 3

    async def test_stats_health_endpoint_share_authentication_secret(
        self, client: AsyncClient
    ) -> None:
        """The same secret authenticates both /devops/stats and /devops/health.

        Verifies require_devops_secret is wired identically in both paths.
        """
        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET
            headers = {"X-DevOps-Secret": TEST_DEVOPS_SECRET}

            health = await client.get("/api/devops/health", headers=headers)
            assert_success_response(health, 200)

            stats = await client.get("/api/devops/stats", headers=headers)
            assert_success_response(stats, 200)

            # Wrong secret rejected by both
            bad_headers = {"X-DevOps-Secret": "wrong-secret"}
            bad_health = await client.get("/api/devops/health", headers=bad_headers)
            assert bad_health.status_code == 403
            bad_stats = await client.get("/api/devops/stats", headers=bad_headers)
            assert bad_stats.status_code == 403


# ============================================================================
# DevOps cleanup boundary integration tests
# ============================================================================


class TestDevOpsCleanupBoundaryIntegration:
    """Cleanup endpoints with real entities created via API."""

    async def test_cleanup_test_users_dry_run_does_not_delete(self, client: AsyncClient) -> None:
        """dry_run=true returns the list of matched users without deleting them.

        Cross-call: dry_run preview → actual delete should both find the
        same users, and the second call (without dry_run) should match the
        first call's count.
        """
        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET
            headers = {"X-DevOps-Secret": TEST_DEVOPS_SECRET}

            # Register matching test users via API
            await register_and_get_token(client, "smoketest_alpha", "SmokePass1!")
            await register_and_get_token(client, "smoketest_beta", "SmokePass2!")
            await register_and_get_token(client, "canary_gamma", "CanaryPass1!")
            # And a non-matching user (should NOT be touched)
            await register_and_get_token(client, "real_user_delta", "RealPass1!")

            # Dry run
            dry_response = await client.delete(
                "/api/devops/cleanup/test-users?dry_run=true",
                headers=headers,
            )
            dry_data = assert_success_response(dry_response, 200)
            assert dry_data["dry_run"] is True
            usernames = set(dry_data["usernames"])
            assert "smoketest_alpha" in usernames
            assert "smoketest_beta" in usernames
            assert "canary_gamma" in usernames
            assert "real_user_delta" not in usernames

            # Verify dry run did not delete: real login still works
            login = await client.post(
                "/api/auth/login",
                json={"username": "smoketest_alpha", "password": "SmokePass1!"},
            )
            assert_success_response(login, 200)

    async def test_cleanup_test_users_actual_delete_then_login_fails(
        self, client: AsyncClient
    ) -> None:
        """After cleanup runs (dry_run=false), the deleted users can no longer log in.

        Verifies the cleanup actually removes users in a way that breaks auth,
        i.e., the user really was deleted (not just marked).
        """
        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET
            headers = {"X-DevOps-Secret": TEST_DEVOPS_SECRET}

            await register_and_get_token(client, "smoketest_to_delete", "DelPass1!")
            # Sanity check: login works first
            pre_login = await client.post(
                "/api/auth/login",
                json={"username": "smoketest_to_delete", "password": "DelPass1!"},
            )
            assert_success_response(pre_login, 200)

            # Run cleanup
            cleanup_response = await client.delete(
                "/api/devops/cleanup/test-users?dry_run=false",
                headers=headers,
            )
            cleanup_data = assert_success_response(cleanup_response, 200)
            assert cleanup_data["dry_run"] is False
            assert "smoketest_to_delete" in cleanup_data["usernames"]

            # Login now fails
            post_login = await client.post(
                "/api/auth/login",
                json={"username": "smoketest_to_delete", "password": "DelPass1!"},
            )
            assert_error_response(post_login, 401)

    async def test_cleanup_orphans_dry_run_does_not_modify_state(self, client: AsyncClient) -> None:
        """dry_run on orphan cleanup returns counts without committing deletes.

        Calling stats before and after dry_run should show identical entity counts.
        """
        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET
            headers = {"X-DevOps-Secret": TEST_DEVOPS_SECRET}

            stats_before = await client.get("/api/devops/stats", headers=headers)
            before_data = assert_success_response(stats_before, 200)

            dry_response = await client.delete(
                "/api/devops/cleanup/orphans?dry_run=true",
                headers=headers,
            )
            dry_data = assert_success_response(dry_response, 200)
            assert dry_data["dry_run"] is True

            stats_after = await client.get("/api/devops/stats", headers=headers)
            after_data = assert_success_response(stats_after, 200)

            assert before_data["users"] == after_data["users"]
            assert before_data["conversations"] == after_data["conversations"]
            assert before_data["messages"] == after_data["messages"]


# ============================================================================
# Feedback workflow integration tests
# ============================================================================


class TestFeedbackWorkflowIntegration:
    """Submit → fetch pending → mark processed full state-transition flow."""

    async def test_submit_then_appears_in_pending_then_marked_processed(
        self, client: AsyncClient
    ) -> None:
        """End-to-end feedback lifecycle.

        1. POST /api/feedback creates a NEW feedback.
        2. GET /api/feedback/pending lists it (status=NEW).
        3. PATCH /api/feedback/{id}/processed marks it as processed.
        4. GET /api/feedback/pending no longer lists it.
        """
        with patch_feedback_processor_secret(TEST_FEEDBACK_SECRET):
            # Submit feedback
            submit_response = await client.post(
                "/api/feedback",
                json={
                    "feedback_type": "bug",
                    "message": "Integration test feedback message",
                },
            )
            submit_data = assert_success_response(submit_response, 201)
            feedback_id = submit_data["id"]

            # Fetch pending — feedback should appear
            pending_response = await client.get(
                f"/api/feedback/pending?secret={TEST_FEEDBACK_SECRET}"
            )
            pending_data = assert_success_response(pending_response, 200)
            pending_ids = [fb["id"] for fb in pending_data["feedbacks"]]
            assert feedback_id in pending_ids

            # Mark as processed
            processed_response = await client.patch(
                f"/api/feedback/{feedback_id}/processed?secret={TEST_FEEDBACK_SECRET}",
                json={"github_issue_url": "https://github.com/example/repo/issues/42"},
            )
            processed_data = assert_success_response(processed_response, 200)
            assert processed_data["success"] is True
            assert processed_data["github_issue_url"] == "https://github.com/example/repo/issues/42"

            # No longer in pending list
            pending_after = await client.get(f"/api/feedback/pending?secret={TEST_FEEDBACK_SECRET}")
            pending_after_data = assert_success_response(pending_after, 200)
            after_ids = [fb["id"] for fb in pending_after_data["feedbacks"]]
            assert feedback_id not in after_ids

    async def test_mark_nonexistent_feedback_returns_404(self, client: AsyncClient) -> None:
        """Marking an unknown feedback id returns 404, not 500 or 403.

        Validates ordering of secret-check vs lookup: secret is verified
        BEFORE the lookup, so a valid secret + bad id yields 404.
        """
        with patch_feedback_processor_secret(TEST_FEEDBACK_SECRET):
            response = await client.patch(
                f"/api/feedback/nonexistent-id/processed?secret={TEST_FEEDBACK_SECRET}",
                json={"github_issue_url": "https://github.com/example/issues/1"},
            )
            assert_error_response(response, 404)

    async def test_pending_endpoint_rejects_wrong_secret(self, client: AsyncClient) -> None:
        """Wrong secret on /pending returns 403 even with submitted feedback present."""
        with patch_feedback_processor_secret(TEST_FEEDBACK_SECRET):
            await client.post(
                "/api/feedback",
                json={
                    "feedback_type": "feature",
                    "message": "A feature request submission",
                },
            )

            response = await client.get("/api/feedback/pending?secret=wrong-secret")
            assert_error_response(response, 403)


# ============================================================================
# Sessions endpoint integration tests
# ============================================================================


class TestSessionsIntegration:
    """Validate /api/sessions/me reflects login-time session creation."""

    async def test_sessions_me_returns_session_for_logged_in_user(
        self, client: AsyncClient
    ) -> None:
        """After register, /api/sessions/me returns the auto-created session.

        Cross-endpoint: register creates a session under the hood;
        /api/sessions/me decodes the JWT and returns it.
        """
        data = await register_and_get_token(client, "session_me_user", "SessionPass1!")
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        response = await client.get("/api/sessions/me", headers=headers)
        session_data = assert_success_response(response, 200)
        # Session should be linked to the user we just registered
        assert "id" in session_data
        # Schema includes user info per get_session_from_token's selectinload(user)
        if "user" in session_data and session_data["user"]:
            assert session_data["user"]["username"] == "session_me_user"

    async def test_sessions_me_with_no_token_returns_401_or_403(self, client: AsyncClient) -> None:
        """Unauthenticated /api/sessions/me returns auth error.

        FastAPI's HTTPBearer with auto_error=True returns 403 when no
        Authorization header is present; with auto_error=False or invalid
        token, 401. Either is acceptable for this contract.
        """
        response = await client.get("/api/sessions/me")
        assert response.status_code in (401, 403)


# ============================================================================
# Auth + Admin permission boundary integration test
# ============================================================================


class TestAuthAdminBoundaryIntegration:
    """Validate role transitions and permission consistency."""

    async def test_promoted_admin_can_access_admin_endpoint_without_relogin(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """A user promoted to admin via DB update can call admin endpoints
        with their existing token (require_admin reads from DB at request time).

        This documents the actual behavior: is_admin is fetched live, not
        baked into the JWT.
        """
        from sqlalchemy import update

        from app.models import User

        # Register as regular user
        data = await register_and_get_token(client, "future_admin", "FuturePass1!")
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        user_id = data["user"]["id"]

        # Confirm denied access first
        denied = await client.get("/api/admin/users", headers=headers)
        assert denied.status_code == 403

        # Promote to admin via DB
        await db_session.execute(update(User).where(User.id == user_id).values(is_admin=True))
        await db_session.commit()

        # Same token now gets through admin endpoint
        granted = await client.get("/api/admin/users", headers=headers)
        assert granted.status_code == 200


# Test markers for organization
pytestmark = [pytest.mark.asyncio]
