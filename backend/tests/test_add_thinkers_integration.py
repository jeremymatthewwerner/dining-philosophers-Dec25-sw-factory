"""Integration tests for PUT /api/conversations/{id}/thinkers endpoint.

Tests the add_thinkers_to_conversation endpoint which allows dynamically
adding thinkers to existing conversations. This endpoint was previously
untested, covering lines 154-220 in app/api/conversations.py.

Issue: #485 (QA Agent integration-gaps focus)
"""

from unittest.mock import MagicMock, patch

from httpx import AsyncClient

from tests.conftest import create_thinker_input, get_auth_headers


class TestAddThinkersToConversation:
    """Test suite for adding thinkers to existing conversations."""

    async def test_add_single_thinker_to_conversation(self, client: AsyncClient) -> None:
        """Test adding a single thinker to a conversation with existing thinkers."""
        # Create conversation with 2 thinkers
        headers = await get_auth_headers(client, "add1user", "password123")

        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Philosophy of Mind",
                "thinkers": [
                    create_thinker_input("Socrates", "Ancient Greek philosopher"),
                    create_thinker_input("Aristotle", "Student of Plato"),
                ],
            },
        )
        assert create_response.status_code == 200
        conversation_id = create_response.json()["id"]

        # Mock knowledge service to avoid triggering real research
        with patch("app.services.knowledge_research.knowledge_service") as mock_service:
            mock_service.trigger_research = MagicMock()

            # Add 1 more thinker
            add_response = await client.put(
                f"/api/conversations/{conversation_id}/thinkers",
                headers=headers,
                json=[
                    create_thinker_input("Plato", "Teacher of Aristotle"),
                ],
            )

        assert add_response.status_code == 200
        data = add_response.json()

        # Verify response contains the new thinker
        assert len(data) == 1
        assert data[0]["name"] == "Plato"
        assert data[0]["bio"] == "Teacher of Aristotle"

        # Verify knowledge research was triggered
        mock_service.trigger_research.assert_called_once_with("Plato")

        # Verify conversation now has 3 thinkers
        get_response = await client.get(
            f"/api/conversations/{conversation_id}",
            headers=headers,
        )
        assert get_response.status_code == 200
        conversation = get_response.json()
        assert len(conversation["thinkers"]) == 3

    async def test_add_multiple_thinkers_to_conversation(self, client: AsyncClient) -> None:
        """Test adding multiple thinkers at once."""
        headers = await get_auth_headers(client, "add2user", "password123")

        # Create conversation with 1 thinker
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Ethics",
                "thinkers": [
                    create_thinker_input("Socrates", "Ancient Greek philosopher"),
                ],
            },
        )
        assert create_response.status_code == 200
        conversation_id = create_response.json()["id"]

        with patch("app.services.knowledge_research.knowledge_service") as mock_service:
            mock_service.trigger_research = MagicMock()

            # Add 2 thinkers at once
            add_response = await client.put(
                f"/api/conversations/{conversation_id}/thinkers",
                headers=headers,
                json=[
                    create_thinker_input("Aristotle", "Student of Plato"),
                    create_thinker_input("Confucius", "Chinese philosopher"),
                ],
            )

        assert add_response.status_code == 200
        data = add_response.json()

        # Verify response contains both new thinkers
        assert len(data) == 2
        assert {t["name"] for t in data} == {"Aristotle", "Confucius"}

        # Verify knowledge research was triggered for both
        assert mock_service.trigger_research.call_count == 2

    async def test_add_thinker_assigns_unique_colors(self, client: AsyncClient) -> None:
        """Test that added thinkers get unique colors not used by existing thinkers."""
        headers = await get_auth_headers(client, "add3user", "password123")

        # Create conversation with 2 thinkers (will use first 2 colors)
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Metaphysics",
                "thinkers": [
                    create_thinker_input("Socrates", "Ancient Greek philosopher"),
                    create_thinker_input("Aristotle", "Student of Plato"),
                ],
            },
        )
        assert create_response.status_code == 200
        conversation_id = create_response.json()["id"]
        existing_colors = {t["color"] for t in create_response.json()["thinkers"]}

        with patch("app.services.knowledge_research.knowledge_service") as mock_service:
            mock_service.trigger_research = MagicMock()

            # Add 1 thinker with default color
            add_response = await client.put(
                f"/api/conversations/{conversation_id}/thinkers",
                headers=headers,
                json=[
                    create_thinker_input("Plato", "Teacher of Aristotle"),
                ],
            )

        assert add_response.status_code == 200
        new_thinker = add_response.json()[0]

        # Verify the new thinker got a unique color
        assert new_thinker["color"] not in existing_colors

    async def test_add_thinker_preserves_custom_color(self, client: AsyncClient) -> None:
        """Test that custom colors are preserved when adding thinkers."""
        headers = await get_auth_headers(client, "add4user", "password123")

        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Logic",
                "thinkers": [
                    create_thinker_input("Socrates", "Ancient Greek philosopher"),
                ],
            },
        )
        assert create_response.status_code == 200
        conversation_id = create_response.json()["id"]

        with patch("app.services.knowledge_research.knowledge_service") as mock_service:
            mock_service.trigger_research = MagicMock()

            # Add thinker with custom color
            custom_color = "#ff0000"
            add_response = await client.put(
                f"/api/conversations/{conversation_id}/thinkers",
                headers=headers,
                json=[
                    {
                        **create_thinker_input("Aristotle", "Student of Plato"),
                        "color": custom_color,
                    }
                ],
            )

        assert add_response.status_code == 200
        new_thinker = add_response.json()[0]

        # Verify custom color was preserved
        assert new_thinker["color"] == custom_color

    async def test_add_thinker_at_max_limit(self, client: AsyncClient) -> None:
        """Test adding thinker when at exactly 4 existing (reaches max 5)."""
        headers = await get_auth_headers(client, "add5user", "password123")

        # Create conversation with 4 thinkers
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Ancient Philosophy",
                "thinkers": [
                    create_thinker_input("Socrates", "Ancient Greek philosopher"),
                    create_thinker_input("Aristotle", "Student of Plato"),
                    create_thinker_input("Plato", "Teacher of Aristotle"),
                    create_thinker_input("Confucius", "Chinese philosopher"),
                ],
            },
        )
        assert create_response.status_code == 200
        conversation_id = create_response.json()["id"]

        with patch("app.services.knowledge_research.knowledge_service") as mock_service:
            mock_service.trigger_research = MagicMock()

            # Add 1 more thinker (reaches exactly 5)
            add_response = await client.put(
                f"/api/conversations/{conversation_id}/thinkers",
                headers=headers,
                json=[
                    create_thinker_input("Marcus Aurelius", "Roman emperor"),
                ],
            )

        assert add_response.status_code == 200
        assert len(add_response.json()) == 1

        # Verify conversation now has exactly 5 thinkers
        get_response = await client.get(
            f"/api/conversations/{conversation_id}",
            headers=headers,
        )
        assert get_response.status_code == 200
        assert len(get_response.json()["thinkers"]) == 5

    async def test_add_thinker_exceeds_max_limit(self, client: AsyncClient) -> None:
        """Test that adding thinker when at 5 limit fails with 400."""
        headers = await get_auth_headers(client, "add6user", "password123")

        # Create conversation with 5 thinkers (maximum)
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "World Philosophy",
                "thinkers": [
                    create_thinker_input("Socrates", "Ancient Greek philosopher"),
                    create_thinker_input("Aristotle", "Student of Plato"),
                    create_thinker_input("Plato", "Teacher of Aristotle"),
                    create_thinker_input("Confucius", "Chinese philosopher"),
                    create_thinker_input("Marcus Aurelius", "Roman emperor"),
                ],
            },
        )
        assert create_response.status_code == 200
        conversation_id = create_response.json()["id"]

        # Attempt to add another thinker (exceeds limit)
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers,
            json=[
                create_thinker_input("Seneca", "Roman Stoic philosopher"),
            ],
        )

        # Verify request is rejected with 400
        assert add_response.status_code == 400
        error_detail = add_response.json()["detail"]
        assert "5" in error_detail  # Error mentions the limit
        assert "Cannot add" in error_detail

    async def test_add_thinker_to_nonexistent_conversation(self, client: AsyncClient) -> None:
        """Test adding thinker to non-existent conversation returns 404."""
        headers = await get_auth_headers(client, "add7user", "password123")

        fake_uuid = "00000000-0000-0000-0000-000000000000"

        add_response = await client.put(
            f"/api/conversations/{fake_uuid}/thinkers",
            headers=headers,
            json=[
                create_thinker_input("Socrates", "Ancient Greek philosopher"),
            ],
        )

        assert add_response.status_code == 404
        assert "not found" in add_response.json()["detail"].lower()

    async def test_add_thinker_to_other_users_conversation(self, client: AsyncClient) -> None:
        """Test that users cannot add thinkers to other users' conversations."""
        # User A creates conversation
        headers_a = await get_auth_headers(client, "add8usera", "password123")
        create_response = await client.post(
            "/api/conversations",
            headers=headers_a,
            json={
                "topic": "Ethics",
                "thinkers": [
                    create_thinker_input("Socrates", "Ancient Greek philosopher"),
                ],
            },
        )
        assert create_response.status_code == 200
        conversation_id = create_response.json()["id"]

        # User B attempts to add thinker to User A's conversation
        headers_b = await get_auth_headers(client, "add8userb", "password123")
        add_response = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=headers_b,
            json=[
                create_thinker_input("Aristotle", "Student of Plato"),
            ],
        )

        # Verify request is rejected with 404 (conversation not found for User B)
        assert add_response.status_code == 404
        assert "not found" in add_response.json()["detail"].lower()
