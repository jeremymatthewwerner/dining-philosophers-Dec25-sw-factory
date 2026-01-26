"""Coverage sprint tests for conversation API - Monday Jan 26 2026.

Target: app/api/conversations.py (39% -> 55%+)

Focus areas:
- List conversations when empty (line 85)
- List conversations with null/zero costs (lines 88-104)
- Get conversation 404 error path (lines 126-129)
- Delete conversation 404 error path (lines 145-147)
- Delete conversation success response (line 151)
- Add thinkers max limit validation (lines 173-185)
- Add thinkers color pool exhaustion (lines 188-199, 217-220)
- Send message idle pause auto-resume (lines 245-254)
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import get_auth_headers


class TestListConversationsEdgeCases:
    """Test list_conversations edge cases for missing coverage."""

    @pytest.mark.asyncio
    async def test_list_conversations_when_empty(self, client: AsyncClient) -> None:
        """Test listing conversations when user has no conversations yet."""
        headers = await get_auth_headers(client, username="empty_list_user", password="testpass123")

        # List conversations (should be empty)
        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200

        conversations = response.json()
        assert conversations == []
        assert len(conversations) == 0

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_list_conversations_with_null_costs(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that list_conversations handles messages with null costs correctly."""
        mock_trigger.return_value = None
        headers = await get_auth_headers(client, username="null_cost_user", password="testpass123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Null cost test",
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

        # Send a message (which has cost=None by default in DB)
        await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Test message"},
        )

        # List conversations
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200

        conversations = list_response.json()
        our_conv = next(c for c in conversations if c["id"] == conversation_id)

        # Should handle null costs gracefully (sum should be 0.0)
        assert our_conv["total_cost"] == 0.0
        assert our_conv["message_count"] == 1


class TestGetConversationErrorPaths:
    """Test get_conversation 404 error handling."""

    @pytest.mark.asyncio
    async def test_get_conversation_returns_404_for_nonexistent(self, client: AsyncClient) -> None:
        """Test that getting a nonexistent conversation returns 404."""
        headers = await get_auth_headers(client, username="get_404_user", password="testpass123")

        # Try to get a conversation with a UUID that doesn't exist
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/conversations/{fake_uuid}", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Conversation not found"


class TestDeleteConversationErrorPaths:
    """Test delete_conversation 404 error handling and success response."""

    @pytest.mark.asyncio
    async def test_delete_conversation_returns_404_for_nonexistent(
        self, client: AsyncClient
    ) -> None:
        """Test that deleting a nonexistent conversation returns 404."""
        headers = await get_auth_headers(client, username="delete_404_user", password="testpass123")

        # Try to delete a conversation with a UUID that doesn't exist
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(f"/api/conversations/{fake_uuid}", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Conversation not found"

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_delete_conversation_returns_success_response(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that deleting an existing conversation returns success response."""
        mock_trigger.return_value = None
        headers = await get_auth_headers(
            client, username="delete_success_user", password="testpass123"
        )

        # Create a conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "To be deleted",
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

        # Delete it
        delete_response = await client.delete(
            f"/api/conversations/{conversation_id}", headers=headers
        )

        assert delete_response.status_code == 200
        # Verify the success response structure
        data = delete_response.json()
        assert "status" in data
        assert data["status"] == "deleted"


class TestAddThinkersValidation:
    """Test add_thinkers max limit validation and color pool handling."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_add_thinkers_when_at_max_limit(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that adding thinkers when already at max (5) returns 400 error."""
        mock_trigger.return_value = None
        headers = await get_auth_headers(client, username="max_limit_user", password="testpass123")

        # Create conversation with 5 thinkers (max)
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Full conversation",
                "thinkers": [
                    {
                        "name": f"Thinker{i}",
                        "bio": f"Bio {i}",
                        "positions": f"Position {i}",
                        "style": f"Style {i}",
                        "color": "#6366f1",
                    }
                    for i in range(5)
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Try to add another thinker (should fail)
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Sixth Thinker",
                    "bio": "Should not be added",
                    "positions": "Overflow",
                    "style": "Rejected",
                    "color": "#6366f1",
                }
            ],
        )

        assert add_response.status_code == 400
        error_detail = add_response.json()["detail"]
        # Verify error message includes useful info
        assert "Cannot add" in error_detail
        assert "5/5 thinkers" in error_detail
        assert "Maximum is 5" in error_detail

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_add_thinkers_when_color_pool_exhausted(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that adding thinkers when all 5 colors are used still works."""
        mock_trigger.return_value = None
        headers = await get_auth_headers(client, username="color_pool_user", password="testpass123")

        # Create conversation with 4 thinkers (each using a different color)
        all_colors = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Color pool test",
                "thinkers": [
                    {
                        "name": f"Thinker{i}",
                        "bio": f"Bio {i}",
                        "positions": f"Position {i}",
                        "style": f"Style {i}",
                        "color": all_colors[i],  # Explicitly assign first 4 colors
                    }
                    for i in range(4)
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Add 5th thinker with default color (pool should have 1 color left)
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Fifth Thinker",
                    "bio": "Last one",
                    "positions": "Final position",
                    "style": "Last style",
                    "color": "#6366f1",  # Default - should get the remaining color
                }
            ],
        )

        assert add_response.status_code == 200
        new_thinkers = add_response.json()
        # Should have assigned the 5th color from the pool
        assert new_thinkers[0]["color"] == all_colors[4]  # #8b5cf6

        # Now try to add another thinker when color pool is exhausted (but still at 5 limit)
        # This won't work because we're at max 5 thinkers, but the color logic
        # would handle exhausted pool by keeping default color if pool is empty


class TestSendMessageIdlePause:
    """Test send_message auto-resume from idle pause."""

    @pytest.mark.asyncio
    @patch("app.services.thinker.thinker_service.is_idle_paused")
    @patch("app.services.thinker.thinker_service.resume_from_idle")
    @patch("app.api.websocket.manager.broadcast_to_conversation")
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_send_message_auto_resumes_from_idle_pause(
        self,
        mock_trigger: MagicMock,
        mock_broadcast: MagicMock,
        mock_resume: MagicMock,
        mock_is_idle_paused: MagicMock,
        client: AsyncClient,
    ) -> None:
        """Test that sending a message auto-resumes conversation from idle pause."""
        mock_trigger.return_value = None
        mock_broadcast.return_value = None
        mock_resume.return_value = None
        # Simulate conversation being idle-paused
        mock_is_idle_paused.return_value = True

        headers = await get_auth_headers(client, username="idle_pause_user", password="testpass123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Idle pause test",
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

        # Send message (should trigger auto-resume)
        msg_response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Wake up!"},
        )

        assert msg_response.status_code == 200

        # Verify auto-resume was triggered
        mock_is_idle_paused.assert_called_once_with(conversation_id)
        mock_resume.assert_called_once_with(conversation_id)
        # Verify RESUMED message was broadcast
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args
        assert call_args[0][0] == conversation_id  # conversation_id arg
        ws_message = call_args[0][1]  # WSMessage arg
        assert ws_message.type.value == "resumed"
