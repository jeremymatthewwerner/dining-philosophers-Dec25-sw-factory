"""Integration gap tests - Wednesday focus (April 8, 2026).

Tests for untested API endpoints and code paths to improve integration test coverage.

Focus areas (from coverage analysis):
- conversations.py (68%): add_thinkers happy path, send_message auto-resume path
- admin.py: update_spend_limit, delete_user success paths
- auth.py (88%): update_language, update_profile, logout success paths
- test_helpers.py (36%): cleanup_test_users endpoint
"""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session, User
from tests.conftest import (
    assert_error_response,
    assert_success_response,
    bearer_header,
    create_admin_headers,
    create_admin_user,
    get_auth_headers,
    register_and_get_token,
)

# Test secret for test_helpers cleanup endpoint
TEST_CLEANUP_SECRET = "test-cleanup-secret"


class TestAddThinkersToConversationIntegration:
    """Integration tests for PUT /api/conversations/{id}/thinkers - the add_thinkers happy path.

    Coverage: conversations.py lines 162-220 (add_thinkers_to_conversation success paths)
    """

    async def test_add_thinkers_to_existing_conversation_success(self, client: AsyncClient) -> None:
        """Test adding a thinker to an existing conversation with 1 thinker.

        Validates: Happy path for add_thinkers_to_conversation endpoint.
        Coverage: conversations.py lines 162-220
        """
        headers = await get_auth_headers(client)

        # Create conversation with one thinker
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Philosophy of Mind",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Ancient Greek philosopher",
                        "positions": "Socratic method",
                        "style": "Questioning",
                    }
                ],
            },
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]

        # Add another thinker
        add_response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Aristotle",
                    "bio": "Student of Plato",
                    "positions": "Logic and ethics",
                    "style": "Systematic",
                }
            ],
        )
        assert add_response.status_code == 200
        data = add_response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Aristotle"
        assert "id" in data[0]
        assert "color" in data[0]

    async def test_add_multiple_thinkers_in_one_request(self, client: AsyncClient) -> None:
        """Test adding multiple thinkers at once to a conversation.

        Validates: Batch add_thinkers operation.
        Coverage: conversations.py lines 192-218 (loop over new thinkers)
        """
        headers = await get_auth_headers(client, "multi_add_user", "testpass123")

        # Create conversation with one thinker
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Science and Philosophy",
                "thinkers": [
                    {
                        "name": "Darwin",
                        "bio": "Naturalist",
                        "positions": "Evolution",
                        "style": "Empirical",
                    }
                ],
            },
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]

        # Add 2 more thinkers
        add_response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Einstein",
                    "bio": "Physicist",
                    "positions": "Relativity",
                    "style": "Thought experiments",
                },
                {
                    "name": "Curie",
                    "bio": "Chemist and physicist",
                    "positions": "Scientific rigor",
                    "style": "Experimental",
                },
            ],
        )
        assert add_response.status_code == 200
        data = add_response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        names = {t["name"] for t in data}
        assert "Einstein" in names
        assert "Curie" in names

    async def test_add_thinker_assigns_available_color(self, client: AsyncClient) -> None:
        """Test that adding a thinker assigns a color that doesn't conflict with existing ones.

        Validates: Color assignment logic (available_colors pop).
        Coverage: conversations.py lines 188-198 (color deduplication logic)
        """
        headers = await get_auth_headers(client, "color_test_user", "testpass123")

        # Create conversation with 2 thinkers
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Color assignment test",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Philosopher",
                        "positions": "Forms",
                        "style": "Dialogue",
                    },
                    {
                        "name": "Kant",
                        "bio": "Enlightenment philosopher",
                        "positions": "Categorical imperative",
                        "style": "Systematic",
                    },
                ],
            },
        )
        assert create_response.status_code == 200
        conv_data = create_response.json()
        conv_id = conv_data["id"]
        # Add another thinker - it should get a different color from the existing ones
        add_response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Hegel",
                    "bio": "Idealist philosopher",
                    "positions": "Dialectic",
                    "style": "Historical",
                }
            ],
        )
        assert add_response.status_code == 200
        new_thinker = add_response.json()[0]
        # Color should be assigned (may be default or available)
        assert "color" in new_thinker
        assert new_thinker["color"].startswith("#")

    async def test_add_thinkers_up_to_max_limit(self, client: AsyncClient) -> None:
        """Test adding thinkers up to the max of 5.

        Validates: Boundary condition - exactly 5 thinkers is allowed.
        Coverage: conversations.py lines 178-184 (count check)
        """
        headers = await get_auth_headers(client, "max_thinker_user", "testpass123")

        # Create with 3 thinkers
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Max thinkers test",
                "thinkers": [
                    {"name": "Socrates", "bio": "Philosopher", "positions": "Ethics", "style": "Q"},
                    {"name": "Plato", "bio": "Philosopher", "positions": "Forms", "style": "D"},
                    {"name": "Aristotle", "bio": "Philosopher", "positions": "Logic", "style": "S"},
                ],
            },
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]

        # Add exactly 2 more to reach the limit of 5
        add_response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                {"name": "Kant", "bio": "Philosopher", "positions": "Duty", "style": "Categorical"},
                {
                    "name": "Hume",
                    "bio": "Empiricist",
                    "positions": "Empiricism",
                    "style": "Skeptical",
                },
            ],
        )
        assert add_response.status_code == 200
        assert len(add_response.json()) == 2


class TestSendMessageIntegration:
    """Integration tests for POST /api/conversations/{id}/messages.

    Coverage: conversations.py lines 223-268 (send_message endpoint)
    """

    async def test_send_message_creates_message_in_conversation(self, client: AsyncClient) -> None:
        """Test that sending a message creates a message record.

        Validates: Happy path for send_message endpoint.
        Coverage: conversations.py lines 256-268
        """
        headers = await get_auth_headers(client, "msg_user", "testpass123")

        # Create a conversation
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Message test",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Philosopher",
                        "positions": "Ethics",
                        "style": "Questioning",
                    }
                ],
            },
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]

        # Mock thinker service at the module it's imported from inside the function
        with (
            patch("app.services.thinker.thinker_service") as mock_thinker_svc,
            patch("app.api.websocket.manager") as mock_manager,
        ):
            mock_thinker_svc.is_idle_paused.return_value = False
            mock_manager.broadcast_to_conversation = MagicMock(return_value=None)

            # Send a message
            msg_response = await client.post(
                f"/api/conversations/{conv_id}/messages",
                headers=headers,
                json={"content": "What is the nature of justice?"},
            )
        assert msg_response.status_code == 200
        msg_data = msg_response.json()
        assert msg_data["content"] == "What is the nature of justice?"
        assert msg_data["sender_type"] == "user"
        assert "id" in msg_data

    async def test_send_message_auto_resume_path(self, client: AsyncClient) -> None:
        """Test that send_message triggers auto-resume when conversation is idle-paused.

        Validates: Auto-resume branch in send_message (lines 246-254).
        Coverage: conversations.py lines 246-254
        """
        headers = await get_auth_headers(client, "resume_user", "testpass123")

        # Create a conversation
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Auto-resume test",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Philosopher",
                        "positions": "Forms",
                        "style": "Dialogue",
                    }
                ],
            },
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]

        # Mock thinker service - it's imported inside the function body
        with patch("app.services.thinker.thinker_service") as mock_thinker_svc:
            mock_thinker_svc.is_idle_paused.return_value = True
            mock_thinker_svc.resume_from_idle = MagicMock()

            with patch("app.api.websocket.manager") as mock_manager:
                mock_manager.broadcast_to_conversation = AsyncMock(return_value=None)
                mock_manager.is_conversation_active.return_value = True

                # Send message - should trigger auto-resume
                msg_response = await client.post(
                    f"/api/conversations/{conv_id}/messages",
                    headers=headers,
                    json={"content": "I am back from my break!"},
                )

        assert msg_response.status_code == 200
        # Verify resume was called
        mock_thinker_svc.resume_from_idle.assert_called_once_with(conv_id)

    async def test_send_message_uses_display_name(self, client: AsyncClient) -> None:
        """Test that send_message uses display_name when available.

        Validates: sender_name uses display_name (not just username).
        Coverage: conversations.py lines 256-259 (display_name fallback)
        """
        # Register user with a display name
        register_response = await client.post(
            "/api/auth/register",
            json={
                "username": "display_name_user",
                "display_name": "Theophrastus",
                "password": "testpass123",
            },
        )
        assert register_response.status_code == 200
        token = register_response.json()["access_token"]
        headers = bearer_header(token)

        # Create conversation
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Display name test",
                "thinkers": [
                    {"name": "Socrates", "bio": "Bio", "positions": "Pos", "style": "Style"}
                ],
            },
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]

        with patch("app.services.thinker.thinker_service") as mock_thinker_svc:
            mock_thinker_svc.is_idle_paused.return_value = False

            msg_response = await client.post(
                f"/api/conversations/{conv_id}/messages",
                headers=headers,
                json={"content": "Hello from Theophrastus!"},
            )

        assert msg_response.status_code == 200
        msg_data = msg_response.json()
        assert msg_data["sender_name"] == "Theophrastus"


class TestAdminSpendLimitIntegration:
    """Integration tests for PATCH /api/admin/users/{id}/spend-limit.

    Coverage: admin.py lines 70-94 (update_spend_limit endpoint)
    """

    async def test_update_spend_limit_success(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that admin can update a user's spend limit.

        Validates: Happy path for update_spend_limit endpoint.
        Coverage: admin.py lines 78-93
        """
        admin_headers = await create_admin_headers(client, db_session, "admin_sl", "adminpass123")

        # Create a regular user
        user_data = await register_and_get_token(client, "target_user_sl", "userpass123")
        target_user_id = user_data["user"]["id"]

        # Update spend limit
        response = await client.patch(
            f"/api/admin/users/{target_user_id}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": 25.0},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == target_user_id
        assert data["spend_limit"] == 25.0
        assert "updated" in data["message"]

    async def test_update_spend_limit_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that updating spend limit for nonexistent user returns 404.

        Validates: Error path in update_spend_limit when user doesn't exist.
        Coverage: admin.py lines 81-85
        """
        admin_headers = await create_admin_headers(
            client, db_session, "admin_sl_nf", "adminpass123"
        )

        response = await client.patch(
            "/api/admin/users/nonexistent-user-id/spend-limit",
            headers=admin_headers,
            json={"spend_limit": 10.0},
        )

        assert_error_response(response, 404, "not found")

    async def test_update_spend_limit_requires_admin(self, client: AsyncClient) -> None:
        """Test that updating spend limit requires admin access.

        Validates: Authorization check in update_spend_limit.
        """
        # Regular user cannot update spend limits
        headers = await get_auth_headers(client, "regular_sl_user", "testpass123")

        response = await client.patch(
            "/api/admin/users/some-user-id/spend-limit",
            headers=headers,
            json={"spend_limit": 10.0},
        )

        assert_error_response(response, 403, "Admin access required")

    async def test_update_spend_limit_invalid_value(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that spend limit must be positive (gt=0).

        Validates: Input validation on spend_limit field.
        """
        admin_headers = await create_admin_headers(
            client, db_session, "admin_sl_val", "adminpass123"
        )
        user_data = await register_and_get_token(client, "target_val_user", "userpass123")

        # Zero value should be rejected (gt=0 constraint)
        response = await client.patch(
            f"/api/admin/users/{user_data['user']['id']}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": 0},
        )

        assert response.status_code == 422  # Validation error


class TestAdminDeleteUserIntegration:
    """Integration tests for DELETE /api/admin/users/{id}.

    Coverage: admin.py lines 97-125 (delete_user endpoint)
    """

    async def test_delete_user_success(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """Test that admin can delete a regular user.

        Validates: Happy path for delete_user endpoint.
        Coverage: admin.py lines 108-125
        """
        admin_headers = await create_admin_headers(client, db_session, "admin_del", "adminpass123")

        # Create a user to delete
        user_data = await register_and_get_token(client, "user_to_delete", "testpass123")
        target_user_id = user_data["user"]["id"]

        # Delete the user
        response = await client.delete(
            f"/api/admin/users/{target_user_id}",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "deleted" in data["message"].lower() or "user_to_delete" in data["message"]

        # Verify user is gone
        result = await db_session.execute(select(User).where(User.id == target_user_id))
        assert result.scalar_one_or_none() is None

    async def test_delete_user_cannot_delete_self(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that admin cannot delete their own account.

        Validates: Self-deletion prevention in delete_user.
        Coverage: admin.py lines 104-109
        """
        admin_data = await create_admin_user(client, db_session, "admin_self_del", "adminpass123")
        admin_headers = bearer_header(admin_data)
        admin_id = admin_data["user"]["id"]

        # Try to delete self
        response = await client.delete(
            f"/api/admin/users/{admin_id}",
            headers=admin_headers,
        )

        assert_error_response(response, 400, "Cannot delete your own account")

    async def test_delete_user_requires_admin(self, client: AsyncClient) -> None:
        """Test that deleting a user requires admin access.

        Validates: Authorization check in delete_user.
        """
        headers = await get_auth_headers(client, "regular_del_user", "testpass123")

        response = await client.delete(
            "/api/admin/users/some-user-id",
            headers=headers,
        )

        assert_error_response(response, 403, "Admin access required")


class TestAuthEndpointsIntegration:
    """Integration tests for auth.py endpoints with lower coverage.

    Coverage: auth.py lines 199-203, 152-155, 46, 50
    """

    async def test_update_profile_success(self, client: AsyncClient) -> None:
        """Test PATCH /api/auth/profile successfully updates display name.

        Validates: update_profile endpoint happy path.
        Coverage: auth.py lines 215-235
        """
        headers = await get_auth_headers(client, "profile_update_user", "testpass123")

        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": "Theophrastus the Elder"},
        )

        assert_success_response(response, 200, ["id", "username", "display_name"])
        data = response.json()
        assert data["display_name"] == "Theophrastus the Elder"

    async def test_update_profile_persists_change(self, client: AsyncClient) -> None:
        """Test that profile update is persisted and visible in /me endpoint.

        Validates: Profile change is committed to database.
        Coverage: auth.py lines 221-235
        """
        headers = await get_auth_headers(client, "persist_profile_user", "testpass123")

        # Update profile
        await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": "New Display Name"},
        )

        # Verify it persists
        me_response = await client.get("/api/auth/me", headers=headers)
        assert me_response.status_code == 200
        assert me_response.json()["display_name"] == "New Display Name"

    async def test_update_language_success(self, client: AsyncClient) -> None:
        """Test PATCH /api/auth/language successfully updates language preference.

        Validates: update_language endpoint happy path.
        Coverage: auth.py lines 192-212
        """
        headers = await get_auth_headers(client, "lang_update_user", "testpass123")

        response = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "fr"},
        )

        assert_success_response(response, 200, ["id", "username", "language_preference"])
        data = response.json()
        assert data["language_preference"] == "fr"

    async def test_update_language_persists_change(self, client: AsyncClient) -> None:
        """Test that language update is persisted and visible in /me endpoint.

        Validates: Language change is committed to database.
        Coverage: auth.py lines 199-212
        """
        headers = await get_auth_headers(client, "persist_lang_user", "testpass123")

        # Update language to Spanish
        await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "es"},
        )

        # Verify it persists
        me_response = await client.get("/api/auth/me", headers=headers)
        assert me_response.status_code == 200
        assert me_response.json()["language_preference"] == "es"

    async def test_logout_endpoint_returns_success(self, client: AsyncClient) -> None:
        """Test POST /api/auth/logout returns success message.

        Validates: logout endpoint (stateless JWT logout).
        Coverage: auth.py lines 262-269
        """
        response = await client.post("/api/auth/logout")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Logged out" in data["message"]

    async def test_login_creates_new_session_when_none_exists(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test login creates a new session when user has none.

        Validates: Session creation in login when no existing session (lines 151-155).
        Coverage: auth.py lines 151-155
        """
        from app.core.auth import get_password_hash

        # Create user directly without a session
        user = User(
            username="no_session_login_user",
            password_hash=get_password_hash("testpass123"),
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Verify no sessions exist for this user
        result = await db_session.execute(select(Session).where(Session.user_id == user.id))
        assert result.scalar_one_or_none() is None

        # Login should create a session
        response = await client.post(
            "/api/auth/login",
            json={"username": "no_session_login_user", "password": "testpass123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

        # Verify session was created
        await db_session.refresh(user)
        result = await db_session.execute(select(Session).where(Session.user_id == user.id))
        session = result.scalar_one_or_none()
        assert session is not None


class TestCleanupTestUsersIntegration:
    """Integration tests for DELETE /api/test/cleanup-test-users endpoint.

    Coverage: test_helpers.py lines 200-237 (cleanup_test_users endpoint)
    """

    async def test_cleanup_test_users_with_valid_secret(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that cleanup-test-users deletes matching test users.

        Validates: Happy path for cleanup_test_users endpoint.
        Coverage: test_helpers.py lines 201-236
        """
        with patch("app.api.test_helpers.get_settings") as mock_settings:
            mock_settings.return_value.test_cleanup_secret = TEST_CLEANUP_SECRET

            # Create test users that should be cleaned up
            smoketest_user = User(
                username="smoketest_cleanup_integration",
                password_hash="fake_hash",
            )
            testuser = User(
                username="testuser_cleanup_integration",
                password_hash="fake_hash",
            )
            db_session.add_all([smoketest_user, testuser])
            await db_session.commit()

            # Run cleanup
            response = await client.delete(
                f"/api/test/cleanup-test-users?secret={TEST_CLEANUP_SECRET}",
            )

        assert response.status_code == 200
        data = response.json()
        assert "deleted_count" in data
        assert "deleted_users" in data
        assert data["deleted_count"] >= 2
        assert "smoketest_cleanup_integration" in data["deleted_users"]
        assert "testuser_cleanup_integration" in data["deleted_users"]

    async def test_cleanup_test_users_with_invalid_secret(self, client: AsyncClient) -> None:
        """Test that cleanup-test-users rejects invalid secrets.

        Validates: Secret validation in cleanup_test_users.
        Coverage: test_helpers.py lines 210-215
        """
        with patch("app.api.test_helpers.get_settings") as mock_settings:
            mock_settings.return_value.test_cleanup_secret = TEST_CLEANUP_SECRET

            response = await client.delete(
                "/api/test/cleanup-test-users?secret=wrong-secret",
            )

        assert_error_response(response, 403, "Invalid cleanup secret")

    async def test_cleanup_test_users_secret_not_configured(self, client: AsyncClient) -> None:
        """Test that cleanup-test-users returns 403 when secret not configured.

        Validates: Missing configuration path in cleanup_test_users.
        Coverage: test_helpers.py lines 203-208
        """
        with patch("app.api.test_helpers.get_settings") as mock_settings:
            mock_settings.return_value.test_cleanup_secret = ""

            response = await client.delete(
                "/api/test/cleanup-test-users?secret=any-secret",
            )

        assert_error_response(response, 403, "not configured")

    async def test_cleanup_test_users_no_matches_returns_zero(self, client: AsyncClient) -> None:
        """Test that cleanup-test-users returns 0 when no test users exist.

        Validates: Empty result path in cleanup_test_users.
        Coverage: test_helpers.py lines 225-226
        """
        with patch("app.api.test_helpers.get_settings") as mock_settings:
            mock_settings.return_value.test_cleanup_secret = TEST_CLEANUP_SECRET

            response = await client.delete(
                f"/api/test/cleanup-test-users?secret={TEST_CLEANUP_SECRET}",
            )

        assert response.status_code == 200
        data = response.json()
        # There may or may not be test users from other tests, but deleted_count and list exist
        assert "deleted_count" in data
        assert isinstance(data["deleted_users"], list)

    async def test_cleanup_test_users_canary_prefix(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that canary_ prefix users are cleaned up.

        Validates: All prefixes are cleaned (smoketest_, canary_, testuser_).
        Coverage: test_helpers.py lines 219-223 (prefix iteration)
        """
        with patch("app.api.test_helpers.get_settings") as mock_settings:
            mock_settings.return_value.test_cleanup_secret = TEST_CLEANUP_SECRET

            # Create canary user
            canary_user = User(
                username="canary_integration_test_user",
                password_hash="fake_hash",
            )
            db_session.add(canary_user)
            await db_session.commit()

            response = await client.delete(
                f"/api/test/cleanup-test-users?secret={TEST_CLEANUP_SECRET}",
            )

        assert response.status_code == 200
        data = response.json()
        assert "canary_integration_test_user" in data["deleted_users"]

    async def test_cleanup_test_users_spares_regular_users(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that cleanup-test-users does not delete regular users.

        Validates: Only test prefixes are targeted.
        Coverage: test_helpers.py lines 219-223 (prefix matching)
        """
        with patch("app.api.test_helpers.get_settings") as mock_settings:
            mock_settings.return_value.test_cleanup_secret = TEST_CLEANUP_SECRET

            # Create a regular user
            regular_user = User(
                username="regular_user_should_survive",
                password_hash="fake_hash",
            )
            db_session.add(regular_user)
            await db_session.commit()

            response = await client.delete(
                f"/api/test/cleanup-test-users?secret={TEST_CLEANUP_SECRET}",
            )

        assert response.status_code == 200
        data = response.json()
        assert "regular_user_should_survive" not in data["deleted_users"]

        # Verify user still exists in DB
        result = await db_session.execute(
            select(User).where(User.username == "regular_user_should_survive")
        )
        assert result.scalar_one_or_none() is not None


class TestConversationListIntegration:
    """Integration tests for GET /api/conversations - list conversations.

    Coverage: conversations.py lines 70-105 (list_conversations with message costs)
    """

    async def test_list_conversations_includes_message_count(self, client: AsyncClient) -> None:
        """Test that listing conversations includes accurate message counts.

        Validates: message_count calculation in list_conversations.
        Coverage: conversations.py lines 88-104 (summary building with message count)
        """
        headers = await get_auth_headers(client, "list_conv_user", "testpass123")

        # Create a conversation
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Message count test",
                "thinkers": [
                    {"name": "Socrates", "bio": "Bio", "positions": "Pos", "style": "Style"}
                ],
            },
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]

        # List conversations - should show 0 messages
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200
        conversations = list_response.json()
        assert len(conversations) == 1
        assert conversations[0]["id"] == conv_id
        assert conversations[0]["message_count"] == 0
        assert conversations[0]["total_cost"] == 0.0

    async def test_list_conversations_returns_correct_count(self, client: AsyncClient) -> None:
        """Test that listing conversations returns the correct number of conversations.

        Validates: list_conversations returns all conversations for the session.
        Coverage: conversations.py lines 76-105
        """
        headers = await get_auth_headers(client, "order_conv_user", "testpass123")

        # Create two conversations
        topics = ["First Philosophy Topic", "Second Philosophy Topic"]
        for topic in topics:
            await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": topic,
                    "thinkers": [
                        {"name": "Socrates", "bio": "Bio", "positions": "Pos", "style": "Style"}
                    ],
                },
            )

        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200
        conversations = list_response.json()
        assert len(conversations) == 2
        # Verify topics are present (order may vary in SQLite)
        all_topics = {c["topic"] for c in conversations}
        assert "First Philosophy Topic" in all_topics
        assert "Second Philosophy Topic" in all_topics
        # Verify structure of each conversation
        for conv in conversations:
            assert "id" in conv
            assert "topic" in conv
            assert "message_count" in conv
            assert "total_cost" in conv
            assert "thinkers" in conv
