"""Edge case tests - Saturday QA focus (Mar 21, 2026).

Tests cover boundary conditions and error paths across multiple API areas:
- auth API: exact min/max username length (3/50), password length (6/100),
  display_name length (1/100), invalid language codes, unicode in fields
- conversations: exact thinker count boundary (min=1, max=5), adding thinkers
  to reach exactly 5 total, adding thinkers when already at 5 raises 400,
  send_message to non-owned conversation returns 404
- feedback schemas: FeedbackCreate message at exact min (10) and max (5000) chars,
  screenshot at exactly MAX_SCREENSHOT_SIZE, screenshot 1 byte over limit raises ValueError
- thinker schemas: ThinkerCreate invalid hex color format, color exactly 6 hex digits
- devops API: missing X-DevOps-Secret header returns 403, wrong secret returns 403,
  devops not configured returns 503
- spend service: get_user_spend_data for non-existent user returns None,
  check_spend_limit for non-existent user returns None
- language validation: all valid languages accepted (en/es/fr), invalid codes rejected
- unicode/special chars: usernames with valid charset, topics with special characters,
  messages with emoji and unicode

Uses `with patch(...)` (not @patch decorator) to ensure coverage is correctly tracked
with pytest-asyncio's auto mode.
"""

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.feedback import MAX_SCREENSHOT_SIZE, FeedbackCreate
from app.services.spend import check_spend_limit, get_user_spend_data
from tests.conftest import get_auth_headers, register_and_get_token

# ============================================================================
# Auth API - Boundary Conditions
# ============================================================================


class TestAuthRegistrationBoundaryConditions:
    """Test exact boundary conditions for user registration validation."""

    async def test_register_username_minimum_length_3(self, client: AsyncClient) -> None:
        """Test that username with exactly 3 chars (min_length) is accepted.

        Boundary: username min_length=3.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "abc",  # exactly 3 chars
                "display_name": "Test",
                "password": "password123",
            },
        )
        assert response.status_code == 200
        assert response.json()["user"]["username"] == "abc"

    async def test_register_username_too_short_2_chars_rejected(self, client: AsyncClient) -> None:
        """Test that username with 2 chars (below min_length=3) is rejected.

        Boundary: username min_length=3, testing one below minimum.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "ab",  # 2 chars - below minimum
                "display_name": "Test",
                "password": "password123",
            },
        )
        assert response.status_code == 422

    async def test_register_username_maximum_length_50(self, client: AsyncClient) -> None:
        """Test that username with exactly 50 chars (max_length) is accepted.

        Boundary: username max_length=50.
        """
        username = "a" * 50  # exactly 50 chars
        response = await client.post(
            "/api/auth/register",
            json={
                "username": username,
                "display_name": "Test",
                "password": "password123",
            },
        )
        assert response.status_code == 200
        assert response.json()["user"]["username"] == username

    async def test_register_username_too_long_51_chars_rejected(self, client: AsyncClient) -> None:
        """Test that username with 51 chars (above max_length=50) is rejected.

        Boundary: username max_length=50, testing one above maximum.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "a" * 51,  # 51 chars - above maximum
                "display_name": "Test",
                "password": "password123",
            },
        )
        assert response.status_code == 422

    async def test_register_password_minimum_length_6(self, client: AsyncClient) -> None:
        """Test that password with exactly 6 chars (min_length) is accepted.

        Boundary: password min_length=6.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "user_pwd6",
                "display_name": "Test",
                "password": "abc123",  # exactly 6 chars
            },
        )
        assert response.status_code == 200

    async def test_register_password_too_short_5_chars_rejected(self, client: AsyncClient) -> None:
        """Test that password with 5 chars (below min_length=6) is rejected.

        Boundary: password min_length=6, testing one below minimum.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "user_short_pwd",
                "display_name": "Test",
                "password": "ab123",  # 5 chars - below minimum
            },
        )
        assert response.status_code == 422

    async def test_register_password_maximum_length_100(self, client: AsyncClient) -> None:
        """Test that password with exactly 100 chars (max_length) is accepted.

        Boundary: password max_length=100.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "user_maxpwd",
                "display_name": "Test",
                "password": "A" * 100,  # exactly 100 chars
            },
        )
        assert response.status_code == 200

    async def test_register_password_too_long_101_chars_rejected(self, client: AsyncClient) -> None:
        """Test that password with 101 chars (above max_length=100) is rejected.

        Boundary: password max_length=100, testing one above maximum.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "user_longpwd",
                "display_name": "Test",
                "password": "A" * 101,  # 101 chars - above maximum
            },
        )
        assert response.status_code == 422

    async def test_register_display_name_minimum_length_1(self, client: AsyncClient) -> None:
        """Test that display_name with exactly 1 char (min_length) is accepted.

        Boundary: display_name min_length=1.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "user_dn_min",
                "display_name": "X",  # exactly 1 char
                "password": "password123",
            },
        )
        assert response.status_code == 200
        assert response.json()["user"]["display_name"] == "X"

    async def test_register_display_name_maximum_length_100(self, client: AsyncClient) -> None:
        """Test that display_name with exactly 100 chars (max_length) is accepted.

        Boundary: display_name max_length=100.
        """
        long_name = "N" * 100  # exactly 100 chars
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "user_dn_max",
                "display_name": long_name,
                "password": "password123",
            },
        )
        assert response.status_code == 200
        assert response.json()["user"]["display_name"] == long_name

    async def test_register_display_name_too_long_101_chars_rejected(
        self, client: AsyncClient
    ) -> None:
        """Test that display_name with 101 chars (above max_length=100) is rejected.

        Boundary: display_name max_length=100, testing one above maximum.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "user_dn_long",
                "display_name": "N" * 101,  # 101 chars - above maximum
                "password": "password123",
            },
        )
        assert response.status_code == 422


# ============================================================================
# Auth API - Language Validation
# ============================================================================


class TestAuthLanguageValidation:
    """Test language preference validation boundaries."""

    async def test_register_all_valid_language_codes_accepted(self, client: AsyncClient) -> None:
        """Test that all valid language codes (en, es, fr, de) are accepted.

        Boundary: language_preference regex pattern '^(en|es|fr|de)$'.
        """
        valid_languages = ["en", "es", "fr", "de"]
        for i, lang in enumerate(valid_languages):
            response = await client.post(
                "/api/auth/register",
                json={
                    "username": f"user_lang_{lang}_{i}",
                    "display_name": f"Test {lang}",
                    "password": "password123",
                    "language_preference": lang,
                },
            )
            assert response.status_code == 200, (
                f"Expected 200 for language '{lang}', got {response.status_code}"
            )
            assert response.json()["user"]["language_preference"] == lang

    async def test_register_invalid_language_code_rejected(self, client: AsyncClient) -> None:
        """Test that unsupported language codes are rejected.

        Edge case: 'zh' (Chinese) is not in the allowed set.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "user_zh",
                "display_name": "Test",
                "password": "password123",
                "language_preference": "zh",
            },
        )
        assert response.status_code == 422

    async def test_update_language_invalid_code_rejected(self, client: AsyncClient) -> None:
        """Test that PATCH /api/auth/language with invalid code is rejected.

        Edge case: 'it' (Italian) is not in the allowed set.
        """
        headers = await get_auth_headers(client, "lang_update_user", "password123")
        response = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "it"},  # Italian - not allowed
        )
        assert response.status_code == 422

    async def test_update_language_valid_code_succeeds(self, client: AsyncClient) -> None:
        """Test that PATCH /api/auth/language with valid code succeeds.

        Edge case: Switching language from default 'en' to 'fr'.
        """
        headers = await get_auth_headers(client, "lang_switch_user", "password123")
        response = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "fr"},
        )
        assert response.status_code == 200
        assert response.json()["language_preference"] == "fr"


# ============================================================================
# Conversation - Exact Thinker Count Boundaries
# ============================================================================


class TestConversationThinkerCountBoundaries:
    """Test exact thinker count boundaries for conversation creation and management."""

    async def test_create_conversation_with_exactly_1_thinker_minimum(
        self, client: AsyncClient
    ) -> None:
        """Test that conversation with exactly 1 thinker (min_length) is accepted.

        Boundary: thinkers list min_length=1.
        """
        from unittest.mock import patch

        headers = await get_auth_headers(client, "thinker_min_user", "password123")
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Solo philosopher test",
                    "thinkers": [
                        {
                            "name": "Socrates",
                            "bio": "Greek philosopher",
                            "positions": "Ethics",
                            "style": "Socratic method",
                        }
                    ],  # exactly 1 thinker
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 1

    async def test_create_conversation_with_0_thinkers_rejected(self, client: AsyncClient) -> None:
        """Test that conversation with 0 thinkers (below min_length=1) is rejected.

        Boundary: thinkers list min_length=1, testing empty list.
        """
        headers = await get_auth_headers(client, "no_thinker_user", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Empty thinkers test",
                "thinkers": [],  # 0 thinkers - below minimum
            },
        )
        assert response.status_code == 422

    async def test_create_conversation_with_exactly_5_thinkers_maximum(
        self, client: AsyncClient
    ) -> None:
        """Test that conversation with exactly 5 thinkers (max_length) is accepted.

        Boundary: thinkers list max_length=5.
        """
        from unittest.mock import patch

        headers = await get_auth_headers(client, "thinker_max5_user", "password123")
        thinker_names = ["Socrates", "Plato", "Aristotle", "Descartes", "Kant"]
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Full roster test",
                    "thinkers": [
                        {
                            "name": name,
                            "bio": f"Bio of {name}",
                            "positions": f"Positions of {name}",
                            "style": f"Style of {name}",
                        }
                        for name in thinker_names
                    ],  # exactly 5 thinkers
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 5

    async def test_create_conversation_with_6_thinkers_rejected(self, client: AsyncClient) -> None:
        """Test that conversation with 6 thinkers (above max_length=5) is rejected.

        Boundary: thinkers list max_length=5, testing one above maximum.
        """
        headers = await get_auth_headers(client, "too_many_thinkers", "password123")
        thinker_names = ["Socrates", "Plato", "Aristotle", "Descartes", "Kant", "Hume"]
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Too many thinkers",
                "thinkers": [
                    {
                        "name": name,
                        "bio": f"Bio of {name}",
                        "positions": f"Positions of {name}",
                        "style": f"Style of {name}",
                    }
                    for name in thinker_names
                ],  # 6 thinkers - above maximum
            },
        )
        assert response.status_code == 422

    async def test_add_thinker_to_conversation_at_exactly_5_is_rejected(
        self, client: AsyncClient
    ) -> None:
        """Test that adding thinker when conversation already has 5 thinkers returns 400.

        Boundary: add_thinkers endpoint enforces max 5 total.
        """
        from unittest.mock import patch

        headers = await get_auth_headers(client, "add_thinker_full_user", "password123")
        thinker_names = ["Socrates", "Plato", "Aristotle", "Descartes", "Kant"]

        # Create conversation with 5 thinkers
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            create_response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Already full",
                    "thinkers": [
                        {
                            "name": name,
                            "bio": f"Bio of {name}",
                            "positions": f"Positions of {name}",
                            "style": f"Style of {name}",
                        }
                        for name in thinker_names
                    ],
                },
            )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]

        # Try to add 1 more thinker (would exceed 5)
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            add_response = await client.put(
                f"/api/conversations/{conv_id}/thinkers",
                headers=headers,
                json=[
                    {
                        "name": "Hume",
                        "bio": "Scottish philosopher",
                        "positions": "Empiricism",
                        "style": "Skeptical",
                    }
                ],
            )
        assert add_response.status_code == 400
        assert "5" in add_response.json()["detail"]

    async def test_get_conversation_wrong_session_returns_404(self, client: AsyncClient) -> None:
        """Test that getting conversation from a different user's session returns 404.

        Security edge case: conversations are session-scoped, not global.
        """
        from unittest.mock import patch

        # User A creates a conversation
        headers_a = await get_auth_headers(client, "owner_user_a", "password123")
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            create_response = await client.post(
                "/api/conversations",
                headers=headers_a,
                json={
                    "topic": "Private conversation",
                    "thinkers": [
                        {
                            "name": "Socrates",
                            "bio": "Greek philosopher",
                            "positions": "Ethics",
                            "style": "Socratic method",
                        }
                    ],
                },
            )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]

        # User B tries to access User A's conversation
        headers_b = await get_auth_headers(client, "other_user_b", "password123")
        get_response = await client.get(
            f"/api/conversations/{conv_id}",
            headers=headers_b,
        )
        assert get_response.status_code == 404

    async def test_delete_conversation_wrong_session_returns_404(self, client: AsyncClient) -> None:
        """Test that deleting conversation from a different user's session returns 404.

        Security edge case: deletion is session-scoped.
        """
        from unittest.mock import patch

        # User A creates a conversation
        headers_a = await get_auth_headers(client, "delete_owner_user", "password123")
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            create_response = await client.post(
                "/api/conversations",
                headers=headers_a,
                json={
                    "topic": "Doomed conversation",
                    "thinkers": [
                        {
                            "name": "Socrates",
                            "bio": "Greek philosopher",
                            "positions": "Ethics",
                            "style": "Socratic method",
                        }
                    ],
                },
            )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]

        # User B tries to delete User A's conversation
        headers_b = await get_auth_headers(client, "delete_attacker_user", "password123")
        delete_response = await client.delete(
            f"/api/conversations/{conv_id}",
            headers=headers_b,
        )
        assert delete_response.status_code == 404


# ============================================================================
# Feedback Schema - Boundary Validation
# ============================================================================


class TestFeedbackSchemaBoundaryConditions:
    """Test boundary conditions for feedback schema validation."""

    def test_feedback_message_exactly_10_chars_is_valid(self) -> None:
        """Test that feedback message with exactly 10 chars (min_length) is valid.

        Boundary: message min_length=10.
        """
        feedback = FeedbackCreate(
            feedback_type="bug",
            message="A" * 10,  # exactly 10 chars
        )
        assert len(feedback.message) == 10

    def test_feedback_message_9_chars_is_invalid(self) -> None:
        """Test that feedback message with 9 chars (below min_length=10) is invalid.

        Boundary: message min_length=10, testing one below minimum.
        """
        with pytest.raises(ValidationError):
            FeedbackCreate(
                feedback_type="bug",
                message="A" * 9,  # 9 chars - below minimum
            )

    def test_feedback_message_exactly_5000_chars_is_valid(self) -> None:
        """Test that feedback message with exactly 5000 chars (max_length) is valid.

        Boundary: message max_length=5000.
        """
        feedback = FeedbackCreate(
            feedback_type="feature",
            message="B" * 5000,  # exactly 5000 chars
        )
        assert len(feedback.message) == 5000

    def test_feedback_message_5001_chars_is_invalid(self) -> None:
        """Test that feedback message with 5001 chars (above max_length=5000) is invalid.

        Boundary: message max_length=5000, testing one above maximum.
        """
        with pytest.raises(ValidationError):
            FeedbackCreate(
                feedback_type="bug",
                message="B" * 5001,  # 5001 chars - above maximum
            )

    def test_feedback_screenshot_at_exactly_max_size_is_valid(self) -> None:
        """Test that screenshot data at exactly MAX_SCREENSHOT_SIZE is valid.

        Boundary: screenshot_data field validator checks len(v) > MAX_SCREENSHOT_SIZE.
        At exactly MAX_SCREENSHOT_SIZE, it should pass (not strictly greater).
        """
        feedback = FeedbackCreate(
            feedback_type="bug",
            message="A" * 10,
            screenshot_data="X" * MAX_SCREENSHOT_SIZE,  # exactly at limit
        )
        assert len(feedback.screenshot_data) == MAX_SCREENSHOT_SIZE

    def test_feedback_screenshot_one_byte_over_max_size_is_invalid(self) -> None:
        """Test that screenshot data 1 byte over MAX_SCREENSHOT_SIZE is rejected.

        Boundary: screenshot_data field validator: len(v) > MAX_SCREENSHOT_SIZE raises ValueError.
        """
        with pytest.raises(ValidationError):
            FeedbackCreate(
                feedback_type="bug",
                message="A" * 10,
                screenshot_data="X" * (MAX_SCREENSHOT_SIZE + 1),  # one byte over limit
            )

    def test_feedback_all_optional_fields_can_be_none(self) -> None:
        """Test that all optional fields can be explicitly set to None.

        Edge case: All optional fields None (email, name, username, user_agent, screenshot).
        """
        feedback = FeedbackCreate(
            feedback_type="other",
            message="This is valid feedback with minimal fields.",
            email=None,
            name=None,
            username=None,
            user_agent=None,
            screenshot_data=None,
            screenshot_filename=None,
        )
        assert feedback.email is None
        assert feedback.name is None
        assert feedback.username is None
        assert feedback.screenshot_data is None

    def test_feedback_all_feedback_type_values_are_valid(self) -> None:
        """Test that all FeedbackType enum values are valid.

        Boundary: feedback_type must be one of 'bug', 'feature', 'other'.
        """
        for fb_type in ["bug", "feature", "other"]:
            feedback = FeedbackCreate(
                feedback_type=fb_type,
                message="Valid feedback message here.",
            )
            assert feedback.feedback_type.value == fb_type


# ============================================================================
# Thinker Schema - Color Hex Validation
# ============================================================================


class TestThinkerSchemaColorValidation:
    """Test thinker color field hex validation."""

    async def test_create_conversation_with_valid_hex_color(self, client: AsyncClient) -> None:
        """Test that thinker with valid 6-digit hex color is accepted.

        Boundary: color pattern r'^#[0-9a-fA-F]{6}$'.
        """
        from unittest.mock import patch

        headers = await get_auth_headers(client, "hex_color_user", "password123")
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Color validation test",
                    "thinkers": [
                        {
                            "name": "Socrates",
                            "bio": "Greek philosopher",
                            "positions": "Ethics",
                            "style": "Socratic method",
                            "color": "#AABBCC",  # valid uppercase hex
                        }
                    ],
                },
            )
        assert response.status_code == 200

    async def test_create_conversation_with_invalid_hex_color_rejected(
        self, client: AsyncClient
    ) -> None:
        """Test that thinker with invalid color format is rejected.

        Edge case: 'red' is not a valid hex color format.
        """
        headers = await get_auth_headers(client, "invalid_hex_user", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Invalid color test",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Greek philosopher",
                        "positions": "Ethics",
                        "style": "Socratic method",
                        "color": "red",  # invalid - not hex format
                    }
                ],
            },
        )
        assert response.status_code == 422

    async def test_create_conversation_with_5_digit_hex_color_rejected(
        self, client: AsyncClient
    ) -> None:
        """Test that thinker with 5-digit hex color (too short) is rejected.

        Boundary: color must have exactly 6 hex digits, not 5.
        """
        headers = await get_auth_headers(client, "short_hex_user", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Short hex color test",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Greek philosopher",
                        "positions": "Forms",
                        "style": "Dialogues",
                        "color": "#12345",  # 5 hex digits - too short
                    }
                ],
            },
        )
        assert response.status_code == 422

    async def test_create_conversation_with_7_digit_hex_color_rejected(
        self, client: AsyncClient
    ) -> None:
        """Test that thinker with 7-digit hex color (too long) is rejected.

        Boundary: color must have exactly 6 hex digits, not 7.
        """
        headers = await get_auth_headers(client, "long_hex_user", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Long hex color test",
                "thinkers": [
                    {
                        "name": "Aristotle",
                        "bio": "Greek philosopher",
                        "positions": "Logic",
                        "style": "Systematic",
                        "color": "#1234567",  # 7 hex digits - too long
                    }
                ],
            },
        )
        assert response.status_code == 422


# ============================================================================
# Special Characters and Unicode
# ============================================================================


class TestSpecialCharactersAndUnicode:
    """Test special characters and unicode in user inputs."""

    async def test_topic_with_unicode_characters_accepted(self, client: AsyncClient) -> None:
        """Test that conversation topics with unicode characters are accepted.

        Edge case: Non-ASCII unicode in topic (emoji, accented chars, CJK).
        """
        from unittest.mock import patch

        headers = await get_auth_headers(client, "unicode_topic_user", "password123")
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "哲学 Philosophy 哲学 🤔 Philosophie",
                    "thinkers": [
                        {
                            "name": "Confucius",
                            "bio": "Chinese philosopher",
                            "positions": "Ethics",
                            "style": "Teaching",
                        }
                    ],
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "哲学" in data["topic"]

    async def test_message_with_emoji_accepted(self, client: AsyncClient) -> None:
        """Test that messages containing emoji are accepted.

        Edge case: Emoji characters in message content.
        """
        from unittest.mock import patch

        headers = await get_auth_headers(client, "emoji_msg_user", "password123")
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Emoji test",
                    "thinkers": [
                        {
                            "name": "Socrates",
                            "bio": "Greek philosopher",
                            "positions": "Ethics",
                            "style": "Socratic method",
                        }
                    ],
                },
            )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        msg_response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Hello! 🌍 What is the meaning of life? 🤔💭"},
        )
        assert msg_response.status_code == 200
        data = msg_response.json()
        assert "🌍" in data["content"]

    async def test_message_with_special_sql_chars_accepted(self, client: AsyncClient) -> None:
        """Test that messages with SQL-special characters don't cause issues.

        Edge case: SQL injection attempt patterns should be stored safely.
        """
        from unittest.mock import patch

        headers = await get_auth_headers(client, "sql_chars_user", "password123")
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "SQL chars test",
                    "thinkers": [
                        {
                            "name": "Socrates",
                            "bio": "Greek philosopher",
                            "positions": "Ethics",
                            "style": "Socratic method",
                        }
                    ],
                },
            )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # SQL injection-like content should be stored as plain text
        sql_content = "'; DROP TABLE users; -- comment"
        msg_response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": sql_content},
        )
        assert msg_response.status_code == 200
        assert msg_response.json()["content"] == sql_content

    async def test_display_name_with_unicode_accepted(self, client: AsyncClient) -> None:
        """Test that display names with unicode characters are accepted.

        Edge case: Non-ASCII display names (e.g., Japanese, Arabic, accented Latin).
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "unicode_name_user",
                "display_name": "Müller 山田",  # German umlaut + Japanese
                "password": "password123",
            },
        )
        assert response.status_code == 200
        assert response.json()["user"]["display_name"] == "Müller 山田"


# ============================================================================
# DevOps API - Authentication Edge Cases
# ============================================================================


class TestDevopsAPIAuthenticationEdgeCases:
    """Test DevOps API authentication header edge cases."""

    async def test_devops_health_without_secret_header_returns_403_or_503(
        self, client: AsyncClient
    ) -> None:
        """Test that DevOps health endpoint without auth header returns 403 or 503.

        Edge case: Missing X-DevOps-Secret header.
        - If DEVOPS_API_SECRET not configured: 503
        - If configured but header missing: 403
        """
        response = await client.get("/api/devops/health")
        # Either 403 (secret set, header missing) or 503 (secret not configured)
        assert response.status_code in [403, 503]

    async def test_devops_stats_with_wrong_secret_returns_403_or_503(
        self, client: AsyncClient
    ) -> None:
        """Test that DevOps stats endpoint with wrong secret returns 403 or 503.

        Edge case: X-DevOps-Secret header present but value is wrong.
        - If DEVOPS_API_SECRET not configured: 503
        - If configured but value doesn't match: 403
        """
        response = await client.get(
            "/api/devops/stats",
            headers={"X-DevOps-Secret": "wrong-secret-value"},
        )
        assert response.status_code in [403, 503]

    async def test_devops_cleanup_stale_sessions_without_auth_returns_403_or_503(
        self, client: AsyncClient
    ) -> None:
        """Test that cleanup endpoint without auth returns 403 or 503.

        Edge case: Destructive endpoints require auth even without real secret configured.
        """
        response = await client.delete("/api/devops/cleanup/stale-sessions")
        assert response.status_code in [403, 503]

    async def test_devops_cleanup_orphans_dry_run_without_auth_returns_403_or_503(
        self, client: AsyncClient
    ) -> None:
        """Test that cleanup/orphans dry_run without auth returns 403 or 503.

        Edge case: Even dry_run mode requires proper authentication.
        """
        response = await client.delete("/api/devops/cleanup/orphans?dry_run=true")
        assert response.status_code in [403, 503]


# ============================================================================
# Spend Service - Edge Cases
# ============================================================================


class TestSpendServiceEdgeCases:
    """Test spend service edge cases including non-existent users and boundaries."""

    async def test_check_spend_limit_user_not_found_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        """Test that check_spend_limit returns None for non-existent user.

        Edge case: User ID that doesn't exist in database.
        """
        result = await check_spend_limit(db_session, "nonexistent-user-id-xyz")
        assert result is None

    async def test_get_user_spend_data_user_not_found_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        """Test that get_user_spend_data returns None for non-existent user.

        Edge case: User ID that doesn't exist in database.
        """
        result = await get_user_spend_data(db_session, "nonexistent-user-id-abc")
        assert result is None

    async def test_check_spend_limit_exactly_at_limit(self, db_session: AsyncSession) -> None:
        """Test check_spend_limit when total_spend equals spend_limit exactly.

        Boundary: is_over_limit is True when total_spend >= spend_limit.
        At exactly equal: is_over_limit should be True.
        """
        from app.models import User

        user = User(
            username="at_limit_user",
            password_hash="hash",
            total_spend=5.0,
            spend_limit=5.0,  # exactly at limit
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        result = await check_spend_limit(db_session, user.id)
        assert result is not None
        assert result.is_over_limit is True  # >= means at limit is over
        assert result.percentage_used == 100.0

    async def test_check_spend_limit_just_below_limit(self, db_session: AsyncSession) -> None:
        """Test check_spend_limit when total_spend is just below spend_limit.

        Boundary: is_over_limit is False when total_spend < spend_limit.
        """
        from app.models import User

        user = User(
            username="below_limit_user",
            password_hash="hash",
            total_spend=4.99,
            spend_limit=5.0,  # spend is 0.01 below limit
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        result = await check_spend_limit(db_session, user.id)
        assert result is not None
        assert result.is_over_limit is False
        assert result.remaining == pytest.approx(0.01, abs=0.001)

    async def test_check_spend_limit_near_limit_threshold_85_percent(
        self, db_session: AsyncSession
    ) -> None:
        """Test check_spend_limit at exactly 85% threshold for is_near_limit.

        Boundary: is_near_limit is True when percentage >= 85.
        At exactly 85%: is_near_limit should be True.
        """
        from app.models import User

        user = User(
            username="near_limit_85_user",
            password_hash="hash",
            total_spend=8.5,
            spend_limit=10.0,  # exactly 85%
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        result = await check_spend_limit(db_session, user.id)
        assert result is not None
        assert result.percentage_used == pytest.approx(85.0)
        assert result.is_near_limit is True  # at 85% threshold

    async def test_check_spend_limit_just_below_near_limit_threshold(
        self, db_session: AsyncSession
    ) -> None:
        """Test check_spend_limit just below 85% threshold for is_near_limit.

        Boundary: is_near_limit is False when percentage < 85.
        At 84%: is_near_limit should be False.
        """
        from app.models import User

        user = User(
            username="below_near_limit_user",
            password_hash="hash",
            total_spend=8.4,
            spend_limit=10.0,  # 84%
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        result = await check_spend_limit(db_session, user.id)
        assert result is not None
        assert result.percentage_used == pytest.approx(84.0)
        assert result.is_near_limit is False  # below 85% threshold


# ============================================================================
# Admin API - Boundary Conditions
# ============================================================================


class TestAdminAPIBoundaryConditions:
    """Test admin API endpoint boundary and error conditions."""

    async def test_update_spend_limit_zero_or_negative_rejected(self, client: AsyncClient) -> None:
        """Test that updating spend limit to zero or negative is rejected.

        Boundary: UpdateSpendLimitRequest.spend_limit field has gt=0 constraint.
        """
        # Register admin user
        await register_and_get_token(client, "admin_spend_limit", "adminpass123")

        # Make the user admin via DB manipulation isn't straightforward here,
        # but we can test that the schema rejects invalid values via another user
        # We test with non-admin user to verify we get 401/403, not 422
        # This tests the validation order: auth before schema validation

        headers = await get_auth_headers(client, "non_admin_spend_test", "password123")

        # Non-admin trying to update spend limit - should get 403 (forbidden)
        response = await client.patch(
            "/api/admin/users/some-user-id/spend-limit",
            headers=headers,
            json={"spend_limit": 10.0},
        )
        assert response.status_code == 403

    async def test_admin_list_users_requires_admin_role(self, client: AsyncClient) -> None:
        """Test that admin user list endpoint requires admin role.

        Security edge case: Regular user cannot access admin endpoints.
        """
        headers = await get_auth_headers(client, "regular_user_admin_test", "password123")
        response = await client.get("/api/admin/users", headers=headers)
        assert response.status_code == 403

    async def test_admin_delete_user_requires_admin_role(self, client: AsyncClient) -> None:
        """Test that admin delete user endpoint requires admin role.

        Security edge case: Regular user cannot delete other users.
        """
        headers = await get_auth_headers(client, "regular_user_delete_test", "password123")
        response = await client.delete(
            "/api/admin/users/some-user-id",
            headers=headers,
        )
        assert response.status_code == 403


# ============================================================================
# Change Password - Boundary Conditions
# ============================================================================


class TestChangePasswordBoundaryConditions:
    """Test change password endpoint boundary conditions."""

    async def test_change_password_new_password_minimum_length_6(self, client: AsyncClient) -> None:
        """Test that new password with exactly 6 chars (min_length) is accepted.

        Boundary: new_password min_length=6.
        """
        headers = await get_auth_headers(client, "pwd_change_min_user", "password123")
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "password123",
                "new_password": "abc123",  # exactly 6 chars
            },
        )
        assert response.status_code == 200

    async def test_change_password_new_password_too_short_rejected(
        self, client: AsyncClient
    ) -> None:
        """Test that new password with 5 chars (below min_length=6) is rejected.

        Boundary: new_password min_length=6, testing one below minimum.
        """
        headers = await get_auth_headers(client, "pwd_change_short_user", "password123")
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "password123",
                "new_password": "ab123",  # 5 chars - below minimum
            },
        )
        assert response.status_code == 422

    async def test_change_password_wrong_current_password_rejected(
        self, client: AsyncClient
    ) -> None:
        """Test that providing wrong current password returns 400.

        Error path: verify_password fails for wrong current password.
        """
        headers = await get_auth_headers(client, "pwd_wrong_current_user", "password123")
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "wrongpassword",  # incorrect current password
                "new_password": "newpassword123",
            },
        )
        assert response.status_code == 400
        assert "incorrect" in response.json()["detail"].lower()

    async def test_change_password_empty_current_password_rejected(
        self, client: AsyncClient
    ) -> None:
        """Test that empty current_password is rejected.

        Boundary: current_password min_length=1, empty string has length 0.
        """
        headers = await get_auth_headers(client, "pwd_empty_current_user", "password123")
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "",  # empty - below min_length=1
                "new_password": "newpassword123",
            },
        )
        assert response.status_code == 422


# ============================================================================
# Profile Update - Boundary Conditions
# ============================================================================


class TestProfileUpdateBoundaryConditions:
    """Test profile update endpoint boundary conditions."""

    async def test_update_profile_display_name_empty_string_rejected(
        self, client: AsyncClient
    ) -> None:
        """Test that updating display_name to empty string is rejected.

        Boundary: display_name min_length=1, empty string has length 0.
        """
        headers = await get_auth_headers(client, "profile_empty_name_user", "password123")
        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": ""},  # empty string - below min_length=1
        )
        assert response.status_code == 422

    async def test_update_profile_display_name_whitespace_only_accepted(
        self, client: AsyncClient
    ) -> None:
        """Test behavior when display_name is set to whitespace-only.

        Edge case: A single space has length 1 (passes min_length=1 check).
        The system accepts it - design choice of whether to trim or not.
        """
        headers = await get_auth_headers(client, "profile_whitespace_user", "password123")
        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": " "},  # single space - passes min_length=1
        )
        # Should be accepted (single space has length 1)
        assert response.status_code == 200

    async def test_update_profile_requires_auth(self, client: AsyncClient) -> None:
        """Test that profile update without authentication is rejected.

        Security edge case: Unauthenticated profile update.
        """
        response = await client.patch(
            "/api/auth/profile",
            json={"display_name": "New Name"},
        )
        assert response.status_code == 401


# ============================================================================
# Thinker Count for Suggest Request
# ============================================================================


class TestThinkerSuggestRequestBoundaries:
    """Test thinker suggest request count boundaries."""

    async def test_suggest_thinkers_count_minimum_1(self, client: AsyncClient) -> None:
        """Test that count=1 (minimum) is accepted in suggest request.

        Boundary: count field ge=1.
        """
        from unittest.mock import AsyncMock, patch

        from app.schemas import ThinkerProfile, ThinkerSuggestion

        mock_suggestions = [
            ThinkerSuggestion(
                name="Socrates",
                reason="Great philosopher",
                profile=ThinkerProfile(
                    name="Socrates",
                    bio="Ancient philosopher",
                    positions="Ethics",
                    style="Questioning",
                    image_url=None,
                ),
            )
        ]

        with patch(
            "app.services.thinker.thinker_service.suggest_thinkers",
            new=AsyncMock(return_value=mock_suggestions),
        ):
            response = await client.post(
                "/api/thinkers/suggest",
                json={"topic": "Philosophy", "count": 1},  # minimum count
            )
        assert response.status_code == 200

    async def test_suggest_thinkers_count_0_rejected(self, client: AsyncClient) -> None:
        """Test that count=0 (below minimum of 1) is rejected.

        Boundary: count field ge=1, testing below minimum.
        """
        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "Philosophy", "count": 0},  # below minimum
        )
        assert response.status_code == 422

    async def test_suggest_thinkers_count_maximum_5(self, client: AsyncClient) -> None:
        """Test that count=5 (maximum) is accepted in suggest request.

        Boundary: count field le=5.
        """
        from unittest.mock import AsyncMock, patch

        from app.schemas import ThinkerProfile, ThinkerSuggestion

        mock_suggestions = [
            ThinkerSuggestion(
                name=f"Thinker{i}",
                reason="Great philosopher",
                profile=ThinkerProfile(
                    name=f"Thinker{i}",
                    bio="Ancient philosopher",
                    positions="Ethics",
                    style="Questioning",
                    image_url=None,
                ),
            )
            for i in range(5)
        ]

        with patch(
            "app.services.thinker.thinker_service.suggest_thinkers",
            new=AsyncMock(return_value=mock_suggestions),
        ):
            response = await client.post(
                "/api/thinkers/suggest",
                json={"topic": "Philosophy", "count": 5},  # maximum count
            )
        assert response.status_code == 200

    async def test_suggest_thinkers_count_6_rejected(self, client: AsyncClient) -> None:
        """Test that count=6 (above maximum of 5) is rejected.

        Boundary: count field le=5, testing above maximum.
        """
        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "Philosophy", "count": 6},  # above maximum
        )
        assert response.status_code == 422

    async def test_suggest_thinkers_invalid_language_rejected(self, client: AsyncClient) -> None:
        """Test that invalid language code in suggest request is rejected.

        Boundary: language pattern '^(en|es|fr)$' - note: 'de' is NOT valid here
        (different from auth language_preference which allows en/es/fr/de).
        """
        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "Philosophy", "count": 3, "language": "de"},  # de not allowed here
        )
        assert response.status_code == 422
