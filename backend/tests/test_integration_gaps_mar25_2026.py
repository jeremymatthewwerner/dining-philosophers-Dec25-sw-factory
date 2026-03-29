"""Integration tests for Wednesday March 25 2026 - filling API coverage gaps.

Focus: Untested API integration paths discovered through coverage analysis.

Key gaps addressed:
- app/api/thinkers.py: suggest endpoint with API key (quota/non-quota errors, empty fallback)
- app/api/thinkers.py: validate_thinker with API key (valid, invalid, ThinkerAPIError)
- app/api/auth.py: update_profile endpoint, change_password endpoint, logout endpoint
- app/api/sessions.py: token without session_id, token referencing nonexistent session
- app/api/spend.py: GET /spend/{user_id} returns 404 for nonexistent user
"""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ThinkerAPIError
from app.schemas import ThinkerProfile, ThinkerSuggestion
from tests.conftest import get_auth_headers, register_and_get_token

# Patch target for knowledge_service.trigger_research
_KNOWLEDGE_PATCH = "app.services.knowledge_research.knowledge_service.trigger_research"

# Patch target for thinker service methods
_THINKER_SUGGEST_PATCH = "app.services.thinker.thinker_service.suggest_thinkers"
_THINKER_VALIDATE_PATCH = "app.services.thinker.thinker_service.validate_thinker"
_THINKER_WIKIPEDIA_PATCH = "app.services.thinker.thinker_service.get_wikipedia_image"


def _make_mock_settings_with_api_key() -> object:
    """Return mock settings object with an API key configured."""
    return type("Settings", (), {"anthropic_api_key": "test-api-key"})()


def _make_mock_settings_no_api_key() -> object:
    """Return mock settings object with no API key (triggers mock mode)."""
    return type("Settings", (), {"anthropic_api_key": None})()


# ---------------------------------------------------------------------------
# Thinkers API - Suggest endpoint with API key path
# ---------------------------------------------------------------------------


class TestSuggestThinkersWithApiKey:
    """Test suggest_thinkers endpoint when API key is configured."""

    @patch(_KNOWLEDGE_PATCH)
    async def test_suggest_thinkers_returns_503_on_quota_error(
        self, _mock_trigger: object, client: AsyncClient
    ) -> None:
        """POST /thinkers/suggest raises 503 when API raises quota ThinkerAPIError.

        Coverage: app/api/thinkers.py lines 142-144 (quota error path)
        When the AI service quota is exceeded, the endpoint should return 503
        to indicate the service is temporarily unavailable.
        """
        quota_error = ThinkerAPIError("API quota exceeded", is_quota_error=True)

        with (
            patch("app.api.thinkers.get_settings", return_value=_make_mock_settings_with_api_key()),
            patch(_THINKER_SUGGEST_PATCH, new_callable=AsyncMock) as mock_suggest,
        ):
            mock_suggest.side_effect = quota_error

            response = await client.post(
                "/api/thinkers/suggest",
                json={"topic": "science", "count": 3},
            )

        assert response.status_code == 503
        data = response.json()
        assert "quota exceeded" in data["detail"].lower()

    @patch(_KNOWLEDGE_PATCH)
    async def test_suggest_thinkers_returns_502_on_non_quota_api_error(
        self, _mock_trigger: object, client: AsyncClient
    ) -> None:
        """POST /thinkers/suggest raises 502 when API raises non-quota ThinkerAPIError.

        Coverage: app/api/thinkers.py lines 142-144 (non-quota error path)
        When the AI service has a non-quota error (e.g., bad request), the endpoint
        should return 502 Bad Gateway.
        """
        api_error = ThinkerAPIError("AI service error: internal error", is_quota_error=False)

        with (
            patch("app.api.thinkers.get_settings", return_value=_make_mock_settings_with_api_key()),
            patch(_THINKER_SUGGEST_PATCH, new_callable=AsyncMock) as mock_suggest,
        ):
            mock_suggest.side_effect = api_error

            response = await client.post(
                "/api/thinkers/suggest",
                json={"topic": "philosophy", "count": 2},
            )

        assert response.status_code == 502
        data = response.json()
        assert "service error" in data["detail"].lower()

    @patch(_KNOWLEDGE_PATCH)
    async def test_suggest_thinkers_falls_back_to_mock_when_api_returns_empty(
        self, _mock_trigger: object, client: AsyncClient
    ) -> None:
        """POST /thinkers/suggest falls back to mock suggestions when API returns empty list.

        Coverage: app/api/thinkers.py line 148 (fallback to mock suggestions)
        When the thinker service returns an empty list (non-error case), the endpoint
        should fall back to returning mock suggestions.
        """
        with (
            patch("app.api.thinkers.get_settings", return_value=_make_mock_settings_with_api_key()),
            patch(_THINKER_SUGGEST_PATCH, new_callable=AsyncMock) as mock_suggest,
            patch(_THINKER_WIKIPEDIA_PATCH, new_callable=AsyncMock) as mock_wiki,
        ):
            mock_suggest.return_value = []  # Empty result triggers fallback
            mock_wiki.return_value = None

            response = await client.post(
                "/api/thinkers/suggest",
                json={"topic": "ethics", "count": 2},
            )

        assert response.status_code == 200
        data = response.json()
        # Should return mock suggestions (Socrates, Einstein, etc.)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]
        assert "reason" in data[0]
        assert "profile" in data[0]

    @patch(_KNOWLEDGE_PATCH)
    async def test_suggest_thinkers_returns_api_results_when_api_succeeds(
        self, _mock_trigger: object, client: AsyncClient
    ) -> None:
        """POST /thinkers/suggest returns real API results when service succeeds.

        Coverage: app/api/thinkers.py lines 136-141 (successful API path)
        When the thinker service returns results, the endpoint should return them
        directly without falling back to mock suggestions.
        """
        mock_profile = ThinkerProfile(
            name="Plato",
            bio="Ancient Greek philosopher, student of Socrates.",
            positions="Theory of forms, philosopher-kings.",
            style="Dialogues and dialectic method.",
            image_url=None,
        )
        api_suggestions = [
            ThinkerSuggestion(
                name="Plato",
                reason="Expert in epistemology and political philosophy.",
                profile=mock_profile,
            )
        ]

        with (
            patch("app.api.thinkers.get_settings", return_value=_make_mock_settings_with_api_key()),
            patch(_THINKER_SUGGEST_PATCH, new_callable=AsyncMock) as mock_suggest,
        ):
            mock_suggest.return_value = api_suggestions

            response = await client.post(
                "/api/thinkers/suggest",
                json={"topic": "justice", "count": 1},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Plato"
        assert data[0]["reason"] == "Expert in epistemology and political philosophy."


# ---------------------------------------------------------------------------
# Thinkers API - Validate endpoint with API key path
# ---------------------------------------------------------------------------


class TestValidateThinkerWithApiKey:
    """Test validate_thinker endpoint when API key is configured and thinker is not in mock list."""

    @patch(_KNOWLEDGE_PATCH)
    async def test_validate_thinker_with_api_key_valid_result(
        self, _mock_trigger: object, client: AsyncClient
    ) -> None:
        """POST /thinkers/validate returns valid=True when API validates non-mock thinker.

        Coverage: app/api/thinkers.py lines 196-203 (API key path - valid thinker)
        When a non-mock thinker name is provided and API key is configured, the
        validate_thinker service should be called and a valid result returned.
        """
        mock_profile = ThinkerProfile(
            name="Immanuel Kant",
            bio="German philosopher (1724-1804), founder of critical philosophy.",
            positions="Categorical imperative, transcendental idealism.",
            style="Systematic and rigorous argument.",
            image_url=None,
        )

        with (
            patch("app.api.thinkers.get_settings", return_value=_make_mock_settings_with_api_key()),
            patch(_THINKER_VALIDATE_PATCH, new_callable=AsyncMock) as mock_validate,
            patch(_KNOWLEDGE_PATCH),
        ):
            mock_validate.return_value = (True, mock_profile)

            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "Immanuel Kant"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["name"] == "Immanuel Kant"
        assert (
            data["profile"]["bio"]
            == "German philosopher (1724-1804), founder of critical philosophy."
        )

    @patch(_KNOWLEDGE_PATCH)
    async def test_validate_thinker_with_api_key_invalid_result(
        self, _mock_trigger: object, client: AsyncClient
    ) -> None:
        """POST /thinkers/validate returns valid=False when API says thinker is not real.

        Coverage: app/api/thinkers.py lines 210-213 (API key path - invalid thinker)
        When the API confirms a name is not a real historical figure, the endpoint
        should return valid=False with an appropriate error message.
        """
        with (
            patch("app.api.thinkers.get_settings", return_value=_make_mock_settings_with_api_key()),
            patch(_THINKER_VALIDATE_PATCH, new_callable=AsyncMock) as mock_validate,
        ):
            mock_validate.return_value = (False, None)

            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "FakePersonXYZ123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["name"] == "FakePersonXYZ123"
        assert data["error"] is not None
        assert "FakePersonXYZ123" in data["error"]

    @patch(_KNOWLEDGE_PATCH)
    async def test_validate_thinker_returns_503_on_quota_error(
        self, _mock_trigger: object, client: AsyncClient
    ) -> None:
        """POST /thinkers/validate raises 503 when API raises quota ThinkerAPIError.

        Coverage: app/api/thinkers.py lines 206-209 (validate - quota error)
        When the AI service quota is exceeded during validation, the endpoint
        should return 503.
        """
        quota_error = ThinkerAPIError("Quota exceeded", is_quota_error=True)

        with (
            patch("app.api.thinkers.get_settings", return_value=_make_mock_settings_with_api_key()),
            patch(_THINKER_VALIDATE_PATCH, new_callable=AsyncMock) as mock_validate,
        ):
            mock_validate.side_effect = quota_error

            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "Plato"},
            )

        assert response.status_code == 503
        data = response.json()
        assert "Quota exceeded" in data["detail"]

    @patch(_KNOWLEDGE_PATCH)
    async def test_validate_thinker_returns_502_on_non_quota_api_error(
        self, _mock_trigger: object, client: AsyncClient
    ) -> None:
        """POST /thinkers/validate raises 502 when API raises non-quota ThinkerAPIError.

        Coverage: app/api/thinkers.py lines 206-209 (validate - non-quota error)
        When the AI service has a non-quota failure during validation, the endpoint
        should return 502 Bad Gateway.
        """
        api_error = ThinkerAPIError("AI service error: upstream failure", is_quota_error=False)

        with (
            patch("app.api.thinkers.get_settings", return_value=_make_mock_settings_with_api_key()),
            patch(_THINKER_VALIDATE_PATCH, new_callable=AsyncMock) as mock_validate,
        ):
            mock_validate.side_effect = api_error

            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "Nietzsche"},
            )

        assert response.status_code == 502
        data = response.json()
        assert "upstream failure" in data["detail"]

    @patch(_KNOWLEDGE_PATCH)
    async def test_validate_thinker_with_api_key_and_language(
        self, _mock_trigger: object, client: AsyncClient
    ) -> None:
        """POST /thinkers/validate passes language parameter to service.

        Coverage: app/api/thinkers.py lines 196-203 (validate API key path with language)
        The language parameter should be forwarded to the thinker service.
        """
        mock_profile = ThinkerProfile(
            name="Descartes",
            bio="French philosopher (1596-1650).",
            positions="Cogito ergo sum, mind-body dualism.",
            style="Methodological doubt.",
            image_url=None,
        )

        with (
            patch("app.api.thinkers.get_settings", return_value=_make_mock_settings_with_api_key()),
            patch(_THINKER_VALIDATE_PATCH, new_callable=AsyncMock) as mock_validate,
            patch(_KNOWLEDGE_PATCH),
        ):
            mock_validate.return_value = (True, mock_profile)

            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "Descartes", "language": "fr"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        # Verify language was passed to the service
        mock_validate.assert_called_once_with("Descartes", "fr")


# ---------------------------------------------------------------------------
# Auth API - Profile update endpoint
# ---------------------------------------------------------------------------


class TestUpdateProfile:
    """Test PATCH /api/auth/profile endpoint."""

    async def test_update_profile_sets_display_name(self, client: AsyncClient) -> None:
        """PATCH /api/auth/profile updates the user's display name.

        Coverage: app/api/auth.py lines 222-226 (update_profile happy path)
        When authenticated, the user should be able to update their display name.
        """
        headers = await get_auth_headers(client, "profileuser", "pass123")

        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": "Updated Display Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Display Name"
        assert data["username"] == "profileuser"

    async def test_update_profile_persists_across_me_request(self, client: AsyncClient) -> None:
        """PATCH /api/auth/profile change is visible in subsequent GET /api/auth/me.

        Coverage: app/api/auth.py lines 222-226 (update_profile persists to DB)
        After updating the display name, the change should be reflected in the
        /me endpoint response.
        """
        headers = await get_auth_headers(client, "persistprofileuser", "pass123")

        # Update profile
        await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": "Persisted Name"},
        )

        # Verify change persists
        me_response = await client.get("/api/auth/me", headers=headers)
        assert me_response.status_code == 200
        data = me_response.json()
        assert data["display_name"] == "Persisted Name"

    async def test_update_profile_requires_authentication(self, client: AsyncClient) -> None:
        """PATCH /api/auth/profile returns 401 without auth token.

        Coverage: app/api/auth.py lines 222-226 (update_profile auth check)
        The profile update endpoint must require a valid authentication token.
        """
        response = await client.patch(
            "/api/auth/profile",
            json={"display_name": "Should Fail"},
        )

        assert response.status_code == 401

    async def test_update_profile_returns_all_user_fields(self, client: AsyncClient) -> None:
        """PATCH /api/auth/profile response includes all UserResponse fields.

        Coverage: app/api/auth.py lines 222-226 (update_profile response fields)
        The response should include all standard UserResponse fields.
        """
        headers = await get_auth_headers(client, "fieldsprofileuser", "pass123")

        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": "Field Check Name"},
        )

        assert response.status_code == 200
        data = response.json()
        # Verify all UserResponse fields are present
        assert "id" in data
        assert "username" in data
        assert "display_name" in data
        assert "is_admin" in data
        assert "total_spend" in data
        assert "spend_limit" in data
        assert "language_preference" in data
        assert "created_at" in data


# ---------------------------------------------------------------------------
# Auth API - Change password endpoint
# ---------------------------------------------------------------------------


class TestChangePassword:
    """Test POST /api/auth/change-password endpoint."""

    async def test_change_password_success(self, client: AsyncClient) -> None:
        """POST /api/auth/change-password changes password when current password is correct.

        Coverage: app/api/auth.py lines 249-259 (change_password happy path)
        When the correct current password is provided, the password should be updated.
        """
        headers = await get_auth_headers(client, "changepassuser", "oldpass123")

        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "oldpass123",
                "new_password": "newpass456",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "success" in data["message"].lower() or "changed" in data["message"].lower()

    async def test_change_password_fails_with_wrong_current_password(
        self, client: AsyncClient
    ) -> None:
        """POST /api/auth/change-password returns 400 when current password is wrong.

        Coverage: app/api/auth.py lines 249-253 (change_password wrong password check)
        When the current password is incorrect, the endpoint should return 400
        with a descriptive error message.
        """
        headers = await get_auth_headers(client, "wrongpassuser", "correctpass123")

        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "wrongpassword",
                "new_password": "newpass456",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert "incorrect" in data["detail"].lower()

    async def test_change_password_requires_authentication(self, client: AsyncClient) -> None:
        """POST /api/auth/change-password returns 401 without auth token.

        Coverage: app/api/auth.py lines 249-259 (change_password auth check)
        The change password endpoint must require valid authentication.
        """
        response = await client.post(
            "/api/auth/change-password",
            json={
                "current_password": "oldpass",
                "new_password": "newpass",
            },
        )

        assert response.status_code == 401

    async def test_change_password_allows_login_with_new_password(
        self, client: AsyncClient
    ) -> None:
        """POST /api/auth/change-password - new password works for subsequent login.

        Coverage: app/api/auth.py lines 254-259 (change_password DB update)
        After a successful password change, the user should be able to login
        with the new password.
        """
        # Register user and get token in one step (avoid re-registration)
        data = await register_and_get_token(client, "newpasslogin", "initial123")
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        # Change password
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "initial123",
                "new_password": "changed456",
            },
        )
        assert response.status_code == 200

        # Login with new password
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "newpasslogin", "password": "changed456"},
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()


# ---------------------------------------------------------------------------
# Auth API - Logout endpoint
# ---------------------------------------------------------------------------


class TestLogout:
    """Test POST /api/auth/logout endpoint."""

    async def test_logout_returns_success_message(self, client: AsyncClient) -> None:
        """POST /api/auth/logout returns a success message.

        Coverage: app/api/auth.py line 269 (logout endpoint)
        The logout endpoint should return a success message. Since JWT tokens
        are stateless, logout is handled client-side, but the endpoint provides
        a standardized response.
        """
        response = await client.post("/api/auth/logout")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "logout" in data["message"].lower() or "logged out" in data["message"].lower()

    async def test_logout_works_without_authentication(self, client: AsyncClient) -> None:
        """POST /api/auth/logout succeeds even without auth token.

        Coverage: app/api/auth.py line 269 (logout - no auth required)
        Since JWT logout is client-side, the endpoint should be accessible
        without authentication (no token to invalidate server-side).
        """
        # No auth headers
        response = await client.post("/api/auth/logout")

        assert response.status_code == 200

    async def test_logout_works_with_valid_token(self, client: AsyncClient) -> None:
        """POST /api/auth/logout succeeds when called with a valid auth token.

        Coverage: app/api/auth.py line 269 (logout with token)
        The logout endpoint should work whether or not a token is provided.
        """
        headers = await get_auth_headers(client, "logoutuser", "pass123")

        response = await client.post("/api/auth/logout", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "message" in data


# ---------------------------------------------------------------------------
# Sessions API - Error paths in get_session_from_token
# ---------------------------------------------------------------------------


class TestSessionsErrorPaths:
    """Test error paths in the sessions API get_session_from_token dependency."""

    async def test_get_session_fails_when_token_has_no_session_id(
        self, client: AsyncClient
    ) -> None:
        """GET /api/sessions/me returns 401 when JWT token has no session_id field.

        Coverage: app/api/sessions.py line 34 (no session_id in payload)
        Tokens created with only a user 'sub' field (no session_id) should be rejected
        when accessing session-protected endpoints.
        """
        from app.core.auth import create_access_token

        # Create a token with only 'sub' but no 'session_id'
        token_without_session = create_access_token(data={"sub": "some-user-id"})
        headers = {"Authorization": f"Bearer {token_without_session}"}

        response = await client.get("/api/sessions/me", headers=headers)

        assert response.status_code == 401
        data = response.json()
        assert "session" in data["detail"].lower()

    async def test_get_session_fails_when_session_not_in_db(self, client: AsyncClient) -> None:
        """GET /api/sessions/me returns 404 when token references nonexistent session.

        Coverage: app/api/sessions.py line 41 (session not found)
        When a valid JWT contains a session_id that doesn't exist in the database,
        the endpoint should return 404 Session not found.
        """
        from app.core.auth import create_access_token

        # Create a token with a session_id that doesn't exist in the DB
        token_with_fake_session = create_access_token(
            data={"sub": "some-user-id", "session_id": "nonexistent-session-id-xyz"}
        )
        headers = {"Authorization": f"Bearer {token_with_fake_session}"}

        response = await client.get("/api/sessions/me", headers=headers)

        assert response.status_code == 404
        data = response.json()
        assert "session" in data["detail"].lower()

    async def test_get_session_also_fails_for_conversations_with_no_session_id(
        self, client: AsyncClient
    ) -> None:
        """GET /api/conversations returns 401 when token lacks session_id.

        Coverage: app/api/sessions.py line 34 - also applies to conversation endpoints
        The get_session_from_token dependency is used by conversations and other endpoints.
        Ensure the same validation applies there.
        """
        from app.core.auth import create_access_token

        # Token without session_id
        token = create_access_token(data={"sub": "some-user-id"})
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/conversations", headers=headers)

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Spend API - GET /spend/{user_id} 404 path
# ---------------------------------------------------------------------------


class TestSpendEndpointNotFound:
    """Test the spend API endpoint 404 path."""

    async def test_spend_endpoint_404_with_proper_admin(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """GET /api/spend/{user_id} returns 404 for nonexistent user_id with real admin.

        Coverage: app/api/spend.py line 36 (user not found -> 404)
        Creates a proper admin user directly in the test DB to ensure the
        admin check passes, then tests the 404 path.
        """
        from app.core.auth import create_access_token, get_password_hash
        from app.models import Session as UserSession
        from app.models import User

        # Create an admin user directly
        admin_user = User(
            username="real_spend_admin",
            password_hash=get_password_hash("adminpass"),
            is_admin=True,
        )
        async_session.add(admin_user)
        await async_session.flush()

        # Create a session for the admin
        admin_session = UserSession(user_id=admin_user.id)
        async_session.add(admin_session)
        await async_session.flush()
        await async_session.refresh(admin_session)

        # Create token with session_id
        token = create_access_token(data={"sub": admin_user.id, "session_id": admin_session.id})
        headers = {"Authorization": f"Bearer {token}"}

        # Request spend data for a nonexistent user
        response = await client.get(
            "/api/spend/totally-nonexistent-user-xyz",
            headers=headers,
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower() or "User" in data["detail"]


# ---------------------------------------------------------------------------
# Thinkers API - validate_thinker with API key but is_valid=True and profile=None
# ---------------------------------------------------------------------------


class TestValidateThinkerEdgeCases:
    """Test edge cases in validate_thinker endpoint."""

    @patch(_KNOWLEDGE_PATCH)
    async def test_validate_thinker_returns_invalid_when_is_valid_true_but_no_profile(
        self, _mock_trigger: object, client: AsyncClient
    ) -> None:
        """POST /thinkers/validate returns invalid when API returns (True, None).

        Coverage: app/api/thinkers.py lines 196-202 (is_valid=True but profile=None)
        If the service returns valid=True but no profile, the endpoint should
        fall through to the invalid response (the profile is required).
        """
        with (
            patch("app.api.thinkers.get_settings", return_value=_make_mock_settings_with_api_key()),
            patch(_THINKER_VALIDATE_PATCH, new_callable=AsyncMock) as mock_validate,
        ):
            # Return (True, None) - valid flag but no profile
            mock_validate.return_value = (True, None)

            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "PartialValidThinker"},
            )

        assert response.status_code == 200
        data = response.json()
        # Should return invalid since no profile was returned
        assert data["valid"] is False
        assert "PartialValidThinker" in data["error"]

    @patch(_KNOWLEDGE_PATCH)
    async def test_validate_mock_thinker_triggers_knowledge_research(
        self, mock_trigger: object, client: AsyncClient
    ) -> None:
        """POST /thinkers/validate for a mock thinker triggers background knowledge research.

        Coverage: app/api/thinkers.py lines 173-175 (trigger_research for mock thinkers)
        When a known mock thinker is validated, knowledge research should be triggered
        as a background task.
        """
        with patch(_THINKER_WIKIPEDIA_PATCH, new_callable=AsyncMock) as mock_wiki:
            mock_wiki.return_value = "https://example.com/socrates.jpg"

            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "Socrates"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        # Verify the mock trigger was called (once from validate, possibly once from conftest)
        assert mock_trigger.called  # type: ignore[union-attr]
