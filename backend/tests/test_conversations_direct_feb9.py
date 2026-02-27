"""Direct integration tests for conversation API - Feb 9 2026.

Target: app/api/conversations.py (39% -> 60%+)

These tests minimize mocking to ensure actual code paths are executed.
Focused on lines that other tests haven't covered:
- 46-61: Thinker creation loop with color cycling
- 67: Return conversation after refresh
- 85-105: List conversations with cost calculation
- 126-129, 145-151: Error handling paths
- 173-180, 189, 193-220: Add thinkers logic
- 241-268: Send message with idle handling
"""

from httpx import AsyncClient

from tests.conftest import get_auth_headers


class TestCreateConversationIntegration:
    """Integration tests for create_conversation without heavy mocking."""

    async def test_create_with_multiple_thinkers_different_colors(
        self, client: AsyncClient
    ) -> None:
        """Test creating conversation with multiple thinkers gets different colors.

        This hits lines 46-61 (thinker creation loop) and 67 (return statement).
        """
        headers = await get_auth_headers(client, username="multicolor_user", password="testpass123")

        # Create conversation with 3 thinkers, all using default color
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Philosophy discussion",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Classical Greek philosopher",
                        "positions": "Questioning assumptions",
                        "style": "Socratic method",
                        "color": "#6366f1",  # Default - will cycle
                    },
                    {
                        "name": "Plato",
                        "bio": "Student of Socrates",
                        "positions": "Theory of Forms",
                        "style": "Dialectic",
                        "color": "#6366f1",  # Default - will cycle
                    },
                    {
                        "name": "Aristotle",
                        "bio": "Student of Plato",
                        "positions": "Empiricism",
                        "style": "Logical",
                        "color": "#6366f1",  # Default - will cycle
                    },
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify conversation was created with thinkers
        assert "id" in data
        assert len(data["thinkers"]) == 3

        # Verify each thinker has a different color (lines 46-61)
        colors = [t["color"] for t in data["thinkers"]]
        assert len(set(colors)) == 3, "Each thinker should have a unique color"

        # Verify all colors are from the palette
        palette = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]
        for color in colors:
            assert color in palette


class TestListConversationsIntegration:
    """Integration tests for list_conversations with cost calculations."""

    async def test_list_with_messages_shows_cost_and_count(self, client: AsyncClient) -> None:
        """Test list conversations includes message count and total cost.

        This hits lines 85-105 (query execution, cost calculation, summary building).
        """
        headers = await get_auth_headers(client, username="list_cost_user", password="testpass123")

        # Create a conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Cost tracking",
                "thinkers": [
                    {
                        "name": "Epicurus",
                        "bio": "Ancient Greek philosopher",
                        "positions": "Hedonism",
                        "style": "Pleasure-focused",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # Send a user message
        await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "What is the good life?"},
        )

        # List conversations - this exercises lines 76-105
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200

        conversations = list_response.json()
        assert len(conversations) > 0

        # Find our conversation
        conv = next(c for c in conversations if c["id"] == conversation_id)

        # Verify message_count and total_cost are populated (lines 91-104)
        assert "message_count" in conv
        assert conv["message_count"] >= 1
        assert "total_cost" in conv
        assert isinstance(conv["total_cost"], (int, float))


class TestGetAndDeleteConversation:
    """Integration tests for get and delete endpoints."""

    async def test_get_nonexistent_conversation_404(self, client: AsyncClient) -> None:
        """Test getting non-existent conversation returns 404.

        This hits lines 126-129 (error handling).
        """
        headers = await get_auth_headers(client, username="get_404_test", password="testpass123")

        response = await client.get(
            "/api/conversations/does-not-exist-uuid",
            headers=headers,
        )

        # Lines 127-128: check for None and raise 404
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_delete_nonexistent_conversation_404(self, client: AsyncClient) -> None:
        """Test deleting non-existent conversation returns 404.

        This hits lines 145-147 (error handling).
        """
        headers = await get_auth_headers(client, username="del_404_test", password="testpass123")

        response = await client.delete(
            "/api/conversations/does-not-exist-uuid",
            headers=headers,
        )

        # Lines 146-147: check for None and raise 404
        assert response.status_code == 404

    async def test_delete_conversation_success_returns_status(self, client: AsyncClient) -> None:
        """Test successful delete returns status dict.

        This hits line 151 (return statement).
        """
        headers = await get_auth_headers(
            client, username="del_success_test", password="testpass123"
        )

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "To be deleted",
                "thinkers": [
                    {
                        "name": "Diogenes",
                        "bio": "Cynic philosopher",
                        "positions": "Living simply",
                        "style": "Provocative",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Delete it
        del_response = await client.delete(
            f"/api/conversations/{conversation_id}",
            headers=headers,
        )

        # Line 151: return {"status": "deleted"}
        assert del_response.status_code == 200
        data = del_response.json()
        assert data["status"] == "deleted"


class TestAddThinkersIntegration:
    """Integration tests for add_thinkers endpoint."""

    async def test_add_thinkers_max_limit_validation(self, client: AsyncClient) -> None:
        """Test that adding too many thinkers is rejected.

        This hits lines 173-185 (max thinkers validation).
        """
        headers = await get_auth_headers(client, username="max_limit_test", password="testpass123")

        # Create conversation with 5 thinkers (max)
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Full house",
                "thinkers": [
                    {
                        "name": f"Thinker {i}",
                        "bio": f"Bio {i}",
                        "positions": f"Positions {i}",
                        "style": f"Style {i}",
                        "color": "#6366f1",
                    }
                    for i in range(5)
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Try to add one more thinker
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Extra Thinker",
                    "bio": "Should be rejected",
                    "positions": "Overflow",
                    "style": "Rejected",
                    "color": "#6366f1",
                }
            ],
        )

        # Lines 179-185: reject with 400
        assert add_response.status_code == 400
        assert "cannot add" in add_response.json()["detail"].lower()
        assert "5 total" in add_response.json()["detail"].lower()

    async def test_add_thinkers_avoids_existing_colors(self, client: AsyncClient) -> None:
        """Test that adding thinkers avoids colors already in use.

        This hits lines 188-220 (color selection and thinker creation).
        """
        headers = await get_auth_headers(
            client, username="color_avoid_test", password="testpass123"
        )

        # Create conversation with 2 thinkers
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Color coordination",
                "thinkers": [
                    {
                        "name": "Marcus Aurelius",
                        "bio": "Stoic emperor",
                        "positions": "Virtue ethics",
                        "style": "Meditative",
                        "color": "#6366f1",
                    },
                    {
                        "name": "Seneca",
                        "bio": "Stoic philosopher",
                        "positions": "Practical wisdom",
                        "style": "Epistolary",
                        "color": "#ec4899",
                    },
                ],
            },
        )
        conversation_id = conv_response.json()["id"]
        existing_colors = [t["color"] for t in conv_response.json()["thinkers"]]

        # Add 2 more thinkers with default color
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Epictetus",
                    "bio": "Former slave, Stoic teacher",
                    "positions": "Focus on what you control",
                    "style": "Direct",
                    "color": "#6366f1",  # Default - should get available color
                },
                {
                    "name": "Zeno",
                    "bio": "Founder of Stoicism",
                    "positions": "Living in harmony with nature",
                    "style": "Systematic",
                    "color": "#6366f1",  # Default - should get available color
                },
            ],
        )

        assert add_response.status_code == 200
        new_thinkers = add_response.json()

        # Lines 188-199: calculate available colors and assign them
        new_colors = [t["color"] for t in new_thinkers]
        for color in new_colors:
            assert color not in existing_colors, "New thinkers should not reuse existing colors"


class TestSendMessageIntegration:
    """Integration tests for send_message endpoint."""

    async def test_send_message_creates_message_with_sender_name(self, client: AsyncClient) -> None:
        """Test that sending a message creates it with proper sender_name.

        This hits lines 257-268 (sender_name determination and message creation).
        """
        headers = await get_auth_headers(client, username="sendmsg_test", password="testpass123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Message sending test",
                "thinkers": [
                    {
                        "name": "Hypatia",
                        "bio": "Mathematician and philosopher",
                        "positions": "Neoplatonism",
                        "style": "Analytical",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Send message
        msg_response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Tell me about mathematics and philosophy"},
        )

        assert msg_response.status_code == 200
        message = msg_response.json()

        # Lines 257-268: sender_name is set from user.display_name or user.username
        assert "sender_name" in message
        assert message["sender_name"] == "Sendmsg_Test"  # username.title() from helper
        assert message["content"] == "Tell me about mathematics and philosophy"
        assert message["sender_type"] == "user"
