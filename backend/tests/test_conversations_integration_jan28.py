"""Integration tests for conversation API gaps - QA Agent Jan 28, 2026."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message
from tests.conftest import get_auth_headers


class TestListConversationsIntegration:
    """Test list_conversations endpoint integration (lines 85-105)."""

    async def test_list_conversations_message_count_accuracy(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Verify message_count field accurately reflects the number of messages."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Philosophy",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Ancient Greek philosopher",
                        "positions": "Teacher",
                        "style": "Socratic",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Send 3 messages
        for i in range(3):
            response = await client.post(
                f"/api/conversations/{conversation_id}/messages",
                json={"content": f"Message {i + 1}"},
                headers=auth_headers,
            )
            assert response.status_code == 200

        # List conversations and verify message_count
        response = await client.get("/api/conversations", headers=auth_headers)
        assert response.status_code == 200
        conversations = response.json()
        assert len(conversations) == 1
        assert conversations[0]["message_count"] == 3

        # Verify against actual database count
        result = await db_session.execute(
            select(Message).where(Message.conversation_id == conversation_id)
        )
        actual_messages = result.scalars().all()
        assert len(actual_messages) == 3

    async def test_list_conversations_cost_aggregation(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Verify total_cost field correctly sums all message costs."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Economics",
                "thinkers": [
                    {
                        "name": "Adam Smith",
                        "bio": "Economist",
                        "positions": "Political economist",
                        "style": "Classical",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Create messages with known costs directly in database
        msg1 = Message(
            conversation_id=conversation_id,
            sender_type="user",
            sender_name="Test",
            content="Message 1",
            cost=0.0015,
        )
        msg2 = Message(
            conversation_id=conversation_id,
            sender_type="user",
            sender_name="Test",
            content="Message 2",
            cost=0.0025,
        )
        msg3 = Message(
            conversation_id=conversation_id,
            sender_type="user",
            sender_name="Test",
            content="Message 3",
            cost=0.0010,
        )
        db_session.add_all([msg1, msg2, msg3])
        await db_session.flush()

        # List conversations and verify total_cost
        response = await client.get("/api/conversations", headers=auth_headers)
        assert response.status_code == 200
        conversations = response.json()
        assert len(conversations) == 1
        assert conversations[0]["message_count"] == 3
        # Total should be 0.0015 + 0.0025 + 0.0010 = 0.0050
        assert abs(conversations[0]["total_cost"] - 0.0050) < 0.0001

    async def test_list_conversations_with_zero_cost_messages(self, client: AsyncClient) -> None:
        """Verify total_cost handles None and zero costs correctly."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Free Thoughts",
                "thinkers": [
                    {
                        "name": "Diogenes",
                        "bio": "Cynic philosopher",
                        "positions": "Philosopher",
                        "style": "Cynical",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Send message (will have None or 0 cost)
        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "Free message"},
            headers=auth_headers,
        )
        assert response.status_code == 200

        # List conversations - should not crash on None costs
        response = await client.get("/api/conversations", headers=auth_headers)
        assert response.status_code == 200
        conversations = response.json()
        assert len(conversations) == 1
        assert conversations[0]["total_cost"] >= 0.0


class TestGetConversationIntegration:
    """Test get_conversation endpoint error handling (lines 126-129)."""

    async def test_get_conversation_not_found(self, client: AsyncClient) -> None:
        """Verify 404 is returned when conversation doesn't exist."""
        auth_headers = await get_auth_headers(client)

        # Try to get non-existent conversation
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/conversations/{fake_id}", headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "Conversation not found"

    async def test_get_conversation_belongs_to_different_session(self, client: AsyncClient) -> None:
        """Verify 404 when trying to access another session's conversation."""
        # Create first user and conversation
        auth_headers_1 = await get_auth_headers(client, username="user1")
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Private thoughts",
                "thinkers": [
                    {
                        "name": "Marcus Aurelius",
                        "bio": "Roman emperor",
                        "positions": "Emperor",
                        "style": "Stoic",
                    }
                ],
            },
            headers=auth_headers_1,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Create second user and try to access first user's conversation
        auth_headers_2 = await get_auth_headers(client, username="user2")
        response = await client.get(f"/api/conversations/{conversation_id}", headers=auth_headers_2)
        assert response.status_code == 404
        assert response.json()["detail"] == "Conversation not found"


class TestDeleteConversationIntegration:
    """Test delete_conversation cascade behavior (lines 145-151)."""

    async def test_delete_conversation_cascades_messages(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Verify messages are deleted when conversation is deleted."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Ephemeral",
                "thinkers": [
                    {
                        "name": "Heraclitus",
                        "bio": "Greek philosopher",
                        "positions": "Philosopher",
                        "style": "Change-focused",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Send 3 messages
        for i in range(3):
            response = await client.post(
                f"/api/conversations/{conversation_id}/messages",
                json={"content": f"Message {i + 1}"},
                headers=auth_headers,
            )
            assert response.status_code == 200

        # Verify messages exist
        result = await db_session.execute(
            select(Message).where(Message.conversation_id == conversation_id)
        )
        messages_before = result.scalars().all()
        assert len(messages_before) == 3

        # Delete conversation
        response = await client.delete(
            f"/api/conversations/{conversation_id}", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify messages are also deleted (cascade)
        result = await db_session.execute(
            select(Message).where(Message.conversation_id == conversation_id)
        )
        messages_after = result.scalars().all()
        assert len(messages_after) == 0

    async def test_delete_conversation_not_found(self, client: AsyncClient) -> None:
        """Verify 404 when trying to delete non-existent conversation."""
        auth_headers = await get_auth_headers(client)

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(f"/api/conversations/{fake_id}", headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "Conversation not found"


class TestCreateConversationColorDistribution:
    """Test create_conversation color assignment (lines 46-61)."""

    async def test_create_conversation_color_distribution(self, client: AsyncClient) -> None:
        """Verify colors are distributed correctly when creating conversation with multiple thinkers."""
        auth_headers = await get_auth_headers(client)

        # Create conversation with 5 thinkers (max)
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Spectrum of thought",
                "thinkers": [
                    {
                        "name": f"Thinker {i}",
                        "bio": f"Bio {i}",
                        "positions": "Philosopher",
                        "style": "Analytical",
                    }
                    for i in range(5)
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        thinkers = response.json()["thinkers"]
        assert len(thinkers) == 5

        # Verify each thinker has a unique color
        colors = [t["color"] for t in thinkers]
        assert len(set(colors)) == 5  # All unique

        # Verify colors are from the expected palette
        expected_colors = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]
        for color in colors:
            assert color in expected_colors

    async def test_create_conversation_respects_custom_colors(self, client: AsyncClient) -> None:
        """Verify custom colors are preserved when provided."""
        auth_headers = await get_auth_headers(client)

        custom_color = "#ff00ff"
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Custom",
                "thinkers": [
                    {
                        "name": "Custom Thinker",
                        "bio": "Has custom color",
                        "positions": "Philosopher",
                        "style": "Unique",
                        "color": custom_color,
                    },
                    {
                        "name": "Default Thinker",
                        "bio": "Uses default color",
                        "positions": "Philosopher",
                        "style": "Standard",
                    },
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        thinkers = response.json()["thinkers"]
        assert len(thinkers) == 2

        # First thinker should have custom color
        assert thinkers[0]["color"] == custom_color
        # Second thinker should have color from palette
        assert thinkers[1]["color"] in [
            "#6366f1",
            "#ec4899",
            "#10b981",
            "#f59e0b",
            "#8b5cf6",
        ]
        # Colors should be different
        assert thinkers[0]["color"] != thinkers[1]["color"]


class TestAddThinkersRefreshBehavior:
    """Test add_thinkers refresh after db.flush (lines 216-220)."""

    async def test_add_thinkers_refresh_sets_ids_and_timestamps(self, client: AsyncClient) -> None:
        """Verify new thinkers have IDs and timestamps after being added."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Identity",
                "thinkers": [
                    {
                        "name": "Locke",
                        "bio": "Empiricist",
                        "positions": "Philosopher",
                        "style": "Empirical",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Add new thinker
        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            json=[
                {
                    "name": "Hume",
                    "bio": "Skeptic",
                    "positions": "Philosopher",
                    "style": "Skeptical",
                }
            ],
            headers=auth_headers,
        )
        assert response.status_code == 200
        new_thinkers = response.json()
        assert len(new_thinkers) == 1

        new_thinker = new_thinkers[0]
        # Verify ID is set (not None)
        assert new_thinker["id"] is not None
        assert isinstance(new_thinker["id"], str)
        assert len(new_thinker["id"]) > 0

        # Verify timestamp is set
        assert new_thinker["created_at"] is not None
        assert isinstance(new_thinker["created_at"], str)

        # Verify other fields are correct
        assert new_thinker["name"] == "Hume"
        assert new_thinker["bio"] == "Skeptic"

    async def test_add_multiple_thinkers_all_have_unique_ids(self, client: AsyncClient) -> None:
        """Verify multiple thinkers added at once all get unique IDs."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Plurality",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Idealist",
                        "positions": "Philosopher",
                        "style": "Idealistic",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Add 3 thinkers at once
        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            json=[
                {
                    "name": f"Thinker {i}",
                    "bio": f"Bio {i}",
                    "positions": "Philosopher",
                    "style": "Analytical",
                }
                for i in range(3)
            ],
            headers=auth_headers,
        )
        assert response.status_code == 200
        new_thinkers = response.json()
        assert len(new_thinkers) == 3

        # Verify all have IDs
        ids = [t["id"] for t in new_thinkers]
        assert all(id is not None for id in ids)
        # Verify all IDs are unique
        assert len(set(ids)) == 3

        # Verify all have timestamps
        timestamps = [t["created_at"] for t in new_thinkers]
        assert all(ts is not None for ts in timestamps)
