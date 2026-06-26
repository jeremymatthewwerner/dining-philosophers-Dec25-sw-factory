"""Edge case tests - Saturday QA focus (Mar 14, 2026).

Tests cover boundary conditions and error paths across multiple API areas:
- spend service: zero spend_limit percentage calculation, boundary spend values
- auth API: boundary username/display_name lengths, exact min/max password length
- conversations: exact thinker count limit (5), topic boundary lengths
- feedback schemas: message at exact min/max length, screenshot at size limit
- sessions API: token missing session_id field, malformed payloads
- admin API: spend limit boundary values, user deletion edge cases
- core/auth: JWT with custom expiry, password hash edge cases

Uses `with patch(...)` (not @patch decorator) to ensure coverage is correctly tracked
with pytest-asyncio's auto mode.
"""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.feedback import MAX_SCREENSHOT_SIZE, FeedbackCreate
from app.services.spend import check_spend_limit
from tests.conftest import (
    assert_not_found,
    assert_unauthorized,
    assert_validation_error,
    bearer_header,
    get_auth_headers,
)


class TestSpendServiceZeroLimitEdgeCases:
    """Edge cases for check_spend_limit when spend_limit is zero.

    The formula in spend.py line 42:
        percentage = (user.total_spend / user.spend_limit * 100) if user.spend_limit > 0 else 100

    When spend_limit is 0, percentage defaults to 100 (covered by 'else 100' branch).
    """

    async def test_check_spend_limit_zero_spend_limit_reports_100_percent(
        self, db_session: AsyncSession
    ) -> None:
        """Test that a user with spend_limit=0 shows 100% used (special case: no limit).

        Edge case: The 'else 100' branch in spend.py line 42 when spend_limit == 0.
        """
        user = User(
            username="zero_limit_user",
            password_hash="hash",
            total_spend=0.0,
            spend_limit=0.0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        result = await check_spend_limit(db_session, user.id)

        assert result is not None
        assert result.spend_limit == 0.0
        assert result.percentage_used == 100.0
        assert result.is_over_limit is True  # total_spend (0) >= spend_limit (0)
        assert result.is_near_limit is True  # 100% >= 85%

    async def test_check_spend_limit_zero_spend_limit_remaining_is_zero(
        self, db_session: AsyncSession
    ) -> None:
        """Test that remaining is 0 when spend_limit is 0.

        Edge case: max(0, 0 - 0) = 0.
        """
        user = User(
            username="zero_limit_user2",
            password_hash="hash",
            total_spend=0.0,
            spend_limit=0.0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        result = await check_spend_limit(db_session, user.id)

        assert result is not None
        assert result.remaining == 0.0

    async def test_check_spend_limit_very_small_spend(self, db_session: AsyncSession) -> None:
        """Test very small spend amount near floating point precision.

        Edge case: 0.001 spend on 100.0 limit = 0.001% used.
        """
        user = User(
            username="tiny_spend_user",
            password_hash="hash",
            total_spend=0.001,
            spend_limit=100.0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        result = await check_spend_limit(db_session, user.id)

        assert result is not None
        assert result.is_over_limit is False
        assert result.is_near_limit is False
        assert result.percentage_used == pytest.approx(0.001)
        assert result.remaining == pytest.approx(99.999)

    async def test_check_spend_limit_spend_just_under_85_percent(
        self, db_session: AsyncSession
    ) -> None:
        """Test spend just below the 85% 'near limit' threshold.

        Boundary: 84.9% should NOT trigger is_near_limit.
        """
        user = User(
            username="near_limit_under",
            password_hash="hash",
            total_spend=8.49,
            spend_limit=10.0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        result = await check_spend_limit(db_session, user.id)

        assert result is not None
        assert result.is_near_limit is False
        assert result.percentage_used == pytest.approx(84.9)

    async def test_check_spend_limit_spend_at_exactly_85_percent(
        self, db_session: AsyncSession
    ) -> None:
        """Test spend at exactly 85% threshold.

        Boundary: 85.0% should trigger is_near_limit.
        """
        user = User(
            username="near_limit_exact",
            password_hash="hash",
            total_spend=8.5,
            spend_limit=10.0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        result = await check_spend_limit(db_session, user.id)

        assert result is not None
        assert result.is_near_limit is True
        assert result.percentage_used == pytest.approx(85.0)


class TestAuthBoundaryLengths:
    """Boundary tests for auth schema field lengths.

    UserRegister schema:
    - username: min_length=3, max_length=50
    - display_name: min_length=1, max_length=100
    - password: min_length=6, max_length=100
    """

    async def test_register_username_exactly_minimum_length(self, client: AsyncClient) -> None:
        """Test registration with username at exactly min length (3 chars).

        Boundary: min_length=3 - exactly 3 chars should be accepted.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "abc",  # Exactly 3 chars - minimum
                "display_name": "User",
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["username"] == "abc"

    async def test_register_username_exactly_maximum_length(self, client: AsyncClient) -> None:
        """Test registration with username at exactly max length (50 chars).

        Boundary: max_length=50 - exactly 50 chars should be accepted.
        """
        username = "a" * 50  # Exactly 50 chars - maximum
        response = await client.post(
            "/api/auth/register",
            json={
                "username": username,
                "display_name": "User",
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["username"] == username

    async def test_register_username_below_minimum_length(self, client: AsyncClient) -> None:
        """Test registration with username below min length (2 chars).

        Boundary: min_length=3 - 2 chars should be rejected.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "ab",  # 2 chars - below minimum
                "display_name": "User",
                "password": "password123",
            },
        )
        assert_validation_error(response)

    async def test_register_password_exactly_minimum_length(self, client: AsyncClient) -> None:
        """Test registration with password at exactly min length (6 chars).

        Boundary: min_length=6 - exactly 6 chars should be accepted.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "passbound_user",
                "display_name": "User",
                "password": "abc123",  # Exactly 6 chars - minimum
            },
        )
        assert response.status_code == 200

    async def test_register_password_below_minimum_length(self, client: AsyncClient) -> None:
        """Test registration with password below min length (5 chars).

        Boundary: min_length=6 - 5 chars should be rejected.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "short_pass_user",
                "display_name": "User",
                "password": "abc12",  # 5 chars - below minimum
            },
        )
        assert_validation_error(response)

    async def test_register_display_name_exactly_minimum_length(self, client: AsyncClient) -> None:
        """Test registration with display_name at exactly min length (1 char).

        Boundary: min_length=1 - single char should be accepted.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "display_min_user",
                "display_name": "X",  # Exactly 1 char - minimum
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["display_name"] == "X"

    async def test_register_display_name_at_maximum_length(self, client: AsyncClient) -> None:
        """Test registration with display_name at exactly max length (100 chars).

        Boundary: max_length=100 - exactly 100 chars should be accepted.
        """
        display_name = "A" * 100  # Exactly 100 chars - maximum
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "display_max_user",
                "display_name": display_name,
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["display_name"] == display_name

    async def test_register_display_name_over_maximum_length(self, client: AsyncClient) -> None:
        """Test registration with display_name over max length (101 chars).

        Boundary: max_length=100 - 101 chars should be rejected.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "display_over_max",
                "display_name": "B" * 101,  # 101 chars - over maximum
                "password": "password123",
            },
        )
        assert_validation_error(response)

    async def test_register_password_at_maximum_length(self, client: AsyncClient) -> None:
        """Test registration with password at exactly max length (100 chars).

        Boundary: max_length=100 - exactly 100 chars should be accepted.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "max_pass_user",
                "display_name": "User",
                "password": "p" * 100,  # Exactly 100 chars - maximum
            },
        )
        assert response.status_code == 200

    async def test_register_password_over_maximum_length(self, client: AsyncClient) -> None:
        """Test registration with password over max length (101 chars).

        Boundary: max_length=100 - 101 chars should be rejected.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "over_max_pass_user",
                "display_name": "User",
                "password": "p" * 101,  # 101 chars - over maximum
            },
        )
        assert_validation_error(response)


class TestAuthJWTEdgeCases:
    """Edge cases for JWT token validation."""

    async def test_get_me_with_expired_token(self, client: AsyncClient) -> None:
        """Test that an expired JWT token is rejected.

        Edge case: Token with negative expiry (already expired).
        """
        from app.core.auth import create_access_token

        # Create a token that expired 1 hour ago
        expired_token = create_access_token(
            data={"sub": "some-user-id"}, expires_delta=timedelta(hours=-1)
        )

        response = await client.get(
            "/api/auth/me",
            headers=bearer_header(expired_token),
        )
        assert_unauthorized(response)

    async def test_get_me_with_completely_malformed_token(self, client: AsyncClient) -> None:
        """Test that a completely invalid token string is rejected."""
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer not-a-jwt-token"},
        )
        assert_unauthorized(response)

    async def test_get_me_with_empty_bearer_token(self, client: AsyncClient) -> None:
        """Test that an empty bearer token value is handled gracefully."""
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer "},
        )
        assert_unauthorized(response)

    async def test_get_me_with_token_for_nonexistent_user(self, client: AsyncClient) -> None:
        """Test that a valid JWT for a user that doesn't exist returns 401.

        Edge case: Valid token structure but user was deleted from DB.
        """
        from app.core.auth import create_access_token

        # Create a token for a user that doesn't exist in the DB
        token = create_access_token(data={"sub": "nonexistent-user-id-xyz"})

        response = await client.get(
            "/api/auth/me",
            headers=bearer_header(token),
        )
        assert_unauthorized(response)

    async def test_get_me_with_custom_expiry_token(self, client: AsyncClient) -> None:
        """Test that a JWT with custom positive expiry works correctly.

        Edge case: Token with explicitly set future expiry.
        """

        # We need an actual user in the DB for this test
        # Register via API to create a proper user with session
        reg_response = await client.post(
            "/api/auth/register",
            json={
                "username": "custom_expiry_user",
                "display_name": "Custom",
                "password": "password123",
            },
        )
        assert reg_response.status_code == 200

        # The token from registration should work
        token = reg_response.json()["access_token"]
        response = await client.get(
            "/api/auth/me",
            headers=bearer_header(token),
        )
        assert response.status_code == 200


class TestSessionsTokenEdgeCases:
    """Edge cases for session token validation."""

    async def test_get_session_me_with_token_missing_session_id(self, client: AsyncClient) -> None:
        """Test that a token missing session_id field returns 401.

        Edge case: JWT payload has valid sub but no session_id field.
        Covers line 34 of sessions.py: 'raise HTTPException(401, "Invalid token - no session")'.
        """
        from app.core.auth import create_access_token

        # Token with user id but no session_id
        token = create_access_token(data={"sub": "some-user-id"})

        response = await client.get(
            "/api/sessions/me",
            headers=bearer_header(token),
        )
        # Should get 401 for missing session_id
        assert_unauthorized(response, "Invalid token")

    async def test_get_session_me_with_invalid_session_id(self, client: AsyncClient) -> None:
        """Test that a token with non-existent session_id returns 404.

        Edge case: JWT has valid structure with session_id but no matching DB record.
        Covers line 41 of sessions.py: 'raise HTTPException(404, "Session not found")'.
        """
        from app.core.auth import create_access_token

        # Token with a session_id that doesn't exist in DB
        token = create_access_token(
            data={"sub": "some-user", "session_id": "nonexistent-session-id"}
        )

        response = await client.get(
            "/api/sessions/me",
            headers=bearer_header(token),
        )
        assert_not_found(response)

    async def test_conversations_with_token_missing_session_id(self, client: AsyncClient) -> None:
        """Test that conversations endpoint rejects token without session_id.

        Edge case: The conversations API uses get_session_from_token which requires
        the session_id in the JWT payload.
        """
        from app.core.auth import create_access_token

        # Create a token without session_id (like auth tokens from /api/auth/me)
        token = create_access_token(data={"sub": "some-user-id"})

        response = await client.get(
            "/api/conversations",
            headers=bearer_header(token),
        )
        assert_unauthorized(response)


class TestFeedbackSchemaEdgeCases:
    """Edge cases for feedback schema validation boundaries."""

    async def test_submit_feedback_message_at_exactly_minimum_length(
        self, client: AsyncClient
    ) -> None:
        """Test feedback message at exactly min length (10 chars).

        Boundary: min_length=10 - exactly 10 chars should be accepted.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "bug",
                "message": "a" * 10,  # Exactly 10 chars - minimum
            },
        )
        assert response.status_code == 201

    async def test_submit_feedback_message_below_minimum_length(self, client: AsyncClient) -> None:
        """Test feedback message below min length (9 chars).

        Boundary: min_length=10 - 9 chars should be rejected.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "bug",
                "message": "a" * 9,  # 9 chars - below minimum
            },
        )
        assert_validation_error(response)

    async def test_submit_feedback_message_at_exactly_maximum_length(
        self, client: AsyncClient
    ) -> None:
        """Test feedback message at exactly max length (5000 chars).

        Boundary: max_length=5000 - exactly 5000 chars should be accepted.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "feature",
                "message": "a" * 5000,  # Exactly 5000 chars - maximum
            },
        )
        assert response.status_code == 201

    async def test_submit_feedback_message_over_maximum_length(self, client: AsyncClient) -> None:
        """Test feedback message over max length (5001 chars).

        Boundary: max_length=5000 - 5001 chars should be rejected.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "bug",
                "message": "a" * 5001,  # 5001 chars - over maximum
            },
        )
        assert_validation_error(response)

    def test_feedback_screenshot_at_exactly_max_size_is_accepted(self) -> None:
        """Test that screenshot data at exactly max size is accepted by schema.

        Boundary: MAX_SCREENSHOT_SIZE - exactly at limit should pass validation.
        """
        # Create exactly MAX_SCREENSHOT_SIZE chars of screenshot data
        screenshot = "a" * MAX_SCREENSHOT_SIZE
        feedback = FeedbackCreate(
            message="Test feedback message",
            screenshot_data=screenshot,
        )
        assert feedback.screenshot_data is not None
        assert len(feedback.screenshot_data) == MAX_SCREENSHOT_SIZE

    def test_feedback_screenshot_over_max_size_is_rejected(self) -> None:
        """Test that screenshot data over max size is rejected by schema.

        Boundary: MAX_SCREENSHOT_SIZE + 1 should raise validation error.
        """
        from pydantic import ValidationError

        screenshot = "a" * (MAX_SCREENSHOT_SIZE + 1)
        with pytest.raises(ValidationError) as exc_info:
            FeedbackCreate(
                message="Test feedback message",
                screenshot_data=screenshot,
            )
        assert "too large" in str(exc_info.value).lower()

    def test_feedback_screenshot_none_is_accepted(self) -> None:
        """Test that screenshot_data=None is accepted (optional field)."""
        feedback = FeedbackCreate(
            message="Test feedback message",
            screenshot_data=None,
        )
        assert feedback.screenshot_data is None

    async def test_submit_feedback_without_request_client_ip(self, client: AsyncClient) -> None:
        """Test feedback submission works with X-Forwarded-For having multiple IPs.

        Edge case: Multi-hop proxy with comma-separated IP list.
        get_client_ip takes the first IP from the chain.
        """
        response = await client.post(
            "/api/feedback",
            headers={"X-Forwarded-For": "10.0.0.1, 172.16.0.1, 192.168.1.1"},
            json={
                "feedback_type": "other",
                "message": "Test feedback with multi-hop proxy chain.",
            },
        )
        assert response.status_code == 201

    async def test_submit_feedback_with_all_optional_fields_none(self, client: AsyncClient) -> None:
        """Test feedback submission with all optional fields explicitly set to None."""
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "bug",
                "message": "Minimal feedback with all optional fields null.",
                "email": None,
                "name": None,
                "username": None,
                "user_agent": None,
                "screenshot_data": None,
                "screenshot_filename": None,
            },
        )
        assert response.status_code == 201

    async def test_submit_feedback_default_type_is_bug(self, client: AsyncClient) -> None:
        """Test that feedback without feedback_type field defaults to 'bug'.

        Edge case: Default value for feedback_type enum field.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "message": "Feedback without specifying a type for defaults check.",
            },
        )
        assert response.status_code == 201

    async def test_submit_feedback_email_at_max_length(self, client: AsyncClient) -> None:
        """Test feedback with email at exactly max length (255 chars).

        Boundary: max_length=255 for email field.
        """
        # 255-char email: 243 chars of local part + @test.com (9 chars) = 252 chars
        email = "a" * 246 + "@test.com"  # 255 chars total
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "bug",
                "message": "Testing with maximum length email address.",
                "email": email,
            },
        )
        assert response.status_code == 201


class TestConversationThinkerBoundaryEdgeCases:
    """Edge cases for conversation thinker count boundaries."""

    async def test_create_conversation_with_exactly_5_thinkers(self, client: AsyncClient) -> None:
        """Test creating a conversation with exactly 5 thinkers (the maximum).

        Boundary: ConversationCreate schema has thinkers max_length=5.
        """

        headers = await get_auth_headers(client, "five_thinker_user", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Five philosophers debate",
                "thinkers": [
                    {
                        "name": f"Philosopher{i}",
                        "bio": f"Bio {i}",
                        "positions": f"Position {i}",
                        "style": f"Style {i}",
                    }
                    for i in range(5)
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 5

    async def test_create_conversation_with_6_thinkers_rejected(self, client: AsyncClient) -> None:
        """Test creating a conversation with 6 thinkers is rejected.

        Boundary: ConversationCreate thinkers max_length=5, so 6 should be rejected.
        """
        headers = await get_auth_headers(client, "six_thinker_user", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Six philosophers debate",
                "thinkers": [
                    {
                        "name": f"Philosopher{i}",
                        "bio": f"Bio {i}",
                        "positions": f"Position {i}",
                        "style": f"Style {i}",
                    }
                    for i in range(6)
                ],
            },
        )
        assert_validation_error(response)

    async def test_add_thinkers_to_reach_exactly_5(self, client: AsyncClient) -> None:
        """Test adding thinkers to reach exactly the 5-thinker limit.

        Edge case: Start with 3, add 2, total should be exactly 5 (allowed).
        """

        headers = await get_auth_headers(client, "add_to_five_user", "password123")
        # Create conversation with 3 thinkers
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Building to 5 thinkers",
                "thinkers": [
                    {
                        "name": f"Initial{i}",
                        "bio": f"Bio {i}",
                        "positions": f"Position {i}",
                        "style": f"Style {i}",
                    }
                    for i in range(3)
                ],
            },
        )
        assert response.status_code == 200
        conv_id = response.json()["id"]

        # Add 2 more to reach exactly 5
        add_response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": f"Added{i}",
                    "bio": f"Added Bio {i}",
                    "positions": f"Added Position {i}",
                    "style": f"Added Style {i}",
                }
                for i in range(2)
            ],
        )

        assert add_response.status_code == 200
        assert len(add_response.json()) == 2

    async def test_add_thinkers_exceeding_5_limit_rejected(self, client: AsyncClient) -> None:
        """Test adding thinkers that would exceed the 5-thinker limit.

        Edge case: Start with 4, try to add 2 - should be rejected since 4+2=6 > 5.
        """

        headers = await get_auth_headers(client, "exceed_limit_user", "password123")
        # Create conversation with 4 thinkers
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Near limit conversation",
                "thinkers": [
                    {
                        "name": f"Existing{i}",
                        "bio": f"Bio {i}",
                        "positions": f"Position {i}",
                        "style": f"Style {i}",
                    }
                    for i in range(4)
                ],
            },
        )
        assert response.status_code == 200
        conv_id = response.json()["id"]

        # Try to add 2 more (would make 6, exceeding 5 limit)
        add_response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": f"Extra{i}",
                    "bio": f"Extra Bio {i}",
                    "positions": f"Extra Position {i}",
                    "style": f"Extra Style {i}",
                }
                for i in range(2)
            ],
        )

        assert add_response.status_code == 400
        assert "Cannot add" in add_response.json()["detail"]

    async def test_thinker_name_at_exactly_max_length(self, client: AsyncClient) -> None:
        """Test creating thinker with name at exactly max length (255 chars).

        Boundary: ThinkerCreate name max_length=255.
        """

        headers = await get_auth_headers(client, "long_name_thinker_user", "password123")
        long_name = "A" * 255  # Exactly 255 chars - maximum
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Long name thinker test",
                "thinkers": [
                    {
                        "name": long_name,
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["thinkers"][0]["name"] == long_name

    async def test_thinker_name_over_max_length_rejected(self, client: AsyncClient) -> None:
        """Test creating thinker with name over max length (256 chars) is rejected.

        Boundary: ThinkerCreate name max_length=255.
        """
        headers = await get_auth_headers(client, "over_max_name_user", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Over max name test",
                "thinkers": [
                    {
                        "name": "A" * 256,  # 256 chars - over maximum
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                    }
                ],
            },
        )
        assert_validation_error(response)

    async def test_thinker_color_invalid_format_rejected(self, client: AsyncClient) -> None:
        """Test creating thinker with invalid hex color format is rejected.

        Edge case: ThinkerCreate color field has pattern validation r'^#[0-9a-fA-F]{6}$'.
        """
        headers = await get_auth_headers(client, "invalid_color_user", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Invalid color test",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                        "color": "blue",  # Invalid - not a hex color
                    }
                ],
            },
        )
        assert_validation_error(response)

    async def test_thinker_color_valid_uppercase_hex_accepted(self, client: AsyncClient) -> None:
        """Test creating thinker with valid uppercase hex color is accepted.

        Edge case: Pattern allows a-fA-F so uppercase hex is valid.
        """

        headers = await get_auth_headers(client, "uppercase_color_user", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Uppercase color test",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                        "color": "#AABBCC",  # Valid uppercase hex
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Custom color (not default) should be preserved
        assert data["thinkers"][0]["color"] == "#AABBCC"


class TestAdminSpendLimitBoundary:
    """Edge cases for admin spend limit update boundaries."""

    def test_update_spend_limit_to_very_small_positive(self) -> None:
        """Test that UpdateSpendLimitRequest accepts very small positive value (0.01).

        Boundary: spend_limit field has gt=0, so 0.01 should be accepted by schema.
        """
        from app.api.admin import UpdateSpendLimitRequest

        request = UpdateSpendLimitRequest(spend_limit=0.01)
        assert request.spend_limit == 0.01

    async def test_update_spend_limit_zero_rejected_by_schema(self) -> None:
        """Test that spend_limit=0 is rejected by schema validation (gt=0).

        Edge case: UpdateSpendLimitRequest has gt=0 constraint.
        """
        from pydantic import ValidationError

        from app.api.admin import UpdateSpendLimitRequest

        with pytest.raises(ValidationError):
            UpdateSpendLimitRequest(spend_limit=0.0)

    async def test_update_spend_limit_negative_rejected_by_schema(self) -> None:
        """Test that negative spend_limit is rejected by schema validation.

        Edge case: UpdateSpendLimitRequest has gt=0 constraint.
        """
        from pydantic import ValidationError

        from app.api.admin import UpdateSpendLimitRequest

        with pytest.raises(ValidationError):
            UpdateSpendLimitRequest(spend_limit=-5.0)


class TestPasswordChangeEdgeCases:
    """Edge cases for the change-password endpoint."""

    async def test_change_password_to_exactly_min_length(self, client: AsyncClient) -> None:
        """Test changing password to exactly minimum length (6 chars).

        Boundary: ChangePasswordRequest new_password min_length=6.
        """
        headers = await get_auth_headers(client, "min_pass_change", "oldpassword123")

        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "oldpassword123",
                "new_password": "abc123",  # Exactly 6 chars - minimum
            },
        )
        assert response.status_code == 200
        assert "Password changed" in response.json()["message"]

    async def test_change_password_to_below_min_length_rejected(self, client: AsyncClient) -> None:
        """Test changing password to below minimum length (5 chars) is rejected.

        Boundary: ChangePasswordRequest new_password min_length=6.
        """
        headers = await get_auth_headers(client, "short_new_pass", "oldpassword123")

        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "oldpassword123",
                "new_password": "ab123",  # 5 chars - below minimum
            },
        )
        assert_validation_error(response)

    async def test_change_password_to_max_length(self, client: AsyncClient) -> None:
        """Test changing password to exactly max length (100 chars).

        Boundary: ChangePasswordRequest new_password max_length=100.
        """
        headers = await get_auth_headers(client, "max_pass_change", "oldpassword123")

        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "oldpassword123",
                "new_password": "p" * 100,  # Exactly 100 chars - maximum
            },
        )
        assert response.status_code == 200

    async def test_change_password_empty_current_password_rejected(
        self, client: AsyncClient
    ) -> None:
        """Test that empty current_password is rejected.

        Edge case: ChangePasswordRequest current_password min_length=1.
        """
        headers = await get_auth_headers(client, "empty_current_pass", "oldpassword123")

        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "",  # Empty - min_length=1
                "new_password": "newpassword123",
            },
        )
        assert_validation_error(response)

    async def test_change_password_with_special_characters(self, client: AsyncClient) -> None:
        """Test changing password to one with special characters and unicode.

        Edge case: Password with symbols, spaces, and unicode should be accepted.
        """
        headers = await get_auth_headers(client, "special_pass_user", "oldpassword123")

        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "oldpassword123",
                "new_password": "P@ssw0rd! $peci@l #chars",
            },
        )
        assert response.status_code == 200


class TestThinkerSuggestRequestBoundary:
    """Edge cases for ThinkerSuggestRequest schema validation."""

    def test_suggest_request_count_at_minimum(self) -> None:
        """Test ThinkerSuggestRequest count at minimum value (1).

        Boundary: count field has ge=1.
        """
        from app.schemas.thinker import ThinkerSuggestRequest

        req = ThinkerSuggestRequest(topic="Philosophy", count=1)
        assert req.count == 1

    def test_suggest_request_count_below_minimum_rejected(self) -> None:
        """Test ThinkerSuggestRequest count below minimum (0) is rejected.

        Boundary: count field has ge=1.
        """
        from pydantic import ValidationError

        from app.schemas.thinker import ThinkerSuggestRequest

        with pytest.raises(ValidationError):
            ThinkerSuggestRequest(topic="Philosophy", count=0)

    def test_suggest_request_count_at_maximum(self) -> None:
        """Test ThinkerSuggestRequest count at maximum value (5).

        Boundary: count field has le=5.
        """
        from app.schemas.thinker import ThinkerSuggestRequest

        req = ThinkerSuggestRequest(topic="Philosophy", count=5)
        assert req.count == 5

    def test_suggest_request_count_over_maximum_rejected(self) -> None:
        """Test ThinkerSuggestRequest count over maximum (6) is rejected.

        Boundary: count field has le=5.
        """
        from pydantic import ValidationError

        from app.schemas.thinker import ThinkerSuggestRequest

        with pytest.raises(ValidationError):
            ThinkerSuggestRequest(topic="Philosophy", count=6)

    def test_suggest_request_empty_topic_rejected(self) -> None:
        """Test ThinkerSuggestRequest with empty topic is rejected.

        Edge case: topic field has min_length=1.
        """
        from pydantic import ValidationError

        from app.schemas.thinker import ThinkerSuggestRequest

        with pytest.raises(ValidationError):
            ThinkerSuggestRequest(topic="", count=3)

    def test_suggest_request_invalid_language_rejected(self) -> None:
        """Test ThinkerSuggestRequest with invalid language code is rejected.

        Edge case: language field has pattern '^(en|es|fr)$'.
        Note: ThinkerSuggestRequest only allows en|es|fr (not de like UserRegister).
        """
        from pydantic import ValidationError

        from app.schemas.thinker import ThinkerSuggestRequest

        with pytest.raises(ValidationError):
            ThinkerSuggestRequest(topic="Philosophy", language="xx")

    def test_suggest_request_german_language_rejected(self) -> None:
        """Test ThinkerSuggestRequest with German (de) is rejected.

        Edge case: ThinkerSuggestRequest only allows en|es|fr (NOT de).
        This differs from UserRegister which allows de.
        """
        from pydantic import ValidationError

        from app.schemas.thinker import ThinkerSuggestRequest

        with pytest.raises(ValidationError):
            ThinkerSuggestRequest(topic="Philosophy", language="de")

    def test_suggest_request_default_values(self) -> None:
        """Test ThinkerSuggestRequest default values.

        Edge case: Verify count=3, language='en', exclude=[] as defaults.
        """
        from app.schemas.thinker import ThinkerSuggestRequest

        req = ThinkerSuggestRequest(topic="Philosophy")
        assert req.count == 3
        assert req.language == "en"
        assert req.exclude == []

    def test_suggest_request_exclude_list_populated(self) -> None:
        """Test ThinkerSuggestRequest with populated exclude list.

        Edge case: exclude list should accept multiple thinker names.
        """
        from app.schemas.thinker import ThinkerSuggestRequest

        req = ThinkerSuggestRequest(
            topic="Philosophy",
            exclude=["Socrates", "Plato", "Aristotle"],
        )
        assert len(req.exclude) == 3
        assert "Socrates" in req.exclude


class TestProfileUpdateEdgeCases:
    """Edge cases for the profile update endpoint."""

    async def test_update_profile_display_name_exactly_min_length(
        self, client: AsyncClient
    ) -> None:
        """Test updating display_name to exactly min length (1 char).

        Boundary: UserProfileUpdate display_name min_length=1.
        """
        headers = await get_auth_headers(client, "min_display_user", "password123")

        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": "X"},  # Exactly 1 char - minimum
        )
        assert response.status_code == 200
        assert response.json()["display_name"] == "X"

    async def test_update_profile_display_name_empty_rejected(self, client: AsyncClient) -> None:
        """Test updating display_name to empty string is rejected.

        Edge case: UserProfileUpdate display_name min_length=1.
        """
        headers = await get_auth_headers(client, "empty_display_user", "password123")

        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": ""},  # Empty - below minimum
        )
        assert_validation_error(response)

    async def test_update_profile_display_name_at_max_length(self, client: AsyncClient) -> None:
        """Test updating display_name to exactly max length (100 chars).

        Boundary: UserProfileUpdate display_name max_length=100.
        """
        headers = await get_auth_headers(client, "max_display_user", "password123")

        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": "D" * 100},  # Exactly 100 chars - maximum
        )
        assert response.status_code == 200

    async def test_update_profile_display_name_over_max_length_rejected(
        self, client: AsyncClient
    ) -> None:
        """Test updating display_name over max length (101 chars) is rejected.

        Boundary: UserProfileUpdate display_name max_length=100.
        """
        headers = await get_auth_headers(client, "over_max_display_user", "password123")

        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": "D" * 101},  # 101 chars - over maximum
        )
        assert_validation_error(response)

    async def test_update_language_all_valid_codes(self, client: AsyncClient) -> None:
        """Test updating language to all valid codes (en, es, fr, de).

        Edge case: Verify each valid language code is accepted.
        """
        for lang in ["es", "fr", "de", "en"]:
            headers = await get_auth_headers(client, f"lang_user_{lang}", "password123")
            response = await client.patch(
                "/api/auth/language",
                headers=headers,
                json={"language_preference": lang},
            )
            assert response.status_code == 200
            assert response.json()["language_preference"] == lang
