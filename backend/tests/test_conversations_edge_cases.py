"""Edge case tests for conversation API endpoints.

Focus areas:
- Invalid UUIDs (malformed, non-existent)
- Boundary conditions (empty thinkers, max thinkers)
- Concurrent operations (race conditions)
- Error paths (missing data, invalid data)
- Very long inputs (topic, thinker names)
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import get_auth_headers, register_and_get_token


class TestConversationCreation:
    """Test edge cases in conversation creation."""

    @pytest.mark.asyncio
    async def test_create_conversation_with_very_long_topic(self, client: AsyncClient) -> None:
        """Test creating conversation with 1000+ character topic."""
        headers = await get_auth_headers(client, username="user_long_topic", password="testpass123")

        # Create topic with 1000 characters
        very_long_topic = "A" * 1000

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": very_long_topic,
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Greek philosopher",
                        "positions": "Question everything",
                        "style": "Socratic method",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == very_long_topic
        assert len(data["thinkers"]) == 1

    @pytest.mark.asyncio
    async def test_create_conversation_with_unicode_topic(self, client: AsyncClient) -> None:
        """Test creating conversation with unicode characters and emojis."""
        data = await register_and_get_token(client, username="user_unicode", password="testpass123")
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        # Topic with Chinese, Japanese, emojis
        unicode_topic = "哲学 🤔 と 心理学 💭: What is 意識?"

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": unicode_topic,
                "thinkers": [
                    {
                        "name": "Confucius",
                        "bio": "Chinese philosopher",
                        "positions": "Virtue ethics",
                        "style": "Analects",
                        "color": "#10b981",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == unicode_topic

    @pytest.mark.asyncio
    async def test_create_conversation_with_single_thinker(self, client: AsyncClient) -> None:
        """Test boundary: conversation with exactly 1 thinker."""
        data = await register_and_get_token(client, username="user_single", password="testpass123")
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Solo philosophy",
                "thinkers": [
                    {
                        "name": "Diogenes",
                        "bio": "Cynic philosopher",
                        "positions": "Live simply",
                        "style": "Provocative",
                        "color": "#f59e0b",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 1

    @pytest.mark.asyncio
    async def test_create_conversation_with_duplicate_thinker_names(
        self, client: AsyncClient
    ) -> None:
        """Test edge case: multiple thinkers with same name but different attributes."""
        data = await register_and_get_token(
            client, username="user_duplicates", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Multiple perspectives from similar thinkers",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Early Socrates",
                        "positions": "Virtue is knowledge",
                        "style": "Early dialogues",
                        "color": "#6366f1",
                    },
                    {
                        "name": "Socrates",
                        "bio": "Late Socrates",
                        "positions": "Know thyself",
                        "style": "Later dialogues",
                        "color": "#ec4899",
                    },
                ],
            },
        )
        # Should succeed - backend allows duplicate names (different instances)
        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 2
        assert all(t["name"] == "Socrates" for t in data["thinkers"])


class TestConversationRetrieval:
    """Test edge cases in conversation retrieval."""

    @pytest.mark.asyncio
    async def test_get_conversation_with_invalid_uuid_format(self, client: AsyncClient) -> None:
        """Test GET with malformed UUID."""
        data = await register_and_get_token(
            client, username="user_invalid_uuid", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        # Invalid UUID format
        response = await client.get("/api/conversations/not-a-valid-uuid", headers=headers)
        # FastAPI validates UUID format and returns 422 for invalid format
        assert response.status_code in [404, 422]

    @pytest.mark.asyncio
    async def test_get_conversation_with_nonexistent_uuid(self, client: AsyncClient) -> None:
        """Test GET with valid UUID format but nonexistent conversation."""
        data = await register_and_get_token(
            client, username="user_nonexistent", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        # Valid UUID format but doesn't exist
        fake_uuid = str(uuid.uuid4())
        response = await client.get(f"/api/conversations/{fake_uuid}", headers=headers)
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_conversations_when_empty(self, client: AsyncClient) -> None:
        """Test listing conversations when user has none."""
        data = await register_and_get_token(
            client, username="user_empty_list", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_conversations_with_many_conversations(self, client: AsyncClient) -> None:
        """Test listing conversations when user has many (10+)."""
        data = await register_and_get_token(
            client, username="user_many_convs", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        # Create 15 conversations
        for i in range(15):
            await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": f"Topic {i}",
                    "thinkers": [
                        {
                            "name": f"Thinker{i}",
                            "bio": f"Bio {i}",
                            "positions": f"Position {i}",
                            "style": f"Style {i}",
                            "color": "#6366f1",
                        }
                    ],
                },
            )

        # List should return all 15
        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 15
        # Verify all topics are present (order may vary if created_at is identical)
        topics = [conv["topic"] for conv in data]
        expected_topics = {f"Topic {i}" for i in range(15)}
        actual_topics = set(topics)
        assert actual_topics == expected_topics


class TestConversationDeletion:
    """Test edge cases in conversation deletion."""

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(self, client: AsyncClient) -> None:
        """Test deleting conversation that doesn't exist."""
        data = await register_and_get_token(
            client, username="user_delete_fake", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        fake_uuid = str(uuid.uuid4())
        response = await client.delete(f"/api/conversations/{fake_uuid}", headers=headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_conversation_with_malformed_uuid(self, client: AsyncClient) -> None:
        """Test delete with malformed UUID."""
        data = await register_and_get_token(
            client, username="user_delete_invalid", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        response = await client.delete("/api/conversations/not-a-uuid", headers=headers)
        # FastAPI validates UUID format
        assert response.status_code in [404, 422]

    @pytest.mark.asyncio
    async def test_delete_conversation_from_different_user(self, client: AsyncClient) -> None:
        """Test user A cannot delete user B's conversation."""
        # User A creates conversation
        data_a = await register_and_get_token(
            client, username="user_a_delete", password="testpass123"
        )
        headers_a = {"Authorization": f"Bearer {data_a['access_token']}"}

        response = await client.post(
            "/api/conversations",
            headers=headers_a,
            json={
                "topic": "User A's conversation",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Student of Socrates",
                        "positions": "Theory of Forms",
                        "style": "Dialogues",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # User B tries to delete User A's conversation
        data_b = await register_and_get_token(
            client, username="user_b_delete", password="testpass123"
        )
        headers_b = {"Authorization": f"Bearer {data_b['access_token']}"}

        response = await client.delete(f"/api/conversations/{conversation_id}", headers=headers_b)
        # Should get 404 (conversation not found for this session)
        assert response.status_code == 404


class TestMessageSending:
    """Test edge cases in message sending."""

    @pytest.mark.asyncio
    async def test_send_message_to_nonexistent_conversation(self, client: AsyncClient) -> None:
        """Test sending message to conversation that doesn't exist."""
        data = await register_and_get_token(
            client, username="user_msg_fake", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        fake_uuid = str(uuid.uuid4())
        response = await client.post(
            f"/api/conversations/{fake_uuid}/messages",
            headers=headers,
            json={"content": "Hello?"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_send_very_long_message(self, client: AsyncClient) -> None:
        """Test sending message with 10,000+ characters."""
        data = await register_and_get_token(
            client, username="user_long_msg", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Long messages",
                "thinkers": [
                    {
                        "name": "Marcus Aurelius",
                        "bio": "Roman Emperor",
                        "positions": "Stoicism",
                        "style": "Meditations",
                        "color": "#8b5cf6",
                    }
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Send very long message (10,000 characters)
        very_long_content = "A" * 10000
        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": very_long_content},
        )
        # Should succeed - no max length constraint
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == very_long_content
        assert len(data["content"]) == 10000

    @pytest.mark.asyncio
    async def test_send_message_with_special_characters(self, client: AsyncClient) -> None:
        """Test sending message with special characters, emojis, and unicode."""
        data = await register_and_get_token(
            client, username="user_special_msg", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Special characters",
                "thinkers": [
                    {
                        "name": "Laozi",
                        "bio": "Founder of Taoism",
                        "positions": "The Way",
                        "style": "Dao De Jing",
                        "color": "#10b981",
                    }
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Message with emojis, Chinese, and special chars
        special_content = "道 🌟 means 'the way' — ¿comprende? <tag> & \"quotes\""
        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": special_content},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == special_content

    @pytest.mark.asyncio
    async def test_send_message_to_other_users_conversation(self, client: AsyncClient) -> None:
        """Test user B cannot send message to user A's conversation."""
        # User A creates conversation
        data_a = await register_and_get_token(client, username="user_a_msg", password="testpass123")
        headers_a = {"Authorization": f"Bearer {data_a['access_token']}"}

        response = await client.post(
            "/api/conversations",
            headers=headers_a,
            json={
                "topic": "User A's chat",
                "thinkers": [
                    {
                        "name": "Aristotle",
                        "bio": "Student of Plato",
                        "positions": "Golden mean",
                        "style": "Systematic",
                        "color": "#ec4899",
                    }
                ],
            },
        )
        conversation_id = response.json()["id"]

        # User B tries to send message to User A's conversation
        data_b = await register_and_get_token(client, username="user_b_msg", password="testpass123")
        headers_b = {"Authorization": f"Bearer {data_b['access_token']}"}

        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers_b,
            json={"content": "Can I join?"},
        )
        # Should get 404 (conversation not found for this session)
        assert response.status_code == 404


class TestAddThinkersToConversation:
    """Test edge cases for adding thinkers to existing conversations."""

    @pytest.mark.asyncio
    async def test_add_single_thinker_to_conversation(self, client: AsyncClient) -> None:
        """Test adding one thinker to an existing conversation."""
        data = await register_and_get_token(
            client, username="user_add_thinker", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        # Create conversation with 1 thinker
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Philosophy discussion",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Greek philosopher",
                        "positions": "Question everything",
                        "style": "Socratic method",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # Add another thinker
        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Plato",
                    "bio": "Student of Socrates",
                    "positions": "Theory of Forms",
                    "style": "Dialogues",
                    "color": "#ec4899",
                }
            ],
        )
        assert response.status_code == 200
        new_thinkers = response.json()
        assert len(new_thinkers) == 1
        assert new_thinkers[0]["name"] == "Plato"

        # Verify conversation now has 2 thinkers
        get_response = await client.get(f"/api/conversations/{conversation_id}", headers=headers)
        assert get_response.status_code == 200
        assert len(get_response.json()["thinkers"]) == 2

    @pytest.mark.asyncio
    async def test_add_multiple_thinkers_to_conversation(self, client: AsyncClient) -> None:
        """Test adding multiple thinkers at once."""
        data = await register_and_get_token(
            client, username="user_add_multi", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        # Create conversation with 1 thinker
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Multi-thinker discussion",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Greek philosopher",
                        "positions": "Question everything",
                        "style": "Socratic method",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Add 2 more thinkers
        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Plato",
                    "bio": "Student of Socrates",
                    "positions": "Theory of Forms",
                    "style": "Dialogues",
                    "color": "#ec4899",
                },
                {
                    "name": "Aristotle",
                    "bio": "Student of Plato",
                    "positions": "Golden mean",
                    "style": "Systematic",
                    "color": "#10b981",
                },
            ],
        )
        assert response.status_code == 200
        new_thinkers = response.json()
        assert len(new_thinkers) == 2

    @pytest.mark.asyncio
    async def test_cannot_exceed_max_thinkers(self, client: AsyncClient) -> None:
        """Test that adding thinkers beyond the limit (5) fails."""
        data = await register_and_get_token(
            client, username="user_max_thinkers", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        # Create conversation with 4 thinkers
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Full discussion",
                "thinkers": [
                    {
                        "name": f"Thinker{i}",
                        "bio": f"Bio {i}",
                        "positions": f"Position {i}",
                        "style": f"Style {i}",
                        "color": "#6366f1",
                    }
                    for i in range(4)
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Try to add 2 more (would make 6 total)
        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Extra1",
                    "bio": "Extra bio",
                    "positions": "Extra position",
                    "style": "Extra style",
                    "color": "#f59e0b",
                },
                {
                    "name": "Extra2",
                    "bio": "Extra bio 2",
                    "positions": "Extra position 2",
                    "style": "Extra style 2",
                    "color": "#8b5cf6",
                },
            ],
        )
        assert response.status_code == 400
        assert "Maximum is 5" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_add_thinker_to_nonexistent_conversation(self, client: AsyncClient) -> None:
        """Test adding thinkers to a conversation that doesn't exist."""
        data = await register_and_get_token(
            client, username="user_add_nonexist", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        fake_uuid = str(uuid.uuid4())
        response = await client.put(
            f"/api/conversations/{fake_uuid}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Orphan Thinker",
                    "bio": "No home",
                    "positions": "Lost",
                    "style": "Wandering",
                    "color": "#6366f1",
                }
            ],
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_add_thinker_to_other_users_conversation(
        self, client: AsyncClient
    ) -> None:
        """Test that user B cannot add thinkers to user A's conversation."""
        # User A creates conversation
        data_a = await register_and_get_token(client, username="user_a_add", password="testpass123")
        headers_a = {"Authorization": f"Bearer {data_a['access_token']}"}

        conv_response = await client.post(
            "/api/conversations",
            headers=headers_a,
            json={
                "topic": "User A's private chat",
                "thinkers": [
                    {
                        "name": "Private Thinker",
                        "bio": "Only for A",
                        "positions": "Private",
                        "style": "Exclusive",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # User B tries to add thinker
        data_b = await register_and_get_token(client, username="user_b_add", password="testpass123")
        headers_b = {"Authorization": f"Bearer {data_b['access_token']}"}

        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers_b,
            json=[
                {
                    "name": "Intruder",
                    "bio": "Uninvited",
                    "positions": "None",
                    "style": "Sneaky",
                    "color": "#ff0000",
                }
            ],
        )
        # Should get 404 (conversation not found for this session)
        assert response.status_code == 404
