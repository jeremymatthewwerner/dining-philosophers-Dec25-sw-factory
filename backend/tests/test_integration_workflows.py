"""Integration tests for cross-endpoint workflows."""

from collections.abc import AsyncGenerator

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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


class TestFullUserJourney:
    """Test complete user workflows from registration to conversation management."""

    async def test_full_user_journey(self, client: AsyncClient) -> None:
        """Test the complete user journey: register → login → create conversation → send messages → list → delete."""
        # Step 1: Register user
        register_response = await client.post(
            "/api/auth/register",
            json={
                "username": "journeyuser",
                "display_name": "Journey User",
                "password": "password123",
            },
        )
        assert register_response.status_code == 200
        register_data = register_response.json()
        assert "access_token" in register_data
        token = register_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Verify we can get user info
        me_response = await client.get("/api/auth/me", headers=headers)
        assert me_response.status_code == 200
        assert me_response.json()["username"] == "journeyuser"

        # Step 3: Create a conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "The nature of reality",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Ancient Greek philosopher",
                        "positions": "Theory of Forms",
                        "style": "Dialectic method",
                    },
                    {
                        "name": "Descartes",
                        "bio": "French philosopher",
                        "positions": "Mind-body dualism",
                        "style": "Methodological doubt",
                    },
                ],
            },
        )
        assert conv_response.status_code == 200
        conv_data = conv_response.json()
        conversation_id = conv_data["id"]
        assert conv_data["topic"] == "The nature of reality"
        assert len(conv_data["thinkers"]) == 2

        # Step 4: Send messages to the conversation
        message_contents = [
            "What is real?",
            "How do we know anything exists?",
            "Can we trust our senses?",
        ]
        for content in message_contents:
            msg_response = await client.post(
                f"/api/conversations/{conversation_id}/messages",
                headers=headers,
                json={"content": content},
            )
            assert msg_response.status_code == 200
            msg_data = msg_response.json()
            assert msg_data["content"] == content
            assert msg_data["sender_type"] == "user"
            assert msg_data["sender_name"] == "Journey User"

        # Step 5: List conversations and verify it appears
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200
        conversations = list_response.json()
        assert len(conversations) == 1
        assert conversations[0]["id"] == conversation_id
        assert conversations[0]["message_count"] == 3
        assert conversations[0]["topic"] == "The nature of reality"

        # Step 6: Get the conversation with messages
        get_response = await client.get(
            f"/api/conversations/{conversation_id}",
            headers=headers,
        )
        assert get_response.status_code == 200
        full_conv = get_response.json()
        assert len(full_conv["messages"]) == 3
        assert full_conv["messages"][0]["content"] == "What is real?"

        # Step 7: Delete the conversation
        delete_response = await client.delete(
            f"/api/conversations/{conversation_id}",
            headers=headers,
        )
        assert delete_response.status_code == 200

        # Step 8: Verify it's gone
        list_after_delete = await client.get("/api/conversations", headers=headers)
        assert len(list_after_delete.json()) == 0

        get_after_delete = await client.get(
            f"/api/conversations/{conversation_id}",
            headers=headers,
        )
        assert get_after_delete.status_code == 404

        # Step 9: Logout
        logout_response = await client.post("/api/auth/logout")
        assert logout_response.status_code == 200

    async def test_multiple_users_isolated_conversations(self, client: AsyncClient) -> None:
        """Test that multiple users have isolated conversations."""
        # Register two users
        user1_response = await client.post(
            "/api/auth/register",
            json={
                "username": "user1",
                "display_name": "User One",
                "password": "password123",
            },
        )
        user1_token = user1_response.json()["access_token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}

        user2_response = await client.post(
            "/api/auth/register",
            json={
                "username": "user2",
                "display_name": "User Two",
                "password": "password456",
            },
        )
        user2_token = user2_response.json()["access_token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        # Each user creates a conversation
        conv1_response = await client.post(
            "/api/conversations",
            headers=user1_headers,
            json={
                "topic": "User 1's topic",
                "thinkers": [
                    {
                        "name": "Thinker1",
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                    },
                ],
            },
        )
        conv1_id = conv1_response.json()["id"]

        conv2_response = await client.post(
            "/api/conversations",
            headers=user2_headers,
            json={
                "topic": "User 2's topic",
                "thinkers": [
                    {
                        "name": "Thinker2",
                        "bio": "Bio",
                        "positions": "Positions",
                        "style": "Style",
                    },
                ],
            },
        )
        conv2_id = conv2_response.json()["id"]

        # User 1 should only see their conversation
        user1_list = await client.get("/api/conversations", headers=user1_headers)
        user1_convs = user1_list.json()
        assert len(user1_convs) == 1
        assert user1_convs[0]["id"] == conv1_id

        # User 2 should only see their conversation
        user2_list = await client.get("/api/conversations", headers=user2_headers)
        user2_convs = user2_list.json()
        assert len(user2_convs) == 1
        assert user2_convs[0]["id"] == conv2_id

        # User 1 cannot access User 2's conversation
        access_attempt = await client.get(
            f"/api/conversations/{conv2_id}",
            headers=user1_headers,
        )
        assert access_attempt.status_code == 404

    async def test_login_after_registration(self, client: AsyncClient) -> None:
        """Test that users can login after registration with correct credentials."""
        # Register
        await client.post(
            "/api/auth/register",
            json={
                "username": "loginaftereq",
                "display_name": "Login Test",
                "password": "mypassword",
            },
        )

        # Login with same credentials
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "loginaftereq", "password": "mypassword"},
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "access_token" in login_data
        assert login_data["user"]["username"] == "loginaftereq"
        assert login_data["user"]["display_name"] == "Login Test"

        # Verify token works
        headers = {"Authorization": f"Bearer {login_data['access_token']}"}
        me_response = await client.get("/api/auth/me", headers=headers)
        assert me_response.status_code == 200
        assert me_response.json()["username"] == "loginaftereq"
