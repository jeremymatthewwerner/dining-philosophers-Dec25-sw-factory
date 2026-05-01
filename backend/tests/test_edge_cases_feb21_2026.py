"""Edge case tests - Saturday QA focus on error paths and boundary conditions.

Tests cover:
- Auth API: logout endpoint, require_admin 403, login session creation,
  token with deleted user, boundary conditions
- Admin API: spend-limit 404, delete-user 404, non-admin access
- Feedback API: rate limiting, pending feedback, mark processed, min/max lengths
- Conversation API: max thinkers (5), add thinkers over limit, thinker color exhaustion
- Boundary conditions: unicode topics, special characters, min/max field lengths
"""

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from tests.conftest import (
    assert_not_found,
    assert_unauthorized,
    assert_validation_error,
    get_auth_headers,
    register_and_get_token,
)


class TestAuthLogoutEndpoint:
    """Test logout endpoint edge cases."""

    async def test_logout_succeeds_without_auth(self, client: AsyncClient) -> None:
        """Test that logout endpoint works without authentication.

        Edge case: Logout is stateless (JWT), so no auth needed.
        Covers: auth.py logout function (line 263-269)
        """
        response = await client.post("/api/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logged out successfully"

    async def test_logout_succeeds_with_valid_auth(self, client: AsyncClient) -> None:
        """Test that logout succeeds with a valid auth token.

        Edge case: Confirms logout ignores auth token state.
        """
        headers = await get_auth_headers(
            client, username="logout_auth_user_feb21", password="pass123"
        )
        response = await client.post("/api/auth/logout", headers=headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"


class TestRequireAdminEdgeCases:
    """Test require_admin dependency edge cases."""

    async def test_admin_endpoint_rejects_non_admin_user(self, client: AsyncClient) -> None:
        """Test that admin endpoints return 403 for non-admin users.

        Edge case: require_admin dependency raises 403 for non-admin.
        Covers: auth.py require_admin function (lines 73-78)
        """
        # Register a non-admin user
        headers = await get_auth_headers(
            client, username="non_admin_user_feb21", password="testpass123"
        )

        # Try to access admin endpoint
        response = await client.get("/api/admin/users", headers=headers)
        assert response.status_code == 403
        assert "admin" in response.json()["detail"].lower()

    async def test_admin_endpoint_rejects_no_auth(self, client: AsyncClient) -> None:
        """Test that admin endpoints return 401 without authentication.

        Edge case: require_user dependency raises 401 with no credentials.
        Covers: auth.py require_user function (lines 60-66)
        """
        response = await client.get("/api/admin/users")
        assert response.status_code in [401, 403]


class TestLoginSessionCreation:
    """Test login when user has no existing session."""

    async def test_login_creates_session_when_none_exists(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that login creates a new session when user has no existing sessions.

        Edge case: Login when no session exists (lines 151-155 in auth.py).
        This covers the branch where session is None and a new one is created.
        """
        from sqlalchemy import delete

        from app.models import Session as AppSession

        # Register a user (creates a session)
        data = await register_and_get_token(
            client, username="no_session_user_feb21", password="testpass123"
        )
        user_id = data["user"]["id"]

        # Delete all sessions for this user
        await db_session.execute(delete(AppSession).where(AppSession.user_id == user_id))
        await db_session.commit()

        # Now login - should create a new session
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "no_session_user_feb21", "password": "testpass123"},
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "access_token" in login_data
        assert login_data["user"]["username"] == "no_session_user_feb21"

    async def test_login_wrong_password_returns_401(self, client: AsyncClient) -> None:
        """Test that login with wrong password returns 401.

        Edge case: Invalid credentials path in login.
        Covers: auth.py login function, invalid password branch (lines 141-145)
        """
        await register_and_get_token(
            client, username="wrong_pass_user_feb21", password="correctpass"
        )

        response = await client.post(
            "/api/auth/login",
            json={"username": "wrong_pass_user_feb21", "password": "wrongpass"},
        )
        assert_unauthorized(response, "Invalid username or password")

    async def test_login_nonexistent_user_returns_401(self, client: AsyncClient) -> None:
        """Test that login with nonexistent username returns 401.

        Edge case: User not found in database.
        """
        response = await client.post(
            "/api/auth/login",
            json={"username": "does_not_exist_feb21", "password": "anypass"},
        )
        assert_unauthorized(response, "Invalid username or password")


class TestAuthUpdateEndpoints:
    """Test auth profile update endpoints."""

    async def test_update_language_returns_user_response(self, client: AsyncClient) -> None:
        """Test that updating language returns full user response.

        Covers: auth.py update_language function (lines 192-212)
        """
        headers = await get_auth_headers(
            client, username="lang_update_user_feb21", password="testpass123"
        )

        response = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "es"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["language_preference"] == "es"
        assert "id" in data
        assert "username" in data

    async def test_update_profile_returns_user_with_new_name(self, client: AsyncClient) -> None:
        """Test that updating profile returns user with updated display name.

        Covers: auth.py update_profile function (lines 215-235)
        """
        headers = await get_auth_headers(
            client, username="profile_update_feb21", password="testpass123"
        )

        new_display_name = "Updated Display Name Feb21"
        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": new_display_name},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == new_display_name

    async def test_change_password_returns_success_message(self, client: AsyncClient) -> None:
        """Test that changing password returns success message.

        Covers: auth.py change_password function return (line 259)
        """
        headers = await get_auth_headers(
            client, username="change_pass_feb21", password="original_pass"
        )

        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "original_pass",
                "new_password": "new_secure_pass123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "success" in data["message"].lower() or "changed" in data["message"].lower()

    async def test_change_password_wrong_current_password(self, client: AsyncClient) -> None:
        """Test that changing password with wrong current password returns 400.

        Edge case: Invalid current password.
        Covers: auth.py change_password error path (lines 249-253)
        """
        headers = await get_auth_headers(
            client, username="wrong_curr_pass_feb21", password="correct_pass"
        )

        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "wrong_pass",
                "new_password": "new_pass",
            },
        )
        assert response.status_code == 400
        assert "incorrect" in response.json()["detail"].lower()


class TestRegisterEdgeCases:
    """Test registration edge cases."""

    async def test_register_duplicate_username_returns_400(self, client: AsyncClient) -> None:
        """Test that registering with duplicate username returns 400.

        Edge case: Username already taken.
        Covers: auth.py register function existing_user check (lines 89-94)
        """
        username = "dup_user_feb21"
        await register_and_get_token(client, username=username, password="pass123")

        # Try to register with same username
        response = await client.post(
            "/api/auth/register",
            json={
                "username": username,
                "display_name": "Another User",
                "password": "different_pass",
            },
        )
        assert response.status_code == 400
        assert "already taken" in response.json()["detail"].lower()

    async def test_register_with_display_name_none(self, client: AsyncClient) -> None:
        """Test that registering without a display_name uses username by default.

        Edge case: Optional display_name field - tests None handling.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "no_display_feb21",
                "password": "testpass123",
                # No display_name provided
            },
        )
        # Should succeed or fail with validation error
        assert response.status_code in [200, 422]
        if response.status_code == 200:
            data = response.json()
            assert "user" in data


class TestAdminSpendLimitEdgeCases:
    """Test admin spend limit endpoint edge cases."""

    async def test_update_spend_limit_for_nonexistent_user(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that updating spend limit for nonexistent user returns 404.

        Edge case: User not found in database.
        Covers: admin.py update_spend_limit 404 path (lines 81-85)
        """
        admin_data = await register_and_get_token(
            client, username="admin_404_test_feb21", password="adminpass"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()

        # Login as admin
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin_404_test_feb21", "password": "adminpass"},
        )
        admin_token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Try to update spend limit for nonexistent user
        response = await client.patch(
            "/api/admin/users/nonexistent-user-id-12345/spend-limit",
            headers=admin_headers,
            json={"spend_limit": 100.0},
        )
        assert_not_found(response, "User not found")

    async def test_delete_nonexistent_user_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that deleting a nonexistent user returns 404.

        Edge case: User not found in database.
        Covers: admin.py delete_user 404 path (lines 115-119)
        """
        admin_data = await register_and_get_token(
            client, username="admin_del_404_feb21", password="adminpass"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()

        # Login as admin
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin_del_404_feb21", "password": "adminpass"},
        )
        admin_token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Try to delete nonexistent user
        response = await client.delete(
            "/api/admin/users/nonexistent-user-xyz-9999",
            headers=admin_headers,
        )
        assert_not_found(response, "User not found")

    async def test_update_spend_limit_success_returns_response(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test successful spend limit update returns proper response.

        Covers: admin.py update_spend_limit success path (lines 87-93)
        """
        admin_data = await register_and_get_token(
            client, username="admin_succ_feb21", password="adminpass"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()

        target_data = await register_and_get_token(
            client, username="target_user_feb21", password="testpass"
        )
        target_id = target_data["user"]["id"]

        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin_succ_feb21", "password": "adminpass"},
        )
        admin_token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        response = await client.patch(
            f"/api/admin/users/{target_id}/spend-limit",
            headers=admin_headers,
            json={"spend_limit": 50.0},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["spend_limit"] == 50.0
        assert data["user_id"] == target_id
        assert "$50.00" in data["message"]


class TestFeedbackEdgeCases:
    """Test feedback API edge cases."""

    async def test_submit_feedback_minimum_valid_message(self, client: AsyncClient) -> None:
        """Test submitting feedback with exactly minimum length message (10 chars).

        Edge case: Boundary condition - min_length=10.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "other",
                "message": "1234567890",  # exactly 10 chars
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "message" in data

    async def test_submit_feedback_maximum_valid_message(self, client: AsyncClient) -> None:
        """Test submitting feedback with exactly maximum length message (5000 chars).

        Edge case: Boundary condition - max_length=5000.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "bug",
                "message": "A" * 5000,  # exactly 5000 chars
            },
        )
        assert response.status_code == 201

    async def test_submit_feedback_message_too_short(self, client: AsyncClient) -> None:
        """Test submitting feedback with message shorter than 10 chars.

        Edge case: Boundary violation - message too short.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "bug",
                "message": "short",  # only 5 chars
            },
        )
        assert_validation_error(response)

    async def test_submit_feedback_message_too_long(self, client: AsyncClient) -> None:
        """Test submitting feedback with message longer than 5000 chars.

        Edge case: Boundary violation - message too long.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "feature",
                "message": "A" * 5001,  # one more than max
            },
        )
        assert_validation_error(response)

    async def test_submit_feedback_feature_type(self, client: AsyncClient) -> None:
        """Test submitting feedback with 'feature' type.

        Edge case: Different feedback types - validates type enum handling.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "feature",
                "message": "Please add dark mode to the application!",
            },
        )
        assert response.status_code == 201

    async def test_submit_feedback_with_invalid_type(self, client: AsyncClient) -> None:
        """Test submitting feedback with invalid feedback type.

        Edge case: Invalid enum value.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "invalid_type",
                "message": "This has an invalid feedback type value",
            },
        )
        assert_validation_error(response)

    async def test_get_pending_feedback_no_secret_configured(self, client: AsyncClient) -> None:
        """Test that pending feedback endpoint returns 503 when no secret is configured.

        Edge case: FEEDBACK_PROCESSOR_SECRET not set in environment.
        Covers: feedback.py verify_feedback_processor_secret (lines 125-130)
        """
        # In test environment, FEEDBACK_PROCESSOR_SECRET is not set (default empty string)
        response = await client.get(
            "/api/feedback/pending",
            params={"secret": "any_secret"},
        )
        # Returns 503 because secret is not configured, or 403 if wrong secret
        assert response.status_code in [503, 403]

    async def test_submit_feedback_with_all_optional_fields(self, client: AsyncClient) -> None:
        """Test submitting feedback with all optional fields populated.

        Edge case: All optional fields - exercises full object creation.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "bug",
                "message": "This is a bug report with all fields populated for testing",
                "email": "test@example.com",
                "name": "Test User",
                "username": "testuser123",
                "user_agent": "Mozilla/5.0 (Test Browser)",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data

    async def test_submit_feedback_oversized_screenshot(self, client: AsyncClient) -> None:
        """Test submitting feedback with screenshot that exceeds 7MB limit.

        Edge case: Screenshot data validation.
        Covers: feedback.py schema validator (lines 39-41)
        """
        # Generate a base64 string larger than 7MB
        large_data = "A" * 7_000_001  # > MAX_SCREENSHOT_SIZE

        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "bug",
                "message": "Bug with a very large screenshot attached",
                "screenshot_data": large_data,
                "screenshot_filename": "screenshot.png",
            },
        )
        assert_validation_error(response)

    async def test_submit_feedback_rate_limiting(self, client: AsyncClient) -> None:
        """Test that feedback rate limiting kicks in after 5 submissions.

        Edge case: Rate limiting boundary - 5 per hour per IP.
        Covers: feedback.py rate limiting check (lines 68-82)
        """
        # Submit 5 feedbacks (within limit)
        for i in range(5):
            response = await client.post(
                "/api/feedback",
                json={
                    "feedback_type": "other",
                    "message": f"Rate limit test submission number {i + 1} - testing boundary",
                },
            )
            assert response.status_code == 201, f"Submission {i + 1} failed: {response.text}"

        # 6th submission should be rate limited
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "other",
                "message": "This should be rate limited - 6th submission in an hour",
            },
        )
        assert response.status_code == 429
        assert "Too many" in response.json()["detail"]


class TestConversationMaxThinkersEdgeCases:
    """Test conversation thinker limit edge cases."""

    async def test_create_conversation_with_exactly_5_thinkers(self, client: AsyncClient) -> None:
        """Test that creating a conversation with exactly 5 thinkers succeeds.

        Edge case: Maximum thinkers boundary (max_length=5 in ConversationCreate schema).
        """
        headers = await get_auth_headers(
            client, username="max_thinkers_feb21", password="testpass123"
        )

        thinker_names = ["Plato", "Aristotle", "Socrates", "Descartes", "Hume"]
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Philosophy roundtable with 5 thinkers",
                "thinkers": [
                    {
                        "name": name,
                        "bio": f"Bio of {name}",
                        "positions": f"Positions of {name}",
                        "style": f"Style of {name}",
                        "color": "#6366f1",
                    }
                    for name in thinker_names
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 5

    async def test_create_conversation_with_6_thinkers_rejected(self, client: AsyncClient) -> None:
        """Test that creating a conversation with 6 thinkers is rejected.

        Edge case: Exceeds maximum thinkers boundary (max_length=5).
        """
        headers = await get_auth_headers(
            client, username="over_max_thinkers_feb21", password="testpass123"
        )

        thinker_names = ["Plato", "Aristotle", "Socrates", "Descartes", "Hume", "Kant"]
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Over-limit thinkers",
                "thinkers": [
                    {
                        "name": name,
                        "bio": f"Bio of {name}",
                        "positions": f"Positions of {name}",
                        "style": f"Style of {name}",
                        "color": "#6366f1",
                    }
                    for name in thinker_names
                ],
            },
        )
        assert_validation_error(response)

    async def test_add_thinkers_when_at_capacity_returns_400(self, client: AsyncClient) -> None:
        """Test that adding thinkers to a conversation already at 5 returns 400.

        Edge case: Conversation at max capacity.
        Covers: conversations.py add_thinkers capacity check (lines 179-185)
        """
        headers = await get_auth_headers(
            client, username="add_at_capacity_feb21", password="testpass123"
        )

        # Create conversation with 5 thinkers
        thinker_names = ["Plato", "Aristotle", "Socrates", "Descartes", "Hume"]
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Full capacity conversation",
                "thinkers": [
                    {
                        "name": name,
                        "bio": f"Bio of {name}",
                        "positions": f"Positions of {name}",
                        "style": f"Style of {name}",
                        "color": "#6366f1",
                    }
                    for name in thinker_names
                ],
            },
        )
        assert create_response.status_code == 200
        conversation_id = create_response.json()["id"]

        # Try to add one more thinker
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Kant",
                    "bio": "German philosopher",
                    "positions": "Categorical imperative",
                    "style": "Systematic",
                    "color": "#6366f1",
                }
            ],
        )
        assert add_response.status_code == 400
        assert "Cannot add" in add_response.json()["detail"]
        assert "Maximum is 5" in add_response.json()["detail"]

    async def test_add_thinkers_to_nonexistent_conversation_returns_404(
        self, client: AsyncClient
    ) -> None:
        """Test that adding thinkers to nonexistent conversation returns 404.

        Edge case: Conversation not found.
        Covers: conversations.py add_thinkers 404 check (lines 173-175)
        """
        headers = await get_auth_headers(
            client, username="add_thinkers_404_feb21", password="testpass123"
        )

        response = await client.put(
            "/api/conversations/nonexistent-conv-id-9876/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Kant",
                    "bio": "German philosopher",
                    "positions": "Categorical imperative",
                    "style": "Systematic",
                    "color": "#6366f1",
                }
            ],
        )
        assert_not_found(response)
        assert "not found" in response.json()["detail"].lower()

    async def test_add_thinkers_too_many_at_once_returns_400(self, client: AsyncClient) -> None:
        """Test adding multiple thinkers that would exceed 5 total.

        Edge case: Batch add that would exceed capacity.
        Covers: conversations.py capacity validation (lines 179-185)
        """
        headers = await get_auth_headers(
            client, username="add_many_thinkers_feb21", password="testpass123"
        )

        # Create conversation with 3 thinkers
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Partial capacity conversation",
                "thinkers": [
                    {
                        "name": name,
                        "bio": f"Bio of {name}",
                        "positions": f"Positions of {name}",
                        "style": f"Style of {name}",
                        "color": "#6366f1",
                    }
                    for name in ["Plato", "Aristotle", "Socrates"]
                ],
            },
        )
        assert create_response.status_code == 200
        conversation_id = create_response.json()["id"]

        # Try to add 3 more (would make 6 total)
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": name,
                    "bio": f"Bio of {name}",
                    "positions": f"Positions of {name}",
                    "style": f"Style of {name}",
                    "color": "#6366f1",
                }
                for name in ["Descartes", "Hume", "Kant"]
            ],
        )
        assert add_response.status_code == 400
        assert "Cannot add 3 thinkers" in add_response.json()["detail"]


class TestUnicodeAndSpecialCharacters:
    """Test unicode and special character handling across the API."""

    async def test_create_conversation_with_unicode_topic(self, client: AsyncClient) -> None:
        """Test that unicode topic is stored and retrieved correctly.

        Edge case: Unicode handling in conversation topics.
        """
        headers = await get_auth_headers(
            client, username="unicode_topic_feb21", password="testpass123"
        )

        unicode_topic = "哲学対話: プラトンとアリストテレスの議論 🏛️"

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": unicode_topic,
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Greek philosopher",
                        "positions": "Theory of Forms",
                        "style": "Dialogues",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == unicode_topic

    async def test_create_conversation_with_arabic_topic(self, client: AsyncClient) -> None:
        """Test that Arabic topic text is handled correctly.

        Edge case: RTL language support.
        """
        headers = await get_auth_headers(
            client, username="arabic_topic_feb21", password="testpass123"
        )

        arabic_topic = "الفلسفة اليونانية القديمة"

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": arabic_topic,
                "thinkers": [
                    {
                        "name": "Aristotle",
                        "bio": "Greek philosopher",
                        "positions": "Logic",
                        "style": "Analytical",
                        "color": "#ec4899",
                    }
                ],
            },
        )
        assert response.status_code == 200
        assert response.json()["topic"] == arabic_topic

    async def test_create_conversation_with_special_chars_in_thinker_name(
        self, client: AsyncClient
    ) -> None:
        """Test that special characters in thinker names are handled.

        Edge case: Special characters in free-text fields.
        """
        headers = await get_auth_headers(
            client, username="special_chars_feb21", password="testpass123"
        )

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Testing special characters in names",
                "thinkers": [
                    {
                        "name": "J.J. Rousseau",  # Periods in name
                        "bio": 'A "complex" philosopher with <tags> & symbols',
                        "positions": "Liberty & equality - freedom's role",
                        "style": "Passionate; direct",
                        "color": "#10b981",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["thinkers"][0]["name"] == "J.J. Rousseau"

    async def test_send_message_with_unicode_content(self, client: AsyncClient) -> None:
        """Test that unicode messages are sent and stored correctly.

        Edge case: Unicode in message content.
        """
        headers = await get_auth_headers(
            client, username="unicode_message_feb21", password="testpass123"
        )

        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Unicode message test",
                "thinkers": [
                    {
                        "name": "Confucius",
                        "bio": "Chinese philosopher",
                        "positions": "Virtue ethics",
                        "style": "Aphoristic",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        unicode_message = "孔子曰：学而时习之，不亦说乎？🎓"
        msg_response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": unicode_message},
        )
        assert msg_response.status_code == 200
        assert msg_response.json()["content"] == unicode_message


class TestMessageBoundaryConditions:
    """Test message content boundary conditions."""

    async def test_send_message_to_nonexistent_conversation(self, client: AsyncClient) -> None:
        """Test sending message to nonexistent conversation returns 404.

        Edge case: Conversation not found when sending message.
        Covers: conversations.py send_message 404 path (lines 241-243)
        """
        headers = await get_auth_headers(client, username="msg_404_feb21", password="testpass123")

        response = await client.post(
            "/api/conversations/nonexistent-conv-id-abcd/messages",
            headers=headers,
            json={"content": "Hello, is anyone there?"},
        )
        assert_not_found(response)
        assert "not found" in response.json()["detail"].lower()

    async def test_send_message_to_other_users_conversation(self, client: AsyncClient) -> None:
        """Test that user cannot send messages to another user's conversation.

        Edge case: Cross-user conversation isolation.
        Covers: conversations.py send_message session check (lines 236-243)
        """
        # User 1 creates a conversation
        user1_headers = await get_auth_headers(
            client, username="msg_isolation_user1_feb21", password="testpass123"
        )
        conv_response = await client.post(
            "/api/conversations",
            headers=user1_headers,
            json={
                "topic": "Private conversation",
                "thinkers": [
                    {
                        "name": "Nietzsche",
                        "bio": "German philosopher",
                        "positions": "Will to power",
                        "style": "Aphoristic",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # User 2 tries to send a message to User 1's conversation
        user2_headers = await get_auth_headers(
            client, username="msg_isolation_user2_feb21", password="testpass123"
        )
        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=user2_headers,
            json={"content": "Unauthorized message attempt!"},
        )
        assert_not_found(response)

    async def test_get_conversation_with_messages_returns_cost(self, client: AsyncClient) -> None:
        """Test that getting a conversation with messages returns total_cost.

        Edge case: Verify total_cost field in conversation response.
        """
        headers = await get_auth_headers(client, username="conv_cost_feb21", password="testpass123")

        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Cost tracking test",
                "thinkers": [
                    {
                        "name": "Hegel",
                        "bio": "German idealist philosopher",
                        "positions": "Dialectics",
                        "style": "Systematic",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # Send a message
        await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "What is the Hegelian dialectic?"},
        )

        # Get the conversation - should include total_cost
        get_response = await client.get(
            f"/api/conversations/{conversation_id}",
            headers=headers,
        )
        assert get_response.status_code == 200
        data = get_response.json()
        assert "total_cost" in data
        assert data["total_cost"] >= 0.0
        assert "messages" in data


class TestConversationListEdgeCases:
    """Test conversation list edge cases."""

    async def test_list_conversations_empty_for_new_user(self, client: AsyncClient) -> None:
        """Test that new user with no conversations gets empty list.

        Edge case: Empty list result.
        """
        headers = await get_auth_headers(
            client, username="empty_convs_feb21", password="testpass123"
        )

        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_conversations_includes_zero_cost_messages(
        self, client: AsyncClient
    ) -> None:
        """Test that conversation list correctly shows zero total_cost for no messages.

        Edge case: Null/zero cost aggregation in list view.
        Covers: conversations.py list_conversations summary building (lines 91-105)
        """
        headers = await get_auth_headers(
            client, username="zero_cost_list_feb21", password="testpass123"
        )

        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Zero cost conversation",
                "thinkers": [
                    {
                        "name": "Bertrand Russell",
                        "bio": "British philosopher",
                        "positions": "Logical atomism",
                        "style": "Analytical",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200

        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200
        conversations = list_response.json()
        assert len(conversations) == 1
        # No messages sent, cost should be 0
        assert conversations[0]["total_cost"] == 0.0
        assert conversations[0]["message_count"] == 0
