"""Integration gap tests - Wednesday focus (June 10, 2026).

Cross-endpoint workflow tests centered on the spend aggregation endpoint
(`GET /api/spend/{user_id}`). That endpoint runs a multi-table join
(Session ⨝ Conversation ⨝ Message) in app/services/spend.py. The join is
exercised by service-level unit tests (test_spend_service.py) but **not**
through the real REST write path: POST /conversations, POST /messages, and
DELETE /conversations. These integration tests close that gap by driving the
write endpoints and asserting the spend read endpoint reflects the result -
catching contract drift (session linkage, cost filtering, delete cascade)
that single-endpoint tests cannot.

Workflows covered:
- Multiple conversations created via POST /conversations all appear in
  GET /spend with the correct per-session conversation_count.
- User messages sent via POST /messages carry cost=NULL, so spend's
  message_count (filtered on cost IS NOT NULL) and total_spend stay at 0.
- DELETE /conversations/{id} removes the conversation from GET /spend.
- The session id is identical across GET /sessions/me, the POST /conversations
  response session_id, and the GET /spend session entry.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    assert_success_response,
    bearer_header,
    create_admin_headers,
    create_conversation_with_thinker,
    register_and_get_token,
)

pytestmark = [pytest.mark.asyncio]


# ============================================================================
# Spend aggregation reflects conversations created over REST
# ============================================================================


class TestSpendReflectsRestCreatedConversations:
    """GET /spend must aggregate conversations created via POST /conversations.

    test_api.py covers the single-conversation case; this asserts the
    aggregation behaviour for *multiple* conversations and the per-session
    conversation_count, which depends on the Session⨝Conversation join and the
    in-Python grouping in get_user_spend_data.
    """

    async def test_spend_lists_all_conversations_created_via_rest(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin_headers = await create_admin_headers(
            client, db_session, "spend_admin_j10", "AdminPw1!"
        )

        user = await register_and_get_token(client, "multi_conv_user", "UserPw1!")
        user_headers = bearer_header(user)
        user_id = user["user"]["id"]

        topics = ["Ethics of AI", "Free will debate", "Nature of beauty"]
        created_ids = set()
        for topic in topics:
            created_ids.add(await create_conversation_with_thinker(client, user_headers, topic))

        spend = await client.get(f"/api/spend/{user_id}", headers=admin_headers)
        data = assert_success_response(spend, 200)

        # Every REST-created conversation appears in the spend aggregation.
        spend_conv_ids = {c["conversation_id"] for c in data["conversations"]}
        assert created_ids == spend_conv_ids
        spend_topics = {c["topic"] for c in data["conversations"]}
        assert spend_topics == set(topics)

        # The single auto-created session reports a conversation_count of 3.
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["conversation_count"] == 3

    async def test_spend_conversation_count_excludes_other_users(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """One user's conversations must not leak into another user's spend.

        Exercises the WHERE UserSession.user_id == user_id clause of the spend
        join against two real users who each created conversations over REST.
        """
        admin_headers = await create_admin_headers(
            client, db_session, "spend_admin_iso", "AdminPw2!"
        )

        user_a = await register_and_get_token(client, "spend_alice", "AlicePw1!")
        headers_a = bearer_header(user_a)
        id_a = user_a["user"]["id"]

        user_b = await register_and_get_token(client, "spend_bob", "BobPw1!")
        headers_b = bearer_header(user_b)

        await create_conversation_with_thinker(client, headers_a, "Alice only")
        await create_conversation_with_thinker(client, headers_b, "Bob one")
        await create_conversation_with_thinker(client, headers_b, "Bob two")

        spend_a = await client.get(f"/api/spend/{id_a}", headers=admin_headers)
        data_a = assert_success_response(spend_a, 200)
        assert {c["topic"] for c in data_a["conversations"]} == {"Alice only"}
        assert data_a["sessions"][0]["conversation_count"] == 1


# ============================================================================
# Cost-filter contract: REST user messages do not inflate spend
# ============================================================================


class TestUserMessagesDoNotInflateSpend:
    """Messages sent via POST /messages have cost=NULL and must not count.

    The spend query counts messages with `cost IS NOT NULL`. A regression that
    counted *all* messages (or defaulted user-message cost to 0.0 in a way that
    passed the filter) would surface here, where single-endpoint tests on either
    side would not.
    """

    async def test_user_messages_leave_message_count_and_total_at_zero(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin_headers = await create_admin_headers(client, db_session, "msg_admin_j10", "AdminPw3!")

        user = await register_and_get_token(client, "msg_user", "UserPw2!")
        user_headers = bearer_header(user)
        user_id = user["user"]["id"]

        conv_id = await create_conversation_with_thinker(client, user_headers, "Costless topic")

        for i in range(3):
            resp = await client.post(
                f"/api/conversations/{conv_id}/messages",
                headers=user_headers,
                json={"content": f"User message number {i}"},
            )
            assert resp.status_code == 200

        spend = await client.get(f"/api/spend/{user_id}", headers=admin_headers)
        data = assert_success_response(spend, 200)

        conv_spend = next(c for c in data["conversations"] if c["conversation_id"] == conv_id)
        # User messages carry no cost -> excluded from message_count and total_spend.
        assert conv_spend["message_count"] == 0
        assert conv_spend["total_spend"] == 0.0
        # User-level lifetime spend is likewise untouched by user messages.
        assert data["total_spend"] == 0.0


# ============================================================================
# Delete cascade into the spend aggregation
# ============================================================================


class TestDeleteConversationDropsFromSpend:
    """DELETE /conversations/{id} must remove the conversation from GET /spend.

    Chains a write (create x2), a delete (one), and a read on a *different*
    endpoint (spend) - verifying the delete is durably committed and the spend
    join no longer returns the removed row or counts it in the session total.
    """

    async def test_deleting_one_conversation_removes_it_from_spend(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin_headers = await create_admin_headers(client, db_session, "del_admin_j10", "AdminPw4!")

        user = await register_and_get_token(client, "del_spend_user", "UserPw3!")
        user_headers = bearer_header(user)
        user_id = user["user"]["id"]

        keep_id = await create_conversation_with_thinker(client, user_headers, "Keep me")
        drop_id = await create_conversation_with_thinker(client, user_headers, "Delete me")

        # Sanity: both present before deletion.
        before = assert_success_response(
            await client.get(f"/api/spend/{user_id}", headers=admin_headers), 200
        )
        assert {c["conversation_id"] for c in before["conversations"]} == {keep_id, drop_id}
        assert before["sessions"][0]["conversation_count"] == 2

        delete_resp = await client.delete(f"/api/conversations/{drop_id}", headers=user_headers)
        assert delete_resp.status_code == 200

        after = assert_success_response(
            await client.get(f"/api/spend/{user_id}", headers=admin_headers), 200
        )
        after_ids = {c["conversation_id"] for c in after["conversations"]}
        assert after_ids == {keep_id}
        assert drop_id not in after_ids
        # The session's conversation_count drops accordingly.
        assert after["sessions"][0]["conversation_count"] == 1


# ============================================================================
# Session-id linkage consistency across three endpoints
# ============================================================================


class TestSessionIdConsistencyAcrossEndpoints:
    """The same session id must surface from /sessions/me, conversation, spend.

    The JWT carries both `sub` (user) and `session_id`. /sessions/me decodes
    the session id from the token, POST /conversations stamps it onto the
    conversation, and /spend reports it per session. A drift between any two
    (e.g. a second session being created on a write path) would break this
    chain; no existing test ties all three together.
    """

    async def test_session_id_identical_across_sessions_me_conversation_and_spend(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin_headers = await create_admin_headers(
            client, db_session, "link_admin_j10", "AdminPw5!"
        )

        user = await register_and_get_token(client, "link_user", "UserPw4!")
        user_headers = bearer_header(user)
        user_id = user["user"]["id"]

        # Session id as reported by /sessions/me.
        me = assert_success_response(
            await client.get("/api/sessions/me", headers=user_headers), 200
        )
        session_id_from_me = me["id"]

        # Session id stamped on a freshly created conversation.
        conv_resp = await client.post(
            "/api/conversations",
            headers=user_headers,
            json={
                "topic": "Linkage check",
                "thinkers": [{"name": "T", "bio": "b", "positions": "p", "style": "s"}],
            },
        )
        conv_data = assert_success_response(conv_resp, 200)
        assert conv_data["session_id"] == session_id_from_me

        # Session id as reported by the spend aggregation.
        spend = assert_success_response(
            await client.get(f"/api/spend/{user_id}", headers=admin_headers), 200
        )
        assert len(spend["sessions"]) == 1
        assert spend["sessions"][0]["session_id"] == session_id_from_me
        # And the conversation's spend row references the same session.
        assert spend["conversations"][0]["session_id"] == session_id_from_me
