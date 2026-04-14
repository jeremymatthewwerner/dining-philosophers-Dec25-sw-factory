"""Flaky test hunt and hardening tests for QA Agent Tuesday focus.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-04-14).
Issue: #832

This file addresses the following flakiness risks identified in the Apr 14 session:

1. Deterministic random seeds vs probabilistic loops in ThinkerService tests
   - test_thinker_service.py uses `random.seed(None)` + loop-based assertions.
   - While currently stable (passes 5/5), the probabilistic approach can fail
     if the random number generator produces an unlikely sequence.
   - These hardening tests add deterministic fixed-seed variants that always
     produce the same result, verifying known-good behavior.

2. Datetime boundary conditions in knowledge staleness checks
   - Tests that compare `datetime.now(UTC)` to fixed-day thresholds (30 days)
     can fail at exact boundary moments, especially under CI load.
   - These hardening tests verify the staleness logic is correct at safe
     distances from the boundary (2 days inside and outside 30-day window).

3. ConnectionManager room cleanup state between test runs
   - Tests that create ConnectionManager instances and add rooms without
     cleanup can leak state into subsequent tests sharing the singleton.
   - These hardening tests verify that cleanup methods work correctly
     and that fresh instances start with empty state.

4. asyncio.create_task cleanup in ThinkerService
   - Tests that create tasks via asyncio.create_task without properly
     cancelling them can leave dangling tasks that interfere with other tests.
   - These hardening tests verify the stop_conversation_agents cleanup path
     correctly handles edge cases (already-done tasks, multiple thinkers, etc.)
"""

import asyncio
import random
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.api.websocket import ConnectionManager
from app.models.thinker_knowledge import ResearchStatus, ThinkerKnowledge
from app.services.knowledge_research import KnowledgeResearchService
from app.services.thinker import ThinkerService


class TestDeterministicRandomSplitBehavior:
    """Hardening tests for _split_response_into_bubbles with fixed seeds.

    The existing tests in TestSplitResponseIntoBubbles use random.seed(None)
    which resets to a non-deterministic state. These tests use fixed seeds to
    verify known-good behavior without relying on probabilistic outcomes.
    """

    def test_seed_42_produces_consistent_output(self) -> None:
        """Test that a fixed seed always produces the same split result.

        Regression guard: If the random number generator or split logic changes,
        this test will fail deterministically rather than intermittently.
        """
        service = ThinkerService()
        text = (
            "This is the first sentence of a response that has multiple parts. "
            "Here is a second sentence adding more detail about the same topic. "
            "And a third sentence to pad out the length beyond 250 characters total."
        )
        random.seed(42)
        result_first = service._split_response_into_bubbles(text)

        # Same seed should produce identical output
        random.seed(42)
        result_second = service._split_response_into_bubbles(text)

        assert result_first == result_second, "Fixed random seed must produce deterministic output"
        # The output must be a non-empty list of non-empty strings
        assert len(result_first) >= 1
        for bubble in result_first:
            assert len(bubble.strip()) > 0

    def test_short_text_never_splits_regardless_of_seed(self) -> None:
        """Test text under 60 chars is never split, even with seeds that favor splits.

        Deterministic version of test_text_under_60_chars_never_splits.
        Tests seeds 0-9 explicitly rather than using random.seed(None) loop.
        """
        service = ThinkerService()
        text = "Brief philosophical thought."  # 28 chars, well under 60

        for seed in range(10):
            random.seed(seed)
            result = service._split_response_into_bubbles(text)
            assert len(result) == 1, (
                f"Short text should never split with seed={seed}, got {len(result)} bubbles"
            )
            assert result[0] == text

    def test_long_text_splits_with_known_seeds(self) -> None:
        """Test that long text splits with specific known-good seeds.

        Identifies seeds that reliably produce a split, providing deterministic
        coverage of the multi-bubble path without relying on random.seed(None).
        """
        service = ThinkerService()
        # This text is designed to reliably trigger splits
        text = (
            "Socrates was an ancient Greek philosopher known for the Socratic method. "
            "However, he left no written works and is known only through the writings "
            "of his students. Furthermore, he was executed in 399 BC for impiety. "
            "These facts combine to make him one of the most enigmatic philosophers."
        )
        # Find seeds that produce splits (for documentation purposes)
        splitting_seeds = []
        for seed in range(20):
            random.seed(seed)
            result = service._split_response_into_bubbles(text)
            if len(result) >= 2:
                splitting_seeds.append(seed)

        # At least some seeds should produce splits for sufficiently long text
        assert len(splitting_seeds) >= 1, (
            "Long text should split with at least one seed in range 0-19"
        )

        # Verify splits produce well-formed bubbles (deterministic check)
        first_splitting_seed = splitting_seeds[0]
        random.seed(first_splitting_seed)
        result = service._split_response_into_bubbles(text)
        for bubble in result:
            assert len(bubble.strip()) > 0, "Split bubbles must be non-empty"

    def test_very_long_text_always_splits_with_any_seed(self) -> None:
        """Test that extremely long text (>500 chars) always splits.

        Stronger guarantee than the existing test: verify all 20 tested seeds
        produce multi-bubble output, not just 'at least 1 bubble'.
        """
        service = ThinkerService()
        # 600+ character text - well above the force-split threshold
        text = "Philosophy is the study of general and fundamental questions. " * 10

        for seed in range(20):
            random.seed(seed)
            result = service._split_response_into_bubbles(text)
            assert len(result) >= 2, (
                f"Very long text (600+ chars) must always split, but got 1 bubble with seed={seed}"
            )


class TestKnowledgeStalenessDatetimeBoundaries:
    """Hardening tests for datetime-based staleness checks.

    The staleness check compares datetime.now(UTC) to knowledge.updated_at.
    Tests using exact boundary values (30 days exactly) can fail under CI load
    due to clock skew. These tests use safe margins (1 day inside/outside).
    """

    def test_fresh_knowledge_is_not_stale_with_margin(self) -> None:
        """Test that knowledge updated 1 day ago is not stale.

        Safe version of the boundary test: 1 day is far enough from the
        30-day threshold that CI clock drift can't affect the outcome.
        """
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.COMPLETE,
            research_data={"data": "fresh"},
            updated_at=datetime.now(UTC) - timedelta(days=1),
        )
        assert service.is_stale(knowledge) is False, (
            "Knowledge updated 1 day ago (well within 30-day window) must not be stale"
        )

    def test_stale_knowledge_is_stale_with_margin(self) -> None:
        """Test that knowledge updated 31 days ago is stale.

        Safe version of the boundary test: 31 days is far enough from the
        30-day threshold that CI clock drift can't affect the outcome.
        """
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.COMPLETE,
            research_data={"data": "stale"},
            updated_at=datetime.now(UTC) - timedelta(days=31),
        )
        assert service.is_stale(knowledge) is True, (
            "Knowledge updated 31 days ago (outside 30-day window) must be stale"
        )

    def test_future_timestamp_is_not_stale(self) -> None:
        """Test that a future-dated knowledge entry is not considered stale.

        Edge case: if a knowledge entry somehow gets a future timestamp
        (e.g., clock drift, daylight saving time edge), it should not be
        considered stale since it's newer than now.
        """
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.COMPLETE,
            research_data={"data": "future"},
            updated_at=datetime.now(UTC) + timedelta(hours=1),
        )
        # Future-dated knowledge is "fresh" (not stale)
        assert service.is_stale(knowledge) is False, (
            "Knowledge with a future timestamp should not be stale"
        )

    def test_very_old_knowledge_is_stale(self) -> None:
        """Test that very old knowledge (1 year) is definitely stale.

        Ensures staleness works correctly for extreme age values,
        not just near the 30-day boundary.
        """
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.COMPLETE,
            research_data={"data": "ancient"},
            updated_at=datetime.now(UTC) - timedelta(days=365),
        )
        assert service.is_stale(knowledge) is True, "Year-old knowledge must be stale"

    def test_non_complete_status_always_stale_regardless_of_age(self) -> None:
        """Test that non-COMPLETE status is always stale regardless of timestamp.

        Prevents regression where a FAILED or IN_PROGRESS entry with a very
        recent timestamp might be incorrectly treated as fresh.
        """
        service = KnowledgeResearchService()
        for status in [ResearchStatus.FAILED, ResearchStatus.IN_PROGRESS, ResearchStatus.PENDING]:
            knowledge = ThinkerKnowledge(
                name="Test",
                status=status,
                research_data={},
                updated_at=datetime.now(UTC),  # Very fresh, but wrong status
            )
            assert service.is_stale(knowledge) is True, (
                f"Status {status} must always be stale regardless of age"
            )


class TestConnectionManagerFreshInstanceIsolation:
    """Hardening tests for ConnectionManager instance state.

    Each test creates a fresh ConnectionManager instance to verify that
    newly created instances start with clean state. This prevents test
    interference when tests share the global manager singleton.
    """

    def test_fresh_instance_has_no_rooms(self) -> None:
        """Test that a fresh ConnectionManager has no rooms.

        Prevents flakiness: if tests reuse the global manager singleton and
        add rooms without cleanup, subsequent tests see stale room state.
        Fresh instances must always start empty.
        """
        manager = ConnectionManager()
        assert len(manager.rooms) == 0

    def test_fresh_instance_conversation_not_active(self) -> None:
        """Test that any conversation is inactive in a fresh instance.

        Verifies that is_conversation_active returns False for any ID
        in a fresh instance, even IDs that might exist in the global singleton.
        """
        manager = ConnectionManager()
        assert manager.is_conversation_active("any-conversation-id") is False
        assert manager.is_conversation_active("test-conv-1") is False
        assert manager.is_conversation_active("") is False

    async def test_disconnect_from_empty_room_is_safe(self) -> None:
        """Test that disconnecting from a non-existent room doesn't raise.

        Guards against KeyError when disconnect is called for a conversation_id
        that was never connected (e.g., after a test cleanup race condition).
        """
        manager = ConnectionManager()
        mock_ws = MagicMock()

        # Should not raise even if conversation_id was never added
        await manager.disconnect(mock_ws, "nonexistent-conv")

    async def test_broadcast_to_empty_room_is_safe(self) -> None:
        """Test that broadcasting to a room with no connections is safe.

        Guards against errors when broadcast_to_conversation is called for a
        conversation_id that has no active WebSocket connections.
        """
        from app.api.websocket import WSMessage, WSMessageType

        manager = ConnectionManager()
        msg = WSMessage(type=WSMessageType.THINKER_TYPING)
        # Should not raise for a non-existent room
        await manager.broadcast_to_conversation("nonexistent-conv", msg)

    def test_speed_multiplier_defaults_to_one_for_new_room(self) -> None:
        """Test that speed multiplier is 1.0 for a conversation with no connections.

        Prevents regression where get_speed_multiplier returns wrong default
        for conversations that have rooms but zero active connections.
        """
        manager = ConnectionManager()
        # Should return 1.0 for non-existent conversations
        assert manager.get_speed_multiplier("no-such-conv") == 1.0


class TestAsyncTaskCleanupHardening:
    """Hardening tests for asyncio task cleanup in ThinkerService.

    Tests that asyncio.create_task cleanup works correctly in edge cases
    that could lead to dangling tasks or resource leaks between tests.
    """

    async def test_stop_agents_for_conversation_with_done_task(self) -> None:
        """Test that stopping agents handles already-completed tasks.

        Edge case: if a task completes naturally before stop is called,
        stop_conversation_agents must handle it without error.
        Task.cancel() on a done task is a no-op, but the code should
        still clean up the reference from _active_tasks.
        """
        service = ThinkerService()
        conversation_id = "done-task-test-conv"

        async def quick_task() -> None:
            pass  # Completes immediately

        task = asyncio.create_task(quick_task())
        # Give the task time to complete
        await asyncio.sleep(0)

        assert task.done()

        service._active_tasks[conversation_id] = {"thinker-1": task}
        # stop_conversation_agents should handle the already-done task
        await service.stop_conversation_agents(conversation_id)

        assert conversation_id not in service._active_tasks

    async def test_stop_agents_cleans_up_multiple_thinkers(self) -> None:
        """Test that stopping agents cancels all thinkers in a conversation.

        Guards against partial cleanup: if stop_conversation_agents only
        cancels the first thinker, remaining tasks could leak into other tests.

        Note: tasks that handle CancelledError internally complete with result=None
        rather than being "cancelled" (raising CancelledError all the way up).
        The key invariant is that all tasks are *done* after stop, not running.
        """
        service = ThinkerService()
        conversation_id = "multi-thinker-cleanup-conv"

        import contextlib

        async def long_running() -> None:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.sleep(100)

        task1 = asyncio.create_task(long_running())
        task2 = asyncio.create_task(long_running())
        task3 = asyncio.create_task(long_running())

        service._active_tasks[conversation_id] = {
            "thinker-1": task1,
            "thinker-2": task2,
            "thinker-3": task3,
        }

        await service.stop_conversation_agents(conversation_id)

        # All tasks must be done (no longer running) — they may complete normally
        # or be cancelled depending on whether the coroutine re-raises CancelledError.
        # The invariant that matters: no dangling running tasks after stop.
        assert task1.done(), "task1 must be done after stop"
        assert task2.done(), "task2 must be done after stop"
        assert task3.done(), "task3 must be done after stop"
        # Reference should be removed from active tasks dict
        assert conversation_id not in service._active_tasks

    async def test_stop_agents_only_affects_target_conversation(self) -> None:
        """Test that stopping one conversation does not affect another.

        Guards against over-eager cleanup where stopping conv-A accidentally
        cancels active tasks for conv-B (e.g., by clearing the entire task dict).
        """
        service = ThinkerService()
        conv_a = "isolation-task-conv-a"
        conv_b = "isolation-task-conv-b"

        async def long_task() -> None:
            await asyncio.sleep(100)

        task_a = asyncio.create_task(long_task())
        task_b = asyncio.create_task(long_task())

        service._active_tasks[conv_a] = {"thinker-1": task_a}
        service._active_tasks[conv_b] = {"thinker-1": task_b}

        await service.stop_conversation_agents(conv_a)

        # conv_a should be cleaned up and task_a done
        assert conv_a not in service._active_tasks
        assert task_a.done(), "task_a must be done after stop"

        # conv_b should be untouched and task_b still running
        assert conv_b in service._active_tasks
        assert not task_b.done(), "task_b must still be running"

        # Cleanup conv_b to avoid leaking tasks
        await service.stop_conversation_agents(conv_b)

    async def test_new_thinker_service_has_no_active_tasks(self) -> None:
        """Test that a new ThinkerService instance has no pre-existing tasks.

        Guards against class-level (static) task dict that might persist
        state across different ThinkerService instances in the same test process.
        """
        service = ThinkerService()
        assert len(service._active_tasks) == 0, "Fresh ThinkerService must have no active tasks"

    @pytest.mark.asyncio
    async def test_pause_resume_state_does_not_affect_task_cleanup(self) -> None:
        """Test that pause/resume state and task state are independent.

        Guards against a regression where pausing a conversation could
        prevent tasks from being cleaned up (e.g., if stop checks pause state).
        """
        service = ThinkerService()
        conversation_id = "pause-task-isolation-conv"

        async def long_task() -> None:
            await asyncio.sleep(100)

        task = asyncio.create_task(long_task())
        service._active_tasks[conversation_id] = {"thinker-1": task}

        # Pause the conversation
        service.pause_conversation(conversation_id)
        assert service.is_paused(conversation_id) is True

        # Stopping should still work even when conversation is paused
        await service.stop_conversation_agents(conversation_id)

        assert conversation_id not in service._active_tasks
        assert task.cancelled()
        # Pause state is independent - still paused after task cleanup
        assert service.is_paused(conversation_id) is True
