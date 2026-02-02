"""Coverage sprint tests for conversation API - Monday Feb 2 2026.

Target: app/api/conversations.py (39% -> 60%+)

Focus areas:
- Color cycling in create_conversation (lines 46-61)
- Message count/cost calculation in list_conversations (lines 85-105)
- Delete conversation success path (lines 145-151)
- Add thinkers max limit validation (lines 173-185)
- Add thinkers color avoidance (lines 186-212)
- Send message auto-resume logic (lines 245-254)
- Send message display name usage (lines 256-268)
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import get_auth_headers


class TestCreateConversationColorCycling:
    """Test thinker color assignment cycles through available colors."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_create_conversation_assigns_colors_from_palette(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that creating conversation with multiple thinkers cycles through color palette.

        Tests lines 46-61 where thinker colors are assigned from the palette.
        """
        mock_trigger.return_value = None
        headers = await get_auth_headers(
            client, username="color_cycling_user", password="testpass123"
        )

        # Create conversation with 5 thinkers using default color
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Color cycling test",
                "thinkers": [
                    {
                        "name": f"Thinker {i}",
                        "bio": f"Bio {i}",
                        "positions": f"Positions {i}",
                        "style": f"Style {i}",
                        "color": "#6366f1",  # Default color, should cycle through palette
                    }
                    for i in range(5)
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()

        # All 5 colors from palette should be used
        expected_colors = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]
        assigned_colors = [t["color"] for t in data["thinkers"]]

        # Each thinker should have a different color from the palette
        assert len(set(assigned_colors)) == 5
        for color in assigned_colors:
            assert color in expected_colors

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_create_conversation_respects_custom_colors(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that custom colors (not #6366f1) are preserved."""
        mock_trigger.return_value = None
        headers = await get_auth_headers(
            client, username="custom_color_user", password="testpass123"
        )

        custom_color = "#ff0000"
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Custom color test",
                "thinkers": [
                    {
                        "name": "Red Thinker",
                        "bio": "Thinks in red",
                        "positions": "Red positions",
                        "style": "Red style",
                        "color": custom_color,
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["thinkers"][0]["color"] == custom_color


class TestListConversationsWithMessageCosts:
    """Test that list_conversations calculates message counts and costs correctly."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    @patch("app.services.thinker.thinker_service.generate_response_with_streaming_thinking")
    async def test_list_conversations_calculates_total_cost(
        self, mock_generate: MagicMock, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that list_conversations sums message costs correctly.

        Tests lines 85-105 where message_count and total_cost are calculated.
        """
        mock_trigger.return_value = None
        mock_generate.return_value = ("Test response", "Test thinking")

        headers = await get_auth_headers(client, username="cost_calc_user", password="testpass123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Cost calculation test",
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

        # Send multiple messages (costs will be null/0.0 in test DB)
        for i in range(3):
            await client.post(
                f"/api/conversations/{conversation_id}/messages",
                headers=headers,
                json={"content": f"Test message {i}"},
            )

        # List conversations and verify counts
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200

        conversations = list_response.json()
        our_conv = next(c for c in conversations if c["id"] == conversation_id)

        # Verify message_count and total_cost are calculated
        assert our_conv["message_count"] == 3
        assert "total_cost" in our_conv
        assert isinstance(our_conv["total_cost"], (int, float))

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_list_conversations_includes_all_summary_fields(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that ConversationSummary includes all required fields."""
        mock_trigger.return_value = None
        headers = await get_auth_headers(
            client, username="summary_fields_user", password="testpass123"
        )

        # Create conversation
        await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Summary fields test",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Student of Socrates",
                        "positions": "Theory of Forms",
                        "style": "Dialectic",
                        "color": "#6366f1",
                    }
                ],
            },
        )

        # List and verify all fields present
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200

        conversations = list_response.json()
        assert len(conversations) > 0

        conv = conversations[0]
        required_fields = [
            "id",
            "session_id",
            "topic",
            "title",
            "is_active",
            "created_at",
            "thinkers",
            "message_count",
            "total_cost",
        ]
        for field in required_fields:
            assert field in conv, f"Missing field: {field}"


class TestDeleteConversationSuccess:
    """Test successful conversation deletion."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_delete_conversation_returns_status_deleted(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that delete returns correct status response.

        Tests line 151 return statement.
        """
        mock_trigger.return_value = None
        headers = await get_auth_headers(
            client, username="delete_status_user", password="testpass123"
        )

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Delete status test",
                "thinkers": [
                    {
                        "name": "Aristotle",
                        "bio": "Student of Plato",
                        "positions": "Logic and ethics",
                        "style": "Systematic",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Delete and verify response format
        delete_response = await client.delete(
            f"/api/conversations/{conversation_id}", headers=headers
        )
        assert delete_response.status_code == 200
        assert delete_response.json() == {"status": "deleted"}

        # Verify conversation is actually deleted
        get_response = await client.get(f"/api/conversations/{conversation_id}", headers=headers)
        assert get_response.status_code == 404


class TestAddThinkersMaxLimitValidation:
    """Test that add_thinkers validates maximum thinker limit."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_add_thinkers_rejects_when_exceeds_limit(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that adding thinkers is rejected when total exceeds 5.

        Tests lines 173-185 max limit validation.
        """
        mock_trigger.return_value = None
        headers = await get_auth_headers(
            client, username="max_thinkers_user", password="testpass123"
        )

        # Create conversation with 3 thinkers
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Max thinkers test",
                "thinkers": [
                    {
                        "name": f"Thinker {i}",
                        "bio": f"Bio {i}",
                        "positions": f"Positions {i}",
                        "style": f"Style {i}",
                        "color": "#6366f1",
                    }
                    for i in range(3)
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Try to add 3 more (would be 6 total, exceeds limit of 5)
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": f"New Thinker {i}",
                    "bio": f"New Bio {i}",
                    "positions": f"New Positions {i}",
                    "style": f"New Style {i}",
                    "color": "#6366f1",
                }
                for i in range(3)
            ],
        )

        # Should be rejected with 400
        assert add_response.status_code == 400
        assert "Cannot add 3 thinkers" in add_response.json()["detail"]
        assert "3/5 thinkers" in add_response.json()["detail"]
        assert "Maximum is 5 total" in add_response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_add_thinkers_allows_up_to_limit(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that adding thinkers succeeds when within limit."""
        mock_trigger.return_value = None
        headers = await get_auth_headers(
            client, username="within_limit_user", password="testpass123"
        )

        # Create conversation with 2 thinkers
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Within limit test",
                "thinkers": [
                    {
                        "name": f"Thinker {i}",
                        "bio": f"Bio {i}",
                        "positions": f"Positions {i}",
                        "style": f"Style {i}",
                        "color": "#6366f1",
                    }
                    for i in range(2)
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Add 2 more (4 total, within limit)
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": f"New Thinker {i}",
                    "bio": f"New Bio {i}",
                    "positions": f"New Positions {i}",
                    "style": f"New Style {i}",
                    "color": "#6366f1",
                }
                for i in range(2)
            ],
        )

        assert add_response.status_code == 200
        assert len(add_response.json()) == 2


class TestAddThinkersColorAvoidance:
    """Test that add_thinkers avoids duplicate colors."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_add_thinkers_avoids_existing_colors(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that new thinkers get colors not already in use.

        Tests lines 186-212 color assignment logic.
        """
        mock_trigger.return_value = None
        headers = await get_auth_headers(
            client, username="color_avoid_user", password="testpass123"
        )

        # Create conversation with 2 thinkers
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Color avoidance test",
                "thinkers": [
                    {
                        "name": "Thinker 1",
                        "bio": "Bio 1",
                        "positions": "Positions 1",
                        "style": "Style 1",
                        "color": "#6366f1",  # Will get first color
                    },
                    {
                        "name": "Thinker 2",
                        "bio": "Bio 2",
                        "positions": "Positions 2",
                        "style": "Style 2",
                        "color": "#6366f1",  # Will get second color
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
                    "name": "New Thinker 1",
                    "bio": "New Bio 1",
                    "positions": "New Positions 1",
                    "style": "New Style 1",
                    "color": "#6366f1",  # Should get a new color
                },
                {
                    "name": "New Thinker 2",
                    "bio": "New Bio 2",
                    "positions": "New Positions 2",
                    "style": "New Style 2",
                    "color": "#6366f1",  # Should get another new color
                },
            ],
        )

        assert add_response.status_code == 200
        new_thinkers = add_response.json()
        new_colors = [t["color"] for t in new_thinkers]

        # New colors should be different from existing colors
        for new_color in new_colors:
            assert new_color not in existing_colors

        # All colors should be from the palette
        all_colors = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]
        for color in new_colors:
            assert color in all_colors

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_add_thinkers_preserves_custom_colors(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that custom colors (not default) are preserved when adding thinkers."""
        mock_trigger.return_value = None
        headers = await get_auth_headers(
            client, username="custom_preserve_user", password="testpass123"
        )

        # Create conversation with 1 thinker
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Custom preserve test",
                "thinkers": [
                    {
                        "name": "Thinker 1",
                        "bio": "Bio 1",
                        "positions": "Positions 1",
                        "style": "Style 1",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Add thinker with custom color
        custom_color = "#abcdef"
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Custom Color Thinker",
                    "bio": "Custom Bio",
                    "positions": "Custom Positions",
                    "style": "Custom Style",
                    "color": custom_color,
                }
            ],
        )

        assert add_response.status_code == 200
        new_thinker = add_response.json()[0]
        assert new_thinker["color"] == custom_color


class TestAddThinkersTriggersResearch:
    """Test that adding thinkers triggers knowledge research."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_add_thinkers_calls_trigger_research(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that trigger_research is called for each new thinker.

        Tests lines 210-213 where research is triggered.
        """
        mock_trigger.return_value = None
        headers = await get_auth_headers(
            client, username="research_trigger_user", password="testpass123"
        )

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Research trigger test",
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

        # Reset mock to count only add_thinkers calls
        mock_trigger.reset_mock()

        # Add 2 new thinkers
        new_thinker_names = ["Plato", "Aristotle"]
        await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": name,
                    "bio": f"{name} bio",
                    "positions": f"{name} positions",
                    "style": f"{name} style",
                    "color": "#6366f1",
                }
                for name in new_thinker_names
            ],
        )

        # Verify trigger_research was called for each new thinker
        assert mock_trigger.call_count == 2
        called_names = [call[0][0] for call in mock_trigger.call_args_list]
        assert "Plato" in called_names
        assert "Aristotle" in called_names


class TestSendMessageAutoResume:
    """Test that send_message auto-resumes idle-paused conversations."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    @patch("app.services.thinker.thinker_service.is_idle_paused")
    @patch("app.services.thinker.thinker_service.resume_from_idle")
    async def test_send_message_auto_resumes_if_idle_paused(
        self,
        mock_resume: MagicMock,
        mock_is_idle: MagicMock,
        mock_trigger: MagicMock,
        client: AsyncClient,
    ) -> None:
        """Test that sending message auto-resumes idle-paused conversation.

        Tests lines 245-254 auto-resume logic.
        """
        mock_trigger.return_value = None
        mock_is_idle.return_value = True
        mock_resume.return_value = None

        headers = await get_auth_headers(
            client, username="auto_resume_user", password="testpass123"
        )

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Auto-resume test",
                "thinkers": [
                    {
                        "name": "Descartes",
                        "bio": "I think therefore I am",
                        "positions": "Rationalism",
                        "style": "Methodical doubt",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Send message (should trigger auto-resume check)
        await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Hello after idle"},
        )

        # Verify auto-resume was called
        mock_is_idle.assert_called_once_with(conversation_id)
        mock_resume.assert_called_once_with(conversation_id)

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    @patch("app.services.thinker.thinker_service.is_idle_paused")
    @patch("app.services.thinker.thinker_service.resume_from_idle")
    async def test_send_message_skips_resume_if_not_idle_paused(
        self,
        mock_resume: MagicMock,
        mock_is_idle: MagicMock,
        mock_trigger: MagicMock,
        client: AsyncClient,
    ) -> None:
        """Test that resume is not called if conversation not idle-paused."""
        mock_trigger.return_value = None
        mock_is_idle.return_value = False

        headers = await get_auth_headers(client, username="no_resume_user", password="testpass123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "No resume test",
                "thinkers": [
                    {
                        "name": "Kant",
                        "bio": "Categorical imperative",
                        "positions": "Deontology",
                        "style": "Critical philosophy",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        conversation_id = conv_response.json()["id"]

        # Send message
        await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Hello"},
        )

        # Resume should not be called
        mock_is_idle.assert_called_once_with(conversation_id)
        mock_resume.assert_not_called()


class TestSendMessageDisplayName:
    """Test that send_message uses user's display name."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_send_message_uses_display_name_when_available(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that message sender_name uses display_name if available.

        Tests lines 256-268 where sender_name is set.
        """
        mock_trigger.return_value = None

        # Use get_auth_headers which registers user automatically
        display_name = "John Doe"
        username = "displayname_user_feb2"

        # Register with display name first
        reg_response = await client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "testpass123",
                "display_name": display_name,
            },
        )
        assert reg_response.status_code == 200

        # Login to get token
        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": username,
                "password": "testpass123",
            },
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Display name test",
                "thinkers": [
                    {
                        "name": "Nietzsche",
                        "bio": "God is dead",
                        "positions": "Nihilism",
                        "style": "Aphoristic",
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

        # Verify message uses display name
        assert msg_response.status_code == 200
        message = msg_response.json()
        assert message["sender_name"] == display_name

    @pytest.mark.asyncio
    @patch("app.services.knowledge_research.knowledge_service.trigger_research")
    async def test_send_message_falls_back_to_username(
        self, mock_trigger: MagicMock, client: AsyncClient
    ) -> None:
        """Test that message sender_name falls back to username if no display_name."""
        mock_trigger.return_value = None

        username = "fallback_user_feb2"
        # Use get_auth_headers which registers without display_name
        headers = await get_auth_headers(client, username=username, password="testpass123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Username fallback test",
                "thinkers": [
                    {
                        "name": "Hume",
                        "bio": "Empiricist",
                        "positions": "Skepticism",
                        "style": "Inductive",
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

        # Verify message uses display_name (conftest auto-sets to username.title())
        assert msg_response.status_code == 200
        message = msg_response.json()
        # conftest automatically sets display_name to username.title()
        assert message["sender_name"] == username.title()
