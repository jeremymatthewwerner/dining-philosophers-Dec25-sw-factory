"""Integration gap tests - Wednesday focus (June 3, 2026).

Cross-endpoint workflow tests targeting integration contracts where a write
through one endpoint must be observable through a *different* endpoint. Each
endpoint already has near-100% unit coverage, but these workflows are what
catch contract drift between endpoints that single-endpoint tests miss.

Workflows covered:
- Profile update propagation: PATCH /auth/profile -> POST /messages reflects
  the *updated* display_name in sender_name (not the registration-time value).
- Conversation list isolation: two authenticated users each see only their own
  conversations through GET /conversations (list-level session filter).
- Delete-user cascade across endpoints: admin DELETE /users/{id} -> victim
  login fails (401) AND admin GET /spend/{id} returns 404.
- Feedback pending limit + ordering: POST /feedback x N -> GET /feedback/pending
  truncates to ?limit and returns items in ascending created_at order.
- Feedback mark-processed isolation: PATCH /feedback/{id}/processed removes only
  that item from /pending and leaves the other NEW items untouched.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    bearer_header,
    create_admin_headers,
    create_conversation_with_thinker,
    register_and_get_token,
    submit_feedback,
)

# ============================================================================
# Profile update -> message sender_name propagation
# ============================================================================


class TestProfileUpdatePropagatesToMessageSenderName:
    """An updated display_name (PATCH /profile) must show up in later messages.

    send_message derives sender_name from `user.display_name or user.username`
    at send time. Existing tests only check the registration-time display_name,
    so a regression that cached the old name (or read a stale user row) would
    slip through. This pairs PATCH /auth/profile with POST /messages.
    """

    async def test_updated_display_name_used_for_subsequent_message(
        self, client: AsyncClient
    ) -> None:
        data = await register_and_get_token(
            client, "profileuser", "profilepass123", display_name="Original Name"
        )
        headers = bearer_header(data)

        # Update the display name via the profile endpoint.
        patch_resp = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": "Updated Name"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["display_name"] == "Updated Name"

        # Send a message and confirm the NEW name is used, not the old one.
        conv_id = await create_conversation_with_thinker(client, headers, "Topic")
        msg_resp = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Hello after rename"},
        )
        assert msg_resp.status_code == 200
        assert msg_resp.json()["sender_name"] == "Updated Name"

    async def test_message_after_two_profile_updates_uses_latest(self, client: AsyncClient) -> None:
        data = await register_and_get_token(
            client, "doubleupdate", "profilepass123", display_name="First"
        )
        headers = bearer_header(data)

        for name in ("Second", "Third"):
            resp = await client.patch(
                "/api/auth/profile", headers=headers, json={"display_name": name}
            )
            assert resp.status_code == 200

        conv_id = await create_conversation_with_thinker(client, headers, "Topic")
        msg_resp = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "latest name please"},
        )
        assert msg_resp.status_code == 200
        assert msg_resp.json()["sender_name"] == "Third"


# ============================================================================
# Conversation list-level isolation between two real users
# ============================================================================


class TestConversationListCrossUserIsolation:
    """GET /conversations must return only the requesting session's conversations.

    The single-resource 404-on-foreign-id case is covered elsewhere; this asserts
    the list endpoint's session_id filter holds when two genuine authenticated
    users have overlapping data, so a dropped WHERE clause would be caught.
    """

    async def test_each_user_sees_only_their_own_conversations(self, client: AsyncClient) -> None:
        user_a = await register_and_get_token(client, "alice", "alicepass123")
        headers_a = bearer_header(user_a)
        user_b = await register_and_get_token(client, "bob", "bobpass123")
        headers_b = bearer_header(user_b)

        a_conv_1 = await create_conversation_with_thinker(client, headers_a, "Alice One")
        a_conv_2 = await create_conversation_with_thinker(client, headers_a, "Alice Two")
        b_conv_1 = await create_conversation_with_thinker(client, headers_b, "Bob One")

        list_a = await client.get("/api/conversations", headers=headers_a)
        assert list_a.status_code == 200
        a_ids = {c["id"] for c in list_a.json()}
        assert a_ids == {a_conv_1, a_conv_2}
        assert b_conv_1 not in a_ids

        list_b = await client.get("/api/conversations", headers=headers_b)
        assert list_b.status_code == 200
        b_ids = {c["id"] for c in list_b.json()}
        assert b_ids == {b_conv_1}
        assert a_conv_1 not in b_ids and a_conv_2 not in b_ids

    async def test_other_users_message_not_counted_in_my_list(self, client: AsyncClient) -> None:
        """A message Bob sends to his conversation must not alter Alice's list."""
        user_a = await register_and_get_token(client, "alice2", "alicepass123")
        headers_a = bearer_header(user_a)
        user_b = await register_and_get_token(client, "bob2", "bobpass123")
        headers_b = bearer_header(user_b)

        a_conv = await create_conversation_with_thinker(client, headers_a, "Alice topic")
        b_conv = await create_conversation_with_thinker(client, headers_b, "Bob topic")

        # Bob sends a message in his own conversation.
        send = await client.post(
            f"/api/conversations/{b_conv}/messages",
            headers=headers_b,
            json={"content": "Bob's private message"},
        )
        assert send.status_code == 200

        # Alice's list still shows exactly her one conversation with zero messages.
        list_a = await client.get("/api/conversations", headers=headers_a)
        assert list_a.status_code == 200
        summaries = list_a.json()
        assert len(summaries) == 1
        assert summaries[0]["id"] == a_conv
        assert summaries[0]["message_count"] == 0


# ============================================================================
# Admin delete-user cascade observable through login + spend endpoints
# ============================================================================


class TestDeleteUserCascadeAcrossEndpoints:
    """Admin DELETE /users/{id} must propagate to auth and spend endpoints.

    A user-deletion that left the row reachable via login or spend would be a
    serious data-integrity bug. This chains delete -> login (must 401) and
    delete -> admin spend lookup (must 404) in a single workflow.
    """

    async def test_deleted_user_cannot_login_and_has_no_spend_record(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        # Create a victim user and confirm they can log in beforehand.
        victim = await register_and_get_token(client, "victim", "victimpass123")
        victim_id = victim["user"]["id"]

        pre_login = await client.post(
            "/api/auth/login",
            json={"username": "victim", "password": "victimpass123"},
        )
        assert pre_login.status_code == 200

        admin_headers = await create_admin_headers(client, db_session)

        # Admin can see the victim's spend record before deletion.
        pre_spend = await client.get(f"/api/spend/{victim_id}", headers=admin_headers)
        assert pre_spend.status_code == 200

        # Delete the victim.
        delete_resp = await client.delete(f"/api/admin/users/{victim_id}", headers=admin_headers)
        assert delete_resp.status_code == 200

        # Login now fails - the user row is gone.
        post_login = await client.post(
            "/api/auth/login",
            json={"username": "victim", "password": "victimpass123"},
        )
        assert post_login.status_code == 401

        # Admin spend lookup for the deleted user now 404s.
        post_spend = await client.get(f"/api/spend/{victim_id}", headers=admin_headers)
        assert post_spend.status_code == 404

    async def test_deleted_user_drops_out_of_admin_user_listing(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        victim = await register_and_get_token(client, "victim2", "victimpass123")
        victim_id = victim["user"]["id"]
        admin_headers = await create_admin_headers(client, db_session)

        before = await client.get("/api/admin/users", headers=admin_headers)
        assert before.status_code == 200
        assert victim_id in {u["id"] for u in before.json()}

        delete_resp = await client.delete(f"/api/admin/users/{victim_id}", headers=admin_headers)
        assert delete_resp.status_code == 200

        after = await client.get("/api/admin/users", headers=admin_headers)
        assert after.status_code == 200
        assert victim_id not in {u["id"] for u in after.json()}


# ============================================================================
# Feedback pending: limit truncation + ascending created_at ordering
# ============================================================================


class TestFeedbackPendingLimitAndOrdering:
    """GET /feedback/pending must truncate to ?limit and order oldest-first.

    Existing tests cover the limit-query *boundary* status codes (1/50/51) but
    not the behaviour: that submitting more than the limit returns exactly the
    limit, and that results come back in non-decreasing created_at order. Both
    are part of the processing contract the DevOps workflow relies on.
    """

    async def test_pending_truncates_to_limit(
        self, client: AsyncClient, mock_feedback_processor_secret: str
    ) -> None:
        secret = mock_feedback_processor_secret
        for i in range(4):
            resp = await submit_feedback(
                client, message=f"Pending limit feedback number {i} for ordering test."
            )
            assert resp.status_code == 201

        pending = await client.get("/api/feedback/pending", params={"secret": secret, "limit": 2})
        assert pending.status_code == 200
        body = pending.json()
        assert body["count"] == 2
        assert len(body["feedbacks"]) == 2

    async def test_pending_returns_items_in_ascending_created_at_order(
        self, client: AsyncClient, mock_feedback_processor_secret: str
    ) -> None:
        secret = mock_feedback_processor_secret
        for i in range(3):
            resp = await submit_feedback(
                client, message=f"Ordered feedback item {i} with enough length here."
            )
            assert resp.status_code == 201

        pending = await client.get("/api/feedback/pending", params={"secret": secret, "limit": 50})
        assert pending.status_code == 200
        created_ats = [fb["created_at"] for fb in pending.json()["feedbacks"]]
        assert len(created_ats) >= 3
        # ISO-8601 timestamps sort lexicographically; oldest must come first.
        assert created_ats == sorted(created_ats)


# ============================================================================
# Feedback mark-processed isolation across multiple NEW items
# ============================================================================


class TestFeedbackMarkProcessedIsolation:
    """Marking one feedback processed must not disturb other NEW feedbacks.

    The single-item submit->process->gone chain is covered. This asserts the
    multi-item invariant: PATCH /processed on one id removes exactly that id
    from /pending while every other NEW item stays pending and unchanged.
    """

    async def test_processing_one_leaves_others_pending(
        self, client: AsyncClient, mock_feedback_processor_secret: str
    ) -> None:
        secret = mock_feedback_processor_secret

        first = await submit_feedback(client, message="First feedback to be processed soon.")
        second = await submit_feedback(client, message="Second feedback should stay pending.")
        third = await submit_feedback(client, message="Third feedback should stay pending too.")
        assert first.status_code == second.status_code == third.status_code == 201

        first_id = first.json()["id"]
        second_id = second.json()["id"]
        third_id = third.json()["id"]

        # Mark only the first as processed.
        mark = await client.patch(
            f"/api/feedback/{first_id}/processed",
            params={"secret": secret},
            json={"github_issue_url": "https://github.com/test/repo/issues/123"},
        )
        assert mark.status_code == 200
        assert mark.json()["success"] is True

        # Pending now excludes the first but retains the second and third.
        pending = await client.get("/api/feedback/pending", params={"secret": secret, "limit": 50})
        assert pending.status_code == 200
        pending_ids = {fb["id"] for fb in pending.json()["feedbacks"]}
        assert first_id not in pending_ids
        assert second_id in pending_ids
        assert third_id in pending_ids

    async def test_processed_feedback_records_issue_url_for_other_items_untouched(
        self, client: AsyncClient, mock_feedback_processor_secret: str
    ) -> None:
        """Marking one item must not stamp another item's github_issue_url."""
        secret = mock_feedback_processor_secret

        target = await submit_feedback(client, message="Target feedback for processing here.")
        bystander = await submit_feedback(
            client, message="Bystander feedback that must remain new."
        )
        target_id = target.json()["id"]
        bystander_id = bystander.json()["id"]

        issue_url = "https://github.com/test/repo/issues/777"
        mark = await client.patch(
            f"/api/feedback/{target_id}/processed",
            params={"secret": secret},
            json={"github_issue_url": issue_url},
        )
        assert mark.status_code == 200

        pending = await client.get("/api/feedback/pending", params={"secret": secret, "limit": 50})
        by_id = {fb["id"]: fb for fb in pending.json()["feedbacks"]}
        # Bystander is still pending and still has no issue url attached.
        assert bystander_id in by_id
        assert by_id[bystander_id]["github_issue_url"] is None
