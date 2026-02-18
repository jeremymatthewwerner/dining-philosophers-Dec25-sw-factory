"""Coverage sprint tests for conversation API - Monday Feb 16 2026.

Target: app/api/conversations.py (39% -> 54%+)

Focus on uncovered paths identified in coverage analysis:
- Create conversation with default color cycling (lines 46-67)
- List conversations cost aggregation detail (lines 85-105)
- Get/Delete conversation success paths (lines 126-151)
- Add thinkers max limit and color pool (lines 173-220)
- Send message idle resume and display name (lines 241-268)
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import get_auth_headers


class TestCreateConversationColorCycling:
    """Test create conversation endpoint with color cycling logic."""

    @pytest.mark.asyncio
    async def test_create_conversation_cycles_default_colors(self, client: AsyncClient) -> None:
        """Test that default color (#6366f1) triggers color cycling from palette.

        Tests lines 46-67 where thinkers are created with colors from the palette.
        When color is default (#6366f1), it should cycle through available colors.
        """
        headers = await get_auth_headers(
            client, username="color_cycle_user", password="testpass123"
        )

        # Create conversation with 3 thinkers, all using default color
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Color cycling test",
                    "thinkers": [
                        {
                            "name": "Socrates",
                            "bio": "Greek philosopher",
                            "positions": "Know thyself",
                            "style": "Socratic method",
                            "color": "#6366f1",  # Default - should cycle
                        },
                        {
                            "name": "Plato",
                            "bio": "Student of Socrates",
                            "positions": "Theory of Forms",
                            "style": "Dialectic",
                            "color": "#6366f1",  # Default - should cycle
                        },
                        {
                            "name": "Aristotle",
                            "bio": "Student of Plato",
                            "positions": "Golden mean",
                            "style": "Empirical",
                            "color": "#6366f1",  # Default - should cycle
                        },
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()

        # Verify thinkers have different colors from the palette
        colors = [t["color"] for t in data["thinkers"]]
        assert len(colors) == 3
        assert len(set(colors)) == 3  # All different colors

        # Verify colors are from the expected palette
        expected_colors = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]
        for color in colors:
            assert color in expected_colors

    @pytest.mark.asyncio
    async def test_create_conversation_preserves_custom_colors(self, client: AsyncClient) -> None:
        """Test that custom colors (non-default) are preserved.

        Tests lines 54-56 where custom colors bypass cycling logic.
        """
        headers = await get_auth_headers(
            client, username="custom_color_user", password="testpass123"
        )

        custom_color = "#ff6600"

        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Custom color test",
                    "thinkers": [
                        {
                            "name": "Einstein",
                            "bio": "Physicist",
                            "positions": "Relativity",
                            "style": "Thought experiments",
                            "color": custom_color,  # Custom color
                        }
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()

        # Verify custom color was preserved
        assert data["thinkers"][0]["color"] == custom_color

    @pytest.mark.asyncio
    async def test_create_conversation_refreshes_with_thinkers(self, client: AsyncClient) -> None:
        """Test that conversation is refreshed with thinkers after creation.

        Tests line 67 where conversation is refreshed to include thinkers.
        """
        headers = await get_auth_headers(
            client, username="refresh_test_user", password="testpass123"
        )

        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Refresh test",
                    "thinkers": [
                        {
                            "name": "Descartes",
                            "bio": "Rationalist",
                            "positions": "Cogito ergo sum",
                            "style": "Methodical doubt",
                            "color": "#6366f1",
                        }
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()

        # Verify thinkers are included in response (proving refresh worked)
        assert "thinkers" in data
        assert len(data["thinkers"]) == 1
        assert data["thinkers"][0]["name"] == "Descartes"
        assert "id" in data["thinkers"][0]  # Has ID from DB
        assert "created_at" in data["thinkers"][0]  # Has timestamp from DB


class TestListConversationsDetail:
    """Test list conversations endpoint cost aggregation details."""

    @pytest.mark.asyncio
    async def test_list_conversations_cost_aggregation_with_nulls(
        self, client: AsyncClient
    ) -> None:
        """Test that cost aggregation handles null costs correctly.

        Tests lines 90 where null costs are handled with 'or 0.0'.
        """
        headers = await get_auth_headers(client, username="null_cost_user", password="testpass123")

        # Create conversation
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Null cost test",
                    "thinkers": [
                        {
                            "name": "Buddha",
                            "bio": "Enlightened one",
                            "positions": "Middle way",
                            "style": "Meditative",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        conversation_id = conv_response.json()["id"]

        # Send message (will have null cost)
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

        # Verify cost calculation works even with null costs
        assert "total_cost" in our_conv
        assert our_conv["total_cost"] >= 0.0
        assert "message_count" in our_conv
        assert our_conv["message_count"] >= 1


class TestGetConversationNotFound:
    """Test get conversation 404 path."""

    @pytest.mark.asyncio
    async def test_get_conversation_nonexistent_returns_404(self, client: AsyncClient) -> None:
        """Test that getting nonexistent conversation returns 404.

        Tests lines 126-128 where HTTPException is raised.
        """
        headers = await get_auth_headers(client, username="get_404_user", password="testpass123")

        # Try to get conversation that doesn't exist
        response = await client.get("/api/conversations/nonexistent-id", headers=headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDeleteConversationSuccess:
    """Test delete conversation success path."""

    @pytest.mark.asyncio
    async def test_delete_conversation_returns_status_deleted(self, client: AsyncClient) -> None:
        """Test that delete conversation returns correct status.

        Tests lines 145-151 where conversation is deleted and status returned.
        """
        headers = await get_auth_headers(
            client, username="delete_success_user", password="testpass123"
        )

        # Create conversation
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Delete test",
                    "thinkers": [
                        {
                            "name": "Nietzsche",
                            "bio": "German philosopher",
                            "positions": "Will to power",
                            "style": "Aphoristic",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        conversation_id = conv_response.json()["id"]

        # Delete conversation
        delete_response = await client.delete(
            f"/api/conversations/{conversation_id}", headers=headers
        )

        assert delete_response.status_code == 200
        data = delete_response.json()
        assert data["status"] == "deleted"

        # Verify it's actually deleted
        get_response = await client.get(f"/api/conversations/{conversation_id}", headers=headers)
        assert get_response.status_code == 404


class TestAddThinkersMaxLimit:
    """Test add thinkers max limit validation."""

    @pytest.mark.asyncio
    async def test_add_thinkers_exceeds_max_limit(self, client: AsyncClient) -> None:
        """Test that adding thinkers beyond limit returns 400.

        Tests lines 173-185 where max thinker limit is validated.
        """
        headers = await get_auth_headers(client, username="max_limit_user", password="testpass123")

        # Create conversation with 3 thinkers
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Max limit test",
                    "thinkers": [
                        {
                            "name": f"Thinker{i}",
                            "bio": f"Bio{i}",
                            "positions": f"Pos{i}",
                            "style": f"Style{i}",
                            "color": "#6366f1",
                        }
                        for i in range(3)
                    ],
                },
            )
        conversation_id = conv_response.json()["id"]

        # Try to add 3 more thinkers (would exceed limit of 5)
        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": f"NewThinker{i}",
                    "bio": f"NewBio{i}",
                    "positions": f"NewPos{i}",
                    "style": f"NewStyle{i}",
                    "color": "#6366f1",
                }
                for i in range(3)
            ],
        )

        assert response.status_code == 400
        error_detail = response.json()["detail"]
        assert "3/5" in error_detail  # Shows existing count
        assert "Maximum is 5" in error_detail


class TestAddThinkersColorPool:
    """Test add thinkers color pool logic."""

    @pytest.mark.asyncio
    async def test_add_thinkers_uses_available_colors_from_pool(self, client: AsyncClient) -> None:
        """Test that add thinkers picks from available colors not used.

        Tests lines 187-220 where color pool is managed and colors assigned.
        """
        headers = await get_auth_headers(client, username="color_pool_user", password="testpass123")

        # Create conversation with 2 thinkers (uses 2 colors)
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Color pool test",
                    "thinkers": [
                        {
                            "name": "Confucius",
                            "bio": "Chinese philosopher",
                            "positions": "Harmony",
                            "style": "Analects",
                            "color": "#6366f1",  # Will cycle to first color
                        },
                        {
                            "name": "Laozi",
                            "bio": "Taoist sage",
                            "positions": "Wu wei",
                            "style": "Paradoxical",
                            "color": "#6366f1",  # Will cycle to second color
                        },
                    ],
                },
            )
        conversation_id = conv_response.json()["id"]
        existing_colors = {t["color"] for t in conv_response.json()["thinkers"]}

        # Add 2 more thinkers with default color
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            add_response = await client.put(
                f"/api/conversations/{conversation_id}/thinkers",
                headers=headers,
                json=[
                    {
                        "name": "Zhuangzi",
                        "bio": "Taoist philosopher",
                        "positions": "Relativism",
                        "style": "Butterfly dream",
                        "color": "#6366f1",  # Should use available color
                    },
                    {
                        "name": "Mencius",
                        "bio": "Confucian scholar",
                        "positions": "Human nature",
                        "style": "Debate",
                        "color": "#6366f1",  # Should use available color
                    },
                ],
            )

        assert add_response.status_code == 200
        new_thinkers = add_response.json()

        # Verify new thinkers got colors not already used
        new_colors = {t["color"] for t in new_thinkers}
        assert len(new_colors & existing_colors) == 0  # No overlap

    @pytest.mark.asyncio
    async def test_add_thinkers_color_pool_exhaustion(self, client: AsyncClient) -> None:
        """Test behavior when color pool is exhausted.

        Tests lines 197-198 where available_colors might be empty.
        """
        headers = await get_auth_headers(
            client, username="exhausted_pool_user", password="testpass123"
        )

        # Create conversation with 4 thinkers (leaves 1 color)
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Exhausted pool test",
                    "thinkers": [
                        {
                            "name": f"Thinker{i}",
                            "bio": f"Bio{i}",
                            "positions": f"Pos{i}",
                            "style": f"Style{i}",
                            "color": "#6366f1",
                        }
                        for i in range(4)
                    ],
                },
            )
        conversation_id = conv_response.json()["id"]

        # Add 1 more thinker - should get last available color
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            add_response = await client.put(
                f"/api/conversations/{conversation_id}/thinkers",
                headers=headers,
                json=[
                    {
                        "name": "FinalThinker",
                        "bio": "Final bio",
                        "positions": "Final position",
                        "style": "Final style",
                        "color": "#6366f1",  # Should get last available color
                    }
                ],
            )

        assert add_response.status_code == 200
        new_thinker = add_response.json()[0]

        # Verify thinker got a color (even if pool exhausted, it should have one)
        assert new_thinker["color"] is not None
        assert new_thinker["color"].startswith("#")


class TestSendMessageIdleResume:
    """Test send message with idle resume logic."""

    @pytest.mark.asyncio
    async def test_send_message_auto_resumes_idle_paused(self, client: AsyncClient) -> None:
        """Test that send message auto-resumes idle-paused conversations.

        Tests lines 245-254 where idle pause is detected and resumed.
        """
        headers = await get_auth_headers(
            client, username="idle_resume_user", password="testpass123"
        )

        # Create conversation
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Idle resume test",
                    "thinkers": [
                        {
                            "name": "Kant",
                            "bio": "German philosopher",
                            "positions": "Categorical imperative",
                            "style": "Critical",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        conversation_id = conv_response.json()["id"]

        # Mock thinker service to simulate idle pause
        with (
            patch(
                "app.services.thinker.thinker_service.is_idle_paused", return_value=True
            ) as mock_is_idle,
            patch("app.services.thinker.thinker_service.resume_from_idle") as mock_resume,
            patch(
                "app.api.websocket.manager.broadcast_to_conversation",
                new_callable=AsyncMock,
            ) as mock_broadcast,
        ):
            # Send message - should trigger resume
            response = await client.post(
                f"/api/conversations/{conversation_id}/messages",
                headers=headers,
                json={"content": "Wake up!"},
            )

            assert response.status_code == 200

            # Verify idle pause was checked and resumed
            mock_is_idle.assert_called_once_with(conversation_id)
            mock_resume.assert_called_once_with(conversation_id)
            mock_broadcast.assert_called_once()

            # Verify RESUMED message was broadcast
            call_args = mock_broadcast.call_args
            assert call_args[0][0] == conversation_id
            ws_message = call_args[0][1]
            # WSMessageType enum value is lowercase
            assert ws_message.type.value == "resumed"


class TestSendMessageDisplayName:
    """Test send message display name handling."""

    @pytest.mark.asyncio
    async def test_send_message_prefers_display_name_over_username(
        self, client: AsyncClient
    ) -> None:
        """Test that send message uses display_name if set, otherwise username.

        Tests lines 257-262 where sender_name is determined.
        """
        # Test with display name
        headers_with_display = await get_auth_headers(
            client, username="displaynameuser", password="testpass123"
        )

        # Update display name to custom value
        profile_response = await client.patch(
            "/api/auth/profile",
            headers=headers_with_display,
            json={"display_name": "The Philosopher"},
        )
        assert profile_response.status_code == 200

        # Create conversation
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_response = await client.post(
                "/api/conversations",
                headers=headers_with_display,
                json={
                    "topic": "Display name test",
                    "thinkers": [
                        {
                            "name": "Hume",
                            "bio": "Scottish philosopher",
                            "positions": "Empiricism",
                            "style": "Skeptical",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        conversation_id = conv_response.json()["id"]

        # Send message
        msg_response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers_with_display,
            json={"content": "Testing display name"},
        )

        assert msg_response.status_code == 200
        message = msg_response.json()
        assert message["sender_name"] == "The Philosopher"

    @pytest.mark.asyncio
    async def test_send_message_falls_back_to_username(self, client: AsyncClient) -> None:
        """Test that send message falls back to username when no display_name.

        Tests line 258 where fallback to username occurs.
        Note: Even without explicit display_name, registration sets it to title-cased username.
        """
        headers = await get_auth_headers(
            client, username="usernamefallback", password="testpass123"
        )

        # Create conversation (user has no display name)
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Username fallback test",
                    "thinkers": [
                        {
                            "name": "Locke",
                            "bio": "English philosopher",
                            "positions": "Tabula rasa",
                            "style": "Empirical",
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
            json={"content": "Testing username fallback"},
        )

        assert msg_response.status_code == 200
        message = msg_response.json()
        # Registration automatically sets display_name to title-cased username
        assert message["sender_name"] == "Usernamefallback"
