"""Tests to improve coverage for app/api/conversations.py.

Written by QA Agent during flaky-hunt session (Tuesday).
Issue: #592

These tests target uncovered error paths and edge cases:
- Get conversation with invalid ID
- Delete conversation with invalid ID
- Add thinkers with validation errors
- Edge cases for max thinker limits
"""

from httpx import AsyncClient

from tests.conftest import create_thinker_input, get_auth_headers


class TestConversationErrorPaths:
    """Test error paths in conversation endpoints."""

    async def test_get_nonexistent_conversation_returns_404(self, client: AsyncClient) -> None:
        """Test getting a conversation that doesn't exist returns 404."""
        headers = await get_auth_headers(client, "flaky_get_404", "password123")

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/conversations/{fake_id}", headers=headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_delete_nonexistent_conversation_returns_404(self, client: AsyncClient) -> None:
        """Test deleting a conversation that doesn't exist returns 404."""
        headers = await get_auth_headers(client, "flaky_del_404", "password123")

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(f"/api/conversations/{fake_id}", headers=headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_add_thinkers_to_nonexistent_conversation_returns_404(
        self, client: AsyncClient
    ) -> None:
        """Test adding thinkers to non-existent conversation returns 404."""
        headers = await get_auth_headers(client, "flaky_add_404", "password123")

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.put(
            f"/api/conversations/{fake_id}/thinkers",
            headers=headers,
            json=[create_thinker_input("Aristotle", "Greek")],
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_add_thinkers_exceeding_max_limit_returns_400(self, client: AsyncClient) -> None:
        """Test adding thinkers beyond the 5 thinker limit returns 400."""
        headers = await get_auth_headers(client, "flaky_max_limit", "password123")

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

    async def test_add_thinker_picks_available_colors(self, client: AsyncClient) -> None:
        """Test that adding thinkers picks from available colors."""
        headers = await get_auth_headers(client, "flaky_colors", "password123")

        # Create conversation with 2 thinkers using specific colors
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Color Test",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Greek",
                        "positions": "Questions",
                        "style": "Socratic",
                        "color": "#6366f1",  # Use first color
                    },
                    {
                        "name": "Plato",
                        "bio": "Greek",
                        "positions": "Forms",
                        "style": "Dialogue",
                        "color": "#ec4899",  # Use second color
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
        # Should be one of the available colors
        assert new_thinker["color"] in ["#10b981", "#f59e0b", "#8b5cf6"]

    async def test_list_conversations_empty_for_new_user(self, client: AsyncClient) -> None:
        """Test listing conversations returns empty array for new users."""
        headers = await get_auth_headers(client, "flaky_empty_list", "password123")

        response = await client.get("/api/conversations", headers=headers)

        assert response.status_code == 200
        assert response.json() == []
