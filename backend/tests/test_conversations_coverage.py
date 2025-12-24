"""Additional tests for conversation API to improve coverage.

This test suite focuses on edge cases and uncovered paths in app/api/conversations.py.
Target: Increase coverage from 49% to 65%+
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.database import get_db
from app.main import app
from tests.test_api import get_auth_headers


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
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestConversationEdgeCases:
    """Test edge cases and uncovered paths in conversation API."""

    async def test_create_conversation_with_custom_colors(self, client: AsyncClient) -> None:
        """Test that custom colors are preserved for thinkers."""
        headers = await get_auth_headers(client, "coloruser1", "password123")

        custom_color = "#FF5733"
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Color test",
                "thinkers": [
                    {
                        "name": "CustomThinker",
                        "bio": "Has custom color",
                        "positions": "Color theory",
                        "style": "Colorful",
                        "color": custom_color,
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["thinkers"][0]["color"] == custom_color

    async def test_create_conversation_with_multiple_thinkers(self, client: AsyncClient) -> None:
        """Test creating conversation with multiple thinkers."""
        headers = await get_auth_headers(client, "coloruser2", "password123")

        # Create conversation with 5 thinkers - omit color to use defaults
        thinkers = []
        for i in range(5):
            thinkers.append(
                {
                    "name": f"Thinker{i}",
                    "bio": f"Bio {i}",
                    "positions": f"Position {i}",
                    "style": f"Style {i}",
                    # Color will default to #6366f1 and trigger rotation
                }
            )

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Multi-thinker test", "thinkers": thinkers},
        )
        assert response.status_code == 200
        data = response.json()

        # Verify all thinkers were created
        assert len(data["thinkers"]) == 5
        colors_found = [t["color"] for t in data["thinkers"]]

        # Verify we have multiple different colors assigned (rotation happened)
        unique_colors = set(colors_found)
        assert len(unique_colors) >= 3  # Should have at least 3 different colors

        # Verify each thinker
        for i in range(5):
            assert data["thinkers"][i]["name"] == f"Thinker{i}"
            assert data["thinkers"][i]["color"].startswith("#")
            assert len(data["thinkers"][i]["color"]) == 7

    async def test_create_conversation_with_image_url(self, client: AsyncClient) -> None:
        """Test creating conversation with thinker image URLs."""
        headers = await get_auth_headers(client, "imageuser", "password123")

        image_url = "https://example.com/thinker.jpg"
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Image test",
                "thinkers": [
                    {
                        "name": "ImageThinker",
                        "bio": "Has image",
                        "positions": "Visual",
                        "style": "Pictorial",
                        "image_url": image_url,
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["thinkers"][0]["image_url"] == image_url

    async def test_list_conversations_with_message_counts(self, client: AsyncClient) -> None:
        """Test that list conversations includes accurate message counts."""
        headers = await get_auth_headers(client, "msgcountuser", "password123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Message count test",
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

        # Send 3 messages
        for i in range(3):
            await client.post(
                f"/api/conversations/{conv_id}/messages",
                headers=headers,
                json={"content": f"Message {i}"},
            )

        # List conversations and check message count
        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["message_count"] == 3

    async def test_list_conversations_with_total_cost(self, client: AsyncClient) -> None:
        """Test that list conversations calculates total cost correctly."""
        headers = await get_auth_headers(client, "costuser", "password123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Cost test",
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

        # Send message (cost will be None for user messages, but we're testing the sum logic)
        await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Test message"},
        )

        # List conversations and verify total_cost field exists
        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "total_cost" in data[0]
        assert isinstance(data[0]["total_cost"], (int, float))
        assert data[0]["total_cost"] >= 0.0

    async def test_list_conversations_ordered_by_created_at(self, client: AsyncClient) -> None:
        """Test that conversations are returned in list ordered by created_at."""
        headers = await get_auth_headers(client, "orderuser", "password123")

        # Create multiple conversations
        topics = ["First", "Second", "Third"]
        for topic in topics:
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
        assert len(data) == 3

        # Verify all created_at fields are present and properly ordered
        assert all("created_at" in conv for conv in data)
        # Extract created_at timestamps and verify they're in descending order
        timestamps = [conv["created_at"] for conv in data]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_get_conversation_from_different_session(self, client: AsyncClient) -> None:
        """Test that users can't access conversations from other sessions."""
        # User 1 creates conversation
        headers1 = await get_auth_headers(client, "isolationuser1", "password123")
        conv_response = await client.post(
            "/api/conversations",
            headers=headers1,
            json={
                "topic": "Private conversation",
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

        # User 2 tries to access it
        headers2 = await get_auth_headers(client, "isolationuser2", "password123")
        response = await client.get(
            f"/api/conversations/{conv_id}",
            headers=headers2,
        )
        assert response.status_code == 404

    async def test_delete_conversation_from_different_session(self, client: AsyncClient) -> None:
        """Test that users can't delete conversations from other sessions."""
        # User 1 creates conversation
        headers1 = await get_auth_headers(client, "deluser1", "password123")
        conv_response = await client.post(
            "/api/conversations",
            headers=headers1,
            json={
                "topic": "Protected conversation",
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

        # User 2 tries to delete it
        headers2 = await get_auth_headers(client, "deluser2", "password123")
        response = await client.delete(
            f"/api/conversations/{conv_id}",
            headers=headers2,
        )
        assert response.status_code == 404

        # User 1 can still access it
        response = await client.get(f"/api/conversations/{conv_id}", headers=headers1)
        assert response.status_code == 200

    async def test_send_message_to_nonexistent_conversation(self, client: AsyncClient) -> None:
        """Test sending message to non-existent conversation returns 404."""
        headers = await get_auth_headers(client, "nonexistmsg", "password123")
        response = await client.post(
            "/api/conversations/non-existent-id/messages",
            headers=headers,
            json={"content": "Hello"},
        )
        assert response.status_code == 404

    async def test_send_message_to_other_users_conversation(self, client: AsyncClient) -> None:
        """Test sending message to another user's conversation returns 404."""
        # User 1 creates conversation
        headers1 = await get_auth_headers(client, "msguser1", "password123")
        conv_response = await client.post(
            "/api/conversations",
            headers=headers1,
            json={
                "topic": "User 1 conversation",
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

        # User 2 tries to send message
        headers2 = await get_auth_headers(client, "msguser2", "password123")
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers2,
            json={"content": "Unauthorized message"},
        )
        assert response.status_code == 404

    async def test_send_message_includes_sender_name(self, client: AsyncClient) -> None:
        """Test that messages include a sender_name field."""
        headers = await get_auth_headers(client, "sendernameuser", "password123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Sender name test",
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
            json={"content": "Test message"},
        )
        assert response.status_code == 200
        data = response.json()
        # Verify sender_name is populated (either display_name or username)
        assert "sender_name" in data
        assert len(data["sender_name"]) > 0
        assert data["sender_type"] == "user"

    async def test_list_conversations_includes_all_fields(self, client: AsyncClient) -> None:
        """Test that conversation summaries include all expected fields."""
        headers = await get_auth_headers(client, "fieldsuser", "password123")

        # Create conversation
        await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Fields test",
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
        assert len(data) == 1

        conversation = data[0]
        # Verify all fields from ConversationSummary schema
        assert "id" in conversation
        assert "session_id" in conversation
        assert "topic" in conversation
        assert "title" in conversation
        assert "is_active" in conversation
        assert "created_at" in conversation
        assert "thinkers" in conversation
        assert "message_count" in conversation
        assert "total_cost" in conversation

        # Verify thinkers list is populated
        assert len(conversation["thinkers"]) == 1
        assert conversation["thinkers"][0]["name"] == "Thinker"

    async def test_delete_conversation_returns_correct_status(self, client: AsyncClient) -> None:
        """Test that delete returns proper status response."""
        headers = await get_auth_headers(client, "delstatususer", "password123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Delete status test",
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
        data = response.json()
        assert data["status"] == "deleted"

        # Verify conversation is actually deleted
        response = await client.get(f"/api/conversations/{conv_id}", headers=headers)
        assert response.status_code == 404
