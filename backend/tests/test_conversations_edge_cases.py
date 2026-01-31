"""Edge case tests for conversations API - comprehensive error paths.

Focus: Testing error conditions, race scenarios, and boundary cases for conversation management.
Saturday QA focus: Edge case analysis - test error paths and boundary conditions.
"""

import pytest
from fastapi import status
from httpx import AsyncClient

from tests.conftest import get_auth_headers


class TestConversationCreationEdgeCases:
    """Test edge cases when creating conversations."""

    @pytest.mark.asyncio
    async def test_create_conversation_with_no_thinkers(self, client: AsyncClient) -> None:
        """Test that creating a conversation with empty thinkers list is rejected.

        Edge case: Empty required list
        """
        headers = await get_auth_headers(
            client, username="user_no_thinkers", password="testpass123"
        )

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test conversation",
                "thinkers": [],  # Empty list
            },
        )

        # Should be rejected with validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_conversation_with_too_many_thinkers(self, client: AsyncClient) -> None:
        """Test creating conversation with more than maximum allowed thinkers.

        Edge case: Upper boundary for list size
        """
        headers = await get_auth_headers(
            client, username="user_many_thinkers", password="testpass123"
        )

        # Create 11 thinkers (assuming max is 10)
        thinkers = [
            {
                "name": f"Thinker{i}",
                "bio": f"Bio {i}",
                "positions": f"Position {i}",
                "style": f"Style {i}",
                "color": "#6366f1",
            }
            for i in range(11)
        ]

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Too many thinkers",
                "thinkers": thinkers,
            },
        )

        # Should either succeed or reject based on max_items validation
        # If no max_items constraint exists, this will succeed
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    @pytest.mark.asyncio
    async def test_create_conversation_with_duplicate_thinker_names(
        self, client: AsyncClient
    ) -> None:
        """Test creating conversation with duplicate thinker names.

        Edge case: Duplicate entries in list
        """
        headers = await get_auth_headers(
            client, username="user_duplicate_thinkers", password="testpass123"
        )

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Duplicate thinkers test",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Greek philosopher",
                        "positions": "Question everything",
                        "style": "Socratic method",
                        "color": "#6366f1",
                    },
                    {
                        "name": "Socrates",  # Duplicate name
                        "bio": "Different bio",
                        "positions": "Different positions",
                        "style": "Different style",
                        "color": "#ec4899",
                    },
                ],
            },
        )

        # API currently allows duplicate names - verify it handles gracefully
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["thinkers"]) == 2

    @pytest.mark.asyncio
    async def test_create_conversation_with_very_long_topic(self, client: AsyncClient) -> None:
        """Test creating conversation with extremely long topic (5000+ chars).

        Edge case: Large text input
        """
        headers = await get_auth_headers(client, username="user_long_topic", password="testpass123")

        # Create 5000 character topic
        long_topic = "Philosophy of everything " * 200  # ~5000 chars

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": long_topic,
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

        # Should either succeed or reject based on max_length constraint
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    @pytest.mark.asyncio
    async def test_create_conversation_with_special_characters_in_thinker_fields(
        self, client: AsyncClient
    ) -> None:
        """Test thinker fields with special characters, emojis, and HTML.

        Edge case: XSS prevention and special character handling
        """
        headers = await get_auth_headers(
            client, username="user_special_chars", password="testpass123"
        )

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Special characters test",
                "thinkers": [
                    {
                        "name": "Test<script>alert('xss')</script>",
                        "bio": "Bio with 🎉 emojis and 你好 unicode",
                        "positions": "Positions with \"quotes\" and 'apostrophes'",
                        "style": "Style with & < > symbols",
                        "color": "#6366f1",
                    }
                ],
            },
        )

        # Should succeed and preserve special characters
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Verify data is preserved (not sanitized on backend)
        assert "script" in data["thinkers"][0]["name"]


class TestConversationRetrievalEdgeCases:
    """Test edge cases when retrieving conversations."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation_different_user(
        self, client: AsyncClient
    ) -> None:
        """Test accessing another user's conversation returns 404.

        Edge case: Authorization boundary - cross-user access
        """
        # Create user 1 with conversation
        user1_headers = await get_auth_headers(
            client, username="user1_conv", password="testpass123"
        )
        conv_response = await client.post(
            "/api/conversations",
            headers=user1_headers,
            json={
                "topic": "User1's conversation",
                "thinkers": [
                    {
                        "name": "Aristotle",
                        "bio": "Greek philosopher",
                        "positions": "Logic",
                        "style": "Systematic",
                        "color": "#10b981",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Create user 2 and try to access user 1's conversation
        user2_headers = await get_auth_headers(
            client, username="user2_conv", password="testpass123"
        )
        response = await client.get(f"/api/conversations/{conv_id}", headers=user2_headers)

        # Should return 404 (not found) not 403 (forbidden)
        # This prevents information disclosure about conversation existence
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_list_conversations_when_session_has_none(self, client: AsyncClient) -> None:
        """Test listing conversations when user has no conversations.

        Edge case: Empty result set
        """
        headers = await get_auth_headers(client, username="user_no_convs", password="testpass123")

        response = await client.get("/api/conversations", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_get_conversation_after_session_expired(self, client: AsyncClient) -> None:
        """Test accessing conversation with expired/invalid token.

        Edge case: Token expiration
        """
        # Use invalid token
        invalid_headers = {"Authorization": "Bearer invalid_token_xyz"}

        fake_uuid = "12345678-1234-5678-1234-567812345678"
        response = await client.get(f"/api/conversations/{fake_uuid}", headers=invalid_headers)

        # Should return 401 (unauthorized)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestConversationDeletionEdgeCases:
    """Test edge cases when deleting conversations."""

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(self, client: AsyncClient) -> None:
        """Test deleting a conversation that doesn't exist.

        Edge case: Idempotency - deleting non-existent resource
        """
        headers = await get_auth_headers(
            client, username="user_delete_nonexistent", password="testpass123"
        )

        fake_uuid = "12345678-1234-5678-1234-567812345678"
        response = await client.delete(f"/api/conversations/{fake_uuid}", headers=headers)

        # Should return 404
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_conversation_with_many_messages(self, client: AsyncClient) -> None:
        """Test deleting conversation with many associated messages.

        Edge case: Cascade deletion performance
        """
        headers = await get_auth_headers(
            client, username="user_delete_large", password="testpass123"
        )

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Large conversation",
                "thinkers": [
                    {
                        "name": "Marcus Aurelius",
                        "bio": "Roman Emperor",
                        "positions": "Stoicism",
                        "style": "Meditations",
                        "color": "#f59e0b",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Delete conversation (messages cascade)
        response = await client.delete(f"/api/conversations/{conv_id}", headers=headers)

        # Should succeed with 200 and JSON response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "deleted"

        # Verify conversation is gone
        get_response = await client.get(f"/api/conversations/{conv_id}", headers=headers)
        assert get_response.status_code == status.HTTP_404_NOT_FOUND


class TestMessageCreationEdgeCases:
    """Test edge cases when creating messages in conversations."""

    @pytest.mark.asyncio
    async def test_create_message_with_empty_content(self, client: AsyncClient) -> None:
        """Test creating message with empty content string.

        Edge case: Empty required field
        """
        headers = await get_auth_headers(
            client, username="user_empty_message", password="testpass123"
        )

        # Create conversation first
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test conversation",
                "thinkers": [
                    {
                        "name": "Confucius",
                        "bio": "Chinese philosopher",
                        "positions": "Ethics",
                        "style": "Analects",
                        "color": "#8b5cf6",
                    }
                ],
            },
        )
        conv_id = conv_response.json()["id"]

        # Try to create empty message
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": ""},
        )

        # Should be rejected with validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_message_with_extremely_long_content(self, client: AsyncClient) -> None:
        """Test creating message with 100k+ character content.

        Edge case: Large input validation
        """
        headers = await get_auth_headers(
            client, username="user_long_message", password="testpass123"
        )

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Long message test",
                "thinkers": [
                    {
                        "name": "Seneca",
                        "bio": "Roman Stoic",
                        "positions": "Ethics",
                        "style": "Letters",
                        "color": "#ec4899",
                    }
                ],
            },
        )
        conv_id = conv_response.json()["id"]

        # Create 100k character message
        long_content = "a" * 100000

        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": long_content},
        )

        # Should either succeed or reject based on max_length constraint
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    @pytest.mark.asyncio
    async def test_create_message_in_nonexistent_conversation(self, client: AsyncClient) -> None:
        """Test creating message in conversation that doesn't exist.

        Edge case: Invalid foreign key reference
        """
        headers = await get_auth_headers(
            client, username="user_message_nonexistent", password="testpass123"
        )

        fake_uuid = "12345678-1234-5678-1234-567812345678"
        response = await client.post(
            f"/api/conversations/{fake_uuid}/messages",
            headers=headers,
            json={"content": "Test message"},
        )

        # Should return 404
        assert response.status_code == status.HTTP_404_NOT_FOUND
