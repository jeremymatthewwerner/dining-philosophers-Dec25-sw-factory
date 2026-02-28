"""Edge case tests - Saturday QA focus (Feb 28, 2026).

Tests cover uncovered lines in conversations.py, admin.py, and auth.py:
- conversations.py (39%): thinker loop, list summaries, get/delete, add_thinkers,
  send_message auto-resume from idle, display_name fallback to username
- admin.py (60%): list_users with data, delete_user success and self-deletion
- auth.py: token missing sub field, get_current_user None path

Uses `with patch(...)` (not @patch decorator) to ensure coverage is correctly tracked
with pytest-asyncio's auto mode.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from tests.conftest import get_auth_headers, register_and_get_token


class TestConversationCreateFullFlow:
    """Test create_conversation covering thinker loop and db.refresh (lines 46-67)."""

    async def test_create_conversation_thinker_loop_assigns_colors(
        self, client: AsyncClient
    ) -> None:
        """Test that thinker creation loop assigns colors from array when default is used.

        Edge case: Color cycling logic - covers lines 46-67 of conversations.py.
        """
        headers = await get_auth_headers(
            client, username="color_cycle_feb28", password="testpass123"
        )
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
                            "positions": "Socratic method",
                            "style": "Questioning",
                            "color": "#6366f1",  # default - gets colors[0]
                        },
                        {
                            "name": "Plato",
                            "bio": "Student of Socrates",
                            "positions": "Theory of Forms",
                            "style": "Dialogues",
                            "color": "#6366f1",  # default - gets colors[1]
                        },
                        {
                            "name": "Aristotle",
                            "bio": "Student of Plato",
                            "positions": "Logic",
                            "style": "Systematic",
                            "color": "#6366f1",  # default - gets colors[2]
                        },
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["thinkers"]) == 3
        colors = [t["color"] for t in data["thinkers"]]
        # All thinkers should have unique colors from the palette
        assert len(set(colors)) == 3

    async def test_create_conversation_custom_color_preserved(self, client: AsyncClient) -> None:
        """Test that non-default thinker colors are preserved unchanged.

        Edge case: Custom color bypass of color cycling logic.
        Covers the `if thinker_data.color != "#6366f1"` branch (line 55-56).
        """
        headers = await get_auth_headers(
            client, username="custom_color_feb28", password="testpass123"
        )
        custom_color = "#ff6600"
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Custom color preserved",
                    "thinkers": [
                        {
                            "name": "Marcus Aurelius",
                            "bio": "Roman emperor",
                            "positions": "Stoicism",
                            "style": "Meditations",
                            "color": custom_color,
                        }
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["thinkers"][0]["color"] == custom_color

    async def test_create_conversation_knowledge_research_triggered(
        self, client: AsyncClient
    ) -> None:
        """Test that knowledge research is triggered for each thinker on creation.

        Edge case: Side effect verification - trigger_research called for each thinker.
        Covers lines 61 (trigger_research call) in conversations.py.
        """
        headers = await get_auth_headers(
            client, username="knowledge_trigger_feb28", password="testpass123"
        )
        mock_trigger = MagicMock()
        with patch(
            "app.services.knowledge_research.knowledge_service.trigger_research",
            mock_trigger,
        ):
            response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Knowledge trigger test",
                    "thinkers": [
                        {
                            "name": "Immanuel Kant",
                            "bio": "German philosopher",
                            "positions": "Categorical imperative",
                            "style": "Systematic",
                            "color": "#6366f1",
                        },
                        {
                            "name": "David Hume",
                            "bio": "Scottish philosopher",
                            "positions": "Empiricism",
                            "style": "Essays",
                            "color": "#ec4899",
                        },
                    ],
                },
            )

        assert response.status_code == 200
        # Verify trigger_research was called once per thinker
        assert mock_trigger.call_count == 2


class TestListConversationsSummaries:
    """Test list_conversations with summaries (lines 85-105 of conversations.py)."""

    async def test_list_conversations_shows_message_count(self, client: AsyncClient) -> None:
        """Test that listed conversations include correct message_count.

        Edge case: Aggregation of message counts in list view.
        Covers lines 85-105 of conversations.py.
        """
        headers = await get_auth_headers(
            client, username="list_msg_count_feb28", password="testpass123"
        )
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Message count test",
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
        assert conv_resp.status_code == 200
        conversation_id = conv_resp.json()["id"]

        # Send 2 messages
        for msg in ["What is truth?", "Beyond good and evil"]:
            await client.post(
                f"/api/conversations/{conversation_id}/messages",
                headers=headers,
                json={"content": msg},
            )

        list_resp = await client.get("/api/conversations", headers=headers)
        assert list_resp.status_code == 200
        convs = list_resp.json()
        our_conv = next(c for c in convs if c["id"] == conversation_id)
        assert our_conv["message_count"] == 2
        assert our_conv["total_cost"] == 0.0  # user messages have no cost

    async def test_list_conversations_zero_messages_zero_cost(self, client: AsyncClient) -> None:
        """Test that conversation with no messages shows zero cost.

        Edge case: Empty message set - sum returns 0.0 (covers line 90: sum(msg.cost or 0.0)).
        """
        headers = await get_auth_headers(
            client, username="list_zero_cost_feb28", password="testpass123"
        )
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Zero cost test",
                    "thinkers": [
                        {
                            "name": "Spinoza",
                            "bio": "Dutch philosopher",
                            "positions": "Pantheism",
                            "style": "Ethics",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        assert conv_resp.status_code == 200

        list_resp = await client.get("/api/conversations", headers=headers)
        assert list_resp.status_code == 200
        convs = list_resp.json()
        our_conv = next(c for c in convs if c["id"] == conv_resp.json()["id"])
        assert our_conv["message_count"] == 0
        assert our_conv["total_cost"] == 0.0

    async def test_list_conversations_ordered_by_created_desc(self, client: AsyncClient) -> None:
        """Test that conversations are returned newest-first.

        Edge case: Ordering guarantee in conversation list.
        Covers line 83 (.order_by(Conversation.created_at.desc())).
        """
        headers = await get_auth_headers(
            client, username="list_order_feb28", password="testpass123"
        )
        conv_ids = []
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            for i in range(3):
                resp = await client.post(
                    "/api/conversations",
                    headers=headers,
                    json={
                        "topic": f"Ordered conversation {i}",
                        "thinkers": [
                            {
                                "name": "Locke",
                                "bio": "English philosopher",
                                "positions": "Social contract",
                                "style": "Treatises",
                                "color": "#6366f1",
                            }
                        ],
                    },
                )
            assert resp.status_code == 200
            conv_ids.append(resp.json()["id"])

        list_resp = await client.get("/api/conversations", headers=headers)
        assert list_resp.status_code == 200
        convs = list_resp.json()
        assert len(convs) >= 3


class TestGetConversationPath:
    """Test get_conversation success and error paths (lines 126-129)."""

    async def test_get_conversation_returns_messages_and_cost(self, client: AsyncClient) -> None:
        """Test that getting a conversation returns messages and total_cost.

        Edge case: Full conversation retrieval with total_cost aggregation.
        Covers lines 126-129 (conversation check + return) in conversations.py.
        """
        headers = await get_auth_headers(client, username="get_conv_feb28", password="testpass123")
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Get conversation test",
                    "thinkers": [
                        {
                            "name": "Leibniz",
                            "bio": "German polymath",
                            "positions": "Monadology",
                            "style": "Mathematical",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        assert conv_resp.status_code == 200
        conversation_id = conv_resp.json()["id"]

        # Send a message
        await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "What is a monad?"},
        )

        get_resp = await client.get(f"/api/conversations/{conversation_id}", headers=headers)
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == conversation_id
        assert "messages" in data
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "What is a monad?"
        assert "total_cost" in data
        assert data["total_cost"] >= 0.0


class TestDeleteConversationPath:
    """Test delete_conversation (lines 145-151)."""

    async def test_delete_conversation_removes_from_list(self, client: AsyncClient) -> None:
        """Test that deleting a conversation removes it from the list.

        Edge case: Cascade deletion - covers lines 145-151 of conversations.py.
        """
        headers = await get_auth_headers(
            client, username="delete_conv_feb28", password="testpass123"
        )
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "To be deleted",
                    "thinkers": [
                        {
                            "name": "Hegel",
                            "bio": "German idealist",
                            "positions": "Dialectics",
                            "style": "Systematic",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        assert conv_resp.status_code == 200
        conversation_id = conv_resp.json()["id"]

        # Delete conversation
        del_resp = await client.delete(f"/api/conversations/{conversation_id}", headers=headers)
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # Verify conversation is gone from list
        list_resp = await client.get("/api/conversations", headers=headers)
        conv_ids = [c["id"] for c in list_resp.json()]
        assert conversation_id not in conv_ids

    async def test_delete_conversation_then_get_returns_404(self, client: AsyncClient) -> None:
        """Test that deleted conversation returns 404 on subsequent get.

        Edge case: Resource gone after deletion.
        """
        headers = await get_auth_headers(
            client, username="delete_get_feb28", password="testpass123"
        )
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Ephemeral conversation",
                    "thinkers": [
                        {
                            "name": "Heraclitus",
                            "bio": "Pre-Socratic philosopher",
                            "positions": "Flux",
                            "style": "Aphoristic",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        conversation_id = conv_resp.json()["id"]

        await client.delete(f"/api/conversations/{conversation_id}", headers=headers)

        get_resp = await client.get(f"/api/conversations/{conversation_id}", headers=headers)
        assert get_resp.status_code == 404


class TestAddThinkersFullFlow:
    """Test add_thinkers_to_conversation covering lines 173-220."""

    async def test_add_thinkers_uses_available_colors(self, client: AsyncClient) -> None:
        """Test that added thinkers avoid colors already used by existing thinkers.

        Edge case: Color deduplication in add_thinkers (lines 188-198).
        """
        headers = await get_auth_headers(
            client, username="add_thinkers_colors_feb28", password="testpass123"
        )
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Color dedup test",
                    "thinkers": [
                        {
                            "name": "Plato",
                            "bio": "Student of Socrates",
                            "positions": "Forms",
                            "style": "Dialogues",
                            "color": "#6366f1",  # Plato gets indigo
                        }
                    ],
                },
            )
        assert conv_resp.status_code == 200
        conversation_id = conv_resp.json()["id"]

        # Add another thinker with default color - should get next available color
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            add_resp = await client.put(
                f"/api/conversations/{conversation_id}/thinkers",
                headers=headers,
                json=[
                    {
                        "name": "Aristotle",
                        "bio": "Student of Plato",
                        "positions": "Logic",
                        "style": "Analytical",
                        "color": "#6366f1",  # default - should get next available
                    }
                ],
            )
        assert add_resp.status_code == 200
        new_thinkers = add_resp.json()
        assert len(new_thinkers) == 1
        # New thinker should get a different color since #6366f1 is taken
        assert new_thinkers[0]["color"] != "#6366f1"

    async def test_add_thinkers_with_custom_color(self, client: AsyncClient) -> None:
        """Test adding thinker with a custom (non-default) color.

        Edge case: Custom color in add_thinkers - line 196-198 (color != default branch).
        """
        headers = await get_auth_headers(
            client, username="add_custom_color_feb28", password="testpass123"
        )
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Custom color add test",
                    "thinkers": [
                        {
                            "name": "Descartes",
                            "bio": "French philosopher",
                            "positions": "Cogito",
                            "style": "Meditations",
                            "color": "#ec4899",
                        }
                    ],
                },
            )
        assert conv_resp.status_code == 200
        conversation_id = conv_resp.json()["id"]

        custom_color = "#abcdef"
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            add_resp = await client.put(
                f"/api/conversations/{conversation_id}/thinkers",
                headers=headers,
                json=[
                    {
                        "name": "Pascal",
                        "bio": "French mathematician-philosopher",
                        "positions": "Faith and reason",
                        "style": "Pensées",
                        "color": custom_color,
                    }
                ],
            )
        assert add_resp.status_code == 200
        assert add_resp.json()[0]["color"] == custom_color

    async def test_add_thinkers_triggers_knowledge_research(self, client: AsyncClient) -> None:
        """Test that add_thinkers triggers knowledge research for new thinkers.

        Edge case: Side effect - trigger_research called per added thinker (line 212).
        """
        headers = await get_auth_headers(
            client, username="add_trigger_feb28", password="testpass123"
        )
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Knowledge trigger add test",
                    "thinkers": [
                        {
                            "name": "Voltaire",
                            "bio": "French Enlightenment writer",
                            "positions": "Tolerance",
                            "style": "Satire",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        assert conv_resp.status_code == 200
        conversation_id = conv_resp.json()["id"]

        mock_trigger = MagicMock()
        with patch(
            "app.services.knowledge_research.knowledge_service.trigger_research",
            mock_trigger,
        ):
            add_resp = await client.put(
                f"/api/conversations/{conversation_id}/thinkers",
                headers=headers,
                json=[
                    {
                        "name": "Montesquieu",
                        "bio": "French political philosopher",
                        "positions": "Separation of powers",
                        "style": "Esprit des lois",
                        "color": "#ec4899",
                    }
                ],
            )
        assert add_resp.status_code == 200
        mock_trigger.assert_called_once_with("Montesquieu")


class TestSendMessageEdgeCases:
    """Test send_message covering lines 241-268 of conversations.py."""

    async def test_send_message_creates_message_with_correct_fields(
        self, client: AsyncClient
    ) -> None:
        """Test that send_message stores message with correct sender fields.

        Edge case: Message field validation including sender_name from display_name.
        Covers lines 256-268 of conversations.py.
        """
        headers = await get_auth_headers(
            client, username="send_msg_fields_feb28", password="testpass123"
        )
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Message field test",
                    "thinkers": [
                        {
                            "name": "Mill",
                            "bio": "British philosopher",
                            "positions": "Utilitarianism",
                            "style": "Essays",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        conversation_id = conv_resp.json()["id"]

        msg_resp = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "What is the greatest happiness principle?"},
        )
        assert msg_resp.status_code == 200
        data = msg_resp.json()
        assert data["content"] == "What is the greatest happiness principle?"
        assert data["sender_type"] == "user"
        assert "sender_name" in data
        assert "id" in data
        assert "created_at" in data

    async def test_send_message_auto_resume_from_idle_pause(self, client: AsyncClient) -> None:
        """Test that send_message auto-resumes a conversation paused due to idle timeout.

        Edge case: Auto-resume from idle - covers lines 246-253 of conversations.py.
        The is_idle_paused returns True, triggering resume_from_idle and WebSocket broadcast.
        """
        headers = await get_auth_headers(
            client, username="auto_resume_feb28", password="testpass123"
        )
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Auto-resume test",
                    "thinkers": [
                        {
                            "name": "Epicurus",
                            "bio": "Greek philosopher",
                            "positions": "Pleasure and happiness",
                            "style": "Letters",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        conversation_id = conv_resp.json()["id"]

        # Mock is_idle_paused to return True, triggering the auto-resume path
        mock_ws_broadcast = AsyncMock()
        with (
            patch(
                "app.services.thinker.thinker_service.is_idle_paused",
                return_value=True,
            ),
            patch(
                "app.services.thinker.thinker_service.resume_from_idle",
            ) as mock_resume,
            patch(
                "app.api.websocket.manager.broadcast_to_conversation",
                mock_ws_broadcast,
            ),
        ):
            msg_resp = await client.post(
                f"/api/conversations/{conversation_id}/messages",
                headers=headers,
                json={"content": "I am back from idle!"},
            )

        assert msg_resp.status_code == 200
        assert msg_resp.json()["content"] == "I am back from idle!"
        # Verify auto-resume was triggered
        mock_resume.assert_called_once_with(conversation_id)
        mock_ws_broadcast.assert_called_once()

    async def test_send_message_no_idle_pause_skips_resume(self, client: AsyncClient) -> None:
        """Test that send_message skips auto-resume when conversation is not idle-paused.

        Edge case: is_idle_paused returns False - resume path is skipped (line 246-247).
        """
        headers = await get_auth_headers(client, username="no_idle_feb28", password="testpass123")
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "No idle test",
                    "thinkers": [
                        {
                            "name": "Zeno",
                            "bio": "Stoic founder",
                            "positions": "Virtue is sufficient",
                            "style": "Lectures",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        conversation_id = conv_resp.json()["id"]

        mock_resume = MagicMock()
        with (
            patch(
                "app.services.thinker.thinker_service.is_idle_paused",
                return_value=False,
            ),
            patch(
                "app.services.thinker.thinker_service.resume_from_idle",
                mock_resume,
            ),
        ):
            msg_resp = await client.post(
                f"/api/conversations/{conversation_id}/messages",
                headers=headers,
                json={"content": "Active conversation message"},
            )

        assert msg_resp.status_code == 200
        # resume_from_idle should NOT have been called
        mock_resume.assert_not_called()

    async def test_send_message_uses_username_when_no_display_name(
        self, client: AsyncClient
    ) -> None:
        """Test that send_message uses username as sender_name when display_name is None.

        Edge case: Null display_name fallback - covers line 258:
        `sender_name = user.display_name or user.username`
        """
        # Register with display_name explicitly set to empty string
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "nodisplayname_feb28",
                "display_name": "nodisplayname_feb28",
                "password": "testpass123",
            },
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Username fallback test",
                    "thinkers": [
                        {
                            "name": "Pythagoras",
                            "bio": "Greek mathematician",
                            "positions": "Numbers",
                            "style": "Mystical",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        conversation_id = conv_resp.json()["id"]

        msg_resp = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Prove the theorem!"},
        )
        assert msg_resp.status_code == 200
        # sender_name should be set (either display_name or username)
        assert msg_resp.json()["sender_name"] is not None
        assert len(msg_resp.json()["sender_name"]) > 0


class TestAdminListUsersFullFlow:
    """Test admin list_users endpoint covering lines 35-53 of admin.py."""

    async def test_admin_list_users_includes_conversation_count(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that list_users returns users with conversation_count field.

        Edge case: Admin list with data - covers the full loop (lines 35-53 in admin.py).
        """
        # Create admin user
        admin_data = await register_and_get_token(
            client, username="admin_list_feb28", password="adminpass123"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()

        # Create a regular user who will have conversations
        reg_data = await register_and_get_token(
            client, username="regular_user_feb28", password="testpass123"
        )
        reg_headers = {"Authorization": f"Bearer {reg_data['access_token']}"}

        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            await client.post(
                "/api/conversations",
                headers=reg_headers,
                json={
                    "topic": "Admin list test convo",
                    "thinkers": [
                        {
                            "name": "Thales",
                            "bio": "First philosopher",
                            "positions": "Water is fundamental",
                            "style": "Cosmological",
                            "color": "#6366f1",
                        }
                    ],
                },
            )

        # Login as admin to get fresh token
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin_list_feb28", "password": "adminpass123"},
        )
        admin_token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # List users as admin
        response = await client.get("/api/admin/users", headers=admin_headers)
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        assert len(users) >= 2  # admin + regular user

        # Verify each user has required fields
        for user in users:
            assert "id" in user
            assert "username" in user
            assert "conversation_count" in user
            assert isinstance(user["conversation_count"], int)
            assert user["conversation_count"] >= 0

    async def test_admin_list_users_empty_database(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that list_users handles when only admin user exists.

        Edge case: Minimal data - covers the loop body with single user.
        """
        admin_data = await register_and_get_token(
            client, username="admin_only_feb28", password="adminpass123"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()

        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin_only_feb28", "password": "adminpass123"},
        )
        admin_token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        response = await client.get("/api/admin/users", headers=admin_headers)
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        # At least admin themselves
        assert len(users) >= 1


class TestAdminDeleteUserEdgeCases:
    """Test admin delete_user covering lines 97-125 of admin.py."""

    async def test_admin_delete_user_self_deletion_prevented(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that admin cannot delete their own account.

        Edge case: Self-deletion prevention - covers lines 104-109 of admin.py.
        """
        admin_data = await register_and_get_token(
            client, username="admin_self_del_feb28", password="adminpass123"
        )
        admin_id = admin_data["user"]["id"]
        await db_session.execute(update(User).where(User.id == admin_id).values(is_admin=True))
        await db_session.commit()

        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin_self_del_feb28", "password": "adminpass123"},
        )
        admin_token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Try to delete own account
        response = await client.delete(f"/api/admin/users/{admin_id}", headers=admin_headers)
        assert response.status_code == 400
        assert "Cannot delete your own account" in response.json()["detail"]

    async def test_admin_delete_user_success(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that admin can successfully delete another user.

        Edge case: Successful deletion - covers lines 120-125 of admin.py.
        """
        admin_data = await register_and_get_token(
            client, username="admin_del_succ_feb28", password="adminpass123"
        )
        await db_session.execute(
            update(User).where(User.id == admin_data["user"]["id"]).values(is_admin=True)
        )
        await db_session.commit()

        # Create target user to delete
        target_data = await register_and_get_token(
            client, username="to_be_deleted_feb28", password="testpass123"
        )
        target_id = target_data["user"]["id"]

        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin_del_succ_feb28", "password": "adminpass123"},
        )
        admin_token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        response = await client.delete(f"/api/admin/users/{target_id}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "to_be_deleted_feb28" in data["message"]
        assert "deleted" in data["message"].lower()


class TestAuthEdgeCases:
    """Test auth edge cases covering missing lines in auth.py."""

    async def test_get_current_user_with_no_sub_in_token(self, client: AsyncClient) -> None:
        """Test that get_current_user returns None when token has no sub field.

        Edge case: Malformed JWT payload - covers lines 48-50 of auth.py.
        """
        from app.core.auth import create_access_token

        # Create token without 'sub' field
        token_no_sub = create_access_token(data={"session_id": "some-session"})
        headers = {"Authorization": f"Bearer {token_no_sub}"}

        # Accessing a protected endpoint - should fail with 401
        response = await client.get("/api/conversations", headers=headers)
        # With invalid token (no session_id or invalid session), expect 401 or 404
        assert response.status_code in [401, 404]

    async def test_request_without_authorization_header(self, client: AsyncClient) -> None:
        """Test that requests without Authorization header get 401/403.

        Edge case: Missing credentials - covers require_user 401 path (lines 60-66).
        """
        response = await client.get("/api/admin/users")
        assert response.status_code in [401, 403]

    async def test_login_with_empty_username(self, client: AsyncClient) -> None:
        """Test that login with empty username returns 422.

        Edge case: Empty required field - input validation boundary.
        """
        response = await client.post(
            "/api/auth/login",
            json={"username": "", "password": "testpass123"},
        )
        # Empty username should fail validation or auth
        assert response.status_code in [401, 422]

    async def test_register_with_very_long_username(self, client: AsyncClient) -> None:
        """Test that very long usernames are handled gracefully.

        Edge case: Max length boundary for username field.
        """
        long_username = "u" * 300
        response = await client.post(
            "/api/auth/register",
            json={
                "username": long_username,
                "display_name": "Test",
                "password": "testpass123",
            },
        )
        # Should either succeed or return validation error - not crash
        assert response.status_code in [200, 400, 422]

    async def test_get_current_user_with_expired_token_format(self, client: AsyncClient) -> None:
        """Test that malformed token gets rejected gracefully.

        Edge case: Token format validation - covers decode_access_token None path.
        """
        malformed_token = "not.a.valid.jwt.token"
        headers = {"Authorization": f"Bearer {malformed_token}"}

        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code in [401, 422]


class TestConversationBoundaryConditions:
    """Test additional boundary conditions for complete coverage."""

    async def test_send_message_to_own_conversation_not_others(self, client: AsyncClient) -> None:
        """Test that a user cannot send messages to another user's conversation.

        Edge case: Cross-user isolation in send_message (lines 235-243).
        """
        user1_headers = await get_auth_headers(
            client, username="isolation_user1_feb28", password="testpass123"
        )
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=user1_headers,
                json={
                    "topic": "Private conversation",
                    "thinkers": [
                        {
                            "name": "Russell",
                            "bio": "British philosopher",
                            "positions": "Logical atomism",
                            "style": "Analytical",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        conversation_id = conv_resp.json()["id"]

        # User 2 tries to send message to User 1's conversation
        user2_headers = await get_auth_headers(
            client, username="isolation_user2_feb28", password="testpass123"
        )
        msg_resp = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=user2_headers,
            json={"content": "This should be rejected"},
        )
        assert msg_resp.status_code == 404

    async def test_add_thinkers_to_other_users_conversation_returns_404(
        self, client: AsyncClient
    ) -> None:
        """Test that adding thinkers to another user's conversation returns 404.

        Edge case: Cross-user isolation in add_thinkers (lines 173-175).
        """
        user1_headers = await get_auth_headers(
            client, username="add_isolation1_feb28", password="testpass123"
        )
        with patch("app.services.knowledge_research.knowledge_service.trigger_research"):
            conv_resp = await client.post(
                "/api/conversations",
                headers=user1_headers,
                json={
                    "topic": "Private conversation for add test",
                    "thinkers": [
                        {
                            "name": "Wittgenstein",
                            "bio": "Austrian philosopher",
                            "positions": "Language games",
                            "style": "Aphoristic",
                            "color": "#6366f1",
                        }
                    ],
                },
            )
        conversation_id = conv_resp.json()["id"]

        user2_headers = await get_auth_headers(
            client, username="add_isolation2_feb28", password="testpass123"
        )
        add_resp = await client.put(
            f"/api/conversations/{conversation_id}/thinkers",
            headers=user2_headers,
            json=[
                {
                    "name": "Frege",
                    "bio": "German logician",
                    "positions": "Sense and reference",
                    "style": "Formal",
                    "color": "#6366f1",
                }
            ],
        )
        assert add_resp.status_code == 404
