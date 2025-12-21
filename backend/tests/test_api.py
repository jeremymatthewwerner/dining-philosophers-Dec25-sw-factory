"""Tests for API endpoints."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import get_db
from app.main import app
from app.models import Base


@pytest.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite engine for testing."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


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


async def register_and_get_token(
    client: AsyncClient,
    username: str = "testuser",
    password: str = "testpass123",
    display_name: str | None = None,
) -> dict[str, Any]:
    """Helper to register a user and get their auth token."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": display_name or username.title(),
            "password": password,
        },
    )
    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    return data


async def get_auth_headers(
    client: AsyncClient,
    username: str = "testuser",
    password: str = "testpass123",
) -> dict[str, str]:
    """Helper to get authorization headers for an authenticated user."""
    data = await register_and_get_token(client, username, password)
    return {"Authorization": f"Bearer {data['access_token']}"}


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

        # Create conversations
        for topic in ["Topic 1", "Topic 2"]:
            await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": topic,
                    "thinkers": [
                        {
                            "name": "Thinker",
                            "bio": "Bio",
                            "positions": "Positions",
                            "style": "Style",
                        },
                    ],
                },
            )

        # List conversations
        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_get_conversation(self, client: AsyncClient) -> None:
        """Test getting a conversation with messages."""
        headers = await get_auth_headers(client, "getuser", "password123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test topic",
                "thinkers": [
                    {
                        "name": "Thinker",
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                    },
                ],
            },
        )
        conv_id = conv_response.json()["id"]

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

        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test",
                "thinkers": [
                    {
                        "name": "Thinker",
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                    },
                ],
            },
        )
        conv_id = conv_response.json()["id"]

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

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "To be deleted",
                "thinkers": [
                    {
                        "name": "Thinker",
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                    },
                ],
            },
        )
        conv_id = conv_response.json()["id"]

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


class TestThinkerAPI:
    """Tests for thinker endpoints."""

    async def test_suggest_thinkers(self, client: AsyncClient) -> None:
        """Test getting thinker suggestions."""
        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "Philosophy of mind", "count": 3},
        )
        assert response.status_code == 200
        data = response.json()
        # Due to parallel fetching and deduplication, we may get slightly fewer
        assert len(data) >= 2
        assert len(data) <= 3
        assert all("name" in t for t in data)
        assert all("profile" in t for t in data)

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

    async def test_validate_unknown_thinker(self, client: AsyncClient) -> None:
        """Test validating an unknown thinker."""
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


async def create_admin_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> dict[str, Any]:
    """Helper to create an admin user for testing."""
    from sqlalchemy import update

    from app.models import User

    # Register a regular user first
    data = await register_and_get_token(client, "adminuser", "adminpass123")

    # Make them an admin directly in the database
    await db_session.execute(
        update(User).where(User.id == data["user"]["id"]).values(is_admin=True)
    )
    await db_session.commit()

    return data


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

    async def test_update_spend_limit_invalid_value(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test validation for invalid spend limit values."""
        admin_data = await create_admin_user(client, db_session)
        headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

        user_data = await register_and_get_token(client, "validationuser", "password123")
        user_id = user_data["user"]["id"]

        # Test zero
        response = await client.patch(
            f"/api/admin/users/{user_id}/spend-limit",
            json={"spend_limit": 0},
            headers=headers,
        )
        assert response.status_code == 422

        # Test negative
        response = await client.patch(
            f"/api/admin/users/{user_id}/spend-limit",
            json={"spend_limit": -5.0},
            headers=headers,
        )
        assert response.status_code == 422

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

        # Create a conversation
        await client.post(
            "/api/conversations",
            headers=user_headers,
            json={
                "topic": "Test topic for spend",
                "thinkers": [
                    {
                        "name": "Thinker",
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                    },
                ],
            },
        )

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
