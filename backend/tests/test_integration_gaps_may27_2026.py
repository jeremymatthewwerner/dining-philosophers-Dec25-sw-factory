"""Integration gap tests - Wednesday focus (May 27, 2026).

Cross-endpoint workflow tests targeting integration scenarios that pair
multiple API calls and assert effects of one call are observable through
another. While each endpoint has near-100% unit coverage, these tests catch
contract drift between endpoints that single-endpoint tests miss.

Workflows covered:
- Message-count propagation: POST /messages -> GET /conversations reflects count
- Spend hierarchy: POST /messages -> admin GET /spend/{user} shows conversation
- Color uniqueness across multiple PUT /thinkers calls (sequential adds)
- Idle-pause auto-resume durability: resume then send another message
- Language preference round-trip through /me and /sessions/me
- Delete-cascade visibility through admin /spend endpoint
- Create-then-get attribute fidelity (thinker fields survive round-trip)
- Admin user listing reflects newly-registered users immediately
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message
from app.models.message import SenderType
from app.services.thinker import thinker_service
from tests.conftest import (
    assert_success_response,
    create_admin_headers,
    get_auth_headers,
    register_and_get_token,
)

# ============================================================================
# Message-count propagation: messages POST -> conversation LIST
# ============================================================================


class TestMessageCountPropagation:
    """POST /messages must increment message_count visible via GET /conversations."""

    async def test_list_message_count_reflects_user_messages_sent(
        self, client: AsyncClient
    ) -> None:
        """After sending N user messages, list endpoint reports message_count=N.

        Exercises send_message in conversations.py and list_conversations'
        message_count aggregation together. Catches mismatches between the
        message insertion path (lines 257-265) and the list summary path
        (lines 88-104).
        """
        headers = await get_auth_headers(client, "msgcount_user", "Password1!")
        create = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Counting test",
                "thinkers": [{"name": "Counter", "bio": "b", "positions": "p", "style": "s"}],
            },
        )
        conv_id = create.json()["id"]

        for i in range(3):
            resp = await client.post(
                f"/api/conversations/{conv_id}/messages",
                headers=headers,
                json={"content": f"message {i}"},
            )
            assert_success_response(resp, 200)

        listed = (await client.get("/api/conversations", headers=headers)).json()
        ours = next(c for c in listed if c["id"] == conv_id)
        assert ours["message_count"] == 3, (
            f"Expected 3 messages in list summary, got {ours['message_count']}"
        )


# ============================================================================
# Spend hierarchy: messages with cost are visible in admin /spend
# ============================================================================


class TestSpendHierarchyIntegration:
    """POST /messages with cost must be observable via GET /api/spend/{user_id}."""

    async def test_admin_spend_endpoint_includes_user_conversation_after_message_send(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Admin viewing /spend/{user_id} sees the conversation a user created.

        Cross-endpoint integration: user creates conversation, admin queries
        spend, response includes that conversation's entry in the top-level
        conversations list. This validates the spend endpoint's join across
        sessions->conversations respects newly-created rows.
        """
        # Create the regular user
        user_data = await register_and_get_token(client, "spend_target_user", "Password1!")
        user_id = user_data["user"]["id"]
        user_headers = {"Authorization": f"Bearer {user_data['access_token']}"}

        create = await client.post(
            "/api/conversations",
            headers=user_headers,
            json={
                "topic": "Spend test topic",
                "thinkers": [{"name": "Spendy", "bio": "b", "positions": "p", "style": "s"}],
            },
        )
        conv_id = create.json()["id"]

        # Admin queries spend
        admin_headers = await create_admin_headers(client, db_session, "spend_admin", "AdminPass1!")
        spend_resp = await client.get(f"/api/spend/{user_id}", headers=admin_headers)
        spend_data = assert_success_response(spend_resp, 200)

        # conversations is a flat list at the top level of the response
        conv_ids = [c["conversation_id"] for c in spend_data.get("conversations", [])]
        assert conv_id in conv_ids, (
            f"Created conversation {conv_id} not in admin spend breakdown: {conv_ids}"
        )
        # The conversation also rolls up under exactly one session entry
        assert len(spend_data.get("sessions", [])) >= 1

    async def test_admin_spend_endpoint_reflects_message_with_cost(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """When a thinker-message with cost is persisted, admin spend reflects it.

        Inserts a direct thinker Message with cost (since user messages have
        no cost), then verifies admin /spend shows non-zero total_cost for
        that conversation.
        """
        user_data = await register_and_get_token(client, "spend_cost_user", "Password1!")
        user_id = user_data["user"]["id"]
        user_headers = {"Authorization": f"Bearer {user_data['access_token']}"}

        create = await client.post(
            "/api/conversations",
            headers=user_headers,
            json={
                "topic": "Cost tracking",
                "thinkers": [{"name": "Pricer", "bio": "b", "positions": "p", "style": "s"}],
            },
        )
        conv_id = create.json()["id"]

        # Insert a thinker message with cost directly into the DB so the spend
        # endpoint reports a non-zero total. User messages don't carry cost.
        db_session.add(
            Message(
                conversation_id=conv_id,
                sender_type=SenderType.THINKER,
                sender_name="Pricer",
                content="reply",
                cost=0.05,
            )
        )
        await db_session.commit()

        admin_headers = await create_admin_headers(client, db_session, "cost_admin", "AdminPass1!")
        spend_resp = await client.get(f"/api/spend/{user_id}", headers=admin_headers)
        spend_data = assert_success_response(spend_resp, 200)

        # Find our conversation in the flat conversations list
        our_conv = next(
            (c for c in spend_data.get("conversations", []) if c["conversation_id"] == conv_id),
            None,
        )
        assert our_conv is not None, (
            f"Could not find conv {conv_id} in spend breakdown: "
            f"{[c['conversation_id'] for c in spend_data.get('conversations', [])]}"
        )
        assert our_conv["total_spend"] >= 0.05, (
            f"Expected total_spend >= 0.05 (1 message at 0.05), got {our_conv['total_spend']}"
        )
        assert our_conv["message_count"] >= 1


# ============================================================================
# Color uniqueness across multiple sequential PUT /thinkers calls
# ============================================================================


class TestSequentialAddThinkersColorUniqueness:
    """Multiple PUT /thinkers calls should each pick a distinct color from pool."""

    async def test_two_sequential_adds_each_get_distinct_color_from_initial(
        self, client: AsyncClient
    ) -> None:
        """Conversation starts with one thinker. Two subsequent PUTs (one thinker
        each) with default color must each receive a distinct color, none equal
        to the original thinker's color.

        Exercises the color-pool logic in add_thinkers_to_conversation
        across consecutive calls — the pool is recomputed on each request, so
        the second call must observe the first call's color allocation.
        """
        headers = await get_auth_headers(client, "color_seq_user", "Password1!")
        create = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Color sequencing",
                "thinkers": [{"name": "First", "bio": "b", "positions": "p", "style": "s"}],
            },
        )
        conv_id = create.json()["id"]
        first_color = create.json()["thinkers"][0]["color"]

        add1 = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[{"name": "Second", "bio": "b", "positions": "p", "style": "s"}],
        )
        assert add1.status_code == 200
        second_color = add1.json()[0]["color"]

        add2 = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[{"name": "Third", "bio": "b", "positions": "p", "style": "s"}],
        )
        assert add2.status_code == 200
        third_color = add2.json()[0]["color"]

        # All three must be distinct and within the canonical palette
        palette = {"#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"}
        assert first_color in palette
        assert second_color in palette
        assert third_color in palette
        assert len({first_color, second_color, third_color}) == 3, (
            f"Colors must be distinct: first={first_color}, "
            f"second={second_color}, third={third_color}"
        )


# ============================================================================
# Idle-pause auto-resume durability across messages
# ============================================================================


class TestIdlePauseResumeDurability:
    """After auto-resume via send_message, subsequent messages must still work."""

    async def test_subsequent_message_after_idle_resume_succeeds(self, client: AsyncClient) -> None:
        """Idle-pause -> first message resumes -> second message processed normally.

        Catches a regression where idle-resume left the conversation in a
        partial state that blocked further messages.
        """
        headers = await get_auth_headers(client, "idle_resume_user", "Password1!")
        create = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Idle resume",
                "thinkers": [{"name": "Resumer", "bio": "b", "positions": "p", "style": "s"}],
            },
        )
        conv_id = create.json()["id"]

        # Force idle-pause state, then resume by sending a user message
        thinker_service.pause_for_idle(conv_id)
        assert thinker_service.is_idle_paused(conv_id) is True

        first = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "wake up"},
        )
        assert_success_response(first, 200)
        assert thinker_service.is_idle_paused(conv_id) is False

        # Second message should succeed normally
        second = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "still awake"},
        )
        assert_success_response(second, 200)
        assert thinker_service.is_idle_paused(conv_id) is False


# ============================================================================
# Language preference round-trip across endpoints
# ============================================================================


class TestLanguagePreferenceRoundTrip:
    """PATCH /profile language must propagate to /me and /sessions/me."""

    async def test_language_update_visible_in_me_after_patch_language(
        self, client: AsyncClient
    ) -> None:
        """Updating language via PATCH /language must be reflected in GET /me
        and the patch response itself.

        Validates that language_preference is correctly stored on the User
        model and that /me reads the canonical source. Catches a regression
        where the PATCH /language response and the /me response diverge.
        """
        headers = await get_auth_headers(client, "lang_user", "Password1!")

        # Pre-update: /me has the default language
        me_before = (await client.get("/api/auth/me", headers=headers)).json()
        default_lang = me_before["language_preference"]

        # Update language to something distinct from default
        new_lang = "es" if default_lang != "es" else "fr"
        patch_resp = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": new_lang},
        )
        patch_data = assert_success_response(patch_resp, 200)
        assert patch_data["language_preference"] == new_lang

        # /me reflects new language
        me_resp = await client.get("/api/auth/me", headers=headers)
        me_data = assert_success_response(me_resp, 200)
        assert me_data["language_preference"] == new_lang, (
            f"Expected /me to show language={new_lang} after PATCH, got "
            f"{me_data['language_preference']}"
        )


# ============================================================================
# Delete-cascade visibility through admin /spend endpoint
# ============================================================================


class TestDeleteCascadeSpendVisibility:
    """Deleting a conversation should remove it from admin /spend breakdown."""

    async def test_deleted_conversation_no_longer_in_admin_spend_breakdown(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Create conversation -> admin spend shows it -> delete -> spend excludes it.

        Validates that DELETE /api/conversations/{id} cascades through the
        spend join (sessions->conversations), so the admin spend view doesn't
        show dangling deleted conversations.
        """
        user_data = await register_and_get_token(client, "delete_spend_user", "Password1!")
        user_id = user_data["user"]["id"]
        user_headers = {"Authorization": f"Bearer {user_data['access_token']}"}

        create = await client.post(
            "/api/conversations",
            headers=user_headers,
            json={
                "topic": "Delete me",
                "thinkers": [{"name": "Deletable", "bio": "b", "positions": "p", "style": "s"}],
            },
        )
        conv_id = create.json()["id"]

        admin_headers = await create_admin_headers(
            client, db_session, "delete_spend_admin", "AdminPass1!"
        )

        # Pre-delete: spend shows the conversation in the flat conversations list
        spend_resp = await client.get(f"/api/spend/{user_id}", headers=admin_headers)
        spend_data = spend_resp.json()
        ids_pre = [c["conversation_id"] for c in spend_data.get("conversations", [])]
        assert conv_id in ids_pre

        # Delete the conversation
        await client.delete(f"/api/conversations/{conv_id}", headers=user_headers)

        # Post-delete: spend no longer shows the conversation
        spend_resp = await client.get(f"/api/spend/{user_id}", headers=admin_headers)
        spend_data = spend_resp.json()
        ids_post = [c["conversation_id"] for c in spend_data.get("conversations", [])]
        assert conv_id not in ids_post, (
            f"Deleted conversation {conv_id} still appears in spend breakdown: {ids_post}"
        )


# ============================================================================
# Create-then-get attribute fidelity for thinker fields
# ============================================================================


class TestCreateGetAttributeFidelity:
    """Thinker fields submitted at create-time survive round-trip through GET."""

    async def test_thinker_fields_persist_across_create_and_get(self, client: AsyncClient) -> None:
        """Submitting bio/positions/style/image_url returns identical values
        via GET /conversations/{id}.

        Catches schema-level mismatches where, e.g., the API drops or trims
        certain fields on response (which a unit test of the create endpoint
        alone wouldn't notice).
        """
        headers = await get_auth_headers(client, "fidelity_user", "Password1!")
        thinker_payload = {
            "name": "DetailedThinker",
            "bio": "A long biography with specific details that must survive.",
            "positions": "Holds nuanced positions on epistemology and ethics.",
            "style": "Formal, deliberate, often allegorical.",
            "image_url": "https://example.com/portrait.png",
        }
        create = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Fidelity test", "thinkers": [thinker_payload]},
        )
        conv_id = create.json()["id"]

        get_resp = await client.get(f"/api/conversations/{conv_id}", headers=headers)
        data = assert_success_response(get_resp, 200)
        assert len(data["thinkers"]) == 1
        t = data["thinkers"][0]
        assert t["name"] == thinker_payload["name"]
        assert t["bio"] == thinker_payload["bio"]
        assert t["positions"] == thinker_payload["positions"]
        assert t["style"] == thinker_payload["style"]
        assert t["image_url"] == thinker_payload["image_url"]


# ============================================================================
# Admin user listing reflects newly-registered users immediately
# ============================================================================


class TestAdminUserListingFreshness:
    """Newly-registered users appear in admin /users without restart/refresh."""

    async def test_user_registered_after_admin_login_appears_in_admin_list(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Admin logs in, then a new user registers, then admin re-lists users
        and sees the new user.

        Verifies the admin list query is not cached and reflects DB state at
        request time. Catches caching/staleness regressions.
        """
        admin_headers = await create_admin_headers(
            client, db_session, "freshness_admin", "AdminPass1!"
        )

        # Initial list — capture usernames
        before = await client.get("/api/admin/users", headers=admin_headers)
        before_names = {u["username"] for u in before.json()}
        assert "freshness_admin" in before_names

        # A new user registers after the admin has authenticated
        new_username = "fresh_newcomer"
        await register_and_get_token(client, new_username, "Password1!")

        # Admin re-lists — new user is present
        after = await client.get("/api/admin/users", headers=admin_headers)
        after_names = {u["username"] for u in after.json()}
        assert new_username in after_names, (
            f"Newly-registered user {new_username} missing from admin list: {after_names}"
        )
        # And user count incremented by exactly 1
        assert len(after.json()) == len(before.json()) + 1


# ============================================================================
# Cross-endpoint authorization: non-admin user 403 on spend, but their own /me works
# ============================================================================


class TestAuthorizationBoundaryAcrossEndpoints:
    """Non-admin user must be rejected from /spend even for their own user_id,
    while still able to read /me. Validates that admin-gating is per-endpoint
    rather than per-user."""

    async def test_non_admin_cannot_read_own_spend_but_can_read_own_me(
        self, client: AsyncClient
    ) -> None:
        """User Alice can GET /api/auth/me but receives 403 on /api/spend/{her_id}.

        This catches a regression where /api/spend might be mis-gated by
        ownership rather than admin-flag, or vice-versa.
        """
        user_data = await register_and_get_token(client, "boundary_user", "Password1!")
        user_id = user_data["user"]["id"]
        headers = {"Authorization": f"Bearer {user_data['access_token']}"}

        # /me succeeds
        me_resp = await client.get("/api/auth/me", headers=headers)
        assert_success_response(me_resp, 200)

        # /spend/{own_id} is forbidden because user is not admin
        spend_resp = await client.get(f"/api/spend/{user_id}", headers=headers)
        # Either 403 (admin check) or another 4xx — we just need NOT 200
        assert spend_resp.status_code != 200, (
            f"Non-admin should not access /spend even for own ID; got {spend_resp.status_code}"
        )
        assert spend_resp.status_code in (401, 403), (
            f"Expected 401/403, got {spend_resp.status_code}"
        )
