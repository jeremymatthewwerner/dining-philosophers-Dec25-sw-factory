"""
Edge case tests - Saturday Feb 14 focus on boundary conditions and error paths.

Tests cover:
- Conversation API edge cases (invalid thinker names, duplicate thinkers, etc.)
- Admin API edge cases (pagination edge cases, negative spend limits, etc.)
- Extreme input validation (very long messages, invalid UUIDs, etc.)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from tests.conftest import get_auth_headers, register_and_get_token


@pytest.mark.asyncio
class TestConversationAPIEdgeCases:
    """Test edge cases for conversation API endpoints."""

    async def test_create_conversation_with_invalid_thinker_name_empty(
        self, client: AsyncClient
    ) -> None:
        """Test creating conversation with empty thinker name."""
        headers = await get_auth_headers(client, "edgeuser1", "password123")

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test Topic",
                "thinkers": [
                    {
                        "name": "",  # Empty name
                        "bio": "Test bio",
                        "positions": "Test position",
                        "style": "Test style",
                        "color": "#6366f1",
                    }
                ],
            },
        )

        # Should fail validation
        assert response.status_code == 422

    async def test_create_conversation_with_invalid_thinker_name_whitespace(
        self, client: AsyncClient
    ) -> None:
        """Test creating conversation with whitespace-only thinker name."""
        headers = await get_auth_headers(client, "edgeuser2", "password123")

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test Topic",
                "thinkers": [
                    {
                        "name": "   ",  # Whitespace only
                        "bio": "Test bio",
                        "positions": "Test position",
                        "style": "Test style",
                        "color": "#6366f1",
                    }
                ],
            },
        )

        # Pydantic should strip and fail validation
        assert response.status_code == 422

    async def test_create_conversation_with_extremely_long_topic(self, client: AsyncClient) -> None:
        """Test creating conversation with very long topic (>10KB)."""
        headers = await get_auth_headers(client, "edgeuser3", "password123")

        # Create a topic that's 15KB
        long_topic = "A" * 15000

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": long_topic,
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Greek philosopher",
                        "positions": "Forms",
                        "style": "Dialectic",
                        "color": "#6366f1",
                    }
                ],
            },
        )

        # Should either succeed or fail gracefully (not crash)
        assert response.status_code in [200, 422, 413]

    async def test_add_thinkers_duplicate_names_same_request(self, client: AsyncClient) -> None:
        """Test adding multiple thinkers with duplicate names in same request."""
        headers = await get_auth_headers(client, "edgeuser4", "password123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test Topic",
                "thinkers": [
                    {
                        "name": "Aristotle",
                        "bio": "Greek philosopher",
                        "positions": "Logic",
                        "style": "Analytical",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # Try to add two thinkers with same name
        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Socrates",
                    "bio": "Greek philosopher 1",
                    "positions": "Ethics",
                    "style": "Socratic",
                    "color": "#ec4899",
                },
                {
                    "name": "Socrates",  # Duplicate
                    "bio": "Greek philosopher 2",
                    "positions": "Ethics",
                    "style": "Socratic",
                    "color": "#10b981",
                },
            ],
        )

        # Should succeed but create two separate thinker instances
        # (business logic allows same thinker name)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Socrates"
        assert data[1]["name"] == "Socrates"

    async def test_delete_conversation_with_invalid_uuid(self, client: AsyncClient) -> None:
        """Test deleting conversation with malformed UUID."""
        headers = await get_auth_headers(client, "edgeuser5", "password123")

        response = await client.delete(
            "/api/conversations/not-a-valid-uuid",
            headers=headers,
        )

        # Should return 404 (not found) not 500 (server error)
        assert response.status_code == 404

    async def test_get_conversation_with_nonexistent_uuid(self, client: AsyncClient) -> None:
        """Test getting conversation with valid UUID format but doesn't exist."""
        headers = await get_auth_headers(client, "edgeuser6", "password123")

        # Valid UUID format but doesn't exist
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/conversations/{fake_uuid}",
            headers=headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Conversation not found"

    async def test_send_message_with_extremely_long_content(self, client: AsyncClient) -> None:
        """Test sending message with very long content (>10MB)."""
        headers = await get_auth_headers(client, "edgeuser7", "password123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test Topic",
                "thinkers": [
                    {
                        "name": "Descartes",
                        "bio": "French philosopher",
                        "positions": "Rationalism",
                        "style": "Methodological",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # Try to send a 12MB message
        huge_content = "X" * (12 * 1024 * 1024)

        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": huge_content},
        )

        # Should reject with 413 (Payload Too Large) or 422
        assert response.status_code in [413, 422]

    async def test_send_message_with_null_content(self, client: AsyncClient) -> None:
        """Test sending message with null content."""
        headers = await get_auth_headers(client, "edgeuser8", "password123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test Topic",
                "thinkers": [
                    {
                        "name": "Kant",
                        "bio": "German philosopher",
                        "positions": "Categorical imperative",
                        "style": "Systematic",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # Try to send message with null content
        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": None},
        )

        # Should fail validation
        assert response.status_code == 422

    async def test_add_thinkers_exceeding_limit_boundary(self, client: AsyncClient) -> None:
        """Test adding thinkers that exactly hits and exceeds the 5-thinker limit."""
        headers = await get_auth_headers(client, "edgeuser9", "password123")

        # Create conversation with 3 thinkers
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test Topic",
                "thinkers": [
                    {
                        "name": f"Thinker{i}",
                        "bio": f"Bio {i}",
                        "positions": f"Pos {i}",
                        "style": f"Style {i}",
                        "color": "#6366f1",
                    }
                    for i in range(3)
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # Try to add 3 more (would total 6, exceeding limit of 5)
        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": f"NewThinker{i}",
                    "bio": f"New Bio {i}",
                    "positions": f"New Pos {i}",
                    "style": f"New Style {i}",
                    "color": "#ec4899",
                }
                for i in range(3)
            ],
        )

        # Should reject with 400
        assert response.status_code == 400
        assert "Maximum is 5 total" in response.json()["detail"]

    async def test_add_thinkers_exactly_at_limit(self, client: AsyncClient) -> None:
        """Test adding thinkers that brings total to exactly 5."""
        headers = await get_auth_headers(client, "edgeuser10", "password123")

        # Create conversation with 3 thinkers
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test Topic",
                "thinkers": [
                    {
                        "name": f"Thinker{i}",
                        "bio": f"Bio {i}",
                        "positions": f"Pos {i}",
                        "style": f"Style {i}",
                        "color": "#6366f1",
                    }
                    for i in range(3)
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # Add 2 more (total 5, exactly at limit)
        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": f"NewThinker{i}",
                    "bio": f"New Bio {i}",
                    "positions": f"New Pos {i}",
                    "style": f"New Style {i}",
                    "color": "#ec4899",
                }
                for i in range(2)
            ],
        )

        # Should succeed
        assert response.status_code == 200
        assert len(response.json()) == 2


@pytest.mark.asyncio
class TestAdminAPIEdgeCases:
    """Test edge cases for admin API endpoints."""

    async def test_list_users_with_page_zero(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test listing users with page=0 (boundary condition)."""
        # Create admin user
        admin_data = await register_and_get_token(
            client, username="admin_page_zero", password="adminpass"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {admin_data['session_token']}"}

        response = await client.get(
            "/api/admin/users?page=0",
            headers=headers,
        )

        # Should either treat as page 1 or reject gracefully
        assert response.status_code in [200, 400, 422]

    async def test_list_users_with_negative_page(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test listing users with negative page number."""
        admin_data = await register_and_get_token(
            client, username="admin_neg_page", password="adminpass"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {admin_data['session_token']}"}

        response = await client.get(
            "/api/admin/users?page=-1",
            headers=headers,
        )

        # Should reject or treat as page 1
        assert response.status_code in [200, 400, 422]

    async def test_list_users_with_extremely_large_page(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test listing users with very large page number."""
        admin_data = await register_and_get_token(
            client, username="admin_large_page", password="adminpass"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {admin_data['session_token']}"}

        response = await client.get(
            "/api/admin/users?page=99999999",
            headers=headers,
        )

        # Should return empty list or handle gracefully
        assert response.status_code == 200
        data = response.json()
        # If pagination works correctly, should return empty list
        assert isinstance(data, list)

    async def test_update_spend_limit_with_negative_value(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test updating spend limit with negative value."""
        admin_data = await register_and_get_token(
            client, username="admin_neg_limit", password="adminpass"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {admin_data['session_token']}"}

        # Create a user first
        user_headers = await get_auth_headers(client, "spenduser1", "password123")
        # Get user info
        response = await client.get("/api/auth/me", headers=user_headers)
        assert response.status_code == 200
        user_id = response.json()["id"]

        # Try to set negative spend limit
        response = await client.put(
            f"/api/admin/users/{user_id}/spend-limit",
            headers=headers,
            json={"spend_limit": -100.0},
        )

        # Should reject with 422 (validation error)
        assert response.status_code == 422

    async def test_update_spend_limit_with_zero(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test updating spend limit to zero (edge case - effectively disable)."""
        admin_data = await register_and_get_token(
            client, username="admin_zero_limit", password="adminpass"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {admin_data['session_token']}"}

        # Create a user first
        user_headers = await get_auth_headers(client, "spenduser2", "password123")
        response = await client.get("/api/auth/me", headers=user_headers)
        assert response.status_code == 200
        user_id = response.json()["id"]

        # Set spend limit to zero
        response = await client.put(
            f"/api/admin/users/{user_id}/spend-limit",
            headers=headers,
            json={"spend_limit": 0.0},
        )

        # Should succeed (zero is valid - means no spending allowed)
        assert response.status_code == 200
        data = response.json()
        assert data["spend_limit"] == 0.0

    async def test_update_spend_limit_with_extremely_large_value(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test updating spend limit with extremely large value (float overflow test)."""
        admin_data = await register_and_get_token(
            client, username="admin_huge_limit", password="adminpass"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {admin_data['session_token']}"}

        # Create a user first
        user_headers = await get_auth_headers(client, "spenduser3", "password123")
        response = await client.get("/api/auth/me", headers=user_headers)
        assert response.status_code == 200
        user_id = response.json()["id"]

        # Try to set extremely large spend limit (close to float max)
        huge_limit = 1e308  # Near max float value

        response = await client.put(
            f"/api/admin/users/{user_id}/spend-limit",
            headers=headers,
            json={"spend_limit": huge_limit},
        )

        # Should either succeed or reject gracefully (not crash)
        assert response.status_code in [200, 422]

    async def test_delete_user_with_invalid_uuid(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test deleting user with invalid UUID format."""
        admin_data = await register_and_get_token(
            client, username="admin_del_invalid", password="adminpass"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {admin_data['session_token']}"}

        response = await client.delete(
            "/api/admin/users/not-a-uuid",
            headers=headers,
        )

        # Should return 404, not 500
        assert response.status_code == 404

    async def test_delete_user_with_nonexistent_valid_uuid(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test deleting user with valid UUID that doesn't exist."""
        admin_data = await register_and_get_token(
            client, username="admin_del_nonexist", password="adminpass"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {admin_data['session_token']}"}

        # Valid UUID that doesn't exist
        fake_uuid = "00000000-0000-0000-0000-000000000000"

        response = await client.delete(
            f"/api/admin/users/{fake_uuid}",
            headers=headers,
        )

        assert response.status_code == 404

    async def test_get_user_stats_for_nonexistent_user(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test getting stats for user that doesn't exist."""
        admin_data = await register_and_get_token(
            client, username="admin_stats_nonexist", password="adminpass"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {admin_data['session_token']}"}

        fake_uuid = "00000000-0000-0000-0000-000000000000"

        response = await client.get(
            f"/api/admin/users/{fake_uuid}/stats",
            headers=headers,
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestAuthAPIEdgeCases:
    """Test edge cases for auth API endpoints."""

    async def test_register_with_extremely_long_username(self, client: AsyncClient) -> None:
        """Test registration with very long username (>1000 chars)."""
        long_username = "user" + "x" * 1000

        response = await client.post(
            "/api/auth/register",
            json={
                "username": long_username,
                "password": "password123",
            },
        )

        # Should reject with validation error
        assert response.status_code == 422

    async def test_register_with_extremely_long_password(self, client: AsyncClient) -> None:
        """Test registration with very long password (>10000 chars)."""
        long_password = "p" * 10000

        response = await client.post(
            "/api/auth/register",
            json={
                "username": "longpassuser",
                "password": long_password,
            },
        )

        # Should either succeed (password gets hashed) or reject if too long
        assert response.status_code in [200, 422]

    async def test_login_with_unicode_username(self, client: AsyncClient) -> None:
        """Test login with unicode characters in username."""
        # Register with unicode username
        unicode_username = "用户名"
        response = await client.post(
            "/api/auth/register",
            json={
                "username": unicode_username,
                "password": "password123",
            },
        )
        assert response.status_code == 200

        # Login with same unicode username
        response = await client.post(
            "/api/auth/login",
            json={
                "username": unicode_username,
                "password": "password123",
            },
        )

        assert response.status_code == 200

    async def test_change_password_with_special_characters(self, client: AsyncClient) -> None:
        """Test changing password to one with many special characters."""
        headers = await get_auth_headers(client, "specialuser", "password123")

        special_password = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"

        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "old_password": "password123",
                "new_password": special_password,
            },
        )

        # Should succeed (special chars are valid in passwords)
        assert response.status_code == 200

        # Verify can login with new password
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "specialuser",
                "password": special_password,
            },
        )
        assert response.status_code == 200


@pytest.mark.asyncio
class TestSessionAPIEdgeCases:
    """Test edge cases for session API endpoints."""

    async def test_get_sessions_after_password_change(self, client: AsyncClient) -> None:
        """Test that sessions remain valid after password change."""
        headers = await get_auth_headers(client, "sessionuser", "password123")

        # Get sessions before password change
        response = await client.get("/api/sessions", headers=headers)
        assert response.status_code == 200
        sessions_before = response.json()

        # Change password
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "old_password": "password123",
                "new_password": "newpassword456",
            },
        )
        assert response.status_code == 200

        # Sessions should still be accessible with old token
        response = await client.get("/api/sessions", headers=headers)
        assert response.status_code == 200
        sessions_after = response.json()

        # Session count should be same
        assert len(sessions_before) == len(sessions_after)

    async def test_get_session_with_invalid_token(self, client: AsyncClient) -> None:
        """Test getting session with malformed token."""
        # Create user first (to verify the endpoint exists)
        await get_auth_headers(client, "tokenuser", "password123")

        # Use invalid token format
        invalid_headers = {"Authorization": "Bearer invalid-token-format"}

        response = await client.get("/api/sessions", headers=invalid_headers)

        # Should return 401 Unauthorized
        assert response.status_code == 401
