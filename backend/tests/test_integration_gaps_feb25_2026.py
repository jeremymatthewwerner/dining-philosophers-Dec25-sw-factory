"""Integration tests for Wednesday Feb 25 2026 - filling coverage gaps.

Focus: API endpoints with missing coverage, using proper mocking of
background tasks to prevent test hangs from Anthropic API calls.

Key discovery: knowledge_service.trigger_research() spawns asyncio background
tasks that call the Anthropic API. Without mocking, these tasks can be slow
in tests. We patch the singleton method to prevent background calls.

Coverage targets:
- app/api/conversations.py: 39% -> 65%+ (thinker loop, list summaries, CRUD)
- app/api/feedback.py: 67% -> 80%+ (X-Forwarded-For, rate limit, pending, processed)
- app/api/admin.py: 60% -> 80%+ (user listing, spend limit, delete user paths)
"""

from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    assert_not_found,
    create_admin_headers,
    create_test_conversation,
    get_auth_headers,
    register_and_get_token,
)

# Patch target for knowledge_service.trigger_research
# The service is imported inside function bodies, so we patch the singleton method
_KNOWLEDGE_PATCH = "app.services.knowledge_research.knowledge_service.trigger_research"


# ---------------------------------------------------------------------------
# Conversations - with mocked knowledge_service to prevent background hangs
# ---------------------------------------------------------------------------


class TestConversationsWithMockedKnowledge:
    """Test conversations API with knowledge_service.trigger_research mocked."""

    async def test_create_conversation_with_thinkers_covers_loop(self, client: AsyncClient) -> None:
        """Create conversation - covers thinker loop (lines 46-61) via mocked knowledge."""
        headers = await get_auth_headers(client, "cquser1", "pass123")

        with patch(_KNOWLEDGE_PATCH) as mock_tr:
            response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Ethics of AI",
                    "thinkers": [
                        {
                            "name": "Aristotle",
                            "bio": "Ancient philosopher",
                            "positions": "Virtue ethics",
                            "style": "Systematic",
                        },
                        {
                            "name": "Kant",
                            "bio": "German philosopher",
                            "positions": "Deontology",
                            "style": "Systematic",
                        },
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == "Ethics of AI"
        assert len(data["thinkers"]) == 2
        thinker_names = {t["name"] for t in data["thinkers"]}
        assert "Aristotle" in thinker_names
        assert "Kant" in thinker_names
        # Verify knowledge research was triggered for each thinker
        assert mock_tr.call_count == 2

    async def test_create_conversation_color_assignment_in_loop(self, client: AsyncClient) -> None:
        """Colors assigned from color pool during thinker creation loop."""
        headers = await get_auth_headers(client, "cquser2", "pass123")
        expected_colors = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]

        with patch(_KNOWLEDGE_PATCH):
            response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Colors",
                    "thinkers": [
                        {
                            "name": f"Thinker{i}",
                            "bio": f"Bio {i}",
                            "positions": "Philosopher",
                            "style": "Analytical",
                        }
                        for i in range(3)
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assigned_colors = [t["color"] for t in data["thinkers"]]
        # All assigned colors should be from the color pool
        for color in assigned_colors:
            assert color in expected_colors
        # Colors should be distinct
        assert len(set(assigned_colors)) == 3

    async def test_create_conversation_with_custom_thinker_color(self, client: AsyncClient) -> None:
        """Custom color on thinker is preserved (not overridden by pool)."""
        headers = await get_auth_headers(client, "cquser3", "pass123")
        custom_color = "#ff5733"

        with patch(_KNOWLEDGE_PATCH):
            response = await client.post(
                "/api/conversations",
                headers=headers,
                json={
                    "topic": "Custom Colors",
                    "thinkers": [
                        {
                            "name": "CustomThinker",
                            "bio": "Bio",
                            "positions": "Positions",
                            "style": "Style",
                            "color": custom_color,
                        }
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["thinkers"][0]["color"] == custom_color

    async def test_list_conversations_with_message_counts(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """list_conversations builds summaries with message counts and costs."""
        from app.models import Message
        from app.models.message import SenderType

        headers = await get_auth_headers(client, "cqlistuser", "pass123")

        with patch(_KNOWLEDGE_PATCH):
            conv_id = await create_test_conversation(
                client, headers, topic="Costs Test", num_thinkers=1
            )

        # Add messages with costs directly via async_session
        msg1 = Message(
            conversation_id=conv_id,
            sender_type=SenderType.USER,
            sender_name="cqlistuser",
            content="Hello",
            cost=0.02,
        )
        msg2 = Message(
            conversation_id=conv_id,
            sender_type=SenderType.THINKER,
            sender_name="Socrates",
            content="Think deeper",
            cost=0.08,
        )
        async_session.add_all([msg1, msg2])
        await async_session.commit()

        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200
        conversations = response.json()

        conv_data = next(c for c in conversations if c["topic"] == "Costs Test")
        assert conv_data["message_count"] == 2
        assert abs(conv_data["total_cost"] - 0.10) < 0.001

    async def test_list_conversations_none_cost_treated_as_zero(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """None-cost messages are treated as 0.0 in total_cost calculation."""
        from app.models import Message
        from app.models.message import SenderType

        headers = await get_auth_headers(client, "cqcostuser", "pass123")

        with patch(_KNOWLEDGE_PATCH):
            conv_id = await create_test_conversation(
                client, headers, topic="Null Costs", num_thinkers=1
            )

        # Message with NULL cost
        msg = Message(
            conversation_id=conv_id,
            sender_type=SenderType.USER,
            sender_name="cqcostuser",
            content="Hello",
            cost=None,
        )
        async_session.add(msg)
        await async_session.commit()

        response = await client.get("/api/conversations", headers=headers)
        assert response.status_code == 200
        conversations = response.json()

        conv_data = next(c for c in conversations if c["topic"] == "Null Costs")
        assert conv_data["total_cost"] == 0.0
        assert conv_data["message_count"] == 1

    async def test_get_conversation_not_found_returns_404(self, client: AsyncClient) -> None:
        """get_conversation raises 404 when conversation not found (line 128)."""
        headers = await get_auth_headers(client, "cq404user", "pass123")

        response = await client.get(
            "/api/conversations/nonexistent-id-xyz",
            headers=headers,
        )
        assert response.status_code == 404
        assert "Conversation not found" in response.json()["detail"]

    async def test_delete_conversation_not_found_returns_404(self, client: AsyncClient) -> None:
        """delete_conversation raises 404 when conversation not found (lines 145-147)."""
        headers = await get_auth_headers(client, "cqdel404user", "pass123")

        response = await client.delete(
            "/api/conversations/nonexistent-id-xyz",
            headers=headers,
        )
        assert response.status_code == 404
        assert "Conversation not found" in response.json()["detail"]

    async def test_delete_conversation_success(self, client: AsyncClient) -> None:
        """delete_conversation removes conversation and returns status (line 151)."""
        headers = await get_auth_headers(client, "cqdeluser", "pass123")

        with patch(_KNOWLEDGE_PATCH):
            conv_id = await create_test_conversation(
                client, headers, topic="To Delete", num_thinkers=1
            )

        response = await client.delete(
            f"/api/conversations/{conv_id}",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify it's actually gone
        get_response = await client.get(
            f"/api/conversations/{conv_id}",
            headers=headers,
        )
        assert get_response.status_code == 404

    async def test_add_thinkers_conversation_not_found_404(self, client: AsyncClient) -> None:
        """add_thinkers returns 404 when conversation not found (lines 173-175)."""
        headers = await get_auth_headers(client, "cqadd404user", "pass123")

        response = await client.put(
            "/api/conversations/nonexistent-id/thinkers",
            headers=headers,
            json=[
                {
                    "name": "Plato",
                    "bio": "Greek philosopher",
                    "positions": "Forms",
                    "style": "Dialogues",
                }
            ],
        )
        assert response.status_code == 404
        assert "Conversation not found" in response.json()["detail"]

    async def test_add_thinkers_exceeds_max_limit_400(self, client: AsyncClient) -> None:
        """add_thinkers returns 400 when total would exceed 5 (lines 179-185)."""
        headers = await get_auth_headers(client, "cqmaxuser", "pass123")

        with patch(_KNOWLEDGE_PATCH):
            # Create conversation with 4 thinkers
            conv_id = await create_test_conversation(
                client, headers, topic="Max Thinkers", num_thinkers=4
            )

        # Try to add 2 more (would bring total to 6)
        with patch(_KNOWLEDGE_PATCH):
            response = await client.put(
                f"/api/conversations/{conv_id}/thinkers",
                headers=headers,
                json=[
                    {
                        "name": "Thinker5",
                        "bio": "Bio 5",
                        "positions": "Pos 5",
                        "style": "Style 5",
                    },
                    {
                        "name": "Thinker6",
                        "bio": "Bio 6",
                        "positions": "Pos 6",
                        "style": "Style 6",
                    },
                ],
            )
        assert response.status_code == 400
        assert "Cannot add" in response.json()["detail"]
        assert "Maximum is 5" in response.json()["detail"]

    async def test_add_thinkers_success_with_colors(self, client: AsyncClient) -> None:
        """add_thinkers adds thinkers with correct color assignment (lines 189-220)."""
        headers = await get_auth_headers(client, "cqaddok", "pass123")

        with patch(_KNOWLEDGE_PATCH):
            conv_id = await create_test_conversation(
                client, headers, topic="Add Thinkers OK", num_thinkers=1
            )
            response = await client.put(
                f"/api/conversations/{conv_id}/thinkers",
                headers=headers,
                json=[
                    {
                        "name": "Plato",
                        "bio": "Greek philosopher",
                        "positions": "Forms",
                        "style": "Dialogues",
                    }
                ],
            )

        assert response.status_code == 200
        thinkers = response.json()
        assert len(thinkers) == 1
        assert thinkers[0]["name"] == "Plato"
        assert thinkers[0]["id"] is not None
        assert thinkers[0]["color"] is not None

    async def test_send_message_conversation_not_found_404(self, client: AsyncClient) -> None:
        """send_message returns 404 for non-existent conversation (lines 241-243)."""
        headers = await get_auth_headers(client, "cqmsg404user", "pass123")

        response = await client.post(
            "/api/conversations/nonexistent-id/messages",
            headers=headers,
            json={"content": "Hello"},
        )
        assert response.status_code == 404
        assert "Conversation not found" in response.json()["detail"]

    async def test_send_message_creates_message_with_correct_sender(
        self, client: AsyncClient
    ) -> None:
        """send_message creates message with user's sender_name (lines 256-268)."""
        headers = await get_auth_headers(client, "cqmsguser", "pass123")

        with patch(_KNOWLEDGE_PATCH):
            conv_id = await create_test_conversation(
                client, headers, topic="Message Test", num_thinkers=1
            )

        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "What is justice?"},
        )
        assert response.status_code == 200
        msg = response.json()
        assert msg["content"] == "What is justice?"
        assert msg["sender_type"] == "user"
        assert msg["sender_name"] is not None
        assert msg["id"] is not None

    async def test_send_message_cross_session_unauthorized(self, client: AsyncClient) -> None:
        """Users cannot send messages to another user's conversation."""
        headers1 = await get_auth_headers(client, "cqown1", "pass123")
        headers2 = await get_auth_headers(client, "cqown2", "pass123")

        with patch(_KNOWLEDGE_PATCH):
            conv_id = await create_test_conversation(
                client, headers1, topic="Private", num_thinkers=1
            )

        # User 2 tries to send a message to user 1's conversation
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers2,
            json={"content": "Intruder!"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Feedback API - specific paths for coverage improvement
# ---------------------------------------------------------------------------


class TestFeedbackIntegrationPaths:
    """Test feedback API paths that lack coverage."""

    async def test_submit_feedback_with_x_forwarded_for_header(self, client: AsyncClient) -> None:
        """X-Forwarded-For header is used for IP extraction (line 46 in feedback.py)."""
        response = await client.post(
            "/api/feedback",
            headers={"X-Forwarded-For": "203.0.113.5, 198.51.100.1"},
            json={
                "feedback_type": "bug",
                "message": "Found a bug with forwarded IP address detection in the app",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "Thank you" in data["message"]

    async def test_submit_feedback_full_data_creates_record(self, client: AsyncClient) -> None:
        """Submit feedback with all optional fields creates a feedback record."""
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "feature",
                "message": "Please add dark mode to the application for better night usage",
                "email": "user@example.com",
                "name": "Test User",
                "username": "testuser123",
                "user_agent": "Mozilla/5.0 Test Browser",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert "Thank you" in data["message"]

    async def test_submit_feedback_other_type(self, client: AsyncClient) -> None:
        """'other' feedback type maps correctly in feedback_type_map."""
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "other",
                "message": "General feedback about the application that does not fit categories",
            },
        )
        assert response.status_code == 201

    async def test_submit_feedback_rate_limit_triggers_429(self, client: AsyncClient) -> None:
        """Rate limiting triggers 429 after 5 submissions from same IP."""
        rate_limit_ip = "192.0.2.100"
        headers = {"X-Forwarded-For": rate_limit_ip}

        # Submit MAX_SUBMISSIONS_PER_HOUR (5) times
        for i in range(5):
            response = await client.post(
                "/api/feedback",
                headers=headers,
                json={
                    "feedback_type": "bug",
                    "message": f"Rate limit test submission {i + 1} with enough characters here",
                },
            )
            assert response.status_code == 201, f"Submission {i + 1} failed: {response.text}"

        # 6th submission should be rate limited
        response = await client.post(
            "/api/feedback",
            headers=headers,
            json={
                "feedback_type": "bug",
                "message": "This submission should be blocked by rate limiting logic",
            },
        )
        assert response.status_code == 429
        assert "Too many" in response.json()["detail"]

    async def test_get_pending_feedback_returns_submitted_items(self, client: AsyncClient) -> None:
        """get_pending_feedback returns items from DB (lines 160-182)."""
        with patch("app.api.feedback.get_settings") as mock_settings:
            mock_settings.return_value.feedback_processor_secret = "test-secret-pend"

            # Submit feedback with a distinct IP to keep it isolated
            await client.post(
                "/api/feedback",
                headers={"X-Forwarded-For": "10.99.1.1"},
                json={
                    "feedback_type": "bug",
                    "message": "Bug to be fetched as pending feedback item for processing",
                    "username": "pendinguser",
                },
            )

            response = await client.get(
                "/api/feedback/pending",
                params={"secret": "test-secret-pend"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert len(data["feedbacks"]) >= 1
        # Verify returned feedback has required fields
        fb = data["feedbacks"][0]
        assert "id" in fb
        assert "feedback_type" in fb
        assert "message" in fb
        assert "status" in fb
        assert "created_at" in fb

    async def test_get_pending_feedback_with_limit_parameter(self, client: AsyncClient) -> None:
        """get_pending_feedback respects the limit parameter."""
        with patch("app.api.feedback.get_settings") as mock_settings:
            mock_settings.return_value.feedback_processor_secret = "test-secret-lim"

            # Submit multiple feedback items from different IPs
            for i in range(3):
                await client.post(
                    "/api/feedback",
                    headers={"X-Forwarded-For": f"10.88.{i}.1"},
                    json={
                        "feedback_type": "feature",
                        "message": f"Feature request {i + 1} for pending feedback limit test",
                    },
                )

            response = await client.get(
                "/api/feedback/pending",
                params={"secret": "test-secret-lim", "limit": 2},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["feedbacks"]) <= 2

    async def test_mark_feedback_processed_success(self, client: AsyncClient) -> None:
        """mark_feedback_processed updates status and returns response (lines 201-220)."""
        with patch("app.api.feedback.get_settings") as mock_settings:
            mock_settings.return_value.feedback_processor_secret = "proc-secret-ok"

            # Submit feedback
            submit_response = await client.post(
                "/api/feedback",
                headers={"X-Forwarded-For": "10.77.1.1"},
                json={
                    "feedback_type": "bug",
                    "message": "Bug that will be processed and linked to a GitHub issue",
                },
            )
            assert submit_response.status_code == 201
            feedback_id = submit_response.json()["id"]

            # Mark as processed
            response = await client.patch(
                f"/api/feedback/{feedback_id}/processed",
                params={"secret": "proc-secret-ok"},
                json={"github_issue_url": "https://github.com/owner/repo/issues/999"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["feedback_id"] == feedback_id
        assert data["github_issue_url"] == "https://github.com/owner/repo/issues/999"

    async def test_mark_feedback_processed_not_found_404(self, client: AsyncClient) -> None:
        """mark_feedback_processed returns 404 for non-existent feedback."""
        with patch("app.api.feedback.get_settings") as mock_settings:
            mock_settings.return_value.feedback_processor_secret = "proc-secret-nf"

            response = await client.patch(
                "/api/feedback/nonexistent-feedback-id/processed",
                params={"secret": "proc-secret-nf"},
                json={"github_issue_url": "https://github.com/owner/repo/issues/123"},
            )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Admin API - coverage gaps in response building and error paths
# ---------------------------------------------------------------------------


class TestAdminIntegrationPaths:
    """Test admin API paths that need coverage."""

    async def test_list_users_builds_correct_stats_response(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """list_users builds UserWithStats objects with correct fields (lines 35-53)."""
        headers = await create_admin_headers(client, async_session, "adminstat1", "adminpass123")

        # Register a regular user
        await register_and_get_token(client, "regularstat1", "userpass123")

        response = await client.get("/api/admin/users", headers=headers)
        assert response.status_code == 200
        users = response.json()
        assert len(users) >= 2

        # Verify all UserWithStats fields are present in response
        for user in users:
            assert "id" in user
            assert "username" in user
            assert "is_admin" in user
            assert "total_spend" in user
            assert "spend_limit" in user
            assert "conversation_count" in user
            assert "created_at" in user

    async def test_update_spend_limit_user_not_found_404(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """update_spend_limit returns 404 for non-existent user (lines 79-85)."""
        headers = await create_admin_headers(client, async_session, "adminspend1", "adminpass123")

        response = await client.patch(
            "/api/admin/users/nonexistent-user-id/spend-limit",
            headers=headers,
            json={"spend_limit": 25.0},
        )
        assert_not_found(response, "User not found")

    async def test_update_spend_limit_success_commits_to_db(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """update_spend_limit commits and returns updated limit (lines 87-94)."""
        headers = await create_admin_headers(client, async_session, "adminspend2", "adminpass123")

        # Register target user
        target_data = await register_and_get_token(client, "targetspend", "userpass123")
        target_id = target_data["user"]["id"]

        response = await client.patch(
            f"/api/admin/users/{target_id}/spend-limit",
            headers=headers,
            json={"spend_limit": 100.0},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == target_id
        assert data["spend_limit"] == 100.0
        assert "100.00" in data["message"]

    async def test_delete_user_not_found_returns_404(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """delete_user returns 404 for non-existent user (lines 113-116)."""
        headers = await create_admin_headers(client, async_session, "admindel1", "adminpass123")

        response = await client.delete(
            "/api/admin/users/nonexistent-user-id",
            headers=headers,
        )
        assert_not_found(response, "User not found")

    async def test_delete_user_returns_success_message(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """delete_user returns success message with username (line 125 in admin.py)."""
        headers = await create_admin_headers(client, async_session, "admindel2", "adminpass123")

        # Create user to delete
        target_data = await register_and_get_token(client, "tobedeleted", "userpass123")
        target_id = target_data["user"]["id"]

        response = await client.delete(
            f"/api/admin/users/{target_id}",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "tobedeleted" in data["message"]
        assert "deleted successfully" in data["message"]
