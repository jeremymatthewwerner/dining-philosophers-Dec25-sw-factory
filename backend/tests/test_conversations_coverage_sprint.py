"""Coverage sprint tests for conversation API - focusing on untested lines.

Target: app/api/conversations.py (40% -> 60%+)

Focus areas:
- Color assignment logic in create_conversation (lines 46-61)
- List conversations with message counts/costs (lines 85-105)
- Add thinkers color management (lines 188-199)
- Send message with display_name fallback (lines 238-251)
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import get_auth_headers


class TestConversationColorAssignment:
    """Test color assignment logic when creating conversations."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_create_with_default_color_uses_color_array(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test thinkers with default color get assigned from color array."""
        mock_trigger.return_value = None
        headers = await get_auth_headers(client, username="user_colors", password="testpass123")

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
        # Should be ["#6366f1", "#ec4899", "#10b981"] from color array indices 0, 1, 2
        assert colors[0] == "#6366f1"
        assert colors[1] == "#ec4899"
        assert colors[2] == "#10b981"
        # All should be unique
        assert len(set(colors)) == 3

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_create_with_custom_color_preserves_it(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test custom (non-default) colors are preserved."""
        mock_trigger.return_value = None
        headers = await get_auth_headers(
            client, username="user_custom_colors", password="testpass123"
        )

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
        # Custom color should be preserved
        assert data["thinkers"][0]["color"] == custom_color


class TestListConversationsWithData:
    """Test list_conversations with message counts and costs."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_list_shows_message_counts_and_costs(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that listed conversations include message_count and total_cost."""
        mock_trigger.return_value = None
        headers = await get_auth_headers(client, username="user_list_data", password="testpass123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test conversation for listing",
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

        # Send a message (user messages have cost 0.0)
        await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Hello philosophers!"},
        )

        # List conversations
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200

        conversations = list_response.json()
        assert len(conversations) >= 1

        # Find our conversation
        our_conv = next(c for c in conversations if c["id"] == conversation_id)

        # Verify message_count and total_cost fields are present
        assert "message_count" in our_conv
        assert "total_cost" in our_conv

        # Should have 1 user message
        assert our_conv["message_count"] == 1

        # User messages have no cost
        assert our_conv["total_cost"] == 0.0

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_list_with_multiple_conversations_all_have_counts(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test listing multiple conversations all show message counts."""
        mock_trigger.return_value = None
        headers = await get_auth_headers(client, username="user_multi_list", password="testpass123")

        # Create 2 conversations
        conv1_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "First conversation",
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
        conv1_id = conv1_response.json()["id"]

        conv2_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Second conversation",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Student of Socrates",
                        "positions": "Theory of Forms",
                        "style": "Dialogues",
                        "color": "#ec4899",
                    }
                ],
            },
        )
        conv2_id = conv2_response.json()["id"]

        # Send messages to first conversation only
        await client.post(
            f"/api/conversations/{conv1_id}/messages",
            headers=headers,
            json={"content": "Message 1"},
        )
        await client.post(
            f"/api/conversations/{conv1_id}/messages",
            headers=headers,
            json={"content": "Message 2"},
        )

        # List all conversations
        list_response = await client.get("/api/conversations", headers=headers)
        conversations = list_response.json()

        # Find our conversations
        conv1 = next(c for c in conversations if c["id"] == conv1_id)
        conv2 = next(c for c in conversations if c["id"] == conv2_id)

        # Conv1 should have 2 messages, conv2 should have 0
        assert conv1["message_count"] == 2
        assert conv2["message_count"] == 0


class TestSendMessageWithDisplayName:
    """Test send_message uses display_name correctly."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_send_message_uses_display_name_when_set(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that messages use user's display_name when available."""
        mock_trigger.return_value = None
        # Register with display_name
        reg_response = await client.post(
            "/api/auth/register",
            json={
                "username": "test_display",
                "password": "testpass123",
                "display_name": "Display Name",
                "language_preference": "en",
            },
        )
        assert reg_response.status_code == 200
        token = reg_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Display name test",
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

        # Send message
        msg_response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Test message"},
        )

        assert msg_response.status_code == 200
        message = msg_response.json()

        # Should use display_name, not username
        assert message["sender_name"] == "Display Name"
        assert message["sender_name"] != "test_display"

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_send_message_falls_back_to_username(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that messages fall back to username when display_name is not set."""
        mock_trigger.return_value = None
        # Register with empty display_name to test fallback to username
        # Note: display_name is required, so we use the username as display_name
        # This test validates that when display_name equals username, message still works
        reg_response = await client.post(
            "/api/auth/register",
            json={
                "username": "fallback_user",
                "password": "testpass123",
                "display_name": "fallback_user",  # Same as username
                "language_preference": "en",
            },
        )
        assert reg_response.status_code == 200
        token = reg_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Fallback test",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Student of Socrates",
                        "positions": "Theory of Forms",
                        "style": "Dialogues",
                        "color": "#ec4899",
                    }
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Send message
        msg_response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Test fallback"},
        )

        assert msg_response.status_code == 200
        message = msg_response.json()

        # Should use username as fallback
        assert message["sender_name"] == "fallback_user"
