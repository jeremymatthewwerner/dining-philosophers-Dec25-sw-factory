"""
Edge case tests - Saturday focus on error paths and boundary conditions.

Tests cover:
- Sending messages to active conversations
- Password change validation edge cases
"""

import pytest
from httpx import AsyncClient

from tests.conftest import get_auth_headers


@pytest.mark.asyncio
class TestConversationMessageEdgeCases:
    """Test edge cases for conversation messaging."""

    async def test_send_message_to_active_conversation_succeeds(self, client: AsyncClient) -> None:
        """Test that sending message to active conversation works normally."""
        # Create user and login
        headers = await get_auth_headers(client, "activeuser", "password123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Active Topic",
                "thinkers": [
                    {
                        "name": "Aristotle",
                        "bio": "Greek philosopher",
                        "positions": "Logic",
                        "style": "Analytical",
                        "color": "#ec4899",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # Send message
        msg_response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Normal message"},
        )

        assert msg_response.status_code == 200
        data = msg_response.json()
        assert data["content"] == "Normal message"

    async def test_send_empty_message_rejected(self, client: AsyncClient) -> None:
        """Test that empty messages are rejected with appropriate error."""
        headers = await get_auth_headers(client, "emptyuser", "password123")

        # Create conversation
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Greek philosopher",
                        "positions": "Ethics",
                        "style": "Socratic method",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # Try to send empty message
        msg_response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": ""},
        )

        # Should be rejected (validation error)
        assert msg_response.status_code == 422


@pytest.mark.asyncio
class TestPasswordChangeEdgeCases:
    """Test edge cases for password change validation."""

    async def test_change_password_to_same_password(self, client: AsyncClient) -> None:
        """Test changing password to the same password (should be allowed but wasteful)."""
        headers = await get_auth_headers(client, "sameuser", "password123")

        # Change password to same password
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "password123",
                "new_password": "password123",
            },
        )

        # Should succeed (no validation preventing same password)
        # This is a design decision - could add validation to prevent this
        assert response.status_code == 200
        assert response.json()["message"] == "Password changed successfully"

    async def test_change_password_with_leading_trailing_whitespace(
        self, client: AsyncClient
    ) -> None:
        """Test that passwords with leading/trailing whitespace are handled correctly."""
        headers = await get_auth_headers(client, "wsuser", "password123")

        # Try to change password with whitespace
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "password123",
                "new_password": "  newpassword123  ",  # Has whitespace
            },
        )

        # Should succeed - passwords are not trimmed, whitespace is part of password
        # This tests that the system doesn't silently trim passwords
        assert response.status_code == 200

        # Verify can login with the whitespace password
        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "wsuser",
                "password": "  newpassword123  ",
            },
        )
        assert login_response.status_code == 200

    async def test_change_password_with_very_long_password(self, client: AsyncClient) -> None:
        """Test that very long passwords are handled correctly."""
        headers = await get_auth_headers(client, "longuser", "password123")

        # Create a 500-character password
        long_password = "A" * 500

        # Try to change to very long password
        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "password123",
                "new_password": long_password,
            },
        )

        # Should either succeed or fail with validation error (not crash)
        assert response.status_code in [200, 400, 422]

        # If it succeeded, verify we can login with the long password
        if response.status_code == 200:
            login_response = await client.post(
                "/api/auth/login",
                json={
                    "username": "longuser",
                    "password": long_password,
                },
            )
            assert login_response.status_code == 200


@pytest.mark.asyncio
class TestConversationEdgeCases:
    """Test edge cases for conversation creation and management."""

    async def test_create_conversation_with_empty_topic(self, client: AsyncClient) -> None:
        """Test that creating conversation with empty topic is rejected."""
        headers = await get_auth_headers(client, "topicuser", "password123")

        # Try to create conversation with empty topic
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "",  # Empty topic
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Greek philosopher",
                        "positions": "Forms",
                        "style": "Dialogues",
                        "color": "#6366f1",
                    }
                ],
            },
        )

        # Should be rejected with validation error
        assert response.status_code == 422

    async def test_create_conversation_with_very_long_topic(self, client: AsyncClient) -> None:
        """Test that very long topics are handled gracefully."""
        headers = await get_auth_headers(client, "longtopicuser", "password123")

        # Create a 10000-character topic
        long_topic = "Philosophy " * 1000  # ~11000 characters

        # Try to create conversation with very long topic
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": long_topic,
                "thinkers": [
                    {
                        "name": "Kant",
                        "bio": "German philosopher",
                        "positions": "Ethics, metaphysics",
                        "style": "Systematic",
                        "color": "#10b981",
                    }
                ],
            },
        )

        # Should either succeed or fail gracefully (not crash)
        assert response.status_code in [200, 400, 422]

        # If it succeeded, verify topic is stored correctly
        if response.status_code == 200:
            conv_id = response.json()["id"]
            get_response = await client.get(
                f"/api/conversations/{conv_id}",
                headers=headers,
            )
            assert get_response.status_code == 200
            # Topic should be preserved (may be truncated depending on DB schema)
            assert len(get_response.json()["topic"]) > 0
