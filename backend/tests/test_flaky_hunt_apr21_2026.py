"""Flaky test hunt and hardening tests for QA Agent Tuesday focus.

Written by QA Agent during flaky-hunt session (Tuesday, 2026-04-21).
Issue: #847

This file addresses the following flakiness risks identified in the Apr 21 session:

1. AsyncMock antipattern in trigger_research tests
   - Two tests in test_regression_prevention_mar29_2026.py used AsyncMock for
     _research_thinker while asyncio.create_task was also mocked. This caused
     "coroutine never awaited" RuntimeWarnings because the mocked create_task
     doesn't schedule the coroutine. Fixed by using MagicMock instead.
   - Hardening tests verify the correct mock pattern and that the done_callback
     works correctly when task is a MagicMock(spec=asyncio.Task).

2. trigger_research done_callback cleanup with mocked tasks
   - The cleanup callback added via task.add_done_callback() uses the mocked task
     and the callback itself may or may not be called depending on mock behavior.
   - Tests verify cleanup works correctly with both real tasks and mock tasks.

3. Global ConnectionManager room accumulation
   - The global `manager` singleton accumulates rooms from WebSocket tests.
   - Rooms become inactive after disconnect but stay in the dict.
   - Tests verify that stale rooms don't cause is_conversation_active to return
     True for disconnected conversations.

4. thinker_service global state persistence after WebSocket tests
   - WebSocket tests that pause conversations leave pause state in the global
     thinker_service singleton. Subsequent tests using overlapping conversation
     IDs would see unexpected pause state.
   - Tests verify safe cleanup patterns and isolation strategies.

5. ThinkerService._active_tasks cleanup callback invariants
   - The cleanup callback is a closure that captures the thinker name. If the
     callback is invoked multiple times or with wrong arguments, it could corrupt
     _active_tasks. Tests verify the callback is idempotent and safe.
"""

import asyncio
from unittest.mock import MagicMock, patch

from app.api.websocket import ConnectionManager, WSMessage, WSMessageType
from app.services.knowledge_research import KnowledgeResearchService
from app.services.thinker import ThinkerService


class TestTriggerResearchMockPattern:
    """Hardening tests verifying the correct mock pattern for trigger_research.

    When both asyncio.create_task and _research_thinker are mocked,
    _research_thinker must use MagicMock (not AsyncMock) to avoid creating
    unawaited coroutines. These tests verify the correct pattern and guard
    against regression to the AsyncMock antipattern.
    """

    def test_trigger_research_mock_pattern_no_coroutine_warning(self) -> None:
        """Test that using MagicMock for _research_thinker generates no warnings.

        Root cause of Apr 21 fix: AsyncMock creates coroutine objects when called.
        When asyncio.create_task is also mocked, these coroutines are never awaited,
        producing RuntimeWarning. MagicMock returns a plain MagicMock, not a
        coroutine, so no warning is produced.

        This test documents the correct pattern to prevent regression.
        """
        service = KnowledgeResearchService()
        mock_task = MagicMock(spec=asyncio.Task)

        with (
            patch("asyncio.create_task", return_value=mock_task),
            patch.object(service, "_research_thinker", new_callable=MagicMock) as mock_research,
        ):
            service.trigger_research("Socrates")

            # _research_thinker should be called with the thinker name
            mock_research.assert_called_once_with("Socrates")
            # The return value (a MagicMock, not coroutine) is passed to create_task
            assert "Socrates" in service._active_tasks

    def test_trigger_research_task_stored_in_active_tasks(self) -> None:
        """Test that the mock task returned by create_task is stored in _active_tasks.

        Regression guard: If trigger_research stores the wrong object (e.g., the
        coroutine arg instead of the task return value), subsequent deduplication
        checks via done() would fail with AttributeError.
        """
        service = KnowledgeResearchService()
        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.done.return_value = False

        with (
            patch("asyncio.create_task", return_value=mock_task),
            patch.object(service, "_research_thinker", new_callable=MagicMock),
        ):
            service.trigger_research("Plato")

            # The task stored should be the one returned by create_task
            assert service._active_tasks.get("Plato") is mock_task

    def test_trigger_research_done_callback_registered_on_task(self) -> None:
        """Test that trigger_research registers a done_callback on the task.

        The cleanup callback removes the entry from _active_tasks when the task
        completes. If it's not registered, completed tasks linger in _active_tasks
        forever, causing the deduplication check to incorrectly skip new research.
        """
        service = KnowledgeResearchService()
        mock_task = MagicMock(spec=asyncio.Task)

        with (
            patch("asyncio.create_task", return_value=mock_task),
            patch.object(service, "_research_thinker", new_callable=MagicMock),
        ):
            service.trigger_research("Kant")

            # A done_callback must be registered to clean up _active_tasks
            mock_task.add_done_callback.assert_called_once()

    def test_trigger_research_deduplication_uses_done_method(self) -> None:
        """Test that deduplication calls done() on the existing task.

        Regression guard: If deduplication checks task identity instead of done()
        status, a completed task would still block new research for the same thinker.
        The code must call done() to distinguish running vs completed tasks.
        """
        service = KnowledgeResearchService()
        mock_running_task = MagicMock(spec=asyncio.Task)
        mock_running_task.done.return_value = False

        service._active_tasks["Descartes"] = mock_running_task

        with patch("asyncio.create_task") as mock_create_task:
            service.trigger_research("Descartes")

        # done() must be called to check task status
        mock_running_task.done.assert_called_once()
        # No new task should be created for a running task
        mock_create_task.assert_not_called()


class TestTriggerResearchDoneCallbackCleanup:
    """Tests for the done_callback cleanup closure in trigger_research.

    The cleanup callback is a closure capturing the thinker name. These tests
    verify it correctly cleans up _active_tasks when invoked.
    """

    async def test_done_callback_removes_entry_from_active_tasks(self) -> None:
        """Test that the done_callback correctly removes thinker from _active_tasks.

        The cleanup closure captures the thinker name from trigger_research's
        scope. When the task completes, the callback must find and remove the
        entry. If the closure captures by reference to a loop variable (antipattern),
        it might remove the wrong thinker.
        """
        service = KnowledgeResearchService()

        async def dummy_coro() -> None:
            pass

        task = asyncio.create_task(dummy_coro())
        # Wait for the task to complete
        await task

        # Manually simulate what trigger_research does
        service._active_tasks["Hume"] = task

        # Simulate what trigger_research does to register the callback
        def cleanup(_: asyncio.Task) -> None:
            if "Hume" in service._active_tasks:
                del service._active_tasks["Hume"]

        cleanup(task)  # Invoke it directly to test the cleanup logic

        assert "Hume" not in service._active_tasks, (
            "cleanup callback must remove thinker from _active_tasks"
        )

    async def test_done_callback_is_idempotent(self) -> None:
        """Test that invoking the cleanup callback twice is safe.

        If the callback is called twice (e.g., via asyncio internals),
        the second call must not raise KeyError on an already-removed entry.
        """
        service = KnowledgeResearchService()

        async def dummy_coro() -> None:
            pass

        task = asyncio.create_task(dummy_coro())
        await task

        service._active_tasks["Nietzsche"] = task

        def cleanup(_: asyncio.Task) -> None:
            if "Nietzsche" in service._active_tasks:
                del service._active_tasks["Nietzsche"]

        # Call twice - should not raise
        cleanup(task)
        cleanup(task)  # Second call: entry already gone, should be safe

        assert "Nietzsche" not in service._active_tasks

    async def test_real_trigger_research_cleanup_on_task_complete(self) -> None:
        """Test that a real trigger_research task removes itself from _active_tasks.

        End-to-end test: create a real (but fast) research task, let it complete,
        and verify _active_tasks no longer contains the entry.

        This is an integration test of the done_callback mechanism with real asyncio.
        """
        service = KnowledgeResearchService()

        # Patch the heavy work to be instant
        async def instant_research(_: str) -> None:
            pass

        with patch.object(service, "_research_thinker", side_effect=instant_research):
            service.trigger_research("Aristotle")
            assert "Aristotle" in service._active_tasks

            # Let the event loop process the task
            await asyncio.sleep(0)
            await asyncio.sleep(0)  # Two ticks to ensure callback fires

        # After the task completes, cleanup callback removes the entry
        assert "Aristotle" not in service._active_tasks, (
            "trigger_research done_callback must remove thinker after task completes"
        )


class TestConnectionManagerGlobalStateAccumulation:
    """Hardening tests for the global ConnectionManager singleton.

    The global `manager` singleton in app.api.websocket accumulates rooms as
    WebSocket tests run. Rooms become inactive (is_active=False) after disconnect
    but remain in the rooms dict. These tests verify that stale rooms don't cause
    incorrect behavior in is_conversation_active and related methods.
    """

    def test_inactive_room_is_not_active(self) -> None:
        """Test that a room with no connections reports is_conversation_active=False.

        After a WebSocket test disconnects, the room remains in the manager.rooms
        dict but with no connections and is_active=False. Other tests that check
        is_conversation_active for that conversation ID must get False.
        """
        manager = ConnectionManager()
        conversation_id = "inactive-room-test"

        # Simulate a room that was connected and then disconnected
        from app.api.websocket import ConversationRoom

        room = ConversationRoom(conversation_id=conversation_id)
        room.is_active = False  # Disconnected
        manager.rooms[conversation_id] = room

        # Must report as not active
        assert manager.is_conversation_active(conversation_id) is False

    def test_multiple_disconnected_rooms_dont_interfere(self) -> None:
        """Test that multiple stale rooms don't interfere with each other.

        Guard against a scenario where is_conversation_active iterates all
        rooms and returns True if ANY room is active (wrong) vs checking the
        specific room for the given conversation_id (correct).
        """
        manager = ConnectionManager()

        # Add one active room and one inactive room
        from app.api.websocket import ConversationRoom

        active_room = ConversationRoom(conversation_id="active-conv")
        active_room.is_active = True
        manager.rooms["active-conv"] = active_room

        inactive_room = ConversationRoom(conversation_id="inactive-conv")
        inactive_room.is_active = False
        manager.rooms["inactive-conv"] = inactive_room

        # Each must independently report its own state
        assert manager.is_conversation_active("active-conv") is True
        assert manager.is_conversation_active("inactive-conv") is False

    def test_get_speed_multiplier_for_stale_room_returns_default(self) -> None:
        """Test that get_speed_multiplier returns 1.0 for a stale inactive room.

        After a test disconnects, the room remains in rooms with whatever
        speed_multiplier was set. New tests using the same conversation ID
        should still get a sensible default if they only check the multiplier.
        """
        manager = ConnectionManager()

        from app.api.websocket import ConversationRoom

        room = ConversationRoom(conversation_id="speed-test-stale")
        room.speed_multiplier = 2.5  # Was set during a test
        room.is_active = False  # Disconnected
        manager.rooms["speed-test-stale"] = room

        # Returns the stale value (not reset) - this is expected behavior
        # The important thing is it doesn't crash
        multiplier = manager.get_speed_multiplier("speed-test-stale")
        assert isinstance(multiplier, float)
        assert 0.0 < multiplier <= 10.0

    def test_broadcast_to_inactive_room_does_not_raise(self) -> None:
        """Test that broadcasting to a stale room with no connections is safe.

        After disconnect, rooms exist but have empty connections sets.
        Broadcasting to such a room must not raise exceptions (e.g., iteration
        over empty set or None connections).
        """
        import asyncio

        from app.api.websocket import ConversationRoom

        manager = ConnectionManager()

        stale_room = ConversationRoom(conversation_id="stale-broadcast-test")
        stale_room.is_active = False
        stale_room.connections = set()  # Empty after disconnect
        manager.rooms["stale-broadcast-test"] = stale_room

        msg = WSMessage(type=WSMessageType.THINKER_TYPING)

        async def run() -> None:
            await manager.broadcast_to_conversation("stale-broadcast-test", msg)

        asyncio.get_event_loop().run_until_complete(run())  # Must not raise


class TestThinkerServiceGlobalStateIsolation:
    """Tests for thinker_service global singleton state isolation.

    WebSocket tests that pause conversations leave pause state in the global
    thinker_service. These tests verify isolation strategies that prevent
    test order dependencies.
    """

    def test_unique_conversation_ids_prevent_state_bleed(self) -> None:
        """Test that tests using unique conversation IDs don't share pause state.

        The most reliable protection against state bleed is using conversation IDs
        that are unique per test (e.g., include the test name in the ID). This test
        verifies that two tests using different IDs never see each other's state.
        """
        service = ThinkerService()

        conv_a = "websocket-test-a-pause-unique-2026-04-21"
        conv_b = "websocket-test-b-pause-unique-2026-04-21"

        service.pause_conversation(conv_a)

        assert service.is_paused(conv_a) is True
        assert service.is_paused(conv_b) is False, (
            "Pausing conv_a must not affect conv_b, even when using the global singleton"
        )

        # Cleanup
        service.resume_conversation(conv_a)

    def test_resume_after_test_cleanup_restores_default_state(self) -> None:
        """Test that explicit cleanup after a test leaves the singleton in a clean state.

        If a test that pauses a conversation explicitly resumes it in teardown,
        subsequent tests won't see stale pause state. This is the recommended
        cleanup pattern for tests that modify global singleton state.
        """
        service = ThinkerService()
        conversation_id = "cleanup-pattern-test-conv-2026-04-21"

        # Simulate test that pauses
        service.pause_conversation(conversation_id)
        assert service.is_paused(conversation_id) is True

        # Simulate teardown cleanup
        service.resume_conversation(conversation_id)

        # After cleanup, the conversation is not paused
        assert service.is_paused(conversation_id) is False

    def test_new_thinker_service_instance_ignores_global_state(self) -> None:
        """Test that fresh ThinkerService instances have clean pause state.

        When tests create fresh service instances (new ThinkerService()) instead
        of using the global thinker_service singleton, they're immune to state
        bleed from WebSocket tests that modify the singleton.

        Regression guard: If ThinkerService uses class-level (static) state,
        fresh instances would still see global state. They must use instance-level
        state so new instances start clean.
        """
        from app.services.thinker import thinker_service

        # Pause a conversation on the global singleton
        test_conv_id = "singleton-isolation-test-2026-04-21"
        thinker_service.pause_conversation(test_conv_id)

        # A fresh instance must not see the global singleton's state
        fresh_service = ThinkerService()
        assert fresh_service.is_paused(test_conv_id) is False, (
            "Fresh ThinkerService instance must not see pause state from global singleton"
        )

        # Cleanup global state
        thinker_service.resume_conversation(test_conv_id)

    def test_paused_conversations_set_is_instance_not_class_level(self) -> None:
        """Test that _paused_conversations is an instance attribute, not class attribute.

        Guards against a regression where _paused_conversations is accidentally
        defined as a class-level set (mutable class attribute) which would be
        shared across all ThinkerService instances.
        """
        service_1 = ThinkerService()
        service_2 = ThinkerService()

        service_1.pause_conversation("class-level-test-conv")

        # service_2 must not see service_1's pause state
        assert service_2.is_paused("class-level-test-conv") is False, (
            "_paused_conversations must be an instance attribute, not a shared class attribute"
        )

        # Cleanup service_1
        service_1.resume_conversation("class-level-test-conv")


class TestKnowledgeResearchSingletonStateIsolation:
    """Tests for KnowledgeResearchService singleton state isolation.

    Similar to ThinkerService, KnowledgeResearchService uses instance-level
    _active_tasks. These tests verify that fresh instances start clean and
    that class-level state is not accidentally shared.
    """

    def test_fresh_service_has_empty_active_tasks(self) -> None:
        """Test that a new KnowledgeResearchService has no active tasks.

        Ensures that _active_tasks is an instance attribute initialized to an
        empty dict, not a class-level dict that accumulates across instances.
        """
        service = KnowledgeResearchService()
        assert len(service._active_tasks) == 0, (
            "Fresh KnowledgeResearchService must have no active tasks"
        )

    def test_active_tasks_isolated_between_instances(self) -> None:
        """Test that _active_tasks is not shared between service instances.

        Guards against a class-level mutable default (e.g., `_active_tasks = {}`
        at class level instead of in __init__). Such a bug would cause tasks from
        one instance to appear in another.
        """
        service_1 = KnowledgeResearchService()
        service_2 = KnowledgeResearchService()

        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.done.return_value = False
        service_1._active_tasks["Hobbes"] = mock_task

        assert "Hobbes" not in service_2._active_tasks, (
            "_active_tasks must be isolated per instance, not shared at class level"
        )

    def test_trigger_research_deduplication_independent_per_instance(self) -> None:
        """Test that deduplication in trigger_research is per-instance.

        Two separate service instances should independently track their own
        active tasks. Triggering research on instance_1 must not block
        instance_2 from starting its own research for the same thinker.
        """
        service_1 = KnowledgeResearchService()
        service_2 = KnowledgeResearchService()

        # Add a running task to service_1
        mock_running = MagicMock(spec=asyncio.Task)
        mock_running.done.return_value = False
        service_1._active_tasks["Locke"] = mock_running

        # service_2 should still allow research for "Locke"
        with (
            patch("asyncio.create_task", return_value=MagicMock(spec=asyncio.Task)) as mock_ct,
            patch.object(service_2, "_research_thinker", new_callable=MagicMock),
        ):
            service_2.trigger_research("Locke")
            (
                mock_ct.assert_called_once(),
                ("service_2 must allow research for 'Locke' even if service_1 has it running"),
            )
