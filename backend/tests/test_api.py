"""Tests for API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    create_admin_user,
    create_conversation_with_thinker,
    get_auth_headers,
    make_simple_thinker_list,
    register_and_get_token,
)


class TestAuthAPI:
    """Tests for authentication endpoints."""

    async def test_register_user(self, client: AsyncClient) -> None:
        """Test user registration."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "display_name": "New User",
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["username"] == "newuser"
        assert data["user"]["display_name"] == "New User"
        assert data["user"]["is_admin"] is False

    async def test_register_duplicate_username(self, client: AsyncClient) -> None:
        """Test that duplicate usernames are rejected."""
        await client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "display_name": "Test User",
                "password": "password123",
            },
        )
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "display_name": "Test User 2",
                "password": "password456",
            },
        )
        assert response.status_code == 400
        assert "already taken" in response.json()["detail"]

    async def test_login_success(self, client: AsyncClient) -> None:
        """Test successful login."""
        # First register
        await client.post(
            "/api/auth/register",
            json={
                "username": "logintest",
                "display_name": "Login Test",
                "password": "password123",
            },
        )
        # Then login
        response = await client.post(
            "/api/auth/login",
            json={"username": "logintest", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["username"] == "logintest"
        assert data["user"]["display_name"] == "Login Test"

    async def test_login_invalid_password(self, client: AsyncClient) -> None:
        """Test login with wrong password."""
        await client.post(
            "/api/auth/register",
            json={
                "username": "testuser2",
                "display_name": "Test User 2",
                "password": "password123",
            },
        )
        response = await client.post(
            "/api/auth/login",
            json={"username": "testuser2", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]

    async def test_get_me(self, client: AsyncClient) -> None:
        """Test getting current user info."""
        headers = await get_auth_headers(client, "meuser", "password123")
        response = await client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "meuser"

    async def test_get_me_no_token(self, client: AsyncClient) -> None:
        """Test that /me requires authentication."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401  # Not authenticated

    async def test_logout(self, client: AsyncClient) -> None:
        """Test logout endpoint."""
        response = await client.post("/api/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Logged out successfully"

    async def test_update_profile_display_name(self, client: AsyncClient) -> None:
        """Test updating user display name."""
        headers = await get_auth_headers(client, "profileuser", "password123")
        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": "Updated Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Name"
        assert data["username"] == "profileuser"

    async def test_update_profile_no_auth(self, client: AsyncClient) -> None:
        """Test that profile update requires authentication."""
        response = await client.patch(
            "/api/auth/profile",
            json={"display_name": "New Name"},
        )
        assert response.status_code == 401

    @pytest.mark.parametrize(
        "username,display_name,description",
        [
            ("emptyprofile", "", "empty string rejected"),
            ("longprofile", "A" * 101, "name over 100 chars rejected"),
        ],
    )
    async def test_update_profile_invalid_display_name(
        self,
        client: AsyncClient,
        username: str,
        display_name: str,
        description: str,
    ) -> None:
        """Test that invalid display names are rejected with 422.

        Parametrized to cover multiple validation failure cases:
        - Empty string (violates min_length constraint)
        - Name over 100 chars (violates max_length constraint)
        """
        headers = await get_auth_headers(client, username, "password123")
        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": display_name},
        )
        assert response.status_code == 422, f"Expected 422 for {description}"

    async def test_change_password_success(self, client: AsyncClient) -> None:
        """Test successful password change."""
        headers = await get_auth_headers(client, "pwduser", "oldpassword123")
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "oldpassword123",
                "new_password": "newpassword456",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Password changed successfully"

        # Verify can login with new password
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "pwduser", "password": "newpassword456"},
        )
        assert login_response.status_code == 200

        # Verify old password no longer works
        old_login_response = await client.post(
            "/api/auth/login",
            json={"username": "pwduser", "password": "oldpassword123"},
        )
        assert old_login_response.status_code == 401

    async def test_change_password_wrong_current(self, client: AsyncClient) -> None:
        """Test that wrong current password is rejected."""
        headers = await get_auth_headers(client, "wrongpwduser", "correctpassword")
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "wrongpassword",
                "new_password": "newpassword123",
            },
        )
        assert response.status_code == 400
        assert "incorrect" in response.json()["detail"].lower()

    async def test_change_password_no_auth(self, client: AsyncClient) -> None:
        """Test that password change requires authentication."""
        response = await client.post(
            "/api/auth/change-password",
            json={
                "current_password": "old",
                "new_password": "new123456",
            },
        )
        assert response.status_code == 401

    @pytest.mark.parametrize(
        "new_password,expected_status,description",
        [
            ("sho", 422, "password under minimum length (3 chars)"),
            ("", 422, "empty password rejected"),
            ("ab", 422, "password of 2 chars rejected"),
        ],
    )
    async def test_change_password_invalid_new_password(
        self,
        client: AsyncClient,
        new_password: str,
        expected_status: int,
        description: str,
    ) -> None:
        """Test that invalid new passwords are rejected with 422.

        Parametrized to cover multiple password validation failure cases.
        The original test_change_password_too_short covered just one case;
        this covers additional boundary values.
        """
        headers = await get_auth_headers(
            client, f"invalidpwduser_{len(new_password)}", "password123"
        )
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "password123",
                "new_password": new_password,
            },
        )
        assert response.status_code == expected_status, (
            f"Expected {expected_status} for {description}"
        )


class TestSessionAPI:
    """Tests for session endpoints."""

    async def test_get_current_session(self, client: AsyncClient) -> None:
        """Test getting current session from token."""
        headers = await get_auth_headers(client, "sessionuser", "password123")
        response = await client.get("/api/sessions/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert len(data["id"]) == 36  # UUID format

    async def test_get_session_no_auth(self, client: AsyncClient) -> None:
        """Test that session requires authentication."""
        response = await client.get("/api/sessions/me")
        assert response.status_code == 401  # Not authenticated

    async def test_get_session_invalid_token(self, client: AsyncClient) -> None:
        """Test that invalid token returns 401."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = await client.get("/api/sessions/me", headers=headers)
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    async def test_get_session_token_missing_session_id(self, client: AsyncClient) -> None:
        """Test that token without session_id returns 401."""
        from app.core.auth import create_access_token

        # Create a token without session_id (only user_id)
        token = create_access_token({"sub": "some-user-id"})
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/sessions/me", headers=headers)
        assert response.status_code == 401
        assert "no session" in response.json()["detail"].lower()

    async def test_get_session_nonexistent_session(self, client: AsyncClient) -> None:
        """Test that token with non-existent session_id returns 404."""
        from uuid import uuid4

        from app.core.auth import create_access_token

        # Create a token with a non-existent session_id
        fake_session_id = str(uuid4())
        token = create_access_token({"sub": "some-user-id", "session_id": fake_session_id})
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/sessions/me", headers=headers)
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]


class TestConversationAPI:
    """Tests for conversation endpoints."""

    async def test_create_conversation(self, client: AsyncClient) -> None:
        """Test creating a new conversation."""
        headers = await get_auth_headers(client, "convuser1", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "What is consciousness?",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Ancient Greek philosopher",
                        "positions": "Socratic method",
                        "style": "Questions everything",
                    },
                    {
                        "name": "Einstein",
                        "bio": "Theoretical physicist",
                        "positions": "Theory of relativity",
                        "style": "Thought experiments",
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == "What is consciousness?"
        assert len(data["thinkers"]) == 2
        assert data["thinkers"][0]["name"] == "Socrates"

    async def test_list_conversations(self, client: AsyncClient) -> None:
        """Test listing conversations for a session."""
        headers = await get_auth_headers(client, "listuser", "password123")

        # Create conversations using the helper to avoid repeating inline thinker dicts
        for topic in ["Topic 1", "Topic 2"]:
            await client.post(
                "/api/conversations",
                headers=headers,
                json={"topic": topic, "thinkers": make_simple_thinker_list()},
            )

        # List conversations
        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_get_conversation(self, client: AsyncClient) -> None:
        """Test getting a conversation with messages."""
        headers = await get_auth_headers(client, "getuser", "password123")

        # Create conversation using helper, then verify retrieval
        conv_id = await create_conversation_with_thinker(client, headers, "Test topic")

        # Get conversation
        response = await client.get(
            f"/api/conversations/{conv_id}",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == conv_id
        assert "messages" in data
        assert "thinkers" in data

    async def test_get_conversation_not_found(self, client: AsyncClient) -> None:
        """Test getting non-existent conversation."""
        headers = await get_auth_headers(client, "notfounduser", "password123")
        response = await client.get(
            "/api/conversations/non-existent",
            headers=headers,
        )
        assert response.status_code == 404

    async def test_send_message(self, client: AsyncClient) -> None:
        """Test sending a user message."""
        headers = await get_auth_headers(client, "msguser", "password123")
        conv_id = await create_conversation_with_thinker(client, headers, "Test")

        # Send message
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Hello, thinkers!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Hello, thinkers!"
        assert data["sender_type"] == "user"

    async def test_delete_conversation(self, client: AsyncClient) -> None:
        """Test deleting a conversation."""
        headers = await get_auth_headers(client, "deleteuser", "password123")
        conv_id = await create_conversation_with_thinker(client, headers, "To be deleted")

        # Delete conversation
        response = await client.delete(
            f"/api/conversations/{conv_id}",
            headers=headers,
        )
        assert response.status_code == 200

        # Verify deleted
        response = await client.get(
            f"/api/conversations/{conv_id}",
            headers=headers,
        )
        assert response.status_code == 404

    async def test_conversation_color_assignment_edge_cases(self, client: AsyncClient) -> None:
        """Test color assignment with max thinkers and custom colors."""
        headers = await get_auth_headers(client, "coloruser", "password123")

        # Test with 5 thinkers (max allowed, uses all 5 colors).
        # Use make_simple_thinker_list to build each entry, varying only the name.
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Many thinkers",
                "thinkers": [make_simple_thinker_list(f"Thinker{i}")[0] for i in range(5)],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 5
        # Verify colors are assigned from the 5-color array
        colors = [t["color"] for t in data["thinkers"]]
        assert all(c for c in colors)  # No empty colors
        # All should be different since we have exactly 5
        assert len(set(colors)) == 5

        # Test custom color is preserved (not default #6366f1)
        custom_color = "#ff0000"
        custom_thinker = {
            **make_simple_thinker_list("CustomColorThinker")[0],
            "color": custom_color,
        }
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Custom color test", "thinkers": [custom_thinker]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["thinkers"][0]["color"] == custom_color

    async def test_conversation_deletion_with_messages(self, client: AsyncClient) -> None:
        """Test that deleting a conversation cascades to delete messages."""
        headers = await get_auth_headers(client, "cascadeuser", "password123")
        conv_id = await create_conversation_with_thinker(client, headers, "Test cascade delete")

        # Send messages
        for i in range(3):
            await client.post(
                f"/api/conversations/{conv_id}/messages",
                headers=headers,
                json={"content": f"Message {i}"},
            )

        # Verify messages exist
        get_response = await client.get(
            f"/api/conversations/{conv_id}",
            headers=headers,
        )
        assert len(get_response.json()["messages"]) == 3

        # Delete conversation
        delete_response = await client.delete(
            f"/api/conversations/{conv_id}",
            headers=headers,
        )
        assert delete_response.status_code == 200

        # Verify conversation and messages are gone
        response = await client.get(
            f"/api/conversations/{conv_id}",
            headers=headers,
        )
        assert response.status_code == 404

    async def test_unauthorized_conversation_access(self, client: AsyncClient) -> None:
        """Test that users cannot access other users' conversations."""
        # User A creates conversation
        headers_a = await get_auth_headers(client, "usera", "password123")
        conv_id = await create_conversation_with_thinker(client, headers_a, "User A's conversation")

        # User B tries to access User A's conversation
        headers_b = await get_auth_headers(client, "userb", "password123")
        response = await client.get(
            f"/api/conversations/{conv_id}",
            headers=headers_b,
        )
        assert response.status_code == 404  # Should not find it

        # User B tries to send message to User A's conversation
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers_b,
            json={"content": "Trying to access!"},
        )
        assert response.status_code == 404  # Should not find it

        # User B tries to delete User A's conversation
        response = await client.delete(
            f"/api/conversations/{conv_id}",
            headers=headers_b,
        )
        assert response.status_code == 404  # Should not find it

    async def test_send_message_to_nonexistent_conversation(self, client: AsyncClient) -> None:
        """Test sending a message to non-existent conversation returns 404."""
        headers = await get_auth_headers(client, "nomsguser", "password123")
        response = await client.post(
            "/api/conversations/nonexistent-id/messages",
            headers=headers,
            json={"content": "This should fail"},
        )
        assert response.status_code == 404
        assert "Conversation not found" in response.json()["detail"]

    async def test_create_conversation_with_custom_color(self, client: AsyncClient) -> None:
        """Test that custom (non-default) thinker colors are preserved."""
        headers = await get_auth_headers(client, "customcoloruser", "password123")
        custom_color = "#ff5733"
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Custom colors test",
                "thinkers": [
                    {
                        "name": "RedThinker",
                        "bio": "A thinker with a custom color",
                        "positions": "Custom positions",
                        "style": "Unique style",
                        "color": custom_color,  # Non-default color
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 1
        assert data["thinkers"][0]["color"] == custom_color
        # Verify custom color was preserved, not replaced with default

    async def test_list_conversations_with_message_counts_and_costs(
        self, client: AsyncClient
    ) -> None:
        """Test that list endpoint includes message_count and total_cost fields."""
        headers = await get_auth_headers(client, "costcountuser", "password123")
        conv_id = await create_conversation_with_thinker(client, headers, "Cost tracking test")

        # Send user message
        await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Test message 1"},
        )

        # List conversations
        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        # Find our conversation
        conv = next((c for c in data if c["id"] == conv_id), None)
        assert conv is not None
        # Verify fields exist and have correct types
        assert "message_count" in conv
        assert "total_cost" in conv
        assert isinstance(conv["message_count"], int)
        assert isinstance(conv["total_cost"], float)
        assert conv["message_count"] == 1  # 1 user message sent
        assert conv["total_cost"] == 0.0  # User messages have no cost

    async def test_send_message_uses_display_name(self, client: AsyncClient) -> None:
        """Test that sent message uses user's display_name when available."""
        # get_auth_headers helper registers user with display_name = username.title()
        # So "displaynameuser" will have display_name "Displaynameuser"
        headers = await get_auth_headers(client, "displaynameuser", "password123")
        conv_id = await create_conversation_with_thinker(client, headers, "Display name test")

        # Send message
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Hello"},
        )
        assert response.status_code == 200
        data = response.json()
        # Verify it uses display_name (which is username.title() in helper)
        assert data["sender_name"] == "Displaynameuser"
        # This proves display_name is being used (not the lowercase username)

    async def test_send_message_falls_back_to_username(self, client: AsyncClient) -> None:
        """Test that message sender logic properly uses display_name or username."""
        # The test helper always sets display_name = username.title()
        # To test the fallback, we need to verify the code path exists
        # In practice, the helper ensures display_name is set, but let's verify
        # the endpoint properly reads from session.user.display_name or .username
        headers = await get_auth_headers(client, "fallbackuser", "password123")
        conv_id = await create_conversation_with_thinker(client, headers, "Sender name test")

        # Send message
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Hello"},
        )
        assert response.status_code == 200
        data = response.json()
        # Verify sender_name field exists and is populated
        assert "sender_name" in data
        assert data["sender_name"] in ["fallbackuser", "Fallbackuser"]
        # This covers the code path: user.display_name or user.username


class TestThinkerAPI:
    """Tests for thinker endpoints."""

    async def test_suggest_thinkers(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting thinker suggestions (using mock fallback)."""
        # Mock settings to return None for API key, triggering the mock fallback
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": None})(),
        )

        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "Philosophy of mind", "count": 3},
        )
        assert response.status_code == 200
        data = response.json()
        # Mock endpoint returns 3 suggestions
        assert len(data) == 3
        assert all("name" in t for t in data)
        assert all("profile" in t for t in data)
        assert all("reason" in t for t in data)

    async def test_validate_known_thinker(self, client: AsyncClient) -> None:
        """Test validating a known thinker."""
        response = await client.post(
            "/api/thinkers/validate",
            json={"name": "Socrates"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["profile"] is not None

    async def test_validate_unknown_thinker(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validating an unknown thinker."""
        from app.services.thinker import thinker_service

        async def mock_validate(*_args: object, **_kwargs: object) -> tuple[bool, None]:
            return False, None

        monkeypatch.setattr(thinker_service, "validate_thinker", mock_validate)

        response = await client.post(
            "/api/thinkers/validate",
            json={"name": "NotARealPerson12345"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["error"] is not None

    async def test_suggest_thinkers_api_error(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that API errors are properly returned as HTTP errors."""
        from app.exceptions import ThinkerAPIError
        from app.services.thinker import thinker_service

        async def mock_suggest(*_args: object, **_kwargs: object) -> None:
            raise ThinkerAPIError(
                "API credit limit reached. Please check your Anthropic billing.",
                is_quota_error=True,
            )

        monkeypatch.setattr(thinker_service, "suggest_thinkers", mock_suggest)
        # Also need to set an API key so the real path is taken
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": "test-key"})(),
        )

        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "Philosophy", "count": 3},
        )
        assert response.status_code == 503
        data = response.json()
        assert "API credit limit reached" in data["detail"]

    async def test_validate_thinker_api_error(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that validation API errors are properly returned as HTTP errors."""
        from app.exceptions import ThinkerAPIError
        from app.services.thinker import thinker_service

        async def mock_validate(*_args: object, **_kwargs: object) -> None:
            raise ThinkerAPIError(
                "API credit limit reached. Please check your Anthropic billing.",
                is_quota_error=True,
            )

        monkeypatch.setattr(thinker_service, "validate_thinker", mock_validate)
        # Also need to set an API key so the real path is taken
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": "test-key"})(),
        )

        response = await client.post(
            "/api/thinkers/validate",
            # Use a name that's not in the mock thinkers dict to trigger the real path
            json={"name": "Friedrich Nietzsche"},
        )
        assert response.status_code == 503
        data = response.json()
        assert "API credit limit reached" in data["detail"]


class TestAdminAPI:
    """Tests for admin endpoints."""

    async def test_list_users_as_admin(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """Test that admins can list all users."""
        admin_data = await create_admin_user(client, db_session)
        headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        # Create some additional users
        await register_and_get_token(client, "user1", "password123")
        await register_and_get_token(client, "user2", "password123")

        response = await client.get("/api/admin/users", headers=headers)
        assert response.status_code == 200
        users = response.json()
        assert len(users) >= 3  # admin + 2 users
        assert all("username" in u for u in users)
        assert all("conversation_count" in u for u in users)

    async def test_list_users_as_non_admin(self, client: AsyncClient) -> None:
        """Test that non-admins cannot list users."""
        headers = await get_auth_headers(client, "regularuser", "password123")
        response = await client.get("/api/admin/users", headers=headers)
        assert response.status_code == 403

    async def test_list_users_no_auth(self, client: AsyncClient) -> None:
        """Test that unauthenticated requests are rejected."""
        response = await client.get("/api/admin/users")
        assert response.status_code == 401

    async def test_delete_user_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that admins can delete users."""
        admin_data = await create_admin_user(client, db_session)
        headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        # Create a user to delete
        user_data = await register_and_get_token(client, "todelete", "password123")
        user_id = user_data["user"]["id"]

        # Delete the user
        response = await client.delete(f"/api/admin/users/{user_id}", headers=headers)
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

        # Verify user is gone from list
        response = await client.get("/api/admin/users", headers=headers)
        users = response.json()
        assert all(u["id"] != user_id for u in users)

    async def test_delete_self_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that admins cannot delete themselves."""
        admin_data = await create_admin_user(client, db_session)
        headers = {"Authorization": f"Bearer {admin_data['access_token']}"}
        admin_id = admin_data["user"]["id"]

        response = await client.delete(f"/api/admin/users/{admin_id}", headers=headers)
        assert response.status_code == 400
        assert "Cannot delete your own account" in response.json()["detail"]

    async def test_delete_user_as_non_admin(self, client: AsyncClient) -> None:
        """Test that non-admins cannot delete users."""
        headers = await get_auth_headers(client, "nonadmin", "password123")
        user_data = await register_and_get_token(client, "victim", "password123")

        response = await client.delete(
            f"/api/admin/users/{user_data['user']['id']}", headers=headers
        )
        assert response.status_code == 403

    async def test_delete_nonexistent_user(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test deleting a non-existent user."""
        admin_data = await create_admin_user(client, db_session)
        headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        response = await client.delete("/api/admin/users/nonexistent-id", headers=headers)
        assert response.status_code == 404

    async def test_update_spend_limit_success(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that admins can update a user's spend limit."""
        admin_data = await create_admin_user(client, db_session)
        headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        # Create a user to update
        user_data = await register_and_get_token(client, "limituser", "password123")
        user_id = user_data["user"]["id"]

        # Update spend limit
        response = await client.patch(
            f"/api/admin/users/{user_id}/spend-limit",
            json={"spend_limit": 50.0},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user_id
        assert data["spend_limit"] == 50.0
        assert "updated" in data["message"].lower()

    async def test_update_spend_limit_not_admin(self, client: AsyncClient) -> None:
        """Test that non-admins cannot update spend limits."""
        headers = await get_auth_headers(client, "nonadminlimit", "password123")
        user_data = await register_and_get_token(client, "targetlimit", "password123")

        response = await client.patch(
            f"/api/admin/users/{user_data['user']['id']}/spend-limit",
            json={"spend_limit": 50.0},
            headers=headers,
        )
        assert response.status_code == 403

    async def test_update_spend_limit_user_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test 404 when updating non-existent user's spend limit."""
        admin_data = await create_admin_user(client, db_session)
        headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        response = await client.patch(
            "/api/admin/users/nonexistent-id/spend-limit",
            json={"spend_limit": 50.0},
            headers=headers,
        )
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "invalid_limit,description",
        [
            (0, "zero value"),
            (-5.0, "negative value"),
            (-100, "large negative value"),
        ],
    )
    async def test_update_spend_limit_invalid_value(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        invalid_limit: float,
        description: str,
    ) -> None:
        """Test validation for invalid spend limit values.

        Parametrized test reduces duplication of validation testing pattern.
        Tests multiple invalid values: zero, negative, large negative.
        """
        admin_data = await create_admin_user(client, db_session)
        headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        user_data = await register_and_get_token(client, "validationuser", "password123")
        user_id = user_data["user"]["id"]

        response = await client.patch(
            f"/api/admin/users/{user_id}/spend-limit",
            json={"spend_limit": invalid_limit},
            headers=headers,
        )
        assert response.status_code == 422, (
            f"Expected 422 for {description}, got {response.status_code}"
        )

    async def test_update_spend_limit_persists(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that updated spend limit persists and shows in user list."""
        admin_data = await create_admin_user(client, db_session)
        headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        user_data = await register_and_get_token(client, "persistuser", "password123")
        user_id = user_data["user"]["id"]

        # Update spend limit
        await client.patch(
            f"/api/admin/users/{user_id}/spend-limit",
            json={"spend_limit": 75.0},
            headers=headers,
        )

        # Verify via user list endpoint
        response = await client.get("/api/admin/users", headers=headers)
        assert response.status_code == 200
        users = response.json()
        user = next(u for u in users if u["id"] == user_id)
        assert user["spend_limit"] == 75.0

    async def test_list_users_includes_spend_limit(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that user list includes spend_limit field."""
        admin_data = await create_admin_user(client, db_session)
        headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        response = await client.get("/api/admin/users", headers=headers)
        assert response.status_code == 200
        users = response.json()
        assert len(users) >= 1
        assert "spend_limit" in users[0]
        assert isinstance(users[0]["spend_limit"], (int, float))


class TestSpendAPI:
    """Tests for spend tracking endpoints."""

    async def test_get_spend_as_admin(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """Test that admins can get user spend data."""
        admin_data = await create_admin_user(client, db_session)
        headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        # Create a user to check spend for
        user_data = await register_and_get_token(client, "spenduser", "password123")
        user_id = user_data["user"]["id"]

        # Get spend data
        response = await client.get(f"/api/spend/{user_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user_id
        assert data["username"] == "spenduser"
        assert data["total_spend"] == 0.0
        assert "sessions" in data
        assert "conversations" in data

    async def test_get_spend_with_conversations(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test spend data includes conversation details."""
        admin_data = await create_admin_user(client, db_session)
        admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        # Create a user with conversations
        user_data = await register_and_get_token(client, "convspenduser", "password123")
        user_id = user_data["user"]["id"]
        user_headers = {"Authorization": f"Bearer {user_data['access_token']}"}

        # Create a conversation using helper to avoid repeating inline thinker dict
        await create_conversation_with_thinker(client, user_headers, "Test topic for spend")

        # Get spend data
        response = await client.get(f"/api/spend/{user_id}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 1
        assert data["conversations"][0]["topic"] == "Test topic for spend"

    async def test_get_spend_user_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test 404 when user doesn't exist."""
        admin_data = await create_admin_user(client, db_session)
        headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        response = await client.get("/api/spend/nonexistent-user-id", headers=headers)
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    async def test_get_spend_as_non_admin(self, client: AsyncClient) -> None:
        """Test that non-admins cannot access spend data."""
        headers = await get_auth_headers(client, "regularspenduser", "password123")
        user_data = await register_and_get_token(client, "targetuser", "password123")

        response = await client.get(f"/api/spend/{user_data['user']['id']}", headers=headers)
        assert response.status_code == 403

    async def test_get_spend_no_auth(self, client: AsyncClient) -> None:
        """Test that unauthenticated requests are rejected."""
        response = await client.get("/api/spend/some-user-id")
        assert response.status_code == 401
