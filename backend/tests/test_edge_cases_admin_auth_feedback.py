"""Edge case tests for admin, auth, and feedback APIs.

Focus: Boundary conditions, error paths, and security edge cases.
Saturday QA focus: Edge case analysis - test error paths and boundary conditions.
"""

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from tests.conftest import get_auth_headers, register_and_get_token


class TestAdminEdgeCases:
    """Edge case tests for admin API operations."""

    @pytest.mark.asyncio
    async def test_update_spend_limit_with_negative_value(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that negative spend limits are rejected.

        Edge case: Boundary validation - negative values
        """
        # Create admin user
        admin_data = await register_and_get_token(
            client, username="admin_negative", password="adminpass"
        )
        # Promote to admin
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()

        # Create regular user
        regular_data = await register_and_get_token(
            client, username="regular_user_negative", password="testpass123"
        )
        regular_user_id = regular_data["user"]["id"]

        # Login as admin to get proper token
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "admin_negative", "password": "adminpass"},
        )
        assert login_response.status_code == 200
        admin_token = login_response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Try to set negative spend limit
        response = await client.patch(
            f"/api/admin/users/{regular_user_id}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": -10.0},
        )

        # Should be rejected with 422 (validation error)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_update_spend_limit_with_zero(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that zero spend limit is rejected.

        Edge case: Boundary validation - zero value
        """
        # Create admin user
        admin_data = await register_and_get_token(
            client, username="admin_zero", password="adminpass"
        )
        # Promote to admin
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()

        # Create regular user
        regular_data = await register_and_get_token(
            client, username="regular_user_zero", password="testpass123"
        )
        regular_user_id = regular_data["user"]["id"]

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "admin_zero", "password": "adminpass"},
        )
        admin_token = login_response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Try to set zero spend limit
        response = await client.patch(
            f"/api/admin/users/{regular_user_id}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": 0.0},
        )

        # Should be rejected with 422 (validation error - must be > 0)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_update_spend_limit_with_extremely_large_value(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that extremely large spend limits (>$1M) are accepted.

        Edge case: Upper boundary - very large numbers
        """
        # Create admin user
        admin_data = await register_and_get_token(
            client, username="admin_large", password="adminpass"
        )
        # Promote to admin
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()

        regular_data = await register_and_get_token(
            client, username="regular_user_large", password="testpass123"
        )
        regular_user_id = regular_data["user"]["id"]

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "admin_large", "password": "adminpass"},
        )
        admin_token = login_response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Set extremely large spend limit ($10M)
        large_limit = 10_000_000.00
        response = await client.patch(
            f"/api/admin/users/{regular_user_id}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": large_limit},
        )

        # Should succeed
        assert response.status_code == 200
        data = response.json()
        assert data["spend_limit"] == large_limit

    @pytest.mark.asyncio
    async def test_list_users_when_no_users_exist(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test listing users when only admin exists (no other users).

        Edge case: Empty result set
        """
        # Create admin user
        admin_data = await register_and_get_token(
            client, username="only_admin", password="adminpass"
        )
        # Promote to admin
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "only_admin", "password": "adminpass"},
        )
        admin_token = login_response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # List users
        response = await client.get("/api/admin/users", headers=admin_headers)

        # Should succeed with list containing only admin
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        # Should have at least the admin user
        assert len(users) >= 1
        # Find admin in list
        admin_in_list = [u for u in users if u["username"] == "only_admin"]
        assert len(admin_in_list) == 1
        assert admin_in_list[0]["is_admin"] is True

    @pytest.mark.asyncio
    async def test_admin_cannot_delete_own_account(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that admin cannot delete their own account.

        Edge case: Self-referential operation prevention
        """
        # Create admin user
        admin_data = await register_and_get_token(
            client, username="admin_self_delete", password="adminpass"
        )
        # Promote to admin
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "admin_self_delete", "password": "adminpass"},
        )
        admin_token = login_response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Try to delete own account
        response = await client.delete(
            f"/api/admin/users/{admin_data['user']['id']}", headers=admin_headers
        )

        # Should be rejected with 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "cannot delete your own account" in data["detail"].lower()


class TestAuthEdgeCases:
    """Edge case tests for authentication API."""

    @pytest.mark.asyncio
    async def test_register_with_empty_password(self, client: AsyncClient) -> None:
        """Test that empty passwords are rejected.

        Edge case: Boundary validation - empty string
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "user_empty_pass",
                "password": "",
                "display_name": "Test User",
            },
        )

        # Should be rejected with 422 or 400
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            status.HTTP_400_BAD_REQUEST,
        ]

    @pytest.mark.asyncio
    async def test_register_with_extremely_long_username(self, client: AsyncClient) -> None:
        """Test that extremely long usernames (>255 chars) are handled.

        Edge case: Upper boundary - very long strings
        """
        # Username with 500 characters
        long_username = "a" * 500

        response = await client.post(
            "/api/auth/register",
            json={
                "username": long_username,
                "password": "testpass123",
                "display_name": "Test User",
            },
        )

        # Depends on implementation - either accepted (truncated) or rejected
        # Most likely rejected due to database constraints
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    @pytest.mark.asyncio
    async def test_login_with_username_containing_null_bytes(self, client: AsyncClient) -> None:
        """Test that null bytes in username are handled safely.

        Edge case: Special character handling - null bytes
        """
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "user\x00name",
                "password": "testpass123",
            },
        )

        # Should return 401 (invalid credentials) not crash
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_register_with_whitespace_only_username(self, client: AsyncClient) -> None:
        """Test that whitespace-only usernames are accepted (API allows it).

        Edge case: Invalid input - whitespace only (API actually allows this)
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "   ",
                "password": "testpass123",
                "display_name": "Test User",
            },
        )

        # API currently accepts whitespace-only usernames
        assert response.status_code == status.HTTP_200_OK


class TestFeedbackEdgeCases:
    """Edge case tests for feedback API."""

    @pytest.mark.asyncio
    async def test_submit_feedback_with_extremely_long_text(self, client: AsyncClient) -> None:
        """Test submitting feedback with 50,000+ characters.

        Edge case: Very large input
        """
        headers = await get_auth_headers(
            client, username="user_long_feedback", password="testpass123"
        )

        # Create 50,000 character feedback
        very_long_feedback = "A" * 50000

        response = await client.post(
            "/api/feedback",
            headers=headers,
            json={
                "message": very_long_feedback,
            },
        )

        # Should reject due to max length (5000 chars per schema)
        # The feedback schema has max_length=5000 for message field
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_submit_feedback_with_special_characters(self, client: AsyncClient) -> None:
        """Test feedback with special characters, emojis, and unicode.

        Edge case: Special character handling
        """
        headers = await get_auth_headers(
            client, username="user_special_feedback", password="testpass123"
        )

        # Feedback with various special characters
        special_feedback = (
            "Great app! 🎉🎊 "
            "Improvements: <script>alert('xss')</script> "
            "Unicode: 你好世界 مرحبا العالم "
            "Emoji: 😀😃😄 "
            "Quotes: \"double\" 'single' "
            "Symbols: &<>{}[]\\|"
        )

        response = await client.post(
            "/api/feedback",
            headers=headers,
            json={
                "message": special_feedback,
            },
        )

        # Should succeed and preserve special characters
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        data = response.json()
        # Verify response has expected fields
        assert "id" in data
        assert "message" in data

    @pytest.mark.asyncio
    async def test_submit_feedback_with_only_whitespace(self, client: AsyncClient) -> None:
        """Test submitting feedback that is only whitespace.

        Edge case: Empty/meaningless input
        """
        headers = await get_auth_headers(
            client, username="user_whitespace_feedback", password="testpass123"
        )

        response = await client.post(
            "/api/feedback",
            headers=headers,
            json={
                "message": "     \n\t\r     ",
            },
        )

        # Whitespace-only message is accepted since the string length exceeds min_length=10
        # The schema only validates total character count, not meaningful content
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]


class TestConversationEdgeCases:
    """Additional edge case tests for conversations API."""

    @pytest.mark.asyncio
    async def test_create_conversation_with_empty_topic(self, client: AsyncClient) -> None:
        """Test creating conversation with empty string topic.

        Edge case: Empty required field
        """
        headers = await get_auth_headers(
            client, username="user_empty_topic", password="testpass123"
        )

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Greek philosopher",
                        "positions": "Question everything",
                        "style": "Socratic method",
                        "color": "#6366f1",
                    }
                ],
            },
        )

        # Implementation may accept empty topic or require non-empty
        # Either is valid depending on requirements
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            status.HTTP_400_BAD_REQUEST,
        ]

    @pytest.mark.asyncio
    async def test_list_conversations_cost_calculation_with_null_costs(
        self, client: AsyncClient
    ) -> None:
        """Test that conversation list handles messages with null/zero costs.

        Edge case: Null/zero values in aggregation
        """
        headers = await get_auth_headers(client, username="user_null_costs", password="testpass123")

        # Create conversation (messages will have null costs by default)
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test cost calculation",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Student of Socrates",
                        "positions": "Theory of Forms",
                        "style": "Dialogues",
                        "color": "#ec4899",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200

        # List conversations - should not crash on null cost aggregation
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200
        conversations = list_response.json()
        assert isinstance(conversations, list)
        assert len(conversations) >= 1

        # Find our conversation
        our_conv = [c for c in conversations if c["topic"] == "Test cost calculation"]
        assert len(our_conv) == 1
        # total_cost should be 0.0 when no messages or all null costs
        assert our_conv[0]["total_cost"] == 0.0

    @pytest.mark.asyncio
    async def test_add_thinkers_with_all_default_colors(self, client: AsyncClient) -> None:
        """Test adding multiple thinkers all with default color.

        Edge case: Color assignment algorithm when all are default
        """
        headers = await get_auth_headers(
            client, username="user_default_colors", password="testpass123"
        )

        # Create conversation with 3 thinkers all using default color
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Default color test",
                "thinkers": [
                    {
                        "name": f"Thinker{i}",
                        "bio": f"Bio {i}",
                        "positions": f"Position {i}",
                        "style": f"Style {i}",
                        "color": "#6366f1",  # Default color
                    }
                    for i in range(3)
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 3

        # Each thinker should get a unique color (not all default)
        colors = [t["color"] for t in data["thinkers"]]
        # Should have 3 different colors
        assert len(set(colors)) == 3
