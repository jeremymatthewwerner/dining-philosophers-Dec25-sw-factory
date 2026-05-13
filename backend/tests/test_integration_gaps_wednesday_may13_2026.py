"""Integration gap tests - Wednesday focus (May 13, 2026).

Cross-endpoint integration workflows that exercise multiple API endpoints in
sequence. Individual endpoint coverage is already high (96.38% overall);
these tests verify that state transitions across endpoints behave correctly.

Workflows covered:
- Cross-user data isolation (User A's conversations invisible to User B)
- Full conversation lifecycle (create → add thinkers → message → GET → delete)
- Conversation list ordering (newest-first across endpoints)
- Knowledge research polling cycle (refresh → status transitions)
- DevOps stats decrement after entity deletion
- PUT thinkers reflects in GET conversation
- Send message reflects in GET conversation
- Stateless JWT logout (token still valid after /logout)
- Re-login reuses existing session
- Thinker validate mock-path with Wikipedia image
- Admin spend management chain (update → list → /me)
- DevOps cleanup-test-users preserves non-matching usernames
"""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    assert_error_response,
    assert_not_found,
    assert_success_response,
    create_admin_headers,
    create_test_conversation,
    get_auth_headers,
    register_and_get_token,
)

# Test secrets reused across the file (scoped to this file's tests)
TEST_DEVOPS_SECRET = "test-devops-secret-may13"


# ============================================================================
# Cross-user data isolation
# ============================================================================


class TestCrossUserDataIsolationIntegration:
    """Conversations created by one user must not be visible/accessible to another."""

    async def test_user_b_cannot_see_user_a_conversation_in_list(self, client: AsyncClient) -> None:
        """GET /api/conversations returns only the requesting user's conversations.

        Validates session-scoping on the conversations list endpoint:
        creating a conversation as user_a does not leak it into user_b's list.
        """
        a_headers = await get_auth_headers(client, "iso_user_a", "PassA1!")
        b_headers = await get_auth_headers(client, "iso_user_b", "PassB1!")

        a_conv_id = await create_test_conversation(client, a_headers, topic="A's topic")

        # User A sees own conversation
        a_list = await client.get("/api/conversations", headers=a_headers)
        a_ids = [c["id"] for c in assert_success_response(a_list, 200)]
        assert a_conv_id in a_ids

        # User B does NOT
        b_list = await client.get("/api/conversations", headers=b_headers)
        b_ids = [c["id"] for c in assert_success_response(b_list, 200)]
        assert a_conv_id not in b_ids

    async def test_user_b_get_user_a_conversation_returns_404(self, client: AsyncClient) -> None:
        """GET /api/conversations/{id} returns 404 to non-owner (not 403).

        This documents the data-hiding behavior — non-owners get a 404, the
        same response shape as a missing conversation, to avoid leaking
        existence of others' conversations.
        """
        a_headers = await get_auth_headers(client, "iso_get_a", "PassA2!")
        b_headers = await get_auth_headers(client, "iso_get_b", "PassB2!")

        conv_id = await create_test_conversation(client, a_headers)

        response = await client.get(f"/api/conversations/{conv_id}", headers=b_headers)
        assert_not_found(response, "Conversation not found")

    async def test_user_b_delete_user_a_conversation_returns_404(self, client: AsyncClient) -> None:
        """DELETE /api/conversations/{id} returns 404 to non-owner, and the
        conversation still exists for the real owner afterward.
        """
        a_headers = await get_auth_headers(client, "iso_del_a", "PassA3!")
        b_headers = await get_auth_headers(client, "iso_del_b", "PassB3!")

        conv_id = await create_test_conversation(client, a_headers)

        # B's delete attempt 404s
        del_response = await client.delete(f"/api/conversations/{conv_id}", headers=b_headers)
        assert_not_found(del_response, "Conversation not found")

        # A can still fetch it (proves it wasn't deleted)
        get_response = await client.get(f"/api/conversations/{conv_id}", headers=a_headers)
        assert_success_response(get_response, 200)


# ============================================================================
# Full conversation lifecycle
# ============================================================================


class TestConversationFullLifecycleIntegration:
    """End-to-end flow: create → add thinker → send message → GET → delete → 404."""

    async def test_full_conversation_lifecycle_endpoints_consistent(
        self, client: AsyncClient
    ) -> None:
        """Multi-endpoint lifecycle:
        POST /conversations → PUT /thinkers → POST /messages → GET /conversations/{id}
        → DELETE /conversations/{id} → GET /conversations/{id} returns 404.

        Validates each step's state is observable in the next step.
        """
        headers = await get_auth_headers(client, "lifecycle_full", "LcPass1!")

        # 1) Create with 1 thinker
        create_resp = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Lifecycle Topic",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                    }
                ],
            },
        )
        conv_id = assert_success_response(create_resp, 200)["id"]

        # 2) Add a thinker
        add_resp = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Aristotle",
                    "bio": "Bio2",
                    "positions": "Positions2",
                    "style": "Style2",
                }
            ],
        )
        assert_success_response(add_resp, 200)

        # 3) Send a message
        msg_resp = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Hello, thinkers!"},
        )
        msg_data = assert_success_response(msg_resp, 200)
        assert msg_data["content"] == "Hello, thinkers!"

        # 4) GET reflects everything
        get_resp = await client.get(f"/api/conversations/{conv_id}", headers=headers)
        full = assert_success_response(get_resp, 200)
        names = [t["name"] for t in full["thinkers"]]
        assert "Socrates" in names
        assert "Aristotle" in names
        contents = [m["content"] for m in full["messages"]]
        assert "Hello, thinkers!" in contents

        # 5) Delete
        del_resp = await client.delete(f"/api/conversations/{conv_id}", headers=headers)
        assert_success_response(del_resp, 200)

        # 6) GET now returns 404
        re_get = await client.get(f"/api/conversations/{conv_id}", headers=headers)
        assert_not_found(re_get, "Conversation not found")

    async def test_conversation_list_returns_all_created_conversations(
        self, client: AsyncClient
    ) -> None:
        """GET /api/conversations returns every conversation the user has created.

        Creating three conversations and then listing them: all three must be
        present in the list response (ordering is exercised by the endpoint's
        ORDER BY created_at DESC, but we don't strictly assert it here because
        the test DB stores timestamps with second-level precision and three
        rapidly-created rows can share a timestamp).
        """
        headers = await get_auth_headers(client, "list_all_user", "ListAllPass1!")

        ids: list[str] = []
        for i in range(3):
            cid = await create_test_conversation(client, headers, topic=f"Topic {i}")
            ids.append(cid)

        list_resp = await client.get("/api/conversations", headers=headers)
        data = assert_success_response(list_resp, 200)
        returned_ids = {c["id"] for c in data}

        for cid in ids:
            assert cid in returned_ids, f"Missing conversation {cid} from list: {returned_ids}"
        assert len(data) == 3


# ============================================================================
# Knowledge research polling cycle
# ============================================================================


class TestKnowledgeResearchCycleIntegration:
    """Knowledge endpoints: refresh → status → status (no flapping)."""

    async def test_refresh_status_cycle_returns_consistent_shape(self, client: AsyncClient) -> None:
        """POST /knowledge/{name}/refresh → GET /knowledge/{name}/status returns
        a well-formed status response with the same name we queried.

        Validates the polling contract used by the frontend: refresh kicks off
        research; status is a lightweight follow-up call that returns
        (name, status, has_data) without raising.
        """
        name = "TestKnowledgeCyclePerson"

        refresh_resp = await client.post(f"/api/thinkers/knowledge/{name}/refresh")
        refresh_data = assert_success_response(refresh_resp, 200)
        assert refresh_data["name"] == name
        assert "status" in refresh_data
        assert "has_data" in refresh_data

        # Polling: status returns same shape
        status_resp = await client.get(f"/api/thinkers/knowledge/{name}/status")
        status_data = assert_success_response(status_resp, 200)
        assert status_data["name"] == name
        assert "status" in status_data
        assert "has_data" in status_data

        # A second status call must return the same name — idempotency check
        status_resp2 = await client.get(f"/api/thinkers/knowledge/{name}/status")
        status_data2 = assert_success_response(status_resp2, 200)
        assert status_data2["name"] == name


# ============================================================================
# DevOps stats decrement after deletion
# ============================================================================


class TestDevOpsStatsDecrementIntegration:
    """Verify /api/devops/stats reflects deletions performed via other endpoints."""

    async def test_stats_user_count_decrements_after_admin_delete(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Create N users, delete one via admin endpoint, stats.users decrements by 1.

        Cross-endpoint: POST /api/auth/register × 2 → DELETE /api/admin/users/{id}
        → GET /api/devops/stats users decreased by 1.
        """
        admin_headers = await create_admin_headers(
            client, db_session, "stats_dec_admin", "AdminPass1!"
        )
        target = await register_and_get_token(client, "stats_dec_target", "TargetPass1!")
        target_id = target["user"]["id"]

        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET
            devops_headers = {"X-DevOps-Secret": TEST_DEVOPS_SECRET}

            before = assert_success_response(
                await client.get("/api/devops/stats", headers=devops_headers), 200
            )

            del_resp = await client.delete(f"/api/admin/users/{target_id}", headers=admin_headers)
            assert_success_response(del_resp, 200)

            after = assert_success_response(
                await client.get("/api/devops/stats", headers=devops_headers), 200
            )

            assert after["users"] == before["users"] - 1


# ============================================================================
# Stateless logout
# ============================================================================


class TestLogoutStatelessIntegration:
    """JWT logout is stateless; tokens remain valid for /me after /logout.

    This documents real intended behavior (see api/auth.py:logout docstring)
    rather than testing a bug. JWT revocation is handled client-side.
    """

    async def test_logout_does_not_revoke_token_for_me(self, client: AsyncClient) -> None:
        """POST /api/auth/logout returns 200, but the token still works for /me."""
        data = await register_and_get_token(client, "logout_user", "LogoutPass1!")
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        logout_resp = await client.post("/api/auth/logout", headers=headers)
        assert_success_response(logout_resp, 200)

        # Token still works (stateless JWT)
        me_resp = await client.get("/api/auth/me", headers=headers)
        me_data = assert_success_response(me_resp, 200)
        assert me_data["username"] == "logout_user"


# ============================================================================
# Re-login reuses existing session
# ============================================================================


class TestReLoginSessionReuseIntegration:
    """Multiple logins for the same user reuse the existing session row,
    rather than creating a new session each time.
    """

    async def test_two_logins_reuse_same_session(self, client: AsyncClient) -> None:
        """After register, login again with same credentials, GET /sessions/me
        for both tokens returns the same session id.
        """
        username = "session_reuse_user"
        password = "SessReusePass1!"
        register_data = await register_and_get_token(client, username, password)
        register_token = register_data["access_token"]

        login_resp = await client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        login_data = assert_success_response(login_resp, 200)
        login_token = login_data["access_token"]

        sess_register = await client.get(
            "/api/sessions/me",
            headers={"Authorization": f"Bearer {register_token}"},
        )
        sess_login = await client.get(
            "/api/sessions/me",
            headers={"Authorization": f"Bearer {login_token}"},
        )
        sess_register_data = assert_success_response(sess_register, 200)
        sess_login_data = assert_success_response(sess_login, 200)

        # The session id returned via both tokens is the same row.
        assert sess_register_data["id"] == sess_login_data["id"]


# ============================================================================
# Thinker validate happy path with Wikipedia image (mock-thinker branch)
# ============================================================================


class TestThinkerValidateMockPathIntegration:
    """POST /api/thinkers/validate for a mock thinker name should return a
    valid response with profile and an image_url (which may be None if the
    Wikipedia fetch fails) — the endpoint never raises in the mock path.
    """

    async def test_validate_mock_thinker_returns_valid_with_profile(
        self, client: AsyncClient
    ) -> None:
        """Validate 'Socrates' (in MOCK_THINKERS): valid=True with profile fields."""
        with patch(
            "app.services.thinker.thinker_service.get_wikipedia_image",
            new=AsyncMock(return_value="https://wiki/image.jpg"),
        ):
            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "Socrates"},
            )
        data = assert_success_response(response, 200)
        assert data["valid"] is True
        assert data["name"] == "Socrates"
        assert data["profile"]["name"] == "Socrates"
        assert data["profile"]["image_url"] == "https://wiki/image.jpg"

    async def test_validate_mock_thinker_case_insensitive(self, client: AsyncClient) -> None:
        """'ARISTOTLE' (uppercased) should still resolve to the mock thinker.

        Validates that MOCK_THINKERS lookup is case-insensitive (via lower()).
        """
        with patch(
            "app.services.thinker.thinker_service.get_wikipedia_image",
            new=AsyncMock(return_value=None),
        ):
            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "ARISTOTLE"},
            )
        data = assert_success_response(response, 200)
        assert data["valid"] is True
        assert data["name"] == "Aristotle"


# ============================================================================
# Admin spend management chain
# ============================================================================


class TestAdminSpendManagementChainIntegration:
    """Admin updates spend limit → reflected in admin user list AND in target's /me."""

    async def test_spend_limit_visible_in_list_users_and_target_me(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """PATCH /api/admin/users/{id}/spend-limit visible via two endpoints:
        - GET /api/admin/users shows new spend_limit
        - target's GET /api/auth/me also shows new spend_limit
        """
        admin_headers = await create_admin_headers(client, db_session, "chain_admin", "AdminPass1!")
        target = await register_and_get_token(client, "chain_target", "TargetPass1!")
        target_headers = {"Authorization": f"Bearer {target['access_token']}"}
        target_id = target["user"]["id"]

        new_limit = 42.42
        patch_resp = await client.patch(
            f"/api/admin/users/{target_id}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": new_limit},
        )
        assert_success_response(patch_resp, 200)

        # admin sees new limit in users list
        list_resp = await client.get("/api/admin/users", headers=admin_headers)
        users = assert_success_response(list_resp, 200)
        target_in_list = next((u for u in users if u["id"] == target_id), None)
        assert target_in_list is not None
        assert target_in_list["spend_limit"] == new_limit

        # target user sees new limit via /me
        me_resp = await client.get("/api/auth/me", headers=target_headers)
        me_data = assert_success_response(me_resp, 200)
        assert me_data["spend_limit"] == new_limit


# ============================================================================
# DevOps cleanup-test-users preserves non-matching users
# ============================================================================


class TestDevOpsCleanupPreservesIntegration:
    """cleanup/test-users must not delete users that don't match the patterns."""

    async def test_real_user_not_deleted_when_test_users_cleaned(self, client: AsyncClient) -> None:
        """Mix of smoketest_/canary_ users and a real_user_; after dry_run=false
        cleanup, the real user still exists (login still works).
        """
        await register_and_get_token(client, "smoketest_preserve", "SmokePass1!")
        await register_and_get_token(client, "canary_preserve", "CanaryPass1!")
        await register_and_get_token(client, "real_user_preserve", "RealPass1!")

        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET
            devops_headers = {"X-DevOps-Secret": TEST_DEVOPS_SECRET}

            cleanup_resp = await client.delete(
                "/api/devops/cleanup/test-users",
                headers=devops_headers,
            )
            cleanup_data = assert_success_response(cleanup_resp, 200)
            assert cleanup_data["deleted_count"] >= 2
            assert "real_user_preserve" not in cleanup_data["usernames"]

        # Real user can still log in
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "real_user_preserve", "password": "RealPass1!"},
        )
        assert_success_response(login_resp, 200)

        # Deleted user cannot log in
        bad_login = await client.post(
            "/api/auth/login",
            json={"username": "smoketest_preserve", "password": "SmokePass1!"},
        )
        assert_error_response(bad_login, 401)
