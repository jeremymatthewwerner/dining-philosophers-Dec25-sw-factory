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


async def create_test_conversation(
    client: AsyncClient,
    headers: dict[str, str],
    topic: str = "Test Topic",
    num_thinkers: int = 2,
) -> str:
    """Helper to create a test conversation and return its ID.

    Reduces duplication of conversation creation pattern that appears 10+ times
    in test_api.py with nearly identical structure.

    Args:
        client: AsyncClient for making requests
        headers: Auth headers
        topic: Conversation topic
        num_thinkers: Number of thinkers to create (default 2)

    Returns:
        The conversation ID
    """
    thinkers = []
    thinker_names = ["Socrates", "Einstein", "Plato", "Darwin", "Curie"]
    for i in range(num_thinkers):
        name = thinker_names[i] if i < len(thinker_names) else f"Thinker{i}"
        thinkers.append(
            {
                "name": name,
                "bio": f"Bio for {name}",
                "positions": f"Positions of {name}",
                "style": f"Style of {name}",
            }
        )

    response = await client.post(
        "/api/conversations",
        headers=headers,
        json={"topic": topic, "thinkers": thinkers},
    )
    assert response.status_code == 200, f"Failed to create conversation: {response.text}"
    data = response.json()
    conversation_id: str = data["id"]
    return conversation_id


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

    async def test_conversation_color_assignment_edge_cases(self, client: AsyncClient) -> None:
        """Test color assignment with max thinkers and custom colors."""
        headers = await get_auth_headers(client, "coloruser", "password123")

        # Test with 5 thinkers (max allowed, uses all 5 colors)
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Many thinkers",
                "thinkers": [
                    {
                        "name": f"Thinker{i}",
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                    }
                    for i in range(5)
                ],
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
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Custom color test",
                "thinkers": [
                    {
                        "name": "CustomColorThinker",
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                        "color": custom_color,
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["thinkers"][0]["color"] == custom_color

    async def test_conversation_deletion_with_messages(self, client: AsyncClient) -> None:
        """Test that deleting a conversation cascades to delete messages."""
        headers = await get_auth_headers(client, "cascadeuser", "password123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test cascade delete",
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
        conv_response = await client.post(
            "/api/conversations",
            headers=headers_a,
            json={
                "topic": "User A's conversation",
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


class TestLanguageSupport:
    """Tests for multi-language support."""

    async def test_register_with_english(self, client: AsyncClient) -> None:
        """Test registration with English language (default)."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "englishuser",
                "display_name": "English User",
                "password": "password123",
                "language": "en",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["language"] == "en"

    async def test_register_with_spanish(self, client: AsyncClient) -> None:
        """Test registration with Spanish language."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "spanishuser",
                "display_name": "Spanish User",
                "password": "password123",
                "language": "es",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["language"] == "es"

    async def test_register_default_language(self, client: AsyncClient) -> None:
        """Test registration defaults to English if language not specified."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "defaultuser",
                "display_name": "Default User",
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["language"] == "en"

    async def test_register_invalid_language(self, client: AsyncClient) -> None:
        """Test registration fails with invalid language."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "invalidlanguser",
                "display_name": "Invalid Lang User",
                "password": "password123",
                "language": "fr",  # French not supported yet
            },
        )
        assert response.status_code == 422  # Validation error

    async def test_login_returns_language(self, client: AsyncClient) -> None:
        """Test that login returns user's language preference."""
        # First register with Spanish
        await client.post(
            "/api/auth/register",
            json={
                "username": "spanishlogin",
                "display_name": "Spanish Login",
                "password": "password123",
                "language": "es",
            },
        )

        # Then login
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "spanishlogin",
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["language"] == "es"
