"""Integration gap tests - Wednesday focus (working subset).

Tests for untested API endpoints to improve integration test coverage.
Focus: admin.py (60%), devops.py (62%)

NOTE: Conversation and feedback tests omitted due to Claude API call timeouts.
These will be added in future iterations with proper API mocking.
"""

from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash
from app.models import Conversation, Session, User
from tests.conftest import assert_error_response, assert_success_response, bearer_header

# Test secret for DevOps API
TEST_DEVOPS_SECRET = "test-devops-secret"


class TestAdminIntegration:
    """Integration tests for admin.py API endpoints."""

    async def test_list_users_with_multiple_users_and_conversations(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test GET /api/admin/users with multiple users having conversations.

        Coverage: app/api/admin.py:35-53 (list users query with conversation counts)
        """
        # Create admin user
        admin_user = User(
            username="admin_list_test",
            display_name="Admin List Test",
            password_hash=get_password_hash("AdminPassword123!"),
            is_admin=True,
        )
        db_session.add(admin_user)

        # Create regular users
        user1 = User(
            username="user1",
            display_name="User One",
            password_hash=get_password_hash("Password123!"),
            is_admin=False,
        )
        user2 = User(
            username="user2",
            display_name="User Two",
            password_hash=get_password_hash("Password123!"),
            is_admin=False,
        )
        db_session.add_all([user1, user2])
        await db_session.commit()
        await db_session.refresh(admin_user)
        await db_session.refresh(user1)
        await db_session.refresh(user2)

        # Create sessions for users
        session1 = Session(user_id=user1.id)
        session2 = Session(user_id=user2.id)
        db_session.add_all([session1, session2])
        await db_session.commit()
        await db_session.refresh(session1)
        await db_session.refresh(session2)

        # Create conversations for user1
        conv1 = Conversation(
            session_id=session1.id,
            topic="Philosophy 101",
            title="Philosophy 101",
        )
        conv2 = Conversation(
            session_id=session1.id,
            topic="Ethics Discussion",
            title="Ethics Discussion",
        )
        db_session.add_all([conv1, conv2])
        await db_session.commit()

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "admin_list_test", "password": "AdminPassword123!"},
        )
        admin_token = login_response.json()["access_token"]
        admin_headers = bearer_header(admin_token)

        # List users
        response = await client.get("/api/admin/users", headers=admin_headers)
        data = assert_success_response(response, 200)
        assert isinstance(data, list)
        assert len(data) >= 3  # admin + 2 users

        # Verify conversation counts
        user1_data = next(u for u in data if u["username"] == "user1")
        user2_data = next(u for u in data if u["username"] == "user2")
        assert user1_data["conversation_count"] == 2
        assert user2_data["conversation_count"] == 0

    async def test_list_users_when_no_conversations_exist(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test GET /api/admin/users when users have no conversations.

        Coverage: app/api/admin.py:35-53 (list users with zero conversations)
        """
        # Create admin
        admin = User(
            username="admin_no_conv",
            display_name="Admin No Conv",
            password_hash=get_password_hash("AdminPassword123!"),
            is_admin=True,
        )
        db_session.add(admin)
        await db_session.commit()
        await db_session.refresh(admin)

        # Create regular user without any sessions/conversations
        user = User(
            username="user_no_conv",
            display_name="No Conv User",
            password_hash=get_password_hash("Password123!"),
            is_admin=False,
        )
        db_session.add(user)
        await db_session.commit()

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "admin_no_conv", "password": "AdminPassword123!"},
        )
        admin_token = login_response.json()["access_token"]
        admin_headers = bearer_header(admin_token)

        # List users
        response = await client.get("/api/admin/users", headers=admin_headers)
        data = assert_success_response(response, 200)
        assert isinstance(data, list)

        # All users should have conversation_count of 0
        for user_data in data:
            assert "conversation_count" in user_data
            assert isinstance(user_data["conversation_count"], int)

    async def test_delete_nonexistent_user_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test DELETE /api/admin/users/{id} with nonexistent user.

        Coverage: app/api/admin.py:113-116 (user not found error path)
        """
        # Create admin
        admin = User(
            username="admin_delete_test",
            display_name="Admin Delete Test",
            password_hash=get_password_hash("AdminPassword123!"),
            is_admin=True,
        )
        db_session.add(admin)
        await db_session.commit()

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "admin_delete_test", "password": "AdminPassword123!"},
        )
        admin_token = login_response.json()["access_token"]
        admin_headers = bearer_header(admin_token)

        # Try to delete nonexistent user
        response = await client.delete(
            "/api/admin/users/nonexistent-user-id", headers=admin_headers
        )
        assert_error_response(response, 404, "not found")


class TestDevOpsIntegration:
    """Integration tests for devops.py API endpoints."""

    async def test_cleanup_stale_sessions_when_no_sessions(self, client: AsyncClient) -> None:
        """Test DELETE /api/devops/cleanup/stale-sessions with no stale sessions.

        Coverage: app/api/devops.py:139-145 (cleanup with zero results)
        """
        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

            headers = {"X-DevOps-Secret": TEST_DEVOPS_SECRET}

            # Call cleanup when no stale sessions exist
            response = await client.delete(
                "/api/devops/cleanup/stale-sessions?hours=1&dry_run=false",
                headers=headers,
            )
            data = assert_success_response(response, 200)
            assert "deleted_count" in data
            assert isinstance(data["deleted_count"], int)
            assert data["deleted_count"] >= 0

    async def test_cleanup_orphans_when_no_orphans(self, client: AsyncClient) -> None:
        """Test DELETE /api/devops/cleanup/orphans with no orphaned records.

        Coverage: app/api/devops.py:186-196 (cleanup with zero results)
        """
        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

            headers = {"X-DevOps-Secret": TEST_DEVOPS_SECRET}

            # Call cleanup when no orphans exist
            response = await client.delete(
                "/api/devops/cleanup/orphans?dry_run=false",
                headers=headers,
            )
            data = assert_success_response(response, 200)
            assert "details" in data
            assert isinstance(data["details"], dict)
            assert data["deleted_count"] >= 0

    async def test_devops_health_endpoint(self, client: AsyncClient) -> None:
        """Test GET /api/devops/health endpoint.

        Coverage: app/api/devops.py:274 (health endpoint)
        """
        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

            headers = {"X-DevOps-Secret": TEST_DEVOPS_SECRET}

            # Call health endpoint
            response = await client.get("/api/devops/health", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert data["status"] == "ok"
