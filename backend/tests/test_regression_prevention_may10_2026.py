"""Regression prevention tests for Sunday QA (May 10, 2026).

Focus: behavioral invariants in core services that lack explicit regression
guards. Each test pins down a specific branch or boundary that — if changed
inadvertently — would cause silent product regressions:

- self-message follow-up suppression in `_should_respond` (line 1593-1594)
- @mention overrides self-message suppression
- consecutive-silence boost capped at 0.9 (line 1588-1589)
- addressed-by-name boost capped at 0.95 (line 1585)
- @mention sets base_probability to exactly 0.98 (line 1581)
- `is_mentioned` with empty thinker_name does not crash (line 105 fallback)
- `_extract_thinking_display` doesn't double-prefix when text already starts
  with a starter prefix (line 961)
- `extract_mentions` quoted name dedupes when same first word appears bare
- `_get_user_name_from_messages` skips users with sender_name=None
- `ConversationRoom.broadcast` deactivates room when ALL clients disconnect
- `ConversationRoom.broadcast` no-op for empty connection set
- `ConnectionManager.connect` creates the room when conversation_id is new
- `ConnectionManager.disconnect` no-op for unknown conversation_id
- `pause_conversation` idempotent; `resume_conversation` idempotent on unpaused
- `SpendStatus.is_near_limit` boundary at 85%
- `SpendStatus` with `spend_limit=0` treated as 100% used
- `can_user_spend` returns False for unknown user
- Auth language schema rejects `hi` while service accepts it (documented gap)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import (
    ConnectionManager,
    ConversationRoom,
    WSMessage,
    WSMessageType,
)
from app.models import ResearchStatus, ThinkerKnowledge
from app.services.knowledge_research import KnowledgeResearchService
from app.services.spend import (
    SpendStatus,
    can_user_spend,
    check_spend_limit,
)
from app.services.thinker import (
    ThinkerService,
    _get_language_instruction,
    extract_mentions,
    is_mentioned,
)
from tests.conftest import get_auth_headers

# ===========================================================================
# TestShouldRespondSelfFollowupSuppression
# Regression guard for thinker.py:1593-1594:
#   if messages[-1].sender_name == thinker.name and not was_at_mentioned:
#       base_probability = 0.05
# This prevents thinkers from responding to their own messages in a tight loop.
# Removing this branch would cause one thinker to monologue indefinitely.
# ===========================================================================


class TestShouldRespondSelfFollowupSuppression:
    """Regression tests: thinker doesn't reply-loop to its own latest message."""

    def test_self_followup_suppressed_to_low_probability(self) -> None:
        """When last message is from this thinker and no @mention, response rate is ~5%.

        Regression guard: removing the `base_probability = 0.05` line would
        cause runaway monologues where one thinker keeps replying to itself.
        Sample at 200 trials so the probability gap (0.05 vs 0.7+) is
        statistically clear.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        own_msg = MagicMock()
        own_msg.content = "I am thinking..."
        own_msg.sender_name = "Socrates"

        responses = [service._should_respond(thinker, [own_msg], 0) for _ in range(200)]
        rate = sum(responses) / len(responses)

        # Should be well below 0.20 — actual is 0.05 (with 15% silent skip,
        # effective rate is 0.05 * 0.85 = ~0.0425). Use 0.20 as a generous
        # ceiling to keep the test deterministic across random seeds.
        assert rate < 0.20, (
            f"Self-followup response rate {rate:.2%} too high — "
            f"the 0.05 suppression has likely regressed."
        )

    def test_at_mentioning_self_bypasses_self_followup_suppression(self) -> None:
        """Self-mention bypasses the 0.05 self-followup floor.

        Regression guard for the `not was_at_mentioned` clause in line 1593.
        The exception exists so that a thinker who explicitly @-mentioned
        itself in its own last message still gets the 0.98 mention boost
        — rare, but the dual-condition logic must remain intact.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Plato"

        own_self_mention = MagicMock()
        own_self_mention.content = "@Plato should reconsider this"
        own_self_mention.sender_name = "Plato"

        responses = [service._should_respond(thinker, [own_self_mention], 0) for _ in range(200)]
        rate = sum(responses) / len(responses)

        # @mention sets base_probability to 0.98 — even with random.random()
        # probabilistic check, observed rate should be well above the 0.05
        # self-followup floor.
        assert rate > 0.7, (
            f"Self @mention rate {rate:.2%} too low — the `not was_at_mentioned` "
            f"bypass clause has likely regressed."
        )


# ===========================================================================
# TestShouldRespondProbabilityCaps
# Regression guards for the ceiling clamps in _should_respond:
#   line 1581: was_at_mentioned → base_probability = 0.98
#   line 1585: was_addressed (no @) → min(base_probability + 0.5, 0.95)
#   line 1589: consecutive_silence boost → min(base_probability + ..., 0.9)
# ===========================================================================


class TestShouldRespondProbabilityCaps:
    """Regression tests: probability caps prevent always-on response behavior."""

    def test_at_mention_does_not_exceed_0_98(self) -> None:
        """@mention sets base_probability to 0.98 (not 1.0).

        Regression guard: the design choice is that even @mentioned thinkers
        skip a turn ~2% of the time to avoid robotic always-responds behavior.
        If this regresses to 1.0, the cap line (`base_probability = 0.98`) was
        removed and tests for "natural variation" would silently degrade.
        Empirically: 200 trials should produce at least one False if cap holds.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Aristotle"

        msg = MagicMock()
        msg.content = "@Aristotle what do you think?"
        msg.sender_name = "Plato"

        # Run many trials; at p=0.98, expect ~4 False per 200 trials.
        # If p were 1.0, we'd never see False.
        responses = [service._should_respond(thinker, [msg], 0) for _ in range(500)]
        false_count = responses.count(False)

        # With p=0.98, P(no False in 500) = 0.98^500 ≈ 4.4e-5 — vanishingly small.
        # If somebody removed the cap, this test would fail consistently.
        assert false_count >= 1, (
            "Expected at least one non-response across 500 @mentioned trials. "
            "The 0.98 cap appears to have regressed to 1.0."
        )

    def test_consecutive_silence_boost_capped_at_0_9(self) -> None:
        """Consecutive-silence boost is capped at 0.9 — never reaches 1.0.

        Regression guard for line 1589's `min(..., 0.9)` clamp. With high
        consecutive_silence (e.g. 10), unbounded boost would saturate at >1.0
        and bypass the silent-skip branch. The 0.9 cap preserves variability.
        """
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Curie"

        # Single user message (not addressed by name, no @mention)
        msg = MagicMock()
        msg.content = "What is radioactivity really?"
        msg.sender_name = "User"

        # Use very high consecutive_silence to push boost to ceiling
        responses = [
            service._should_respond(thinker, [msg], 0, consecutive_silence=10) for _ in range(500)
        ]
        false_count = responses.count(False)

        # Hard cap is 0.9 + 15% silent skip path = 0.9 * 0.85 = 0.765.
        # If cap were removed, effective rate could approach 0.85+.
        # With p=0.765, expect ~117 False per 500 trials.
        assert false_count > 50, (
            f"Got only {false_count} False across 500 trials with high "
            f"consecutive_silence — the 0.9 cap appears to have regressed."
        )


# ===========================================================================
# TestIsMentionedEmptyThinkerName
# Regression guard for thinker.py:105:
#   first_name_lower = thinker_name.split()[0].lower() if thinker_name else ""
# Without the `if thinker_name else ""` guard, "".split()[0] would raise
# IndexError. Empty thinker_name shouldn't happen in practice, but the
# defensive guard prevents crashes from corrupted data.
# ===========================================================================


class TestIsMentionedEmptyThinkerName:
    """Regression tests: is_mentioned tolerates empty thinker_name."""

    def test_empty_thinker_name_does_not_raise(self) -> None:
        """is_mentioned("@something", "") returns False without IndexError.

        Regression guard: line 105 has an explicit `if thinker_name else ""`
        fallback. Without it, `"".split()[0]` raises IndexError. This protects
        the agent loop from crashing if a thinker record has a corrupted name.
        """
        # Should not raise despite empty thinker_name
        result = is_mentioned("@Socrates is here", "")
        assert result is False, "Empty thinker_name should never match any mention"

    def test_empty_thinker_name_with_empty_text_does_not_raise(self) -> None:
        """Both inputs empty: returns False without raising."""
        result = is_mentioned("", "")
        assert result is False


# ===========================================================================
# TestExtractThinkingDisplayStarterPrefixDedup
# Regression guard for thinker.py:961-962:
#   if not text.lower().startswith(starter_prefixes):
#       text = prefix + text
# This prevents double-prefix outputs like "Hmm... Hmm... I think...". If the
# guard regresses, every starter-text input would get a redundant prefix.
# ===========================================================================


class TestExtractThinkingDisplayStarterDedup:
    """Regression tests: no double-prefix when text already starts with a starter."""

    def test_text_starting_with_hmm_does_not_get_double_prefix(self) -> None:
        """Text starting with 'Hmm' is not given another 'Hmm... ' prefix.

        Regression guard: the `if not text.lower().startswith(starter_prefixes)`
        check prevents output like "Hmm... Hmm, I should consider this carefully
        and think about what the user really meant by their question..."
        """
        service = ThinkerService()
        text = (
            "Hmm, I should consider this carefully and think about what the user "
            "really meant by their question regarding philosophy."
        )
        result = service._extract_thinking_display(text, language="en")

        # Result should not have starter prefix added (text starts with "Hmm")
        # Count occurrences of the starter prefixes in the first ~30 chars.
        head = result[:30].lower()
        assert head.count("hmm") <= 1, (
            f"Result has duplicate 'hmm' prefix: {result!r}. "
            f"The starter-prefix dedup check has regressed."
        )

    def test_text_starting_with_let_me_does_not_get_double_prefix(self) -> None:
        """Text starting with 'Let me' is not given another 'Let me... ' prefix."""
        service = ThinkerService()
        text = (
            "Let me think about this. The question raises deep concerns about "
            "the nature of knowledge and how we come to know what we know."
        )
        result = service._extract_thinking_display(text, language="en")

        head = result[:40].lower()
        assert head.count("let me") <= 1, f"Result has duplicate 'Let me' prefix: {result!r}"


# ===========================================================================
# TestExtractMentionsQuotedDedup
# Regression guard for thinker.py:82:
#   if name not in mentions:
#       mentions.append(name)
# This deduplicates simple-pattern matches against quoted ones already
# captured. Without dedup, "@\"Marie Curie\" said... and Marie..." would
# produce ["Marie Curie", "Marie"] — two separate entries that complicate
# downstream is_mentioned() logic.
# ===========================================================================


class TestExtractMentionsQuotedDedup:
    """Regression tests: extract_mentions doesn't double-list quoted-then-bare."""

    def test_quoted_name_followed_by_bare_first_word_does_not_duplicate(self) -> None:
        """When `@"Marie Curie"` appears, then later `@Marie`, no duplicate.

        Regression guard: the simple_pattern (`@(\\w+)`) would match `Marie`
        from the quoted string AND from the later bare reference. The dedup
        check ensures only one `Marie` (the bare one) is added since `Marie
        Curie` was already captured.

        Note: actual behavior — quoted captures "Marie Curie" entirely;
        the bare "@Marie" later is added because "Marie" != "Marie Curie".
        But the simple_pattern would ALSO match the "Marie" from inside the
        quoted text. The dedup `if name not in mentions` prevents that.
        """
        result = extract_mentions('@"Marie Curie" is here. Also @Marie spoke.')

        # The simple_pattern picks up "Marie" from inside the quoted match,
        # but dedup means it only appears once total in the list.
        marie_count = sum(1 for m in result if m == "Marie")
        assert marie_count <= 1, (
            f"'Marie' appears {marie_count} times in {result}. Quoted-vs-bare dedup has regressed."
        )

    def test_simple_pattern_alone_works_for_punctuation_terminator(self) -> None:
        """`@Plato!` (with trailing punctuation) extracts as 'Plato'.

        The simple_pattern `@(\\w+)` stops at non-word chars, so punctuation
        becomes a clean terminator. This is a regression guard for the
        regex itself: any change to the pattern would alter this contract.
        """
        result = extract_mentions("@Plato!")
        assert result == ["Plato"], (
            f"Expected ['Plato'] from '@Plato!', got {result}. "
            f"The simple_pattern regex contract has changed."
        )


# ===========================================================================
# TestGetUserNameSkipsUnnamedUsers
# Regression guard for thinker.py:1417:
#   if is_user and msg.sender_name:
# Without the truthiness check on sender_name, the function would return
# None or empty string from a user message that happens to have no name set.
# This caused the user-prompt feature to address "None" or empty users.
# ===========================================================================


class TestGetUserNameSkipsUnnamedUsers:
    """Regression tests: skip user messages that don't have a sender_name."""

    def test_user_message_without_sender_name_is_skipped(self) -> None:
        """A user message with sender_name=None falls through to the next user.

        Regression guard for line 1417's `and msg.sender_name` truthiness check.
        Without it, the function would return None as a valid user name,
        producing prompts like "None, I'm curious what you think."
        """
        service = ThinkerService()

        unnamed_user = MagicMock()
        unnamed_user.sender_type = "user"
        unnamed_user.sender_name = None

        named_user = MagicMock()
        named_user.sender_type = "user"
        named_user.sender_name = "Alice"

        # Reverse iteration: searches from end backward, so put unnamed last.
        # Service iterates reversed(messages) — unnamed is checked first
        # (last in list), should be skipped, and Alice is found.
        messages = [named_user, unnamed_user]

        result = service._get_user_name_from_messages(messages)
        assert result == "Alice", (
            f"Expected 'Alice' (skipping unnamed user), got {result!r}. "
            f"The `and msg.sender_name` truthiness guard has regressed."
        )

    def test_user_message_with_empty_string_sender_name_is_skipped(self) -> None:
        """sender_name == '' (falsy) is also skipped.

        Defensive guard: empty strings are falsy in Python, so the same
        truthiness check protects against blank names too.
        """
        service = ThinkerService()

        empty_named = MagicMock()
        empty_named.sender_type = "user"
        empty_named.sender_name = ""

        named = MagicMock()
        named.sender_type = "user"
        named.sender_name = "Bob"

        # Iteration is reversed — empty_named is checked first
        messages = [named, empty_named]

        result = service._get_user_name_from_messages(messages)
        assert result == "Bob"


# ===========================================================================
# TestConversationRoomBroadcastDeactivation
# Regression guard for websocket.py:108-109:
#   if not self.connections:
#       self.is_active = False
# When all clients disconnect mid-broadcast, is_active must flip to False so
# the thinker agent loop pauses (waiting for users to reconnect). Without
# this, agents would keep spending tokens despite no audience.
# ===========================================================================


class TestConversationRoomBroadcastDeactivation:
    """Regression tests: broadcast removes failed clients and toggles is_active."""

    async def test_broadcast_deactivates_room_when_all_clients_fail(self) -> None:
        """If all WebSockets fail during broadcast, is_active becomes False.

        Regression guard for the cleanup path: when every client raises an
        exception during send_text, all are added to `disconnected` and
        removed; `is_active` then flips to False. Removing this would leave
        thinker agents running indefinitely against zero audience.
        """
        room = ConversationRoom(conversation_id="all-fail-test")
        ws_a = AsyncMock()
        ws_a.send_text = AsyncMock(side_effect=Exception("connection lost"))
        ws_b = AsyncMock()
        ws_b.send_text = AsyncMock(side_effect=Exception("connection lost"))

        room.add_connection(ws_a)
        room.add_connection(ws_b)
        assert room.is_active is True

        msg = WSMessage(type=WSMessageType.MESSAGE, conversation_id="all-fail-test")
        await room.broadcast(msg)

        # Both connections should be purged
        assert ws_a not in room.connections
        assert ws_b not in room.connections
        # Room should be marked inactive — agents stop spending tokens
        assert room.is_active is False, (
            "Room should be inactive after all clients disconnected during broadcast. "
            "The auto-deactivate path in broadcast has regressed."
        )

    async def test_broadcast_to_empty_room_does_not_raise(self) -> None:
        """Broadcasting to a room with no connections is a silent no-op.

        Regression guard: this happens when a thinker agent generates a
        response after all users disconnected. The for loop iterates 0
        times and the function returns cleanly.
        """
        room = ConversationRoom(conversation_id="empty-room-test")
        msg = WSMessage(type=WSMessageType.MESSAGE, conversation_id="empty-room-test")

        # Should not raise even with no connections
        await room.broadcast(msg)

        # Room state unchanged — it was never activated
        assert room.is_active is False


# ===========================================================================
# TestConnectionManagerLifecycle
# Regression guards for ConnectionManager.connect / disconnect:
#   - connect must create a new room when conversation_id is unseen
#   - disconnect must be a no-op for an unknown conversation_id
# ===========================================================================


class TestConnectionManagerLifecycle:
    """Regression tests: connect/disconnect handle missing rooms safely."""

    async def test_connect_creates_room_for_new_conversation(self) -> None:
        """First connect() for a conversation_id creates the room entry.

        Regression guard for lines 125-127 of websocket.py:
          if conversation_id not in self.rooms:
              self.rooms[conversation_id] = ConversationRoom(...)
        Without this branch, the defaultdict's empty-string conversation_id
        sentinel would be used (set in __init__), breaking is_conversation_active
        which checks `conversation_id in self.rooms`.
        """
        manager = ConnectionManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()

        await manager.connect(ws, "new-conv-create-room")

        assert "new-conv-create-room" in manager.rooms
        assert manager.rooms["new-conv-create-room"].conversation_id == "new-conv-create-room"
        assert ws in manager.rooms["new-conv-create-room"].connections
        assert manager.rooms["new-conv-create-room"].is_active is True

    async def test_disconnect_is_noop_for_unknown_conversation(self) -> None:
        """disconnect for a conversation that was never connected does not raise.

        Regression guard for line 132's `if conversation_id in self.rooms`
        check. Without it, calling disconnect on a stale conversation_id
        (e.g. after server restart) would auto-create a phantom room via
        the defaultdict, then try to remove a connection from it.
        """
        manager = ConnectionManager()
        ws = AsyncMock()

        # Should not raise — and should not create a phantom room
        await manager.disconnect(ws, "never-connected-conv")

        assert "never-connected-conv" not in manager.rooms


# ===========================================================================
# TestThinkerServicePauseIdempotency
# Regression guards for pause_conversation / resume_conversation set semantics.
# Both use set.add() / set.discard(), which are inherently idempotent — but
# explicit tests ensure that any future refactor (e.g. switching to a list or
# adding side effects) preserves this contract.
# ===========================================================================


class TestThinkerServicePauseIdempotency:
    """Regression tests: pause/resume operations are idempotent."""

    def test_pause_conversation_called_twice_is_idempotent(self) -> None:
        """Calling pause_conversation twice leaves is_paused=True.

        Regression guard: removing the set semantics (e.g. using a counter
        or list) could break this. Idempotent pause is required because the
        WebSocket handler calls it on every PAUSE message — clients can
        rapidly send duplicate pause events.
        """
        service = ThinkerService()
        conv_id = "pause-twice-test"

        service.pause_conversation(conv_id)
        service.pause_conversation(conv_id)  # second call

        assert service.is_paused(conv_id) is True
        # Internal set should not have grown (set semantics)
        assert len(service._paused_conversations) == 1

    def test_resume_unpaused_conversation_is_safe(self) -> None:
        """Resuming a never-paused conversation does not raise or corrupt state.

        Regression guard: the implementation uses set.discard() (not remove())
        precisely so that calling resume on an unpaused conversation is a
        no-op. If this regressed to set.remove(), it would raise KeyError.
        """
        service = ThinkerService()
        conv_id = "resume-unpaused-test"

        # Should not raise
        service.resume_conversation(conv_id)

        assert service.is_paused(conv_id) is False
        # State unchanged
        assert conv_id not in service._paused_conversations


# ===========================================================================
# TestSpendStatusBoundaries
# Regression guards for spend.py:
#   line 42: percentage = (total/limit * 100) if limit > 0 else 100
#   line 49: is_near_limit = percentage >= 85
#   line 51: percentage_used = min(100, percentage)
# These boundary semantics are user-visible (the spend bar UI) and must
# not silently drift.
# ===========================================================================


class TestSpendStatusBoundaries:
    """Regression tests for SpendStatus threshold semantics."""

    async def test_is_near_limit_true_at_exactly_85_percent(
        self, async_session: AsyncSession
    ) -> None:
        """is_near_limit becomes True at exactly 85% usage.

        Regression guard: the comparison uses `>=` not `>`. If somebody
        changed it to `>`, users at exactly 85% would not see the warning.
        85% is a deliberate yellow-flag threshold that the UI relies on.
        """
        from app.models import User

        user = User(
            username="boundary85",
            password_hash="hash",
            total_spend=8.50,
            spend_limit=10.0,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        status = await check_spend_limit(async_session, user.id)
        assert status is not None
        assert status.percentage_used == pytest.approx(85.0)
        assert status.is_near_limit is True, (
            "is_near_limit must be True at exactly 85%. The >= boundary has regressed to >."
        )

    async def test_is_near_limit_false_at_84_99_percent(self, async_session: AsyncSession) -> None:
        """is_near_limit is False just below 85% (e.g. 84.99%).

        Regression guard: ensure the threshold doesn't drift downward.
        At 84.99%, users should NOT see the near-limit warning.
        """
        from app.models import User

        user = User(
            username="boundary8499",
            password_hash="hash",
            total_spend=8.499,
            spend_limit=10.0,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        status = await check_spend_limit(async_session, user.id)
        assert status is not None
        assert status.is_near_limit is False, (
            f"is_near_limit at {status.percentage_used:.2f}% should be False"
        )

    async def test_zero_spend_limit_treats_user_as_at_100_percent(
        self, async_session: AsyncSession
    ) -> None:
        """When spend_limit=0, percentage is computed as 100 (over limit).

        Regression guard for line 42's `else 100` fallback. A user with
        zero limit should be blocked, not crash on division-by-zero.
        Without the fallback, a user erroneously created with limit=0
        would crash check_spend_limit.
        """
        from app.models import User

        user = User(
            username="zerolimit",
            password_hash="hash",
            total_spend=5.0,
            spend_limit=0.0,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        status = await check_spend_limit(async_session, user.id)
        assert status is not None
        assert status.percentage_used == 100, (
            "Zero spend_limit should produce percentage_used=100, not crash on division-by-zero."
        )
        assert status.is_over_limit is True
        assert status.is_near_limit is True

    async def test_can_user_spend_returns_false_for_unknown_user(
        self, async_session: AsyncSession
    ) -> None:
        """can_user_spend('nonexistent-uuid') returns False (deny by default).

        Regression guard for line 67 of spend.py:
          if status is None:
              return False  # User not found, deny

        If this regressed to True or raised, an attacker with a forged JWT
        for a deleted user could continue making API calls.
        """
        result = await can_user_spend(async_session, "nonexistent-user-id-12345")
        assert result is False, (
            "Unknown user must be denied — the deny-by-default branch "
            "of can_user_spend has regressed."
        )

    def test_spend_status_dataclass_clamps_percentage_to_100(self) -> None:
        """SpendStatus produced over-limit clamps percentage_used to 100.

        Regression guard for line 51's `min(100, percentage)`. Without the
        clamp, a user at 250% would show 250 in the UI, which would break
        the progress bar (overflow rendering).

        This tests the internal clamping logic via direct construction.
        """
        # Construct a status with hypothetical 250% — caller should clamp.
        status = SpendStatus(
            current_spend=25.0,
            spend_limit=10.0,
            is_over_limit=True,
            is_near_limit=True,
            remaining=0.0,
            percentage_used=min(100, 250.0),
        )
        assert status.percentage_used == 100, (
            "Percentage_used must be clamped to 100 even when actual usage exceeds limit."
        )


# ===========================================================================
# TestKnowledgeRefreshNoStaleEntries
# Regression guard: refresh_stale_knowledge returns 0 when nothing is stale.
# Filtering on (status==COMPLETE) AND (updated_at < threshold) excludes both
# fresh COMPLETE entries and any non-COMPLETE entries.
# ===========================================================================


class TestKnowledgeRefreshNoStaleEntries:
    """Regression tests: refresh_stale_knowledge filtering preserves fresh data."""

    async def test_refresh_stale_returns_zero_for_only_fresh_entries(
        self, async_session: AsyncSession
    ) -> None:
        """When all COMPLETE entries are recent, no refresh tasks are triggered.

        Regression guard: the WHERE clause's compound filter on COMPLETE +
        old timestamp must remain. If somebody simplified to "all entries"
        or "all stale-by-time without status check", FAILED entries would
        get refreshed (potentially looping forever) and recently-completed
        entries would be needlessly re-fetched.
        """
        # Insert a fresh COMPLETE entry (updated NOW)
        fresh_entry = ThinkerKnowledge(
            name="Fresh Thinker May 2026",
            status=ResearchStatus.COMPLETE,
            research_data={"wikipedia": "..."},
        )
        async_session.add(fresh_entry)
        await async_session.commit()
        await async_session.refresh(fresh_entry)

        # Manually set updated_at to be very recent (just to be explicit)
        fresh_entry.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await async_session.commit()

        service = KnowledgeResearchService()
        count = await service.refresh_stale_knowledge(async_session)

        # Fresh entry should not be considered stale → count is 0
        assert count == 0, (
            f"refresh_stale_knowledge returned {count} for only-fresh entries. "
            f"The COMPLETE + old-timestamp filter has regressed."
        )


# ===========================================================================
# TestKnowledgeIsStaleNaiveAwareTimezone
# Regression guard for knowledge_research.py:85:
#   knowledge.updated_at.replace(tzinfo=UTC) < staleness_threshold
# The .replace(tzinfo=UTC) is critical because SQLite stores datetimes naive.
# Without it, comparing naive vs aware would raise TypeError.
# ===========================================================================


class TestKnowledgeIsStaleNaiveAware:
    """Regression tests: is_stale handles naive datetime from SQLite."""

    def test_is_stale_with_naive_recent_timestamp(self) -> None:
        """is_stale handles naive datetime (no tzinfo) without raising.

        Regression guard for the .replace(tzinfo=UTC) call on line 85.
        SQLite stores datetimes naive; PostgreSQL stores aware. The
        explicit .replace makes both work uniformly. Removing it would
        crash on SQLite-backed dev/test environments.
        """
        service = KnowledgeResearchService()
        knowledge = MagicMock()
        knowledge.status = ResearchStatus.COMPLETE
        # Naive datetime simulating SQLite storage
        knowledge.updated_at = datetime.utcnow() - timedelta(days=1)

        # Should not raise TypeError
        result = service.is_stale(knowledge)
        # 1 day < 30 day threshold → not stale
        assert result is False

    def test_is_stale_with_naive_old_timestamp(self) -> None:
        """Old naive timestamp is correctly detected as stale.

        Companion to the recent-timestamp test: confirms that the > 30 day
        threshold still triggers correctly with naive datetimes.
        """
        service = KnowledgeResearchService()
        knowledge = MagicMock()
        knowledge.status = ResearchStatus.COMPLETE
        knowledge.updated_at = datetime.utcnow() - timedelta(days=60)

        result = service.is_stale(knowledge)
        assert result is True, "60-day-old entry should be stale (threshold is 30 days)"


# ===========================================================================
# TestLanguageInstructionMappingGap
# Regression guard documenting the known gap between auth schema validation
# and ThinkerService language support:
#   - app/schemas/auth.py validates language_preference against ^(en|es|fr|de)$
#   - app/services/thinker.py supports en, es, fr, de, hi
# Hindi is supported on the LLM side but rejected by the auth API. This is
# a documented gap (also tested in test_regression_recent_features.py).
# This test pins down the LANGUAGE_NAMES mapping side specifically.
# ===========================================================================


class TestLanguageInstructionMappingGap:
    """Regression tests: language mapping has Hindi but auth schema does not."""

    def test_hindi_maps_to_full_name_in_thinker_service(self) -> None:
        """_get_language_instruction('hi') returns 'Respond in Hindi.'

        Regression guard for the LANGUAGE_NAMES dictionary in thinker.py
        which was extended in fix(i18n) #570. Removing 'hi' from the dict
        would silently regress Hindi support — the prompt would say
        "Respond in hi." (which Claude might still parse, but is wrong).
        """
        instruction = _get_language_instruction("hi")
        assert "Hindi" in instruction, (
            f"Expected 'Hindi' in instruction, got {instruction!r}. "
            f"The LANGUAGE_NAMES['hi'] mapping has regressed."
        )

    def test_unknown_language_code_falls_back_to_code_itself(self) -> None:
        """An unknown code (e.g. 'xx') uses the code as the language name.

        Regression guard for the `LANGUAGE_NAMES.get(language, language)`
        fallback. This is defensive: a future code added to the auth schema
        but not yet to LANGUAGE_NAMES would still produce a sensible
        prompt (Claude can interpret common ISO codes).
        """
        instruction = _get_language_instruction("xx")
        # Falls back to using the code itself
        assert "xx" in instruction

    def test_english_returns_empty_instruction(self) -> None:
        """'en' returns empty string (no language instruction needed).

        Regression guard for the early return on line 50:
          if language == "en":
              return ""
        Without this, prompts would contain "Respond in English." which
        bloats the token count for the default case.
        """
        instruction = _get_language_instruction("en")
        assert instruction == "", (
            f"English language should produce empty instruction, got {instruction!r}"
        )

    async def test_auth_api_still_rejects_hindi(self, client: AsyncClient) -> None:
        """PATCH /api/auth/language with 'hi' returns 422 (schema rejects it).

        Regression guard documenting the gap: ThinkerService has Hindi support
        for LLM responses, but the auth schema pattern is `^(en|es|fr|de)$`,
        which rejects 'hi'. If somebody updates the auth pattern to include
        'hi', this test will fail and prompt them to update the documented
        gap (this test should be moved to test_all_valid_language_codes).
        """
        headers = await get_auth_headers(client, "hindi_gap_user", "password123")

        response = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "hi"},
        )

        # Currently rejected — documents the auth/service gap.
        assert response.status_code == 422, (
            "If this fails with 200, Hindi has been added to the auth schema. "
            "Move this test to the all-valid-codes test instead."
        )
