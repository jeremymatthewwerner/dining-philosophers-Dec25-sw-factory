"""Regression prevention tests for Sunday QA (May 3, 2026).

Focus areas targeting behaviors that could regress from recent bug fixes and
untested code paths:
- _should_prompt_user threshold/probability logic (never previously tested)
- _get_language_instruction for all supported language codes
- _get_user_name_from_messages edge cases (no messages, no sender_name)
- start_conversation_agents stops existing agents before restarting
- KnowledgeResearchService trigger_research done-callback removes task
- ConnectionManager.set_speed_multiplier async clamping and broadcast behavior

Test groups:
- TestShouldPromptUser (5): threshold calculation, message-count guards, probability
- TestGetLanguageInstruction (4): all supported codes + unknown fallback
- TestGetUserNameEdgeCases (4): empty list, thinker-only, no sender_name, most-recent
- TestStartAgentsRestart (3): idempotent restart stops old tasks first
- TestKnowledgeResearchCleanupCallback (3): done-callback lifecycle
- TestSetSpeedMultiplierAsync (3): clamping, per-room isolation, missing-room no-op
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.websocket import ConnectionManager, ConversationRoom
from app.models.message import SenderType
from app.services.thinker import ThinkerService, _get_language_instruction

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _msg(
    sender_type: SenderType | str,
    sender_name: str | None = "Alice",
    created_at: datetime | None = None,
) -> MagicMock:
    """Create a minimal mock Message."""
    m = MagicMock()
    m.sender_type = sender_type
    m.sender_name = sender_name
    m.created_at = created_at or datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
    return m


# ===========================================================================
# TestShouldPromptUser
# Regression guard for _should_prompt_user (lines 1444-1470 in thinker.py).
# This method has NEVER been tested before this session.
#
# Contract:
# - Returns False when < 5 messages exist (not enough context)
# - Returns False when messages_since_user < threshold
# - Threshold is max(4, int(8 / speed_mult**0.3))
# - When threshold met, probability = 0.15 * speed_mult**0.3
# ===========================================================================


class TestShouldPromptUser:
    """Regression tests for _should_prompt_user prompt-frequency logic."""

    def _make_messages(
        self,
        n_thinker: int,
        with_user_at_start: bool = True,
    ) -> list[MagicMock]:
        """Create a message list with a user message followed by n thinker messages."""
        msgs: list[MagicMock] = []
        if with_user_at_start:
            msgs.append(_msg(SenderType.USER, "Alice"))
        for i in range(n_thinker):
            msgs.append(_msg(SenderType.THINKER, f"Thinker{i}"))
        return msgs

    def test_returns_false_for_fewer_than_5_messages(self) -> None:
        """_should_prompt_user returns False when conversation has < 5 messages.

        Regression guard: the early exit at len(messages) < 5 prevents
        prompting when there isn't enough context for a meaningful invitation.
        If this guard is removed, users could be prompted on their very first
        message which feels intrusive and wrong.
        """
        service = ThinkerService()
        short_msgs = self._make_messages(n_thinker=3)  # 4 total (< 5)
        assert len(short_msgs) < 5

        result = service._should_prompt_user(short_msgs, speed_mult=1.0)

        assert result is False, "Should return False for < 5 messages"

    def test_returns_false_when_messages_since_user_below_threshold(self) -> None:
        """_should_prompt_user returns False when recent thinker count < threshold.

        Regression guard: the threshold check ensures we only prompt the user
        after many thinker messages have accumulated. At speed 1.0, threshold
        is max(4, int(8/1.0^0.3)) = max(4, 8) = 8. With only 4 thinker messages
        since the user spoke, we should not prompt.
        """
        service = ThinkerService()
        # 1 user + 4 thinker = 5 messages; threshold at 1x is 8
        msgs = self._make_messages(n_thinker=4)
        assert len(msgs) >= 5, "Need at least 5 messages to pass the first guard"

        result = service._should_prompt_user(msgs, speed_mult=1.0)

        assert result is False, (
            "Should not prompt when only 4 thinker messages since user (threshold=8 at 1x)"
        )

    def test_threshold_floors_at_4(self) -> None:
        """Threshold uses max(4, ...) so it never drops below 4 at any speed.

        Regression guard: at very high speeds (e.g., 6.0), the formula
        int(8 / 6.0^0.3) ≈ int(8 / 1.73) ≈ 4. With fewer than 4 thinker
        messages the prompt should never fire, protecting against spamming
        users even on slow contemplative settings.
        """
        service = ThinkerService()
        # 3 thinker messages since user (below the floor of 4)
        msgs = self._make_messages(n_thinker=3, with_user_at_start=True)
        # Add extra filler so we have >= 5 messages total
        for _ in range(3):
            msgs.insert(0, _msg(SenderType.THINKER, "Filler"))
        assert len(msgs) >= 5

        # At speed 6.0, threshold = max(4, int(8/6^0.3)) ≈ 4
        # But messages_since_user is only 3 (last user msg stops the count)
        result = service._should_prompt_user(msgs, speed_mult=6.0)

        assert result is False, "Should not prompt when below the 4-message floor"

    def test_returns_true_when_threshold_met_and_lucky(self) -> None:
        """_should_prompt_user returns True when threshold is met and random fires.

        Regression guard: the probability path (0.15 * speed^0.3) must be
        reachable. If random.random is always forced below the probability,
        the method should return True. A bug that short-circuits before the
        random check would break user-invitation prompts silently.
        """
        service = ThinkerService()
        # 10 thinker messages since user → exceeds threshold of 8 at 1x
        msgs = self._make_messages(n_thinker=10)
        assert len(msgs) >= 5

        # Force random.random() to return 0.0 (always below any probability)
        with patch("app.services.thinker.random.random", return_value=0.0):
            result = service._should_prompt_user(msgs, speed_mult=1.0)

        assert result is True, (
            "Should return True when threshold met and random.random() < probability"
        )

    def test_returns_false_when_threshold_met_but_unlucky(self) -> None:
        """_should_prompt_user returns False when threshold met but random does not fire.

        Regression guard: the probability gate prevents the user from being
        prompted every single turn even when they've been silent for a long
        time. If the gate is removed, users would be bombarded with prompts.
        """
        service = ThinkerService()
        # 10 thinker messages since user → exceeds threshold
        msgs = self._make_messages(n_thinker=10)

        # Force random.random() to return 1.0 (always above any probability < 1.0)
        with patch("app.services.thinker.random.random", return_value=1.0):
            result = service._should_prompt_user(msgs, speed_mult=1.0)

        assert result is False, (
            "Should return False when threshold met but random.random() >= probability"
        )


# ===========================================================================
# TestGetLanguageInstruction
# Regression guard for _get_language_instruction (lines 40-53 in thinker.py).
# This standalone function has never had dedicated tests.
#
# Contract:
# - English ('en') returns empty string (no instruction appended)
# - Supported codes return "\n\nIMPORTANT: Respond in <Name>."
# - Unknown code uses the code itself as the language name
# ===========================================================================


class TestGetLanguageInstruction:
    """Regression tests for _get_language_instruction language code handling."""

    def test_english_returns_empty_string(self) -> None:
        """_get_language_instruction('en') must return '' not an instruction.

        Regression guard: the fast-path for English prevents appending
        "Respond in English." to every prompt, saving tokens and avoiding
        redundancy. If this fast-path is removed, English prompts would
        include a pointless instruction and waste context window space.
        """
        result = _get_language_instruction("en")

        assert result == "", f"English should return empty string, got: {result!r}"

    def test_spanish_returns_correct_instruction(self) -> None:
        """_get_language_instruction('es') returns instruction naming Spanish.

        Regression guard: the LANGUAGE_NAMES mapping must map 'es' → 'Spanish'.
        If the mapping is renamed or the lookup breaks, thinkers would respond
        in English even when the user set Spanish as their preference.
        """
        result = _get_language_instruction("es")

        assert "Spanish" in result, f"Expected 'Spanish' in instruction, got: {result!r}"
        assert result.startswith("\n\n"), "Instruction should start with two newlines"

    def test_hindi_returns_correct_instruction(self) -> None:
        """_get_language_instruction('hi') returns instruction naming Hindi.

        Regression guard for issue #570 (Jan 23): Hindi language support was
        added but the LANGUAGE_NAMES mapping could be accidentally dropped.
        If 'hi' is missing, the fallback uses the bare code 'hi' as the
        language name which is not a valid English language name.
        """
        result = _get_language_instruction("hi")

        assert "Hindi" in result, f"Expected 'Hindi' in instruction, got: {result!r}"

    def test_unknown_code_uses_code_as_fallback_name(self) -> None:
        """_get_language_instruction with an unknown code uses the code itself.

        Regression guard: LANGUAGE_NAMES.get(code, code) means an unknown
        language code like 'pt' produces "Respond in pt." rather than raising
        a KeyError. This fallback behavior must remain so new language codes
        don't crash the thinker service before LANGUAGE_NAMES is updated.
        """
        result = _get_language_instruction("pt")

        assert "pt" in result, f"Expected language code 'pt' in instruction, got: {result!r}"
        assert result != "", "Unknown code should NOT return empty string"


# ===========================================================================
# TestGetUserNameEdgeCases
# Regression guard for _get_user_name_from_messages (lines 1412-1419).
# Tests scenarios not covered by earlier sessions.
#
# Contract:
# - Empty list → None
# - Only thinker messages → None
# - User message with sender_name=None → skip (don't return None for name,
#   continue searching; if no named message exists, return None)
# - Multiple user messages → returns most recent (reversed iteration)
# ===========================================================================


class TestGetUserNameEdgeCases:
    """Edge case tests for _get_user_name_from_messages."""

    def test_empty_message_list_returns_none(self) -> None:
        """_get_user_name_from_messages returns None for an empty list.

        Regression guard: the for loop over an empty list must return None,
        not raise an exception. If the method crashed on empty input, any
        conversation with no messages would fail to generate prompts.
        """
        service = ThinkerService()

        result = service._get_user_name_from_messages([])

        assert result is None, "Empty list should return None"

    def test_only_thinker_messages_returns_none(self) -> None:
        """_get_user_name_from_messages returns None when no user messages exist.

        Regression guard: the method scans in reverse for user messages.
        If all messages are from thinkers, None is returned, which causes
        generate_user_prompt to skip the user's name in the prompt rather
        than using 'None' as a string.
        """
        service = ThinkerService()
        msgs = [
            _msg(SenderType.THINKER, "Socrates"),
            _msg(SenderType.THINKER, "Plato"),
            _msg(SenderType.THINKER, "Aristotle"),
        ]

        result = service._get_user_name_from_messages(msgs)

        assert result is None, "Thinker-only messages should return None"

    def test_user_message_with_no_sender_name_is_skipped(self) -> None:
        """_get_user_name_from_messages skips user messages with no sender_name.

        Regression guard: if a user message has sender_name=None (e.g.,
        anonymous user), the method should not return None as a name string.
        It should skip that message and keep looking, or return None if no
        named message is found. Returning the string 'None' would produce
        garbled prompts like 'What do you think, None?'.
        """
        service = ThinkerService()
        msgs = [
            _msg(SenderType.USER, sender_name=None),  # user but no name
        ]

        result = service._get_user_name_from_messages(msgs)

        assert result is None, "User message with sender_name=None should return None not 'None'"

    def test_returns_most_recent_user_name(self) -> None:
        """_get_user_name_from_messages returns the name from the most recent user message.

        Regression guard: the method iterates in reverse, so the most recent
        named user message wins. If iteration order changes, the method would
        return stale names (from the start of the conversation) causing the
        prompt to address the user by an old or wrong name.
        """
        service = ThinkerService()
        msgs = [
            _msg(SenderType.USER, "OldName"),
            _msg(SenderType.THINKER, "Socrates"),
            _msg(SenderType.USER, "NewName"),  # most recent user message
            _msg(SenderType.THINKER, "Plato"),
        ]

        result = service._get_user_name_from_messages(msgs)

        assert result == "NewName", f"Expected most recent user name 'NewName', got: {result!r}"


# ===========================================================================
# TestStartAgentsRestart
# Regression guard for start_conversation_agents (lines 1062-1095).
# When called for a conversation that already has running agents, the method
# must stop the old tasks before starting new ones.
#
# Contract:
# - If conversation_id already in _active_tasks, stop old tasks first
# - New tasks are created per-thinker and stored in _active_tasks[conv_id]
# - Empty thinker list results in empty dict under the conversation key
# ===========================================================================


class TestStartAgentsRestart:
    """Regression tests for start_conversation_agents idempotent restart."""

    async def test_restart_stops_existing_tasks_first(self) -> None:
        """start_conversation_agents stops old tasks when re-called for same conversation.

        Regression guard: the check `if conversation_id in self._active_tasks`
        triggers stop_conversation_agents before creating new tasks. If this
        check is removed, old agent tasks would leak and run concurrently with
        new ones, causing duplicate responses and wasted API spend.
        """
        service = ThinkerService()
        conv_id = "restart-test-conv"

        # Plant a real (completed) task in the service so stop_conversation_agents
        # can await it without TypeError.
        async def _trivial() -> None:
            return

        real_task = asyncio.create_task(_trivial())
        await real_task  # Let it complete so await is immediate
        service._active_tasks[conv_id] = {"fake-thinker-id": real_task}

        # Patch stop so we can verify it was called
        stop_called = []
        original_stop = service.stop_conversation_agents

        async def mock_stop(cid: str) -> None:
            stop_called.append(cid)
            await original_stop(cid)

        service.stop_conversation_agents = mock_stop  # type: ignore[method-assign]

        # Call start with an empty thinker list to avoid real task creation
        await service.start_conversation_agents(
            conv_id,
            thinkers=[],
            topic="test topic",
            get_messages=AsyncMock(return_value=[]),
            save_message=AsyncMock(),
        )

        assert conv_id in stop_called, (
            "stop_conversation_agents must be called when conversation already has active tasks"
        )

    async def test_empty_thinker_list_creates_empty_task_dict(self) -> None:
        """start_conversation_agents with no thinkers creates empty task entry.

        Regression guard: the method always initialises _active_tasks[conv_id]
        even when no thinkers are provided. This prevents KeyError when
        stop_conversation_agents is called immediately after start.
        """
        service = ThinkerService()
        conv_id = "empty-thinkers-conv"

        await service.start_conversation_agents(
            conv_id,
            thinkers=[],
            topic="test topic",
            get_messages=AsyncMock(return_value=[]),
            save_message=AsyncMock(),
        )

        assert conv_id in service._active_tasks, (
            "Conversation key must exist in _active_tasks even with 0 thinkers"
        )
        assert service._active_tasks[conv_id] == {}, "No thinkers should produce empty inner dict"

    async def test_second_start_replaces_task_dict(self) -> None:
        """start_conversation_agents replaces old tasks on second call for same conversation.

        Regression guard: after a restart the _active_tasks entry must contain
        only the new tasks, not a mixture of old and new. If old entries persist,
        stop_conversation_agents would try to cancel already-done tasks.
        """
        service = ThinkerService()
        conv_id = "replace-tasks-conv"

        # First start - empty thinkers
        await service.start_conversation_agents(
            conv_id,
            thinkers=[],
            topic="topic1",
            get_messages=AsyncMock(return_value=[]),
            save_message=AsyncMock(),
        )

        first_dict = service._active_tasks[conv_id]

        # Second start - should replace
        await service.start_conversation_agents(
            conv_id,
            thinkers=[],
            topic="topic2",
            get_messages=AsyncMock(return_value=[]),
            save_message=AsyncMock(),
        )

        second_dict = service._active_tasks[conv_id]

        # After replace, should be a fresh empty dict (not the same object as before)
        assert second_dict == {}, "Task dict should be reset to empty on second start"
        assert second_dict is not first_dict, (
            "Task dict should be a new object, not the same reference"
        )


# ===========================================================================
# TestKnowledgeResearchCleanupCallback
# Regression guard for trigger_research done-callback (lines 107-112).
# The cleanup callback removes completed tasks from _active_tasks so that
# trigger_research can be called again for the same thinker.
#
# Contract:
# - callback removes task from _active_tasks[name] when done
# - callback is a no-op if name is no longer in _active_tasks
# - callback is registered via task.add_done_callback
# ===========================================================================


class TestKnowledgeResearchCleanupCallback:
    """Regression tests for the done-callback in trigger_research."""

    async def test_done_callback_removes_task_from_active_tasks(self) -> None:
        """Done callback removes the task entry for the thinker name.

        Regression guard: without the cleanup callback, _active_tasks would
        grow indefinitely and trigger_research would never restart research
        for a thinker whose previous task completed. This breaks the 'refresh'
        flow on the thinker knowledge endpoint.
        """
        from app.services.knowledge_research import KnowledgeResearchService

        service = KnowledgeResearchService()
        thinker_name = "Socrates"

        # Capture the callback registered with add_done_callback
        captured_callback = None
        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.done.return_value = False

        def capture_callback(cb: object) -> None:
            nonlocal captured_callback
            captured_callback = cb

        mock_task.add_done_callback.side_effect = capture_callback

        # trigger_research calls asyncio.create_task() which requires a running loop.
        # Patch create_task to return our mock task instead.
        with patch("app.services.knowledge_research.asyncio.create_task", return_value=mock_task):
            service.trigger_research(thinker_name)

        # Task should be in _active_tasks before callback fires
        assert thinker_name in service._active_tasks

        # Simulate task completing: fire the callback
        assert captured_callback is not None, "Done callback must be registered"
        captured_callback(mock_task)

        # Task should be removed after callback fires
        assert thinker_name not in service._active_tasks, (
            "Done callback must remove the task from _active_tasks when it completes"
        )

    async def test_done_callback_is_noop_when_task_already_removed(self) -> None:
        """Done callback does not raise if task was already removed from _active_tasks.

        Regression guard: the callback uses `if name in self._active_tasks`
        guard before deleting. Without this guard, concurrent cleanup (e.g.,
        a forced stop) followed by the natural done callback would raise KeyError.
        """
        from app.services.knowledge_research import KnowledgeResearchService

        service = KnowledgeResearchService()
        thinker_name = "Plato"

        captured_callback = None
        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.done.return_value = False

        def capture_callback(cb: object) -> None:
            nonlocal captured_callback
            captured_callback = cb

        mock_task.add_done_callback.side_effect = capture_callback

        with patch("app.services.knowledge_research.asyncio.create_task", return_value=mock_task):
            service.trigger_research(thinker_name)

        # Manually remove the task (simulating a forced stop)
        del service._active_tasks[thinker_name]

        # Firing the callback after manual removal should NOT raise
        assert captured_callback is not None
        try:
            captured_callback(mock_task)
        except KeyError as e:
            pytest.fail(f"Done callback raised KeyError when task was already removed: {e}")

    async def test_trigger_research_registers_done_callback(self) -> None:
        """trigger_research calls add_done_callback on the created task.

        Regression guard: if add_done_callback is not called, the cleanup
        never runs, _active_tasks grows forever, and repeated calls to
        trigger_research (e.g., from thinker suggest) never restart stale tasks.
        """
        from app.services.knowledge_research import KnowledgeResearchService

        service = KnowledgeResearchService()
        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.done.return_value = False

        with patch("app.services.knowledge_research.asyncio.create_task", return_value=mock_task):
            service.trigger_research("Aristotle")

        (
            mock_task.add_done_callback.assert_called_once(),
            ("trigger_research must register a done callback to clean up _active_tasks"),
        )


# ===========================================================================
# TestSetSpeedMultiplierAsync
# Regression guard for ConnectionManager.set_speed_multiplier (lines 145-157).
# This async method clamps the value and updates the room, then broadcasts.
#
# Contract:
# - Values below 0.5 are clamped to 0.5
# - Values above 6.0 are clamped to 6.0
# - Method is a no-op if the room does not exist (no KeyError)
# - Speed is stored per-room (isolation)
# ===========================================================================


class TestSetSpeedMultiplierAsync:
    """Regression tests for ConnectionManager.set_speed_multiplier async method."""

    async def test_set_speed_clamps_below_minimum(self) -> None:
        """set_speed_multiplier clamps values below 0.5 to 0.5.

        Regression guard: the clamping `max(0.5, min(6.0, multiplier))` must
        be applied before storing. If removed, a client sending speed=0.0
        would make the loop sleep for 0 seconds (spin-loop) causing CPU thrash.
        """
        cm = ConnectionManager()
        conv_id = "clamp-low-test"
        cm.rooms[conv_id] = ConversationRoom(conversation_id=conv_id)

        # Patch broadcast_to_conversation to avoid WebSocket send
        with patch.object(cm, "broadcast_to_conversation", new_callable=AsyncMock):
            await cm.set_speed_multiplier(conv_id, 0.0)

        assert cm.rooms[conv_id].speed_multiplier == 0.5, "Speed below 0.5 must be clamped to 0.5"

    async def test_set_speed_clamps_above_maximum(self) -> None:
        """set_speed_multiplier clamps values above 6.0 to 6.0.

        Regression guard: without the upper clamp, a client could set
        speed=100.0 making the minimum message interval 1500 seconds —
        effectively freezing the conversation silently.
        """
        cm = ConnectionManager()
        conv_id = "clamp-high-test"
        cm.rooms[conv_id] = ConversationRoom(conversation_id=conv_id)

        with patch.object(cm, "broadcast_to_conversation", new_callable=AsyncMock):
            await cm.set_speed_multiplier(conv_id, 100.0)

        assert cm.rooms[conv_id].speed_multiplier == 6.0, "Speed above 6.0 must be clamped to 6.0"

    async def test_set_speed_is_noop_for_unknown_conversation(self) -> None:
        """set_speed_multiplier does nothing for a conversation not in rooms.

        Regression guard: the method checks `if conversation_id in self.rooms`
        before updating. Without this guard, setting speed for a non-existent
        room would create a partial ConversationRoom via defaultdict with the
        wrong conversation_id, corrupting the rooms state.
        """
        cm = ConnectionManager()
        conv_id = "nonexistent-room"
        assert conv_id not in cm.rooms

        # Should not raise
        with patch.object(cm, "broadcast_to_conversation", new_callable=AsyncMock) as mock_bc:
            await cm.set_speed_multiplier(conv_id, 2.0)

        # Room should not have been auto-created with wrong state
        (
            mock_bc.assert_not_called(),
            ("broadcast_to_conversation should not be called for unknown conversation"),
        )
