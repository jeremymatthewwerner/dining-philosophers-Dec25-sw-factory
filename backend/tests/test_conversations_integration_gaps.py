"""Integration tests for conversation API gaps - QA Agent Wednesday focus."""

from httpx import AsyncClient

from app.services.thinker import thinker_service
from tests.conftest import get_auth_headers


class TestIdlePauseAutoResume:
    """Test idle-pause auto-resume integration (lines 245-254 in conversations.py)."""

    async def test_idle_pause_auto_resume_on_user_message(self, client: AsyncClient) -> None:
        """When a user sends a message to an idle-paused conversation, it should auto-resume."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Philosophy of time",
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
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Manually trigger idle-pause (simulate idle timeout)
        thinker_service.pause_for_idle(conversation_id)
        assert thinker_service.is_idle_paused(conversation_id) is True

        # Send a user message - should auto-resume
        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "What is time?"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        message_data = response.json()
        assert message_data["content"] == "What is time?"
        assert message_data["sender_type"] == "user"

        # Conversation should no longer be idle-paused
        assert thinker_service.is_idle_paused(conversation_id) is False

    async def test_regular_pause_not_affected_by_auto_resume(self, client: AsyncClient) -> None:
        """Manual pause should not be auto-resumed by user messages."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        response = await client.post(
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
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Manually pause (not idle-pause)
        thinker_service.pause_conversation(conversation_id)
        assert thinker_service.is_paused(conversation_id) is True
        assert thinker_service.is_idle_paused(conversation_id) is False

        # Send a user message - manual pause should remain
        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "What is morality?"},
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Manual pause should still be active
        assert thinker_service.is_paused(conversation_id) is True


class TestAddThinkersColorPool:
    """Test color assignment from available pool when adding thinkers (lines 188-198)."""

    async def test_add_thinkers_uses_available_colors_from_pool(self, client: AsyncClient) -> None:
        """When adding thinkers with default color, should pick from available pool."""
        auth_headers = await get_auth_headers(client)

        # Create conversation with 2 thinkers (uses first 2 colors)
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Science",
                "thinkers": [
                    {
                        "name": "Einstein",
                        "bio": "Physicist",
                        "positions": "Scientist",
                        "style": "Theoretical",
                    },
                    {
                        "name": "Newton",
                        "bio": "Physicist",
                        "positions": "Mathematician",
                        "style": "Empirical",
                    },
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]
        existing_thinkers = response.json()["thinkers"]
        existing_colors = {t["color"] for t in existing_thinkers}
        assert len(existing_colors) == 2

        # Add a new thinker with default color - should get 3rd color from pool
        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            json=[
                {
                    "name": "Hawking",
                    "bio": "Theoretical physicist",
                    "positions": "Cosmologist",
                    "style": "Cosmological",
                    "color": "#6366f1",  # Default color
                }
            ],
            headers=auth_headers,
        )
        assert response.status_code == 200
        new_thinkers = response.json()
        assert len(new_thinkers) == 1

        # New thinker should have a color not in existing_colors
        new_color = new_thinkers[0]["color"]
        assert new_color not in existing_colors
        assert new_color in [
            "#6366f1",
            "#ec4899",
            "#10b981",
            "#f59e0b",
            "#8b5cf6",
        ]

    async def test_add_thinkers_respects_custom_color(self, client: AsyncClient) -> None:
        """When adding thinkers with custom color, should preserve it."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Art",
                "thinkers": [
                    {
                        "name": "Da Vinci",
                        "bio": "Renaissance artist",
                        "positions": "Painter",
                        "style": "Renaissance",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Add thinker with custom color
        custom_color = "#ff0000"
        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            json=[
                {
                    "name": "Michelangelo",
                    "bio": "Sculptor",
                    "positions": "Artist",
                    "style": "Classical",
                    "color": custom_color,
                }
            ],
            headers=auth_headers,
        )
        assert response.status_code == 200
        new_thinkers = response.json()
        assert len(new_thinkers) == 1
        assert new_thinkers[0]["color"] == custom_color

    async def test_add_thinkers_color_pool_exhaustion(self, client: AsyncClient) -> None:
        """When all colors are used, adding with default should still work."""
        auth_headers = await get_auth_headers(client)

        # Create conversation with 4 thinkers
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Philosophy",
                "thinkers": [
                    {
                        "name": f"Thinker{i}",
                        "bio": f"Bio {i}",
                        "positions": "Philosopher",
                        "style": "Analytical",
                    }
                    for i in range(4)
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]
        existing_thinkers = response.json()["thinkers"]
        existing_colors = {t["color"] for t in existing_thinkers}
        assert len(existing_colors) == 4

        # Add 5th thinker - color pool might be empty, should still work
        response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            json=[
                {
                    "name": "FifthThinker",
                    "bio": "Fifth philosopher",
                    "positions": "Thinker",
                    "style": "Modern",
                    "color": "#6366f1",  # Default
                }
            ],
            headers=auth_headers,
        )
        assert response.status_code == 200
        new_thinkers = response.json()
        assert len(new_thinkers) == 1
        # Should have some color assigned (might be default if pool empty)
        assert new_thinkers[0]["color"] is not None


class TestSendMessageDisplayName:
    """Test message creation with display name fallback (lines 257-265)."""

    async def test_send_message_uses_display_name_when_set(self, client: AsyncClient) -> None:
        """Messages should use user's display_name if set."""
        auth_headers = await get_auth_headers(client)

        # Update user profile with display name
        response = await client.patch(
            "/api/auth/profile",
            json={"display_name": "Dr. Alice"},
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Create conversation
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Logic",
                "thinkers": [
                    {
                        "name": "Aristotle",
                        "bio": "Ancient philosopher",
                        "positions": "Logician",
                        "style": "Analytical",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Send message
        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "What is logic?"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        message = response.json()
        assert message["sender_name"] == "Dr. Alice"
        assert message["sender_type"] == "user"

    async def test_send_message_falls_back_to_username_when_no_display_name(
        self, client: AsyncClient
    ) -> None:
        """Messages should use username if display_name is not set."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Mathematics",
                "thinkers": [
                    {
                        "name": "Pythagoras",
                        "bio": "Greek mathematician",
                        "positions": "Mathematician",
                        "style": "Geometric",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Send message
        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "What is a triangle?"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        message = response.json()
        # Should use username (testuser) as fallback
        assert message["sender_name"] == "Testuser"
        assert message["sender_type"] == "user"

    async def test_send_message_updates_sender_name_after_profile_change(
        self, client: AsyncClient
    ) -> None:
        """Messages should reflect current display_name, not cached value."""
        auth_headers = await get_auth_headers(client)

        # Create conversation
        response = await client.post(
            "/api/conversations",
            json={
                "topic": "Identity",
                "thinkers": [
                    {
                        "name": "Descartes",
                        "bio": "French philosopher",
                        "positions": "Rationalist",
                        "style": "Methodical",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        conversation_id = response.json()["id"]

        # Send first message (no display name)
        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "Who am I?"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        first_message = response.json()
        assert first_message["sender_name"] == "Testuser"

        # Update display name
        response = await client.patch(
            "/api/auth/profile",
            json={"display_name": "René"},
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Send second message (with display name)
        response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "I think, therefore I am."},
            headers=auth_headers,
        )
        assert response.status_code == 200
        second_message = response.json()
        assert second_message["sender_name"] == "René"
