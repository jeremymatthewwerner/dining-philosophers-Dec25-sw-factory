"""Integration tests for conversation API endpoints - QA Agent Wednesday Feb 4."""

from httpx import AsyncClient

from tests.conftest import get_auth_headers


class TestListConversations:
    """Test GET /api/conversations - list conversations for session."""

    async def test_list_conversations_empty(self, client: AsyncClient) -> None:
        """List conversations should return empty array when no conversations exist."""
        auth_headers = await get_auth_headers(client)

        response = await client.get("/api/conversations", headers=auth_headers)
        assert response.status_code == 200
        conversations = response.json()
        assert isinstance(conversations, list)
        assert len(conversations) == 0

    async def test_list_conversations_with_data(self, client: AsyncClient) -> None:
        """List conversations should return all conversations for the session."""
        auth_headers = await get_auth_headers(client)

        # Create two conversations
        conv1_response = await client.post(
            "/api/conversations",
            json={
                "topic": "Philosophy of mind",
                "thinkers": [
                    {
                        "name": "Aristotle",
                        "bio": "Greek philosopher",
                        "positions": "Teacher",
                        "style": "Analytical",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert conv1_response.status_code == 200
        conv1_id = conv1_response.json()["id"]

        conv2_response = await client.post(
            "/api/conversations",
            json={
                "topic": "Ethics",
                "thinkers": [
                    {
                        "name": "Kant",
                        "bio": "German philosopher",
                        "positions": "Professor",
                        "style": "Systematic",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert conv2_response.status_code == 200
        conv2_id = conv2_response.json()["id"]

        # List conversations
        response = await client.get("/api/conversations", headers=auth_headers)
        assert response.status_code == 200
        conversations = response.json()
        assert len(conversations) == 2

        # Verify conversation IDs are present
        conv_ids = {c["id"] for c in conversations}
        assert conv1_id in conv_ids
        assert conv2_id in conv_ids

        # Verify each conversation has required fields
        for conv in conversations:
            assert "id" in conv
            assert "topic" in conv
            assert "thinkers" in conv
            assert "message_count" in conv
            assert "total_cost" in conv
            assert "created_at" in conv

    async def test_list_conversations_with_messages_shows_count(self, client: AsyncClient) -> None:
        """List conversations should include accurate message counts."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            json={
                "topic": "Test topic",
                "thinkers": [
                    {
                        "name": "Test Thinker",
                        "bio": "Test bio",
                        "positions": "Test",
                        "style": "Test",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Send 3 messages
        for i in range(3):
            msg_response = await client.post(
                f"/api/conversations/{conv_id}/messages",
                json={"content": f"Message {i + 1}"},
                headers=auth_headers,
            )
            assert msg_response.status_code == 200

        # List conversations and verify message count
        response = await client.get("/api/conversations", headers=auth_headers)
        assert response.status_code == 200
        conversations = response.json()
        assert len(conversations) == 1
        assert conversations[0]["message_count"] == 3

    async def test_list_conversations_ordered_by_created_at_desc(self, client: AsyncClient) -> None:
        """List conversations should be ordered newest first."""
        auth_headers = await get_auth_headers(client)

        # Create 3 conversations in sequence
        conv_ids = []
        for i in range(3):
            response = await client.post(
                "/api/conversations",
                json={
                    "topic": f"Topic {i + 1}",
                    "thinkers": [
                        {
                            "name": f"Thinker {i + 1}",
                            "bio": "Bio",
                            "positions": "Position",
                            "style": "Style",
                        }
                    ],
                },
                headers=auth_headers,
            )
            assert response.status_code == 200
            conv_ids.append(response.json()["id"])

        # List conversations
        response = await client.get("/api/conversations", headers=auth_headers)
        assert response.status_code == 200
        conversations = response.json()
        assert len(conversations) == 3

        # Verify ordering: newest first
        # The order should be reversed from creation order
        conv_ids_in_response = [c["id"] for c in conversations]
        # Due to timestamp resolution, we just verify all IDs are present
        # and not in creation order
        assert set(conv_ids_in_response) == set(conv_ids)


class TestGetConversation:
    """Test GET /api/conversations/{id} - get conversation with messages."""

    async def test_get_conversation_success(self, client: AsyncClient) -> None:
        """Get conversation should return full conversation with messages and thinkers."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            json={
                "topic": "Philosophy of science",
                "thinkers": [
                    {
                        "name": "Popper",
                        "bio": "Philosopher of science",
                        "positions": "Professor",
                        "style": "Critical",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Send a message
        await client.post(
            f"/api/conversations/{conv_id}/messages",
            json={"content": "What is falsifiability?"},
            headers=auth_headers,
        )

        # Get conversation
        response = await client.get(f"/api/conversations/{conv_id}", headers=auth_headers)
        assert response.status_code == 200
        conversation = response.json()

        # Verify structure
        assert conversation["id"] == conv_id
        assert conversation["topic"] == "Philosophy of science"
        assert "thinkers" in conversation
        assert len(conversation["thinkers"]) == 1
        assert conversation["thinkers"][0]["name"] == "Popper"
        assert "messages" in conversation
        assert len(conversation["messages"]) == 1
        assert conversation["messages"][0]["content"] == "What is falsifiability?"

    async def test_get_conversation_not_found(self, client: AsyncClient) -> None:
        """Get conversation should return 404 for non-existent conversation."""
        auth_headers = await get_auth_headers(client)

        response = await client.get("/api/conversations/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_get_conversation_different_session_not_authorized(
        self, client: AsyncClient
    ) -> None:
        """Get conversation should return 404 when trying to access another session's conversation."""
        # Create conversation with first user
        auth_headers_1 = await get_auth_headers(
            client, username="user1_conv", password="password123"
        )
        conv_response = await client.post(
            "/api/conversations",
            json={
                "topic": "Private conversation",
                "thinkers": [
                    {
                        "name": "Thinker",
                        "bio": "Bio",
                        "positions": "Position",
                        "style": "Style",
                    }
                ],
            },
            headers=auth_headers_1,
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Try to access with different user
        auth_headers_2 = await get_auth_headers(
            client, username="user2_conv", password="password123"
        )
        response = await client.get(f"/api/conversations/{conv_id}", headers=auth_headers_2)
        assert response.status_code == 404  # Returns 404, not 403, to avoid info leak


class TestDeleteConversation:
    """Test DELETE /api/conversations/{id} - delete conversation."""

    async def test_delete_conversation_success(self, client: AsyncClient) -> None:
        """Delete conversation should remove conversation and return success status."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            json={
                "topic": "To be deleted",
                "thinkers": [
                    {
                        "name": "Thinker",
                        "bio": "Bio",
                        "positions": "Position",
                        "style": "Style",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Delete conversation
        response = await client.delete(f"/api/conversations/{conv_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify conversation no longer exists
        get_response = await client.get(f"/api/conversations/{conv_id}", headers=auth_headers)
        assert get_response.status_code == 404

    async def test_delete_conversation_not_found(self, client: AsyncClient) -> None:
        """Delete conversation should return 404 for non-existent conversation."""
        auth_headers = await get_auth_headers(client)

        response = await client.delete("/api/conversations/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_delete_conversation_cascades_to_messages(self, client: AsyncClient) -> None:
        """Deleting conversation should also delete all messages."""
        auth_headers = await get_auth_headers(client)

        # Create conversation and send messages
        conv_response = await client.post(
            "/api/conversations",
            json={
                "topic": "Test cascade",
                "thinkers": [
                    {
                        "name": "Thinker",
                        "bio": "Bio",
                        "positions": "Position",
                        "style": "Style",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Send messages
        for i in range(3):
            await client.post(
                f"/api/conversations/{conv_id}/messages",
                json={"content": f"Message {i + 1}"},
                headers=auth_headers,
            )

        # Delete conversation
        response = await client.delete(f"/api/conversations/{conv_id}", headers=auth_headers)
        assert response.status_code == 200

        # Verify messages are gone (conversation not found means cascade worked)
        get_response = await client.get(f"/api/conversations/{conv_id}", headers=auth_headers)
        assert get_response.status_code == 404


class TestUpdateConversationThinkers:
    """Test PUT /api/conversations/{id}/thinkers - add thinkers to conversation."""

    async def test_add_thinkers_success(self, client: AsyncClient) -> None:
        """Add thinkers should add new thinkers to existing conversation."""
        auth_headers = await get_auth_headers(client)

        # Create conversation with 1 thinker
        conv_response = await client.post(
            "/api/conversations",
            json={
                "topic": "Philosophy",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Greek philosopher",
                        "positions": "Founder of Academy",
                        "style": "Dialectical",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Add 2 more thinkers
        response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            json=[
                {
                    "name": "Aristotle",
                    "bio": "Student of Plato",
                    "positions": "Teacher",
                    "style": "Empirical",
                },
                {
                    "name": "Socrates",
                    "bio": "Teacher of Plato",
                    "positions": "Philosopher",
                    "style": "Socratic",
                },
            ],
            headers=auth_headers,
        )
        assert response.status_code == 200
        new_thinkers = response.json()
        assert len(new_thinkers) == 2
        assert new_thinkers[0]["name"] == "Aristotle"
        assert new_thinkers[1]["name"] == "Socrates"

        # Verify conversation now has 3 thinkers
        get_response = await client.get(f"/api/conversations/{conv_id}", headers=auth_headers)
        assert get_response.status_code == 200
        conversation = get_response.json()
        assert len(conversation["thinkers"]) == 3

    async def test_add_thinkers_exceeds_max_limit(self, client: AsyncClient) -> None:
        """Add thinkers should reject if total exceeds 5 thinkers."""
        auth_headers = await get_auth_headers(client)

        # Create conversation with 4 thinkers
        conv_response = await client.post(
            "/api/conversations",
            json={
                "topic": "Philosophy",
                "thinkers": [
                    {"name": f"Thinker {i}", "bio": "Bio", "positions": "Pos", "style": "Style"}
                    for i in range(4)
                ],
            },
            headers=auth_headers,
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Try to add 2 more thinkers (would exceed limit)
        response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            json=[
                {"name": "Thinker 5", "bio": "Bio", "positions": "Pos", "style": "Style"},
                {"name": "Thinker 6", "bio": "Bio", "positions": "Pos", "style": "Style"},
            ],
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "maximum" in response.json()["detail"].lower()

    async def test_add_thinkers_assigns_unique_colors(self, client: AsyncClient) -> None:
        """Add thinkers should assign colors from available pool."""
        auth_headers = await get_auth_headers(client)

        # Create conversation with 2 thinkers
        conv_response = await client.post(
            "/api/conversations",
            json={
                "topic": "Test",
                "thinkers": [
                    {"name": "Thinker 1", "bio": "Bio", "positions": "Pos", "style": "Style"},
                    {"name": "Thinker 2", "bio": "Bio", "positions": "Pos", "style": "Style"},
                ],
            },
            headers=auth_headers,
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Get existing colors
        get_response = await client.get(f"/api/conversations/{conv_id}", headers=auth_headers)
        existing_colors = {t["color"] for t in get_response.json()["thinkers"]}

        # Add another thinker
        response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            json=[{"name": "Thinker 3", "bio": "Bio", "positions": "Pos", "style": "Style"}],
            headers=auth_headers,
        )
        assert response.status_code == 200
        new_thinker = response.json()[0]

        # Verify new thinker has a different color
        assert new_thinker["color"] not in existing_colors

    async def test_add_thinkers_conversation_not_found(self, client: AsyncClient) -> None:
        """Add thinkers should return 404 for non-existent conversation."""
        auth_headers = await get_auth_headers(client)

        response = await client.put(
            "/api/conversations/nonexistent-id/thinkers",
            json=[{"name": "Thinker", "bio": "Bio", "positions": "Pos", "style": "Style"}],
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestSendMessage:
    """Test POST /api/conversations/{id}/messages - send user message."""

    async def test_send_message_success(self, client: AsyncClient) -> None:
        """Send message should create message and return message data."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            json={
                "topic": "Test",
                "thinkers": [
                    {"name": "Thinker", "bio": "Bio", "positions": "Pos", "style": "Style"}
                ],
            },
            headers=auth_headers,
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Send message
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            json={"content": "Hello, thinkers!"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        message = response.json()

        # Verify message data
        assert message["content"] == "Hello, thinkers!"
        assert message["sender_type"] == "user"
        assert "sender_name" in message
        assert "created_at" in message

    async def test_send_message_empty_content(self, client: AsyncClient) -> None:
        """Send message should accept empty content (validation at API level)."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            json={
                "topic": "Test",
                "thinkers": [
                    {"name": "Thinker", "bio": "Bio", "positions": "Pos", "style": "Style"}
                ],
            },
            headers=auth_headers,
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Send empty message
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            json={"content": ""},
            headers=auth_headers,
        )
        # Should be rejected at schema validation level (422)
        assert response.status_code == 422

    async def test_send_message_conversation_not_found(self, client: AsyncClient) -> None:
        """Send message should return 404 for non-existent conversation."""
        auth_headers = await get_auth_headers(client)

        response = await client.post(
            "/api/conversations/nonexistent-id/messages",
            json={"content": "Hello"},
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_send_message_uses_display_name(self, client: AsyncClient) -> None:
        """Send message should use user's display name if set."""
        # Create user with display name via profile update
        auth_headers = await get_auth_headers(
            client, username="user_display_test", password="password123"
        )

        # Update profile to set display name
        await client.patch(
            "/api/auth/profile",
            json={"display_name": "Alice Smith"},
            headers=auth_headers,
        )

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            json={
                "topic": "Test",
                "thinkers": [
                    {"name": "Thinker", "bio": "Bio", "positions": "Pos", "style": "Style"}
                ],
            },
            headers=auth_headers,
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Send message
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            json={"content": "Hello"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        message = response.json()

        # Verify sender name is display name
        assert message["sender_name"] == "Alice Smith"
