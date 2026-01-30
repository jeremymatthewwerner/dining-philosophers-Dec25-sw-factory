"""Comprehensive tests for conversation API endpoints.

This file consolidates tests previously spread across:
- test_conversations_coverage_sprint.py
- test_conversations_direct_coverage.py
- test_conversations_flaky_hunt.py

Organization:
- TestConversationCRUD: Create, Read, Update, Delete operations
- TestConversationColors: Color assignment and management
- TestConversationMessages: Message sending and display names
- TestConversationLimits: Max thinker limits and validation
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.conftest import create_thinker_input, get_auth_headers


# Mock knowledge_research.trigger_research for all tests in this module
@pytest.fixture(autouse=True)
def mock_knowledge_research():
    """Mock knowledge research trigger for all conversation tests."""
    with patch("app.services.knowledge_research.knowledge_service.trigger_research") as mock:
        mock.return_value = None
        yield mock


class TestConversationCRUD:
    """Test core CRUD operations for conversations."""

    @pytest.mark.asyncio
    async def test_create_conversation_with_single_thinker(self, client: AsyncClient) -> None:
        """Test creating a conversation with one thinker."""
        headers = await get_auth_headers(client, "crud_create_1", "password123")

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Single Thinker Test",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Ancient Greek philosopher",
                        "positions": "Question everything",
                        "style": "Socratic method",
                        "color": "#6366f1",
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 1
        assert data["topic"] == "Single Thinker Test"

    @pytest.mark.asyncio
    async def test_create_conversation_with_multiple_thinkers(self, client: AsyncClient) -> None:
        """Test creating a conversation with multiple thinkers."""
        headers = await get_auth_headers(client, "crud_create_multi", "password123")

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Three Thinkers",
                "thinkers": [
                    create_thinker_input("Socrates", "Greek philosopher"),
                    create_thinker_input("Plato", "Student of Socrates"),
                    create_thinker_input("Aristotle", "Student of Plato"),
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 3

    @pytest.mark.asyncio
    async def test_get_conversation(self, client: AsyncClient) -> None:
        """Test retrieving a conversation."""
        headers = await get_auth_headers(client, "crud_get", "password123")

        # Create conversation
        create_resp = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Get Test",
                "thinkers": [create_thinker_input("Socrates", "Greek")],
            },
        )
        conv_id = create_resp.json()["id"]

        # Get conversation
        get_resp = await client.get(f"/api/conversations/{conv_id}", headers=headers)
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == conv_id
        assert data["topic"] == "Get Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation_returns_404(self, client: AsyncClient) -> None:
        """Test getting a non-existent conversation returns 404."""
        headers = await get_auth_headers(client, "crud_get_404", "password123")

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/conversations/{fake_id}", headers=headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_conversations(self, client: AsyncClient) -> None:
        """Test listing conversations."""
        headers = await get_auth_headers(client, "crud_list", "password123")

        # Create conversation
        await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "List Test",
                "thinkers": [create_thinker_input("Plato", "Greek")],
            },
        )

        # List conversations
        list_resp = await client.get("/api/conversations", headers=headers)
        assert list_resp.status_code == 200
        conversations = list_resp.json()
        assert len(conversations) >= 1

    @pytest.mark.asyncio
    async def test_list_conversations_empty_for_new_user(self, client: AsyncClient) -> None:
        """Test listing conversations returns empty array for new users."""
        headers = await get_auth_headers(client, "crud_empty_list", "password123")

        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_conversations_includes_message_count(self, client: AsyncClient) -> None:
        """Test that listed conversations include message count."""
        headers = await get_auth_headers(client, "crud_msg_count", "password123")

        # Create conversation
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Count Test",
                "thinkers": [create_thinker_input("Socrates", "Greek")],
            },
        )
        conv_id = conv_resp.json()["id"]

        # Send messages
        for i in range(3):
            await client.post(
                f"/api/conversations/{conv_id}/messages",
                headers=headers,
                json={"content": f"Message {i}"},
            )

        # List and verify message count
        list_resp = await client.get("/api/conversations", headers=headers)
        conversations = list_resp.json()
        our_conv = next(c for c in conversations if c["id"] == conv_id)
        assert our_conv["message_count"] == 3

    @pytest.mark.asyncio
    async def test_list_conversations_includes_total_cost(self, client: AsyncClient) -> None:
        """Test that listed conversations include total cost."""
        headers = await get_auth_headers(client, "crud_cost", "password123")

        # Create conversation and send message
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Cost Test",
                "thinkers": [create_thinker_input("Plato", "Greek")],
            },
        )
        conv_id = conv_resp.json()["id"]

        await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Test"},
        )

        # List and verify cost
        list_resp = await client.get("/api/conversations", headers=headers)
        conversations = list_resp.json()
        our_conv = next(c for c in conversations if c["id"] == conv_id)
        assert "total_cost" in our_conv
        assert our_conv["total_cost"] == 0.0  # User messages have no cost

    @pytest.mark.asyncio
    async def test_delete_conversation(self, client: AsyncClient) -> None:
        """Test deleting a conversation."""
        headers = await get_auth_headers(client, "crud_delete", "password123")

        # Create conversation
        create_resp = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Delete Test",
                "thinkers": [create_thinker_input("Aristotle", "Greek")],
            },
        )
        conv_id = create_resp.json()["id"]

        # Delete conversation
        delete_resp = await client.delete(f"/api/conversations/{conv_id}", headers=headers)
        assert delete_resp.status_code == 200

        # Verify deleted
        get_resp = await client.get(f"/api/conversations/{conv_id}", headers=headers)
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation_returns_404(self, client: AsyncClient) -> None:
        """Test deleting a non-existent conversation returns 404."""
        headers = await get_auth_headers(client, "crud_del_404", "password123")

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(f"/api/conversations/{fake_id}", headers=headers)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestConversationColors:
    """Test color assignment and management for thinkers."""

    @pytest.mark.asyncio
    async def test_default_colors_assigned_from_array(self, client: AsyncClient) -> None:
        """Test thinkers with default color get assigned from color array."""
        headers = await get_auth_headers(client, "colors_default", "password123")

        # Create conversation with 3 thinkers all using default color
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Color assignment test",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Greek philosopher",
                        "positions": "Question everything",
                        "style": "Socratic method",
                        "color": "#6366f1",  # Default color
                    },
                    {
                        "name": "Plato",
                        "bio": "Student of Socrates",
                        "positions": "Theory of Forms",
                        "style": "Dialogues",
                        "color": "#6366f1",  # Default color
                    },
                    {
                        "name": "Aristotle",
                        "bio": "Student of Plato",
                        "positions": "Golden mean",
                        "style": "Systematic",
                        "color": "#6366f1",  # Default color
                    },
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        thinkers = data["thinkers"]

        # Verify colors were assigned from array, not all default
        colors = [t["color"] for t in thinkers]
        assert len(set(colors)) == 3  # All unique
        assert colors[0] == "#6366f1"
        assert colors[1] == "#ec4899"
        assert colors[2] == "#10b981"

    @pytest.mark.asyncio
    async def test_custom_colors_preserved(self, client: AsyncClient) -> None:
        """Test custom (non-default) colors are preserved."""
        headers = await get_auth_headers(client, "colors_custom", "password123")

        custom_color = "#ff6600"
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Custom color test",
                "thinkers": [
                    {
                        "name": "Custom Thinker",
                        "bio": "Has custom color",
                        "positions": "Unique",
                        "style": "Distinctive",
                        "color": custom_color,
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["thinkers"][0]["color"] == custom_color

    @pytest.mark.asyncio
    async def test_add_thinker_picks_available_color(self, client: AsyncClient) -> None:
        """Test that adding thinkers picks from available colors."""
        headers = await get_auth_headers(client, "colors_add", "password123")

        # Create conversation with 2 thinkers
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Color availability test",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Greek",
                        "positions": "Questions",
                        "style": "Socratic",
                        "color": "#6366f1",
                    },
                    {
                        "name": "Plato",
                        "bio": "Greek",
                        "positions": "Forms",
                        "style": "Dialogue",
                        "color": "#ec4899",
                    },
                ],
            },
        )
        conv_id = conv_resp.json()["id"]

        # Add a new thinker with default color
        response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Aristotle",
                    "bio": "Greek",
                    "positions": "Logic",
                    "style": "Lectures",
                    "color": "#6366f1",  # Default - should pick from available
                }
            ],
        )

        assert response.status_code == 200
        new_thinker = response.json()[0]

        # Should get a color different from the existing two
        assert new_thinker["color"] not in ["#6366f1", "#ec4899"]
        assert new_thinker["color"] in ["#10b981", "#f59e0b", "#8b5cf6"]


class TestConversationMessages:
    """Test message sending and display names."""

    @pytest.mark.asyncio
    async def test_send_message(self, client: AsyncClient) -> None:
        """Test sending a message creates a user message."""
        headers = await get_auth_headers(client, "msg_send", "password123")

        # Create conversation
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Send Test",
                "thinkers": [create_thinker_input("Aristotle", "Greek")],
            },
        )
        conv_id = conv_resp.json()["id"]

        # Send message
        msg_resp = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Hello!"},
        )

        assert msg_resp.status_code == 200
        message = msg_resp.json()
        assert message["content"] == "Hello!"
        assert message["sender_type"] == "user"

    @pytest.mark.asyncio
    async def test_send_message_to_nonexistent_conversation_returns_404(
        self, client: AsyncClient
    ) -> None:
        """Test sending to non-existent conversation returns 404."""
        headers = await get_auth_headers(client, "msg_404", "password123")

        fake_id = "00000000-0000-0000-0000-000000000000"
        msg_resp = await client.post(
            f"/api/conversations/{fake_id}/messages",
            headers=headers,
            json={"content": "Test"},
        )

        assert msg_resp.status_code == 404
        assert "not found" in msg_resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_send_message_uses_display_name(self, client: AsyncClient) -> None:
        """Test that messages use user's display_name when available."""
        # Register with display_name
        reg_resp = await client.post(
            "/api/auth/register",
            json={
                "username": "msg_display",
                "password": "password123",
                "display_name": "Display Name",
                "language_preference": "en",
            },
        )
        token = reg_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create conversation
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Display name test",
                "thinkers": [create_thinker_input("Socrates", "Greek")],
            },
        )
        conv_id = conv_resp.json()["id"]

        # Send message
        msg_resp = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Test message"},
        )

        assert msg_resp.status_code == 200
        message = msg_resp.json()
        assert message["sender_name"] == "Display Name"
        assert message["sender_name"] != "msg_display"

    @pytest.mark.asyncio
    async def test_send_message_falls_back_to_username(self, client: AsyncClient) -> None:
        """Test that messages fall back to username when display_name equals username."""
        # Register with username as display_name
        reg_resp = await client.post(
            "/api/auth/register",
            json={
                "username": "msg_fallback",
                "password": "password123",
                "display_name": "msg_fallback",  # Same as username
                "language_preference": "en",
            },
        )
        token = reg_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create conversation
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Fallback test",
                "thinkers": [create_thinker_input("Plato", "Greek")],
            },
        )
        conv_id = conv_resp.json()["id"]

        # Send message
        msg_resp = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Test fallback"},
        )

        assert msg_resp.status_code == 200
        message = msg_resp.json()
        assert message["sender_name"] == "msg_fallback"


class TestConversationLimits:
    """Test max thinker limits and validation."""

    @pytest.mark.asyncio
    async def test_add_thinkers_to_nonexistent_conversation_returns_404(
        self, client: AsyncClient
    ) -> None:
        """Test adding thinkers to non-existent conversation returns 404."""
        headers = await get_auth_headers(client, "limits_add_404", "password123")

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.put(
            f"/api/conversations/{fake_id}/thinkers",
            headers=headers,
            json=[create_thinker_input("Aristotle", "Greek")],
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_add_thinkers_exceeding_max_limit_returns_400(self, client: AsyncClient) -> None:
        """Test adding thinkers beyond the 5 thinker limit returns 400."""
        headers = await get_auth_headers(client, "limits_max", "password123")

        # Create conversation with 3 thinkers
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Max Thinkers Test",
                "thinkers": [
                    create_thinker_input("Socrates", "Greek"),
                    create_thinker_input("Plato", "Greek"),
                    create_thinker_input("Aristotle", "Greek"),
                ],
            },
        )
        conv_id = conv_resp.json()["id"]

        # Try to add 3 more thinkers (would exceed 5 total)
        response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                create_thinker_input("Kant", "German"),
                create_thinker_input("Hegel", "German"),
                create_thinker_input("Nietzsche", "German"),
            ],
        )

        assert response.status_code == 400
        error_msg = response.json()["detail"]
        assert "cannot add" in error_msg.lower()
        assert "3/5" in error_msg.lower()
        assert "maximum is 5" in error_msg.lower()
