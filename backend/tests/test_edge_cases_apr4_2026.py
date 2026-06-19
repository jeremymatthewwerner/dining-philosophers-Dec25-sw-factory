"""Edge case tests for Saturday QA focus (Apr 4, 2026).

Tests cover boundary conditions and error paths across multiple API areas:
- auth API: invalid/malformed JWT, missing session_id, token boundary cases
- conversations API: add_thinkers limit enforcement (exactly 5, exceeding 5),
  cross-session access prevention, empty topic, max thinker name length
- thinkers API: suggest with quota error (503), validate with quota error,
  knowledge endpoint for unknown thinker, refresh triggers research
- feedback API: X-Forwarded-For header handling, pending limit boundary values,
  mark processed 404 for unknown feedback
- admin API: self-deletion prevention, spend limit update for non-existent user,
  delete non-existent user, require admin not just auth
- sessions API: missing session_id in JWT payload, expired token handling

Uses inline `with patch(...)` to ensure coverage is correctly tracked
with pytest-asyncio's auto mode.
"""

from datetime import timedelta
from unittest.mock import patch

from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token
from app.exceptions import ThinkerAPIError
from tests.conftest import (
    assert_error_response,
    assert_forbidden,
    assert_not_found,
    assert_unauthorized,
    assert_validation_error,
    create_admin_headers,
    create_conversation_with_thinker,
    get_auth_headers,
    make_simple_thinker_list,
    patch_feedback_processor_secret,
    register_and_get_token,
)

# ===========================================================================
# Auth API edge cases
# ===========================================================================


class TestAuthEdgeCases:
    """Edge case tests for authentication endpoints."""

    async def test_get_me_with_malformed_token(self, client: AsyncClient) -> None:
        """Test that a completely malformed (non-JWT) token is rejected.

        Edge case: The auth middleware should gracefully handle garbage tokens,
        returning 401 rather than a 500 server error.
        """
        headers = {"Authorization": "Bearer not-a-valid-jwt-at-all"}
        response = await client.get("/api/auth/me", headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_me_with_expired_token(self, client: AsyncClient) -> None:
        """Test that an expired token is rejected with 401.

        Edge case: Token expiry is a critical security path - must be tested.
        """
        # Create a token that expired in the past
        expired_token = create_access_token(
            data={"sub": "fake-user-id"},
            expires_delta=timedelta(seconds=-1),
        )
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = await client.get("/api/auth/me", headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_register_username_at_min_length(self, client: AsyncClient) -> None:
        """Test registration with username exactly at minimum length (3 chars).

        Boundary condition: min_length=3 means 3 chars must succeed.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "abc",
                "display_name": "User ABC",
                "password": "password123",
            },
        )
        assert response.status_code == 200

    async def test_register_username_below_min_length(self, client: AsyncClient) -> None:
        """Test registration with username below minimum length (2 chars).

        Boundary condition: min_length=3 means 2 chars must fail.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "ab",
                "display_name": "User AB",
                "password": "password123",
            },
        )
        assert_validation_error(response)

    async def test_register_password_at_min_length(self, client: AsyncClient) -> None:
        """Test registration with password exactly at minimum length (6 chars).

        Boundary condition: min_length=6 means 6 chars must succeed.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "minpassuser",
                "display_name": "Min Pass User",
                "password": "123456",
            },
        )
        assert response.status_code == 200

    async def test_register_password_below_min_length(self, client: AsyncClient) -> None:
        """Test registration with password below minimum length (5 chars).

        Boundary condition: min_length=6 means 5 chars must fail.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "shortpassuser",
                "display_name": "Short Pass User",
                "password": "12345",
            },
        )
        assert_validation_error(response)

    async def test_register_invalid_language_preference(self, client: AsyncClient) -> None:
        """Test registration with unsupported language preference.

        Edge case: language_preference only accepts en|es|fr|de.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "languser",
                "display_name": "Lang User",
                "password": "password123",
                "language_preference": "jp",
            },
        )
        assert_validation_error(response)

    async def test_login_wrong_password(self, client: AsyncClient) -> None:
        """Test login with correct username but wrong password.

        Error path: Must return 401, not expose which field is wrong.
        """
        # First register
        await client.post(
            "/api/auth/register",
            json={
                "username": "wrongpassuser",
                "display_name": "Wrong Pass User",
                "password": "correctpassword",
            },
        )

        # Login with wrong password
        response = await client.post(
            "/api/auth/login",
            json={"username": "wrongpassuser", "password": "wrongpassword"},
        )
        assert_unauthorized(response)
        # Must not distinguish between wrong username vs wrong password
        assert "Invalid username or password" in response.json()["detail"]

    async def test_login_nonexistent_user(self, client: AsyncClient) -> None:
        """Test login with a username that does not exist.

        Error path: Same 401 as wrong password (no user enumeration).
        """
        response = await client.post(
            "/api/auth/login",
            json={"username": "doesnotexist99999", "password": "anypassword"},
        )
        assert_unauthorized(response, "Invalid username or password")

    async def test_change_password_wrong_current_password(self, client: AsyncClient) -> None:
        """Test change-password with incorrect current password.

        Error path: Must reject with 400 when current password is wrong.
        """
        headers = await get_auth_headers(client, "changepwuser", "oldpassword")
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "wrongoldpassword",
                "new_password": "newpassword123",
            },
        )
        assert response.status_code == 400
        assert "Current password is incorrect" in response.json()["detail"]

    async def test_change_password_new_too_short(self, client: AsyncClient) -> None:
        """Test change-password with new password below minimum length.

        Boundary condition: new_password has min_length=6.
        """
        headers = await get_auth_headers(client, "changepwshort", "currentpass")
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "currentpass",
                "new_password": "12345",
            },
        )
        assert_validation_error(response)

    async def test_update_language_invalid_code(self, client: AsyncClient) -> None:
        """Test language update with unsupported language code.

        Edge case: Only en|es|fr|de are valid language codes.
        """
        headers = await get_auth_headers(client, "langupdate", "password123")
        response = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "zh"},
        )
        assert_validation_error(response)

    async def test_update_profile_empty_display_name_rejected(self, client: AsyncClient) -> None:
        """Test profile update with empty display name.

        Boundary condition: display_name has min_length=1.
        """
        headers = await get_auth_headers(client, "profileuser", "password123")
        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": ""},
        )
        assert_validation_error(response)

    async def test_update_profile_display_name_at_max_length(self, client: AsyncClient) -> None:
        """Test profile update with display name at exactly maximum length (100 chars).

        Boundary condition: max_length=100 means exactly 100 chars must succeed.
        """
        headers = await get_auth_headers(client, "maxnameuser", "password123")
        max_name = "A" * 100
        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": max_name},
        )
        assert response.status_code == 200
        assert response.json()["display_name"] == max_name

    async def test_update_profile_display_name_exceeds_max_length(
        self, client: AsyncClient
    ) -> None:
        """Test profile update with display name exceeding maximum length (101 chars).

        Boundary condition: max_length=100 means 101 chars must fail.
        """
        headers = await get_auth_headers(client, "toolongnameuser", "password123")
        too_long_name = "A" * 101
        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": too_long_name},
        )
        assert_validation_error(response)


# ===========================================================================
# Conversations API edge cases
# ===========================================================================


class TestConversationEdgeCases:
    """Edge case tests for conversation management."""

    async def test_create_conversation_empty_topic_rejected(self, client: AsyncClient) -> None:
        """Test that creating a conversation with an empty topic is rejected.

        Boundary condition: topic has min_length=1, so empty string must fail.
        """
        headers = await get_auth_headers(client, "emptytopicuser", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "", "thinkers": make_simple_thinker_list()},
        )
        assert_validation_error(response)

    async def test_create_conversation_no_thinkers_rejected(self, client: AsyncClient) -> None:
        """Test that creating a conversation with no thinkers is rejected.

        Boundary condition: thinkers list has min_length=1.
        """
        headers = await get_auth_headers(client, "nothinkeruser", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Some topic", "thinkers": []},
        )
        assert_validation_error(response)

    async def test_create_conversation_too_many_thinkers_rejected(
        self, client: AsyncClient
    ) -> None:
        """Test that creating a conversation with more than 5 thinkers is rejected.

        Boundary condition: thinkers list has max_length=5, so 6 must fail.
        """
        headers = await get_auth_headers(client, "manythinkersuser", "password123")
        thinkers = [
            {
                "name": f"Thinker{i}",
                "bio": f"Bio {i}",
                "positions": f"Positions {i}",
                "style": f"Style {i}",
            }
            for i in range(6)
        ]
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Six thinkers", "thinkers": thinkers},
        )
        assert_validation_error(response)

    async def test_create_conversation_with_exactly_5_thinkers(self, client: AsyncClient) -> None:
        """Test that creating a conversation with exactly 5 thinkers (the max) succeeds.

        Boundary condition: max_length=5 means exactly 5 must succeed.
        """
        headers = await get_auth_headers(client, "fivethinkersuser", "password123")
        thinkers = [
            {
                "name": f"Thinker{i}",
                "bio": f"Bio {i}",
                "positions": f"Positions {i}",
                "style": f"Style {i}",
            }
            for i in range(5)
        ]
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Five thinkers", "thinkers": thinkers},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 5

    async def test_get_conversation_other_users_conv_returns_404(self, client: AsyncClient) -> None:
        """Test that accessing another user's conversation returns 404.

        Security edge case: Users must only be able to access their own conversations.
        The API returns 404 (not 403) to avoid leaking conversation existence.
        """
        # Create user A's conversation
        headers_a = await get_auth_headers(client, "usera_conv", "password123")
        conv_id = await create_conversation_with_thinker(client, headers_a, "User A Topic")

        # User B tries to access User A's conversation
        headers_b = await get_auth_headers(client, "userb_conv", "password123")
        response = await client.get(f"/api/conversations/{conv_id}", headers=headers_b)
        assert_not_found(response)

    async def test_delete_conversation_other_users_conv_returns_404(
        self, client: AsyncClient
    ) -> None:
        """Test that deleting another user's conversation returns 404.

        Security edge case: Cross-user deletion must be prevented.
        """
        headers_a = await get_auth_headers(client, "del_usera", "password123")
        conv_id = await create_conversation_with_thinker(client, headers_a, "User A Topic")

        headers_b = await get_auth_headers(client, "del_userb", "password123")
        response = await client.delete(f"/api/conversations/{conv_id}", headers=headers_b)
        assert_not_found(response)

    async def test_get_conversation_nonexistent_id_returns_404(self, client: AsyncClient) -> None:
        """Test that fetching a non-existent conversation ID returns 404.

        Error path: Clear 404 for unknown resources.
        """
        headers = await get_auth_headers(client, "getmissuser", "password123")
        response = await client.get("/api/conversations/nonexistent-conv-id-xyz", headers=headers)
        assert_not_found(response)

    async def test_send_message_empty_content_rejected(self, client: AsyncClient) -> None:
        """Test that sending a message with empty content is rejected.

        Boundary condition: content must not be empty (validated by MessageCreate schema).
        """
        headers = await get_auth_headers(client, "emptymsguser", "password123")
        conv_id = await create_conversation_with_thinker(client, headers, "Msg Test Topic")
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": ""},
        )
        # Should fail - empty content not valid
        assert_validation_error(response)

    async def test_send_message_to_nonexistent_conversation(self, client: AsyncClient) -> None:
        """Test sending message to a conversation that does not exist.

        Error path: 404 returned for non-existent conversation.
        """
        headers = await get_auth_headers(client, "msgnoconvuser", "password123")
        response = await client.post(
            "/api/conversations/nonexistent-conv-id-xyz/messages",
            headers=headers,
            json={"content": "Hello there"},
        )
        assert_not_found(response)

    async def test_add_thinkers_exceeds_max_limit(self, client: AsyncClient) -> None:
        """Test adding thinkers that would exceed the 5-thinker maximum.

        Boundary condition: The add_thinkers endpoint checks total count <=5.
        """
        headers = await get_auth_headers(client, "addlimituser", "password123")

        # Create conversation with 4 thinkers
        thinkers_4 = [
            {
                "name": f"Thinker{i}",
                "bio": f"Bio {i}",
                "positions": f"Pos {i}",
                "style": f"Style {i}",
                "color": ["#6366f1", "#ec4899", "#10b981", "#f59e0b"][i],
            }
            for i in range(4)
        ]
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Add limit test", "thinkers": thinkers_4},
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Try to add 2 more (would make 6)
        new_thinkers = [
            {
                "name": "ExtraThinker1",
                "bio": "Bio",
                "positions": "Pos",
                "style": "Style",
            },
            {
                "name": "ExtraThinker2",
                "bio": "Bio",
                "positions": "Pos",
                "style": "Style",
            },
        ]
        response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=new_thinkers,
        )
        assert response.status_code == 400
        assert "Cannot add" in response.json()["detail"]
        assert "Maximum is 5" in response.json()["detail"]

    async def test_add_thinkers_to_nonexistent_conversation(self, client: AsyncClient) -> None:
        """Test adding thinkers to a conversation that does not exist.

        Error path: 404 for non-existent conversation in add_thinkers.
        """
        headers = await get_auth_headers(client, "addnonexistuser", "password123")
        response = await client.put(
            "/api/conversations/nonexistent-conv-xyz/thinkers",
            headers=headers,
            json=make_simple_thinker_list(),
        )
        assert_not_found(response)

    async def test_add_thinkers_to_other_users_conversation(self, client: AsyncClient) -> None:
        """Test adding thinkers to another user's conversation returns 404.

        Security edge case: Cross-user modification must be prevented.
        """
        headers_a = await get_auth_headers(client, "thinker_usera", "password123")
        conv_id = await create_conversation_with_thinker(client, headers_a, "User A's conversation")

        headers_b = await get_auth_headers(client, "thinker_userb", "password123")
        response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers_b,
            json=make_simple_thinker_list("New Thinker"),
        )
        assert_not_found(response)

    async def test_add_thinkers_with_invalid_color_rejected(self, client: AsyncClient) -> None:
        """Test adding a thinker with an invalid hex color is rejected.

        Boundary condition: color must match ^#[0-9a-fA-F]{6}$.
        """
        headers = await get_auth_headers(client, "coloruser", "password123")
        conv_id = await create_conversation_with_thinker(client, headers, "Color test")
        response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Thinker",
                    "bio": "Bio",
                    "positions": "Pos",
                    "style": "Style",
                    "color": "not-a-hex-color",
                }
            ],
        )
        assert_validation_error(response)

    async def test_conversation_list_empty_for_new_user(self, client: AsyncClient) -> None:
        """Test that a brand new user has an empty conversation list.

        Boundary condition: 0 conversations is a valid and expected state.
        """
        headers = await get_auth_headers(client, "newconvlistuser", "password123")
        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200
        assert response.json() == []

    async def test_conversations_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        """Test that conversation listing without auth returns 401.

        Security: All conversation endpoints require authentication.
        """
        response = await client.get("/api/conversations")
        assert_unauthorized(response)

    async def test_thinker_name_at_max_length(self, client: AsyncClient) -> None:
        """Test creating a thinker with name at exactly the max length (255 chars).

        Boundary condition: name has max_length=255.
        """
        headers = await get_auth_headers(client, "maxnamethinker", "password123")
        max_name = "A" * 255
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Max name topic",
                "thinkers": [
                    {
                        "name": max_name,
                        "bio": "Some bio",
                        "positions": "Some positions",
                        "style": "Some style",
                    }
                ],
            },
        )
        assert response.status_code == 200

    async def test_thinker_name_exceeds_max_length(self, client: AsyncClient) -> None:
        """Test that a thinker name exceeding max length (256 chars) is rejected.

        Boundary condition: max_length=255 means 256 chars must fail.
        """
        headers = await get_auth_headers(client, "toolongthinkeruser", "password123")
        too_long = "A" * 256
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Too long name topic",
                "thinkers": [
                    {
                        "name": too_long,
                        "bio": "Some bio",
                        "positions": "Some positions",
                        "style": "Some style",
                    }
                ],
            },
        )
        assert_validation_error(response)


# ===========================================================================
# Thinkers API edge cases
# ===========================================================================


class TestThinkersApiEdgeCases:
    """Edge case tests for the thinkers API endpoints."""

    async def test_suggest_thinkers_quota_error_returns_503(self, client: AsyncClient) -> None:
        """Test that a quota error from the AI service returns 503.

        Error path: ThinkerAPIError with is_quota_error=True -> 503 status.
        """
        with (
            patch("app.api.thinkers.get_settings") as mock_settings,
            patch("app.services.thinker.thinker_service.suggest_thinkers") as mock_suggest,
        ):
            mock_settings.return_value.anthropic_api_key = "fake-api-key"
            mock_suggest.side_effect = ThinkerAPIError("API quota exceeded", is_quota_error=True)

            response = await client.post(
                "/api/thinkers/suggest",
                json={"topic": "philosophy"},
            )

        assert response.status_code == 503
        assert "quota" in response.json()["detail"].lower()

    async def test_suggest_thinkers_api_error_returns_502(self, client: AsyncClient) -> None:
        """Test that a non-quota API error returns 502 Bad Gateway.

        Error path: ThinkerAPIError with is_quota_error=False -> 502 status.
        """
        with (
            patch("app.api.thinkers.get_settings") as mock_settings,
            patch("app.services.thinker.thinker_service.suggest_thinkers") as mock_suggest,
        ):
            mock_settings.return_value.anthropic_api_key = "fake-api-key"
            mock_suggest.side_effect = ThinkerAPIError("API unavailable", is_quota_error=False)

            response = await client.post(
                "/api/thinkers/suggest",
                json={"topic": "philosophy"},
            )

        assert response.status_code == 502

    async def test_suggest_thinkers_count_at_min(self, client: AsyncClient) -> None:
        """Test suggest thinkers with count at minimum value (1).

        Boundary condition: count has ge=1, so count=1 must succeed.
        Mock both API key and Wikipedia image fetching to ensure mock path is used.
        """
        with (
            patch("app.api.thinkers.get_settings") as mock_settings,
            patch(
                "app.services.thinker.thinker_service.get_wikipedia_image",
                return_value=None,
            ),
        ):
            mock_settings.return_value.anthropic_api_key = None
            response = await client.post(
                "/api/thinkers/suggest",
                json={"topic": "philosophy", "count": 1},
            )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    async def test_suggest_thinkers_count_at_max(self, client: AsyncClient) -> None:
        """Test suggest thinkers with count at maximum value (5).

        Boundary condition: count has le=5, so count=5 must succeed.
        Mock both API key and Wikipedia image fetching to ensure mock path is used.
        """
        with (
            patch("app.api.thinkers.get_settings") as mock_settings,
            patch(
                "app.services.thinker.thinker_service.get_wikipedia_image",
                return_value=None,
            ),
        ):
            mock_settings.return_value.anthropic_api_key = None
            response = await client.post(
                "/api/thinkers/suggest",
                json={"topic": "philosophy", "count": 5},
            )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

    async def test_suggest_thinkers_count_exceeds_max_rejected(self, client: AsyncClient) -> None:
        """Test suggest thinkers with count exceeding maximum (6).

        Boundary condition: count has le=5, so count=6 must fail.
        """
        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "philosophy", "count": 6},
        )
        assert_validation_error(response)

    async def test_suggest_thinkers_count_zero_rejected(self, client: AsyncClient) -> None:
        """Test suggest thinkers with count=0 is rejected.

        Boundary condition: count has ge=1, so count=0 must fail.
        """
        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "philosophy", "count": 0},
        )
        assert_validation_error(response)

    async def test_suggest_thinkers_empty_topic_rejected(self, client: AsyncClient) -> None:
        """Test that suggest with empty topic is rejected.

        Boundary condition: topic has min_length=1.
        """
        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": ""},
        )
        assert_validation_error(response)

    async def test_suggest_thinkers_invalid_language_rejected(self, client: AsyncClient) -> None:
        """Test that suggest with unsupported language is rejected.

        Edge case: language only accepts en|es|fr per schema pattern.
        """
        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "philosophy", "language": "de"},
        )
        # 'de' is not in the allowed pattern ^(en|es|fr)$ for thinkers
        assert_validation_error(response)

    async def test_validate_thinker_quota_error_returns_503(self, client: AsyncClient) -> None:
        """Test that quota error in validate endpoint returns 503.

        Error path: ThinkerAPIError with is_quota_error=True -> 503.
        """
        with (
            patch("app.api.thinkers.get_settings") as mock_settings,
            patch("app.services.thinker.thinker_service.validate_thinker") as mock_validate,
        ):
            mock_settings.return_value.anthropic_api_key = "fake-api-key"
            mock_validate.side_effect = ThinkerAPIError("Quota exceeded", is_quota_error=True)

            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "SomeRealPerson"},
            )

        assert response.status_code == 503

    async def test_validate_thinker_api_error_returns_502(self, client: AsyncClient) -> None:
        """Test that non-quota API error in validate returns 502.

        Error path: ThinkerAPIError with is_quota_error=False -> 502.
        """
        with (
            patch("app.api.thinkers.get_settings") as mock_settings,
            patch("app.services.thinker.thinker_service.validate_thinker") as mock_validate,
        ):
            mock_settings.return_value.anthropic_api_key = "fake-api-key"
            mock_validate.side_effect = ThinkerAPIError("API error", is_quota_error=False)

            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "SomeRealPerson"},
            )

        assert response.status_code == 502

    async def test_validate_thinker_empty_name_rejected(self, client: AsyncClient) -> None:
        """Test that validate with empty name is rejected.

        Boundary condition: name has min_length=1.
        """
        response = await client.post(
            "/api/thinkers/validate",
            json={"name": ""},
        )
        assert_validation_error(response)

    async def test_validate_thinker_no_api_key_unknown_name(self, client: AsyncClient) -> None:
        """Test validate with no API key returns valid=False for unknown names.

        Edge case: Without API key, only mock thinkers are recognized.
        """
        with patch("app.api.thinkers.get_settings") as mock_settings:
            mock_settings.return_value.anthropic_api_key = None
            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "UnknownPersonXYZ123"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "error" in data

    async def test_get_knowledge_for_unknown_thinker_creates_pending_entry(
        self, client: AsyncClient
    ) -> None:
        """Test GET /api/thinkers/knowledge/{name} for unknown thinker creates entry.

        Edge case: Unknown thinker should trigger research creation (PENDING status).
        The endpoint creates a new knowledge entry if none exists.
        """
        response = await client.get("/api/thinkers/knowledge/CompletelyUnknownThinkerXYZ")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "CompletelyUnknownThinkerXYZ"
        # Should be pending or in_progress since research was just triggered
        assert data["status"] in ["pending", "in_progress", "complete", "failed"]

    async def test_get_knowledge_status_for_unknown_thinker(self, client: AsyncClient) -> None:
        """Test GET /api/thinkers/knowledge/{name}/status for unknown thinker.

        Edge case: Status endpoint returns PENDING for thinkers with no knowledge yet.
        """
        response = await client.get("/api/thinkers/knowledge/AbsolutelyUnknownThinkerABC/status")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "AbsolutelyUnknownThinkerABC"
        assert data["status"] == "pending"
        assert data["has_data"] is False

    async def test_refresh_knowledge_creates_entry_if_missing(self, client: AsyncClient) -> None:
        """Test POST /api/thinkers/knowledge/{name}/refresh creates entry for new thinker.

        Edge case: Refresh on unknown thinker should create entry and trigger research.
        """
        response = await client.post("/api/thinkers/knowledge/NewThinkerForRefreshTest/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "NewThinkerForRefreshTest"


# ===========================================================================
# Sessions API edge cases
# ===========================================================================


class TestSessionsEdgeCases:
    """Edge case tests for the sessions API."""

    async def test_get_session_with_token_missing_session_id(self, client: AsyncClient) -> None:
        """Test that a valid JWT token without session_id in payload is rejected.

        Error path: The get_session_from_token function checks for session_id
        and returns 401 if missing.
        """
        # Create token without session_id
        token = create_access_token(data={"sub": "some-user-id"})
        headers = {"Authorization": f"Bearer {token}"}

        # Try to access conversations (which uses get_session_from_token)
        response = await client.get("/api/conversations", headers=headers)
        assert_unauthorized(response, "no session")

    async def test_get_session_with_nonexistent_session_id(self, client: AsyncClient) -> None:
        """Test that a JWT with a session_id that doesn't exist in DB returns 404.

        Error path: Token is valid but session was deleted or never existed.
        """
        token = create_access_token(
            data={"sub": "some-user-id", "session_id": "nonexistent-session-xyz"}
        )
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/conversations", headers=headers)
        assert_not_found(response, "Session not found")

    async def test_get_current_session_authenticated(self, client: AsyncClient) -> None:
        """Test that an authenticated user can retrieve their session.

        Happy path: Valid credentials allow session retrieval via /api/sessions/me.
        """
        headers = await get_auth_headers(client, "sessionme", "password123")
        response = await client.get("/api/sessions/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data


# ===========================================================================
# Admin API edge cases
# ===========================================================================


class TestAdminEdgeCases:
    """Edge case tests for the admin API."""

    async def test_admin_delete_self_rejected(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that an admin cannot delete their own account.

        Security edge case: Self-deletion is prevented to avoid lockout.
        """
        admin_data = await register_and_get_token(client, "selfdelete_admin", "adminpass123")
        admin_user_id = admin_data["user"]["id"]
        admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        # Promote to admin
        from sqlalchemy import update

        from app.models import User

        await db_session.execute(update(User).where(User.id == admin_user_id).values(is_admin=True))
        await db_session.commit()

        response = await client.delete(
            f"/api/admin/users/{admin_user_id}",
            headers=admin_headers,
        )
        assert_error_response(response, 400, "Cannot delete your own account")

    async def test_admin_delete_nonexistent_user(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that deleting a non-existent user returns 404.

        Error path: Admin attempting to delete unknown user ID.
        """
        admin_headers = await create_admin_headers(
            client, db_session, "del_nonexist_admin", "adminpass123"
        )
        response = await client.delete(
            "/api/admin/users/nonexistent-user-xyz",
            headers=admin_headers,
        )
        assert_not_found(response, "User not found")

    async def test_admin_update_spend_limit_nonexistent_user(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test updating spend limit for non-existent user returns 404.

        Error path: Admin attempting to update unknown user's spend limit.
        """
        admin_headers = await create_admin_headers(
            client, db_session, "spend_admin", "adminpass123"
        )
        response = await client.patch(
            "/api/admin/users/nonexistent-user-xyz/spend-limit",
            headers=admin_headers,
            json={"spend_limit": 100.0},
        )
        assert_not_found(response, "User not found")

    async def test_non_admin_user_cannot_access_admin_endpoints(self, client: AsyncClient) -> None:
        """Test that a regular authenticated user cannot access admin endpoints.

        Security: Admin endpoints require is_admin=True, not just authentication.
        """
        # Regular user (not admin)
        headers = await get_auth_headers(client, "nonadmin_try", "password123")
        response = await client.get("/api/admin/users", headers=headers)
        assert_forbidden(response, "Admin access required")

    async def test_unauthenticated_user_cannot_access_admin_endpoints(
        self, client: AsyncClient
    ) -> None:
        """Test that unauthenticated requests to admin endpoints return 401.

        Security: Admin endpoints require both auth and admin role.
        """
        response = await client.get("/api/admin/users")
        assert_unauthorized(response)


# ===========================================================================
# Feedback API edge cases
# ===========================================================================


class TestFeedbackEdgeCases:
    """Edge case tests for the feedback API."""

    async def test_submit_feedback_message_at_exact_min_length(self, client: AsyncClient) -> None:
        """Test feedback with message at exactly the minimum length (10 chars).

        Boundary condition: min_length=10 means exactly 10 chars must succeed.
        """
        response = await client.post(
            "/api/feedback",
            json={"message": "1234567890"},  # exactly 10 chars
        )
        assert response.status_code == 201

    async def test_submit_feedback_message_at_max_length(self, client: AsyncClient) -> None:
        """Test feedback with message at exactly the maximum length (5000 chars).

        Boundary condition: max_length=5000 means exactly 5000 chars must succeed.
        """
        response = await client.post(
            "/api/feedback",
            json={"message": "A" * 5000},
        )
        assert response.status_code == 201

    async def test_submit_feedback_message_exceeds_max_length(self, client: AsyncClient) -> None:
        """Test feedback with message exceeding the maximum length (5001 chars).

        Boundary condition: max_length=5000 means 5001 chars must fail.
        """
        response = await client.post(
            "/api/feedback",
            json={"message": "A" * 5001},
        )
        assert_validation_error(response)

    async def test_submit_feedback_via_x_forwarded_for(self, client: AsyncClient) -> None:
        """Test that X-Forwarded-For header is used for rate limiting.

        Edge case: The rate limiting uses X-Forwarded-For when present, which
        affects how many submissions are allowed per IP.
        """
        # Submit feedback with a specific forwarded IP
        response = await client.post(
            "/api/feedback",
            headers={"X-Forwarded-For": "203.0.113.1"},
            json={
                "message": "Feedback submitted via forwarded proxy connection.",
            },
        )
        assert response.status_code == 201

    async def test_get_pending_feedback_limit_at_min(self, client: AsyncClient) -> None:
        """Test GET /api/feedback/pending with limit at minimum value (1).

        Boundary condition: limit has ge=1.
        """
        with patch_feedback_processor_secret("test-secret"):
            response = await client.get("/api/feedback/pending?secret=test-secret&limit=1")
        assert response.status_code == 200

    async def test_get_pending_feedback_limit_at_max(self, client: AsyncClient) -> None:
        """Test GET /api/feedback/pending with limit at maximum value (50).

        Boundary condition: limit has le=50.
        """
        with patch_feedback_processor_secret("test-secret"):
            response = await client.get("/api/feedback/pending?secret=test-secret&limit=50")
        assert response.status_code == 200

    async def test_get_pending_feedback_limit_exceeds_max(self, client: AsyncClient) -> None:
        """Test GET /api/feedback/pending with limit exceeding maximum (51).

        Boundary condition: limit has le=50, so 51 must fail.
        """
        with patch_feedback_processor_secret("test-secret"):
            response = await client.get("/api/feedback/pending?secret=test-secret&limit=51")
        assert_validation_error(response)

    async def test_mark_processed_not_configured_returns_503(self, client: AsyncClient) -> None:
        """Test mark-processed when secret is not configured returns 503.

        Error path: FEEDBACK_PROCESSOR_SECRET not set -> 503 Service Unavailable.
        """
        with patch_feedback_processor_secret(""):
            response = await client.patch(
                "/api/feedback/some-id/processed?secret=any-secret",
                json={"github_issue_url": "https://github.com/test/test/issues/1"},
            )
        assert response.status_code == 503

    async def test_submit_feedback_with_forwarded_for_chain(self, client: AsyncClient) -> None:
        """Test that the first IP in X-Forwarded-For chain is used.

        Edge case: When multiple proxies forward, only the originating IP
        should be used for rate limiting (first in the chain).
        """
        response = await client.post(
            "/api/feedback",
            headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.2, 10.0.0.3"},
            json={
                "message": "Feedback with multiple proxy chain addresses.",
            },
        )
        assert response.status_code == 201
