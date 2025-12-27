"""Edge case tests for API endpoints.

Focus on error paths, boundary conditions, and unusual inputs.
Saturday QA focus: Edge Case Analysis.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.core.database import get_db
from app.main import app


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database override."""
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


class TestConversationEdgeCases:
    """Edge case tests for conversation endpoints."""

    async def test_create_conversation_with_empty_thinker_list(self, client: AsyncClient) -> None:
        """Test creating conversation with no thinkers fails validation."""
        from tests.test_api import get_auth_headers

        headers = await get_auth_headers(client, "edgeuser1", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Empty conversation",
                "thinkers": [],  # Empty list should fail
            },
        )
        assert response.status_code == 422  # Validation error
        assert "thinkers" in response.json()["detail"][0]["loc"]

    async def test_create_conversation_with_max_thinkers(self, client: AsyncClient) -> None:
        """Test creating conversation with exactly 5 thinkers (max allowed)."""
        from tests.test_api import get_auth_headers

        headers = await get_auth_headers(client, "edgeuser2", "password123")
        thinkers = [
            {
                "name": f"Thinker {i}",
                "bio": f"Bio {i}",
                "positions": f"Position {i}",  # Must be string, not list
                "style": f"Style {i}",
            }
            for i in range(5)
        ]
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Max thinkers test", "thinkers": thinkers},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 5

    async def test_create_conversation_with_over_max_thinkers(self, client: AsyncClient) -> None:
        """Test creating conversation with more than 5 thinkers fails."""
        from tests.test_api import get_auth_headers

        headers = await get_auth_headers(client, "edgeuser3", "password123")
        thinkers = [
            {
                "name": f"Thinker {i}",
                "bio": f"Bio {i}",
                "positions": [f"Position {i}"],
                "style": f"Style {i}",
            }
            for i in range(6)  # 6 thinkers, over the limit
        ]
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Too many thinkers", "thinkers": thinkers},
        )
        assert response.status_code == 422  # Validation error
        assert "thinkers" in response.json()["detail"][0]["loc"]

    async def test_create_conversation_with_empty_topic(self, client: AsyncClient) -> None:
        """Test creating conversation with empty topic fails validation."""
        from tests.test_api import get_auth_headers

        headers = await get_auth_headers(client, "edgeuser4", "password123")
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "",  # Empty topic
                "thinkers": [
                    {
                        "name": "Test Thinker",
                        "bio": "Test bio",
                        "positions": ["Test position"],
                        "style": "Test style",
                    }
                ],
            },
        )
        assert response.status_code == 422  # Validation error
        assert "topic" in response.json()["detail"][0]["loc"]

    async def test_get_conversation_invalid_uuid(self, client: AsyncClient) -> None:
        """Test getting conversation with invalid UUID format."""
        from tests.test_api import get_auth_headers

        headers = await get_auth_headers(client, "edgeuser5", "password123")
        # Use a non-UUID string
        response = await client.get(
            "/api/conversations/not-a-valid-uuid",
            headers=headers,
        )
        # Should return 404 (not found) since query won't match any conversation
        assert response.status_code == 404

    async def test_delete_already_deleted_conversation(self, client: AsyncClient) -> None:
        """Test deleting a conversation twice returns 404 on second attempt."""
        from tests.test_api import create_test_conversation, get_auth_headers

        headers = await get_auth_headers(client, "edgeuser6", "password123")

        # Create conversation - returns conversation ID as string
        conv_id = await create_test_conversation(client, headers)

        # Delete it once
        response = await client.delete(
            f"/api/conversations/{conv_id}",
            headers=headers,
        )
        assert response.status_code == 200

        # Try to delete again
        response = await client.delete(
            f"/api/conversations/{conv_id}",
            headers=headers,
        )
        assert response.status_code == 404
        assert "Conversation not found" in response.json()["detail"]

    async def test_send_message_empty_content(self, client: AsyncClient) -> None:
        """Test sending message with empty content fails validation."""
        from tests.test_api import create_test_conversation, get_auth_headers

        headers = await get_auth_headers(client, "edgeuser7", "password123")
        conv_id = await create_test_conversation(client, headers)

        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": ""},  # Empty content
        )
        assert response.status_code == 422  # Validation error

    async def test_send_message_very_long_content(self, client: AsyncClient) -> None:
        """Test sending message with very long content (10,000 chars)."""
        from tests.test_api import create_test_conversation, get_auth_headers

        headers = await get_auth_headers(client, "edgeuser8", "password123")
        conv_id = await create_test_conversation(client, headers)

        # Create a very long message (10k characters)
        long_content = "A" * 10000

        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": long_content},
        )
        # Should succeed - no explicit max length on message content
        assert response.status_code == 200
        data = response.json()
        assert len(data["content"]) == 10000


class TestAuthEdgeCases:
    """Edge case tests for authentication endpoints."""

    async def test_register_empty_username(self, client: AsyncClient) -> None:
        """Test registration with empty username fails validation."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "",  # Empty username
                "display_name": "Test User",
                "password": "password123",
            },
        )
        assert response.status_code == 422  # Validation error
        assert "username" in response.json()["detail"][0]["loc"]

    async def test_register_empty_password(self, client: AsyncClient) -> None:
        """Test registration with empty password fails validation."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "validuser",
                "display_name": "Test User",
                "password": "",  # Empty password
            },
        )
        assert response.status_code == 422  # Validation error
        assert "password" in response.json()["detail"][0]["loc"]

    async def test_register_short_username(self, client: AsyncClient) -> None:
        """Test registration with username shorter than min length (3 chars)."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "ab",  # Only 2 chars, min is 3
                "display_name": "Test User",
                "password": "password123",
            },
        )
        assert response.status_code == 422  # Validation error

    async def test_register_short_password(self, client: AsyncClient) -> None:
        """Test registration with password shorter than min length (6 chars)."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "validuser",
                "display_name": "Test User",
                "password": "12345",  # Only 5 chars, min is 6
            },
        )
        assert response.status_code == 422  # Validation error

    async def test_register_username_with_special_characters(self, client: AsyncClient) -> None:
        """Test registration with special characters in username."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "user@#$%",  # Special characters
                "display_name": "Test User",
                "password": "password123",
            },
        )
        # Should succeed - no explicit pattern restriction on username
        assert response.status_code == 200

    async def test_register_very_long_username(self, client: AsyncClient) -> None:
        """Test registration with username at max length (50 chars)."""
        long_username = "a" * 50  # Exactly 50 chars
        response = await client.post(
            "/api/auth/register",
            json={
                "username": long_username,
                "display_name": "Test User",
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["username"] == long_username

    async def test_register_over_max_username(self, client: AsyncClient) -> None:
        """Test registration with username over max length (51 chars)."""
        long_username = "a" * 51  # Over 50 char limit
        response = await client.post(
            "/api/auth/register",
            json={
                "username": long_username,
                "display_name": "Test User",
                "password": "password123",
            },
        )
        assert response.status_code == 422  # Validation error

    async def test_register_very_long_display_name(self, client: AsyncClient) -> None:
        """Test registration with display name at max length (100 chars)."""
        long_name = "A" * 100  # Exactly 100 chars
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "longnameuser",
                "display_name": long_name,
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["display_name"] == long_name

    async def test_register_over_max_display_name(self, client: AsyncClient) -> None:
        """Test registration with display name over max length (101 chars)."""
        long_name = "A" * 101  # Over 100 char limit
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "toolongname",
                "display_name": long_name,
                "password": "password123",
            },
        )
        assert response.status_code == 422  # Validation error

    async def test_login_empty_username(self, client: AsyncClient) -> None:
        """Test login with empty username."""
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "",  # Empty username
                "password": "password123",
            },
        )
        # Should return 401 (unauthorized) not 422, as validation allows empty
        # but authentication will fail
        assert response.status_code == 401

    async def test_login_empty_password(self, client: AsyncClient) -> None:
        """Test login with empty password."""
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "validuser",
                "password": "",  # Empty password
            },
        )
        # Should return 401 (unauthorized)
        assert response.status_code == 401

    async def test_register_invalid_language_preference(self, client: AsyncClient) -> None:
        """Test registration with invalid language preference."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "languser",
                "display_name": "Lang User",
                "password": "password123",
                "language_preference": "fr",  # Only 'en' and 'es' are valid
            },
        )
        assert response.status_code == 422  # Validation error
        assert "language_preference" in response.json()["detail"][0]["loc"]

    async def test_update_language_invalid_preference(self, client: AsyncClient) -> None:
        """Test updating language with invalid preference."""
        from tests.test_api import get_auth_headers

        headers = await get_auth_headers(client, "languser2", "password123")
        response = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "de"},  # Invalid language
        )
        assert response.status_code == 422  # Validation error


class TestThinkerEdgeCases:
    """Edge case tests for thinker endpoints."""

    async def test_suggest_thinkers_with_zero_count(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test suggesting thinkers with count=0."""
        # Mock settings to return None for API key
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": None})(),
        )

        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "Philosophy", "count": 0},
        )
        # Should fail validation (count must be >= 1)
        assert response.status_code == 422

    async def test_suggest_thinkers_with_negative_count(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test suggesting thinkers with negative count."""
        # Mock settings to return None for API key
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": None})(),
        )

        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "Philosophy", "count": -1},
        )
        # Should fail validation
        assert response.status_code == 422

    async def test_validate_thinker_with_empty_name(self, client: AsyncClient) -> None:
        """Test validating thinker with empty name."""
        response = await client.post(
            "/api/thinkers/validate",
            json={"name": ""},  # Empty name
        )
        # Should fail validation
        assert response.status_code == 422

    async def test_suggest_thinkers_with_empty_topic(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test suggesting thinkers with empty topic."""
        # Mock settings to return None for API key
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": None})(),
        )

        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "", "count": 3},
        )
        # Should fail validation (min_length=1 on topic)
        assert response.status_code == 422

    async def test_suggest_thinkers_with_very_long_topic(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test suggesting thinkers with very long topic (1000 chars)."""
        # Mock settings to return None for API key
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": None})(),
        )

        long_topic = "A" * 1000
        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": long_topic, "count": 3},
        )
        # Should succeed - no explicit max length on topic
        assert response.status_code == 200
