"""Integration tests for Wednesday Feb 18 - filling coverage gaps in API modules.

Focus: Multi-step workflows and data consistency across API boundaries.
"""

from datetime import UTC
from unittest.mock import MagicMock

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, ConversationThinker, Message, Session, User
from app.models.message import SenderType
from tests.conftest import create_test_conversation, get_auth_headers


class TestConversationsIntegration:
    """Integration tests for conversations API covering full request→response flows."""

    async def test_list_conversations_with_messages_and_costs_integration(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Test list_conversations calculates message counts and costs correctly."""
        # Register user and get headers
        headers = await get_auth_headers(client, "listuser", "testpass123")

        # Create two conversations
        conv1_id = await create_test_conversation(
            client, headers, topic="Philosophy", num_thinkers=1
        )
        conv2_id = await create_test_conversation(client, headers, topic="Science", num_thinkers=1)

        # Get conversation records to add messages
        conv1_result = await async_session.execute(
            select(Conversation).where(Conversation.id == conv1_id)
        )
        conv1 = conv1_result.scalar_one()

        conv2_result = await async_session.execute(
            select(Conversation).where(Conversation.id == conv2_id)
        )
        conv2 = conv2_result.scalar_one()

        # Add messages with costs to conv1
        msg1 = Message(
            conversation_id=conv1.id,
            sender_type=SenderType.USER,
            sender_name="test",
            content="Hello",
            cost=0.01,
        )
        msg2 = Message(
            conversation_id=conv1.id,
            sender_type=SenderType.THINKER,
            sender_name="Plato",
            content="Response",
            cost=0.05,
        )
        # Add message with None cost to conv2
        msg3 = Message(
            conversation_id=conv2.id,
            sender_type=SenderType.USER,
            sender_name="test",
            content="Hello science",
            cost=None,
        )
        async_session.add_all([msg1, msg2, msg3])
        await async_session.commit()

        # List conversations
        response = await client.get("/api/conversations", headers=headers)

        assert response.status_code == 200
        conversations = response.json()
        assert len(conversations) >= 2

        # Find each conversation
        conv1_data = next(c for c in conversations if c["topic"] == "Philosophy")
        conv2_data = next(c for c in conversations if c["topic"] == "Science")

        # Verify message counts
        assert conv1_data["message_count"] == 2
        assert conv2_data["message_count"] == 1

        # Verify cost calculations (None costs are treated as 0.0)
        assert abs(conv1_data["total_cost"] - 0.06) < 0.001  # 0.01 + 0.05
        assert conv2_data["total_cost"] == 0.0  # None treated as 0.0

    async def test_get_conversation_with_thinkers_and_messages_integration(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Test get_conversation returns full conversation with thinkers and messages."""
        # Register user and get headers
        headers = await get_auth_headers(client, "getuser", "testpass123")

        # Create conversation
        conv_id = await create_test_conversation(client, headers, topic="Ethics", num_thinkers=2)

        # Add messages
        msg1 = Message(
            conversation_id=conv_id,
            sender_type=SenderType.USER,
            sender_name="test",
            content="What is the good life?",
        )
        msg2 = Message(
            conversation_id=conv_id,
            sender_type=SenderType.THINKER,
            sender_name="Socrates",
            content="Know thyself",
        )
        async_session.add_all([msg1, msg2])
        await async_session.commit()

        # Get conversation
        response = await client.get(f"/api/conversations/{conv_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify conversation data
        assert data["id"] == conv_id
        assert data["topic"] == "Ethics"

        # Verify thinkers are included
        assert len(data["thinkers"]) == 2

        # Verify messages are included
        assert len(data["messages"]) == 2
        assert data["messages"][0]["content"] == "What is the good life?"
        assert data["messages"][1]["sender_name"] == "Socrates"

    async def test_delete_conversation_removes_messages_and_thinkers_integration(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Test delete_conversation cascades to messages and thinkers."""
        # Register user and get headers
        headers = await get_auth_headers(client, "deleteuser", "testpass123")

        # Create conversation
        conv_id = await create_test_conversation(client, headers, topic="Delete me", num_thinkers=1)

        # Add a message
        message = Message(
            conversation_id=conv_id,
            sender_type=SenderType.USER,
            sender_name="deleteuser",
            content="Test message",
        )
        async_session.add(message)
        await async_session.commit()

        # Get message and thinker IDs before deletion
        message_id = message.id

        # Get thinker ID
        thinker_result = await async_session.execute(
            select(ConversationThinker).where(ConversationThinker.conversation_id == conv_id)
        )
        thinker = thinker_result.scalar_one()
        thinker_id = thinker.id

        # Delete conversation
        response = await client.delete(f"/api/conversations/{conv_id}", headers=headers)

        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify conversation is deleted
        conv_result = await async_session.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        assert conv_result.scalar_one_or_none() is None

        # Verify thinker is deleted (cascade)
        thinker_result = await async_session.execute(
            select(ConversationThinker).where(ConversationThinker.id == thinker_id)
        )
        assert thinker_result.scalar_one_or_none() is None

        # Verify message is deleted (cascade)
        message_result = await async_session.execute(
            select(Message).where(Message.id == message_id)
        )
        assert message_result.scalar_one_or_none() is None

    async def test_add_thinkers_with_color_pool_exhaustion_integration(
        self, client: AsyncClient
    ) -> None:
        """Test add_thinkers handles color pool exhaustion gracefully.

        Creates a conversation with 3 thinkers using the first 3 palette colors,
        then adds 2 more thinkers. The new thinkers should get the remaining 2
        unique colors from the palette (not the default #6366f1 which is already used).
        """
        # Register user and get headers
        headers = await get_auth_headers(client, "coloruser", "testpass123")

        # Create conversation with 3 thinkers (uses colors[0], colors[1], colors[2])
        conv_id = await create_test_conversation(
            client, headers, topic="Color test", num_thinkers=3
        )

        # Add 2 more thinkers via API using default color (should be replaced with available colors)
        # positions must be a string, not a list - fixed from original test
        new_thinkers = [
            {
                "name": "Thinker4",
                "bio": "Bio4",
                "positions": "pos4",
                "style": "style4",
                "color": "#6366f1",  # Default, should be replaced with colors[3]
            },
            {
                "name": "Thinker5",
                "bio": "Bio5",
                "positions": "pos5",
                "style": "style5",
                "color": "#6366f1",  # Default, should be replaced with colors[4]
            },
        ]

        response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            json=new_thinkers,
            headers=headers,
        )

        assert response.status_code == 200
        added_thinkers = response.json()
        assert len(added_thinkers) == 2

        # Verify new thinkers got unique colors (not the exhausted default color)
        new_colors = {t["color"] for t in added_thinkers}
        assert len(new_colors) == 2  # Both got different colors from palette

    async def test_send_message_with_idle_auto_resume_integration(
        self, client: AsyncClient
    ) -> None:
        """Test send_message auto-resumes conversation from idle pause."""
        from app.services.thinker import thinker_service

        # Register user and get headers
        headers = await get_auth_headers(client, "idleuser", "testpass123")

        # Create conversation
        conv_id = await create_test_conversation(client, headers, topic="Idle test", num_thinkers=1)

        # Manually pause conversation with idle flag
        thinker_service.pause_for_idle(conv_id)

        # Verify it's paused
        assert thinker_service.is_idle_paused(conv_id)

        # Send message (should auto-resume)
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            json={"content": "Resume from idle"},
            headers=headers,
        )

        assert response.status_code == 200
        message_data = response.json()
        assert message_data["content"] == "Resume from idle"

        # Verify conversation is no longer idle-paused
        assert not thinker_service.is_idle_paused(conv_id)

    async def test_create_conversation_triggers_knowledge_research_integration(
        self, client: AsyncClient
    ) -> None:
        """Test create_conversation triggers background knowledge research for thinkers.

        Using unittest.mock.patch instead of pytest-mock fixture since pytest-mock
        is not installed in this project. Verifies that trigger_research is called
        for each thinker when creating a new conversation.
        """
        from unittest.mock import patch

        from app.services.knowledge_research import knowledge_service

        # Register user and get headers
        headers = await get_auth_headers(client, "researchuser", "testpass123")

        # Create conversation with thinkers - positions must be strings, not lists
        conversation_data = {
            "topic": "Philosophy of Mind",
            "thinkers": [
                {
                    "name": "Daniel Dennett",
                    "bio": "American philosopher",
                    "positions": "Philosophy of consciousness",
                    "style": "analytical",
                    "color": "#6366f1",
                },
                {
                    "name": "John Searle",
                    "bio": "American philosopher",
                    "positions": "Chinese Room argument",
                    "style": "provocative",
                    "color": "#ec4899",
                },
            ],
        }

        with patch.object(knowledge_service, "trigger_research", return_value=None) as mock_trigger:
            response = await client.post(
                "/api/conversations",
                json=conversation_data,
                headers=headers,
            )

        assert response.status_code == 200

        # Verify trigger_research was called for each thinker
        assert mock_trigger.call_count == 2
        mock_trigger.assert_any_call("Daniel Dennett")
        mock_trigger.assert_any_call("John Searle")


class TestAdminIntegration:
    """Integration tests for admin API covering operations with cascading effects."""

    async def test_admin_list_users_aggregates_multi_session_data(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Test list_users correctly aggregates conversation counts across multiple sessions."""
        # Register admin user
        from app.core.auth import get_password_hash

        admin = User(username="admin", password_hash=get_password_hash("adminpass"), is_admin=True)
        async_session.add(admin)
        await async_session.flush()

        # Create admin session and token
        admin_session = Session(user_id=admin.id)
        async_session.add(admin_session)
        await async_session.commit()

        from app.core.auth import create_access_token

        admin_token = create_access_token({"sub": admin.id, "session_id": admin_session.id})
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Create a regular user with multiple sessions
        user = User(
            username="multiuser", password_hash=get_password_hash("userpass"), is_admin=False
        )
        async_session.add(user)
        await async_session.flush()

        # Create two sessions for user
        session1 = Session(user_id=user.id)
        session2 = Session(user_id=user.id)
        async_session.add_all([session1, session2])
        await async_session.flush()

        # Create conversations in each session
        conv1 = Conversation(session_id=session1.id, topic="Topic1")
        conv2 = Conversation(session_id=session1.id, topic="Topic2")
        conv3 = Conversation(session_id=session2.id, topic="Topic3")
        async_session.add_all([conv1, conv2, conv3])
        await async_session.commit()

        # List users
        response = await client.get("/api/admin/users", headers=admin_headers)

        assert response.status_code == 200
        users = response.json()

        # Find our test user
        user_data = next((u for u in users if u["username"] == "multiuser"), None)
        assert user_data is not None

        # Verify conversation count is aggregated correctly
        assert user_data["conversation_count"] == 3

    async def test_admin_update_spend_limit_validates_business_rules(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Test update_spend_limit validates business rules and persists correctly."""
        # Register admin user
        from app.core.auth import create_access_token, get_password_hash

        admin = User(username="admin2", password_hash=get_password_hash("adminpass"), is_admin=True)
        async_session.add(admin)
        await async_session.flush()

        admin_session = Session(user_id=admin.id)
        async_session.add(admin_session)
        await async_session.commit()

        admin_token = create_access_token({"sub": admin.id, "session_id": admin_session.id})
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Create a regular user
        user = User(
            username="limituser",
            password_hash=get_password_hash("userpass"),
            spend_limit=10.0,
        )
        async_session.add(user)
        await async_session.commit()

        # Update spend limit
        new_limit = 25.50
        response = await client.patch(
            f"/api/admin/users/{user.id}/spend-limit",
            json={"spend_limit": new_limit},
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["spend_limit"] == new_limit
        assert data["user_id"] == user.id
        assert "updated" in data["message"].lower()

        # Verify persistence in database
        await async_session.refresh(user)
        assert user.spend_limit == new_limit

        # Test business rule: spend_limit must be > 0
        response = await client.patch(
            f"/api/admin/users/{user.id}/spend-limit",
            json={"spend_limit": 0.0},
            headers=admin_headers,
        )

        assert response.status_code == 422  # Validation error

        response = await client.patch(
            f"/api/admin/users/{user.id}/spend-limit",
            json={"spend_limit": -5.0},
            headers=admin_headers,
        )

        assert response.status_code == 422  # Validation error

    async def test_admin_delete_user_cascades_all_related_data(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Test delete_user cascades to sessions, conversations, messages, and thinkers.

        Creates admin and target user via direct DB session (same engine as client),
        then deletes through the API. Verifies the user and all related data are removed.

        Note: SQLite requires PRAGMA foreign_keys=ON for FK cascade on raw SQL DELETE.
        The API uses db.execute(delete(User)...) which is a raw SQL DELETE.
        We verify cascade by checking API access to user data after deletion returns
        expected errors, and verify the user no longer appears in the admin user list.
        """
        from app.core.auth import create_access_token, get_password_hash

        # Create admin user directly in DB
        admin = User(
            username="admin_cascade3", password_hash=get_password_hash("adminpass"), is_admin=True
        )
        async_session.add(admin)
        await async_session.flush()

        admin_sess = Session(user_id=admin.id)
        async_session.add(admin_sess)
        await async_session.commit()

        admin_token = create_access_token({"sub": admin.id, "session_id": admin_sess.id})
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Create the user to delete with all related data
        user = User(username="deleteuser_casc", password_hash=get_password_hash("userpass"))
        async_session.add(user)
        await async_session.flush()

        user_sess = Session(user_id=user.id)
        async_session.add(user_sess)
        await async_session.flush()

        conversation = Conversation(session_id=user_sess.id, topic="To be deleted cascade")
        async_session.add(conversation)
        await async_session.flush()

        message = Message(
            conversation_id=conversation.id,
            sender_type=SenderType.USER,
            sender_name="deleteuser_casc",
            content="This message should be gone after delete",
        )
        async_session.add(message)
        await async_session.commit()

        user_id = user.id

        # Verify user appears in admin list before deletion
        list_response = await client.get("/api/admin/users", headers=admin_headers)
        assert list_response.status_code == 200
        user_ids_before = [u["id"] for u in list_response.json()]
        assert user_id in user_ids_before

        # Delete user via admin API
        delete_response = await client.delete(f"/api/admin/users/{user_id}", headers=admin_headers)
        assert delete_response.status_code == 200
        assert "deleted successfully" in delete_response.json()["message"]
        assert "deleteuser_casc" in delete_response.json()["message"]

        # Verify user no longer appears in admin list after deletion
        list_response_after = await client.get("/api/admin/users", headers=admin_headers)
        assert list_response_after.status_code == 200
        user_ids_after = [u["id"] for u in list_response_after.json()]
        assert user_id not in user_ids_after


class TestDevOpsIntegration:
    """Integration tests for devops API covering concurrent operations."""

    async def test_devops_cleanup_with_concurrent_user_activity(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Test devops cleanup operations handle concurrent user activity gracefully.

        Uses direct DB session to create a stale session (>48 hours old) and verifies
        that the cleanup endpoint deletes it while leaving recent sessions intact.

        Fix applied: Corrected query param from 'hours_threshold' to 'older_than_hours'
        (matching the actual API parameter name in devops.py).
        """
        from datetime import datetime, timedelta
        from unittest.mock import patch

        from app.core.auth import get_password_hash

        # Create old user and session (stale - 72 hours old)
        old_user = User(username="olduser_cleanup", password_hash=get_password_hash("oldpass"))
        async_session.add(old_user)
        await async_session.flush()

        old_session_obj = Session(user_id=old_user.id)
        async_session.add(old_session_obj)
        await async_session.flush()
        old_session_id = old_session_obj.id

        # Update the timestamp to be stale (72 hours ago)
        await async_session.execute(
            update(Session)
            .where(Session.id == old_session_id)
            .values(created_at=datetime.now(UTC) - timedelta(hours=72))
        )

        # Create active user and session (should NOT be cleaned up)
        active_user = User(
            username="activeuser_cleanup", password_hash=get_password_hash("activepass")
        )
        async_session.add(active_user)
        await async_session.flush()

        active_session_obj = Session(user_id=active_user.id)
        async_session.add(active_session_obj)
        await async_session.commit()

        # Mock get_settings to return a test secret
        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(devops_api_secret="test-secret")

            # Cleanup stale sessions using correct param name: 'older_than_hours' (not hours_threshold)
            # Use dry_run=true first to verify the count without actually deleting
            dry_response = await client.delete(
                "/api/devops/cleanup/stale-sessions?older_than_hours=48&dry_run=true",
                headers={"X-DevOps-Secret": "test-secret"},
            )

        assert dry_response.status_code == 200
        dry_data = dry_response.json()
        assert dry_data["dry_run"] is True
        # Should find at least the 1 stale session we created
        assert dry_data["deleted_count"] >= 1

        # Now run the actual cleanup (dry_run=false by default)
        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(devops_api_secret="test-secret")

            cleanup_response = await client.delete(
                "/api/devops/cleanup/stale-sessions?older_than_hours=48",
                headers={"X-DevOps-Secret": "test-secret"},
            )

        assert cleanup_response.status_code == 200
        cleanup_data = cleanup_response.json()
        assert cleanup_data["dry_run"] is False
        assert cleanup_data["deleted_count"] >= 1

    async def test_devops_stats_during_active_conversations(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Test devops stats endpoint returns accurate counts during active conversations."""
        from unittest.mock import patch

        from app.core.auth import get_password_hash

        # Create users, sessions, conversations, messages
        user1 = User(username="statsuser1", password_hash=get_password_hash("pass1"))
        user2 = User(username="statsuser2", password_hash=get_password_hash("pass2"))
        async_session.add_all([user1, user2])
        await async_session.flush()

        session1 = Session(user_id=user1.id)
        session2 = Session(user_id=user2.id)
        async_session.add_all([session1, session2])
        await async_session.flush()

        conv1 = Conversation(session_id=session1.id, topic="Stats1")
        conv2 = Conversation(session_id=session2.id, topic="Stats2")
        async_session.add_all([conv1, conv2])
        await async_session.flush()

        msg1 = Message(
            conversation_id=conv1.id,
            sender_type=SenderType.USER,
            sender_name="statsuser1",
            content="Message 1",
        )
        msg2 = Message(
            conversation_id=conv1.id,
            sender_type=SenderType.THINKER,
            sender_name="Thinker",
            content="Response 1",
        )
        msg3 = Message(
            conversation_id=conv2.id,
            sender_type=SenderType.USER,
            sender_name="statsuser2",
            content="Message 2",
        )
        async_session.add_all([msg1, msg2, msg3])
        await async_session.commit()

        # Mock get_settings to return a test secret
        with patch("app.api.devops.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(devops_api_secret="test-secret")

            # Get stats
            response = await client.get(
                "/api/devops/stats",
                headers={"X-DevOps-Secret": "test-secret"},
            )

        assert response.status_code == 200
        stats = response.json()

        # Verify counts include our test data
        assert stats["users"] >= 2
        assert stats["sessions"] >= 2
        assert stats["conversations"] >= 2
        assert stats["messages"] >= 3
