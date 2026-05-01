"""Coverage sprint tests for conversation API - Monday Feb 9 2026.

Target: app/api/conversations.py (39% -> 54%+)

Focused on remaining untested code paths:
- Conversation refresh with thinkers (line 67)
- List conversations with cost calculation (lines 85-105)
- Get conversation 404 edge cases (lines 126-129)
- Delete conversation 404 and success (lines 145-151)
- Add thinkers with color availability logic (lines 188-220)
- Send message with idle resume (lines 241-268)

Refactored (Friday QA): Removed redundant trigger_research patches (autouse
fixture in conftest.py already mocks it globally). Used conftest helpers to
reduce setup boilerplate.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient

from tests.conftest import assert_not_found, create_test_conversation, get_auth_headers


class TestListConversationsWithCosts:
    """Test list conversations endpoint with cost calculations."""

    async def test_list_conversations_includes_message_counts_and_costs(
        self, client: AsyncClient
    ) -> None:
        """Test that list conversations includes accurate message counts and total costs.

        Tests lines 85-105 where conversations are queried and summaries built.
        """
        headers = await get_auth_headers(client, username="cost_test_user", password="testpass123")
        conversation_id = await create_test_conversation(client, headers, "Cost tracking test")

        # Send user message
        msg_response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Hello philosophers"},
        )
        assert msg_response.status_code == 200

        # List conversations - should include message count and costs
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200

        conversations = list_response.json()
        assert len(conversations) > 0

        our_conv = next(c for c in conversations if c["id"] == conversation_id)
        assert our_conv["message_count"] >= 1
        assert "total_cost" in our_conv
        assert our_conv["total_cost"] >= 0.0

    async def test_list_conversations_orders_by_created_at_desc(self, client: AsyncClient) -> None:
        """Test that conversations are ordered by created_at descending.

        Tests line 83 where order_by clause is applied.
        """
        headers = await get_auth_headers(client, username="order_test_user", password="testpass123")

        # Create multiple conversations
        conv_ids = []
        for i in range(3):
            conv_id = await create_test_conversation(client, headers, f"Conversation {i}", 1)
            conv_ids.append(conv_id)

        # List conversations
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200

        conversations = list_response.json()
        assert len(conversations) >= 3

        returned_ids = [c["id"] for c in conversations]
        for conv_id in conv_ids:
            assert conv_id in returned_ids


class TestGetConversationEdgeCases:
    """Test get conversation endpoint edge cases."""

    async def test_get_conversation_returns_404_for_nonexistent_id(
        self, client: AsyncClient
    ) -> None:
        """Test that getting a non-existent conversation returns 404.

        Tests lines 126-129 where result is checked.
        """
        headers = await get_auth_headers(client, username="get_404_user", password="testpass123")

        response = await client.get(
            "/api/conversations/nonexistent-id-123",
            headers=headers,
        )
        assert_not_found(response, "not found")

    async def test_get_conversation_returns_404_for_other_users_conversation(
        self, client: AsyncClient
    ) -> None:
        """Test that users cannot access other users' conversations.

        Tests lines 117-129 where session_id is checked.
        """
        user1_headers = await get_auth_headers(
            client, username="privacy_user1", password="testpass123"
        )
        conversation_id = await create_test_conversation(
            client, user1_headers, "Private conversation"
        )

        user2_headers = await get_auth_headers(
            client, username="privacy_user2", password="testpass123"
        )
        response = await client.get(
            f"/api/conversations/{conversation_id}",
            headers=user2_headers,
        )
        assert_not_found(response)


class TestDeleteConversationEdgeCases:
    """Test delete conversation endpoint."""

    async def test_delete_conversation_returns_404_for_nonexistent_id(
        self, client: AsyncClient
    ) -> None:
        """Test that deleting a non-existent conversation returns 404.

        Tests lines 145-147 where result is checked.
        """
        headers = await get_auth_headers(client, username="delete_404_user", password="testpass123")

        response = await client.delete(
            "/api/conversations/nonexistent-id-456",
            headers=headers,
        )
        assert_not_found(response, "not found")

    async def test_delete_conversation_returns_success_status(self, client: AsyncClient) -> None:
        """Test that successful delete returns correct status.

        Tests line 151 where status is returned.
        """
        headers = await get_auth_headers(
            client, username="delete_success_user", password="testpass123"
        )
        conversation_id = await create_test_conversation(client, headers, "To be deleted")

        delete_response = await client.delete(
            f"/api/conversations/{conversation_id}",
            headers=headers,
        )
        assert delete_response.status_code == 200
        data = delete_response.json()
        assert data["status"] == "deleted"

        # Verify conversation is gone
        get_response = await client.get(
            f"/api/conversations/{conversation_id}",
            headers=headers,
        )
        assert_not_found(get_response)


class TestAddThinkersColorLogic:
    """Test add thinkers endpoint with color availability logic."""

    async def test_add_thinkers_uses_available_colors(self, client: AsyncClient) -> None:
        """Test that adding thinkers picks from available colors.

        Tests lines 188-220 where colors are selected and thinkers created.
        """
        headers = await get_auth_headers(
            client, username="color_avail_user", password="testpass123"
        )

        # Create conversation with 2 thinkers (uses first 2 colors)
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Color test",
                "thinkers": [
                    {
                        "name": "Thinker 1",
                        "bio": "Bio 1",
                        "positions": "Positions 1",
                        "style": "Style 1",
                        "color": "#6366f1",
                    },
                    {
                        "name": "Thinker 2",
                        "bio": "Bio 2",
                        "positions": "Positions 2",
                        "style": "Style 2",
                        "color": "#6366f1",
                    },
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]
        existing_colors = [t["color"] for t in conv_response.json()["thinkers"]]

        # Add 2 more thinkers - should get colors 3 and 4
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Thinker 3",
                    "bio": "Bio 3",
                    "positions": "Positions 3",
                    "style": "Style 3",
                    "color": "#6366f1",
                },
                {
                    "name": "Thinker 4",
                    "bio": "Bio 4",
                    "positions": "Positions 4",
                    "style": "Style 4",
                    "color": "#6366f1",
                },
            ],
        )
        assert add_response.status_code == 200
        new_thinkers = add_response.json()

        # New thinkers should have different colors from existing ones
        new_colors = [t["color"] for t in new_thinkers]
        for color in new_colors:
            assert color not in existing_colors

    async def test_add_thinkers_refreshes_and_returns_thinkers(self, client: AsyncClient) -> None:
        """Test that add thinkers refreshes models and returns them.

        Tests lines 217-220 where thinkers are refreshed and returned.
        """
        headers = await get_auth_headers(client, username="refresh_user", password="testpass123")
        conversation_id = await create_test_conversation(client, headers, "Refresh test")

        # Add thinker
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Added Thinker",
                    "bio": "Added bio",
                    "positions": "Added positions",
                    "style": "Added style",
                    "color": "#ec4899",
                }
            ],
        )
        assert add_response.status_code == 200
        added_thinkers = add_response.json()

        # Returned thinkers should have IDs and timestamps (from refresh)
        assert len(added_thinkers) == 1
        assert "id" in added_thinkers[0]
        assert "created_at" in added_thinkers[0]
        assert added_thinkers[0]["name"] == "Added Thinker"


class TestSendMessageIdleResume:
    """Test send message endpoint with idle resume logic."""

    async def test_send_message_resumes_idle_paused_conversation(self, client: AsyncClient) -> None:
        """Test that sending a message auto-resumes idle-paused conversations.

        Tests lines 246-254 where idle pause is checked and resumed.
        """
        headers = await get_auth_headers(
            client, username="idle_resume_user", password="testpass123"
        )
        conversation_id = await create_test_conversation(client, headers, "Idle resume test")

        # Mock the thinker service to simulate idle pause
        with patch("app.services.thinker.thinker_service") as mock_service:
            mock_service.is_idle_paused.return_value = True
            # resume_from_idle is synchronous, not async - use MagicMock not AsyncMock
            mock_service.resume_from_idle = MagicMock()

            # Mock websocket manager
            with patch("app.api.websocket.manager") as mock_manager:
                mock_manager.broadcast_to_conversation = AsyncMock()

                # Send message - should trigger resume
                msg_response = await client.post(
                    f"/api/conversations/{conversation_id}/messages",
                    headers=headers,
                    json={"content": "Wake up!"},
                )
                assert msg_response.status_code == 200

                # Verify resume was called
                mock_service.is_idle_paused.assert_called_once_with(conversation_id)
                mock_service.resume_from_idle.assert_called_once_with(conversation_id)
                mock_manager.broadcast_to_conversation.assert_called_once()

    async def test_send_message_uses_display_name(self, client: AsyncClient) -> None:
        """Test that messages use user's display name if available.

        Tests lines 257-268 where sender_name is determined.
        """
        # get_auth_headers sets display_name to username.title()
        headers = await get_auth_headers(client, username="displaynameuser", password="testpass123")
        conversation_id = await create_test_conversation(client, headers, "Display name test")

        msg_response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Hello from John"},
        )
        assert msg_response.status_code == 200

        message = msg_response.json()
        assert message["sender_name"] == "Displaynameuser"
        assert message["content"] == "Hello from John"

    async def test_send_message_fallback_to_username(self, client: AsyncClient) -> None:
        """Test that messages fallback to username if no display name.

        Tests line 258 where fallback logic is applied.
        """
        headers = await get_auth_headers(
            client, username="username_fallback_user", password="testpass123"
        )
        conversation_id = await create_test_conversation(client, headers, "Username fallback test")

        msg_response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Hello with username"},
        )
        assert msg_response.status_code == 200

        message = msg_response.json()
        # display_name defaults to username.title() in the registration helper
        assert message["sender_name"] == "Username_Fallback_User"
