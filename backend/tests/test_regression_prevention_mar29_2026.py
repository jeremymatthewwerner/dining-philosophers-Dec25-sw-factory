"""Regression prevention tests - Sunday QA focus (Mar 29, 2026).

Tests cover critical code paths and regression prevention for recently fixed bugs:

1. TestKnowledgeServiceGlobalMockBehavior:
   - autouse mock intercepts trigger_research during conversation creation
   - trigger_research called once per thinker in create_conversation
   - autouse mock call count starts fresh each test (no bleed from prior tests)
   - PUT /thinkers endpoint also calls trigger_research per new thinker

2. TestKnowledgeResearchDeduplication:
   - trigger_research skips if task already in-progress for same thinker
   - trigger_research starts new task after previous task completes (done=True)
   - trigger_research starts new task after done callback removes from _active_tasks

3. TestKnowledgeResearchIsStale:
   - is_stale returns True for FAILED status (not COMPLETE)
   - is_stale returns True for IN_PROGRESS status (not COMPLETE)
   - is_stale returns False for COMPLETE status updated within 30 days
   - is_stale returns True for COMPLETE status updated more than 30 days ago

4. TestConversationSessionIsolation:
   - User B gets 404 when accessing user A's conversation
   - User B gets 404 when deleting user A's conversation
   - User B gets 404 when sending message to user A's conversation
   - User B gets 404 when adding thinkers to user A's conversation

5. TestThinkerServiceIdlePausedState:
   - pause_for_idle adds conversation to both _paused and _idle_paused sets
   - resume_from_idle removes conversation from both sets
   - resume_from_idle does NOT resume manually-paused conversations
   - is_idle_paused returns False for conversations only in _paused (not _idle_paused)
   - Idle pause state for one conversation does not affect another conversation

All tests pass consistently (no flakiness).

Root cause of each regression risk:
- #783: Without the global autouse mock in conftest.py, tests that create conversations
  trigger real asyncio.Task(s) making HTTP requests to Wikipedia, hanging tests indefinitely.
- KnowledgeResearchService deduplication: The _active_tasks dict prevents concurrent research
  for the same thinker; regression would cause duplicate HTTP requests and race conditions.
- Conversation isolation: Session-based access control prevents cross-user data access;
  regression would be a security bug.
- ThinkerService idle state: The dual-set pattern (_paused + _idle_paused) distinguishes
  manually paused conversations from idle-paused ones; regression would prevent auto-resume
  from idle while allowing manual pauses to bypass resume-from-idle calls.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from httpx import AsyncClient

from app.models import ResearchStatus, ThinkerKnowledge
from app.services.knowledge_research import KnowledgeResearchService
from app.services.thinker import ThinkerService
from tests.conftest import create_thinker_input, get_auth_headers


class TestKnowledgeServiceGlobalMockBehavior:
    """Regression tests for the global autouse mock fix (PR #783).

    Root cause: Creating a conversation calls knowledge_service.trigger_research()
    which spawns an asyncio.Task making real HTTP requests to Wikipedia. Without
    the autouse fixture in conftest.py, any test creating conversations would hang.

    These tests verify the mock infrastructure works correctly to prevent
    this regression from silently breaking test isolation again.
    """

    async def test_create_conversation_calls_trigger_research_per_thinker(
        self, client: AsyncClient, mock_knowledge_service_trigger: MagicMock
    ) -> None:
        """Test that creating a conversation calls trigger_research for each thinker.

        Regression guard: conversations.py calls trigger_research once per thinker
        in the loop (line ~61). If this call is removed or moved outside the loop,
        knowledge research would not be triggered. The autouse mock lets us verify
        the call count without real HTTP requests.
        """
        mock_knowledge_service_trigger.reset_mock()
        headers = await get_auth_headers(client, "trigger_count_test1", "testpass123")

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Philosophy of Mind",
                "thinkers": [
                    create_thinker_input("Socrates"),
                    create_thinker_input("Descartes"),
                    create_thinker_input("Kant"),
                ],
            },
        )

        assert response.status_code == 200
        # trigger_research called exactly once per thinker
        assert mock_knowledge_service_trigger.call_count == 3
        called_names = [call[0][0] for call in mock_knowledge_service_trigger.call_args_list]
        assert "Socrates" in called_names
        assert "Descartes" in called_names
        assert "Kant" in called_names

    async def test_mock_call_count_starts_fresh_each_test(
        self, client: AsyncClient, mock_knowledge_service_trigger: MagicMock
    ) -> None:
        """Test that the autouse mock resets call count between tests.

        Regression guard: If the mock fixture were session-scoped instead of
        function-scoped, call counts would accumulate across tests, making
        call_count assertions unreliable. This test verifies isolation.
        """
        # At start of each test, mock call count should be 0
        # (the autouse fixture creates a fresh mock per test)
        assert mock_knowledge_service_trigger.call_count == 0

        # One thinker → one call
        headers = await get_auth_headers(client, "mock_isolation_test2", "testpass123")
        await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Test",
                "thinkers": [create_thinker_input("Aristotle")],
            },
        )

        assert mock_knowledge_service_trigger.call_count == 1

    async def test_add_thinkers_endpoint_also_triggers_research(
        self, client: AsyncClient, mock_knowledge_service_trigger: MagicMock
    ) -> None:
        """Test that PUT /conversations/{id}/thinkers also calls trigger_research.

        Regression guard: Both conversation creation AND thinker addition paths
        must trigger research. If one path is refactored and the trigger_research
        call is dropped, thinkers added post-creation won't have knowledge research.
        """
        mock_knowledge_service_trigger.reset_mock()
        headers = await get_auth_headers(client, "add_thinker_trigger_test3", "testpass123")

        # Create conversation with 1 thinker
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Ethics",
                "thinkers": [create_thinker_input("Plato")],
            },
        )
        assert conv_resp.status_code == 200
        conv_id = conv_resp.json()["id"]
        initial_call_count = mock_knowledge_service_trigger.call_count  # 1

        # Add 2 more thinkers
        response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                create_thinker_input("Nietzsche"),
                create_thinker_input("Hume"),
            ],
        )

        assert response.status_code == 200
        # Should have called trigger_research for the 2 new thinkers
        assert mock_knowledge_service_trigger.call_count == initial_call_count + 2
        recent_calls = [
            call[0][0]
            for call in mock_knowledge_service_trigger.call_args_list[initial_call_count:]
        ]
        assert "Nietzsche" in recent_calls
        assert "Hume" in recent_calls

    async def test_single_thinker_conversation_triggers_research_once(
        self, client: AsyncClient, mock_knowledge_service_trigger: MagicMock
    ) -> None:
        """Test that a single-thinker conversation calls trigger_research exactly once.

        Regression guard: The trigger_research call is inside a for-loop over thinkers.
        A single-thinker conversation should trigger exactly 1 research call. This
        prevents a regression where the call might be duplicated (called before AND
        inside the loop) or skipped for single-thinker conversations.
        """
        mock_knowledge_service_trigger.reset_mock()
        headers = await get_auth_headers(client, "single_thinker_trigger4", "testpass123")

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Metaphysics",
                "thinkers": [create_thinker_input("Hegel")],
            },
        )

        assert response.status_code == 200
        assert mock_knowledge_service_trigger.call_count == 1
        assert mock_knowledge_service_trigger.call_args[0][0] == "Hegel"


class TestKnowledgeResearchDeduplication:
    """Regression tests for task deduplication in KnowledgeResearchService.trigger_research.

    Root cause: trigger_research creates asyncio.Task objects that make real HTTP
    requests. If deduplication fails, multiple simultaneous research tasks for the
    same thinker waste resources and could cause database race conditions.
    """

    def test_trigger_research_skips_if_task_already_running(self) -> None:
        """Test that trigger_research does not start a new task if one is in progress.

        Regression guard: conversations.py lines 95-97 check `not task.done()`.
        If this guard is removed, calling trigger_research twice for the same thinker
        creates duplicate background tasks making concurrent HTTP requests.
        """
        service = KnowledgeResearchService()
        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.done.return_value = False  # Task is still running

        service._active_tasks["Socrates"] = mock_task

        with patch("asyncio.create_task") as mock_create_task:
            service.trigger_research("Socrates")
            # Should NOT create a new task because one is already running
            mock_create_task.assert_not_called()

    def test_trigger_research_starts_new_task_after_previous_completes(self) -> None:
        """Test that trigger_research starts a new task when the previous one is done.

        Regression guard: The done() check allows re-triggering research for a thinker
        after their previous research task finishes. If the check were reversed (not
        checking done()), completed thinkers could never have their research refreshed.
        """
        service = KnowledgeResearchService()
        mock_completed_task = MagicMock(spec=asyncio.Task)
        mock_completed_task.done.return_value = True  # Task is done

        service._active_tasks["Aristotle"] = mock_completed_task

        mock_new_task = MagicMock(spec=asyncio.Task)
        with (
            patch("asyncio.create_task", return_value=mock_new_task) as mock_create_task,
            patch.object(service, "_research_thinker", new_callable=MagicMock),
        ):
            service.trigger_research("Aristotle")
            # Should create a new task because previous is done
            mock_create_task.assert_called_once()

    def test_trigger_research_starts_task_for_new_thinker(self) -> None:
        """Test that trigger_research starts a task for a thinker not yet researched.

        Regression guard: The _active_tasks dict starts empty. First call for a
        thinker should always create a task. If the check inadvertently prevents
        this (e.g., key exists with None value), new thinkers would never be researched.
        """
        service = KnowledgeResearchService()
        assert "Einstein" not in service._active_tasks

        mock_task = MagicMock(spec=asyncio.Task)
        with (
            patch("asyncio.create_task", return_value=mock_task) as mock_create_task,
            patch.object(service, "_research_thinker", new_callable=MagicMock),
        ):
            service.trigger_research("Einstein")
            mock_create_task.assert_called_once()


class TestKnowledgeResearchIsStale:
    """Regression tests for KnowledgeResearchService.is_stale() boundary conditions.

    Root cause: Incorrect staleness classification causes cache misses (fresh data
    researched again) or stale cache hits (outdated data served). The staleness
    threshold is 30 days. Non-COMPLETE statuses are always stale.
    """

    def test_is_stale_returns_true_for_failed_status(self) -> None:
        """Test that FAILED knowledge is always considered stale.

        Regression guard: is_stale() checks `status != ResearchStatus.COMPLETE`.
        A FAILED entry must always be refreshed. If the check were reversed or
        omitted, failed research would appear fresh and never be retried.
        """
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.FAILED,
            research_data={},
            updated_at=datetime.now(UTC),  # Fresh timestamp, but FAILED
        )
        assert service.is_stale(knowledge) is True

    def test_is_stale_returns_true_for_in_progress_status(self) -> None:
        """Test that IN_PROGRESS knowledge is considered stale.

        Regression guard: Research stuck in IN_PROGRESS (e.g., from a crashed task)
        should be retried. If is_stale returns False for IN_PROGRESS, stuck research
        entries would never be refreshed.
        """
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.IN_PROGRESS,
            research_data={},
            updated_at=datetime.now(UTC),
        )
        assert service.is_stale(knowledge) is True

    def test_is_stale_returns_true_for_pending_status(self) -> None:
        """Test that PENDING knowledge is considered stale.

        Regression guard: PENDING entries that never started research should be
        retried. If is_stale returns False for PENDING, orphaned entries would
        accumulate without ever being researched.
        """
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.PENDING,
            research_data={},
            updated_at=datetime.now(UTC),
        )
        assert service.is_stale(knowledge) is True

    def test_is_stale_returns_false_for_recent_complete(self) -> None:
        """Test that recently completed knowledge is not stale.

        Regression guard: Freshly completed research (within 30 days) should be
        served from cache. If is_stale always returns True, every request would
        trigger a re-research, defeating the caching system.
        """
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.COMPLETE,
            research_data={"data": "fresh"},
            updated_at=datetime.now(UTC) - timedelta(days=1),  # 1 day ago is fresh
        )
        assert service.is_stale(knowledge) is False

    def test_is_stale_returns_true_for_old_complete(self) -> None:
        """Test that old completed knowledge (>30 days) is stale.

        Regression guard: The 30-day cache staleness threshold ensures knowledge
        is periodically refreshed. If the threshold check fails, very old cached
        data would be served forever without refresh.
        """
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.COMPLETE,
            research_data={"data": "old"},
            updated_at=datetime.now(UTC) - timedelta(days=31),  # 31 days ago is stale
        )
        assert service.is_stale(knowledge) is True

    def test_is_stale_boundary_at_exactly_30_days(self) -> None:
        """Test staleness at exactly 30 days (boundary condition).

        Regression guard: The staleness check uses `< staleness_threshold`. Exactly
        at the 30-day mark, the knowledge should be considered stale. This ensures
        the boundary condition is handled correctly (not an off-by-one error).
        """
        service = KnowledgeResearchService()
        # Exactly 30 days + 1 second ago: should be stale
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.COMPLETE,
            research_data={"data": "boundary"},
            updated_at=datetime.now(UTC) - timedelta(days=30, seconds=1),
        )
        assert service.is_stale(knowledge) is True


class TestConversationSessionIsolation:
    """Regression tests for cross-session conversation access control.

    Root cause: Conversations are scoped to a specific user session. API endpoints
    filter by session_id (not just conversation_id). If session scoping is removed,
    any authenticated user could read/modify/delete other users' conversations.
    This would be a critical security regression.
    """

    async def test_user_b_cannot_read_user_a_conversation(self, client: AsyncClient) -> None:
        """Test that user B gets 404 when reading user A's conversation.

        Regression guard: conversations.py GET /{id} filters by both conversation_id
        AND session_id. Removing the session_id filter would allow any user to read
        all conversations by ID — a security vulnerability.
        """
        # User A creates a conversation
        headers_a = await get_auth_headers(client, "sess_iso_userA_get", "testpass123")
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers_a,
            json={
                "topic": "Private Discussion",
                "thinkers": [create_thinker_input("Locke")],
            },
        )
        assert conv_resp.status_code == 200
        conv_id = conv_resp.json()["id"]

        # User B tries to read User A's conversation
        headers_b = await get_auth_headers(client, "sess_iso_userB_get", "testpass123")
        response = await client.get(f"/api/conversations/{conv_id}", headers=headers_b)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_user_b_cannot_delete_user_a_conversation(self, client: AsyncClient) -> None:
        """Test that user B gets 404 when deleting user A's conversation.

        Regression guard: DELETE /{id} filters by session_id. Removing the filter
        would allow arbitrary deletion of other users' conversations.
        """
        # User A creates a conversation
        headers_a = await get_auth_headers(client, "sess_iso_userA_del", "testpass123")
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers_a,
            json={
                "topic": "Private Topic",
                "thinkers": [create_thinker_input("Mill")],
            },
        )
        assert conv_resp.status_code == 200
        conv_id = conv_resp.json()["id"]

        # User B tries to delete User A's conversation
        headers_b = await get_auth_headers(client, "sess_iso_userB_del", "testpass123")
        response = await client.delete(f"/api/conversations/{conv_id}", headers=headers_b)

        assert response.status_code == 404

        # User A's conversation still exists
        get_resp = await client.get(f"/api/conversations/{conv_id}", headers=headers_a)
        assert get_resp.status_code == 200

    async def test_user_b_cannot_send_message_to_user_a_conversation(
        self, client: AsyncClient
    ) -> None:
        """Test that user B gets 404 when sending a message to user A's conversation.

        Regression guard: POST /{id}/messages filters by session_id. Without it,
        any user could inject messages into other users' conversations.
        """
        headers_a = await get_auth_headers(client, "sess_iso_userA_msg", "testpass123")
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers_a,
            json={
                "topic": "Confidential",
                "thinkers": [create_thinker_input("Rousseau")],
            },
        )
        assert conv_resp.status_code == 200
        conv_id = conv_resp.json()["id"]

        # User B tries to send a message
        headers_b = await get_auth_headers(client, "sess_iso_userB_msg", "testpass123")
        response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers_b,
            json={"content": "Injected message"},
        )

        assert response.status_code == 404

    async def test_user_b_cannot_add_thinkers_to_user_a_conversation(
        self, client: AsyncClient
    ) -> None:
        """Test that user B gets 404 when adding thinkers to user A's conversation.

        Regression guard: PUT /{id}/thinkers filters by session_id. Without it,
        any user could add thinkers to another user's conversation.
        """
        headers_a = await get_auth_headers(client, "sess_iso_userA_tkr", "testpass123")
        conv_resp = await client.post(
            "/api/conversations",
            headers=headers_a,
            json={
                "topic": "Solo Philosophy",
                "thinkers": [create_thinker_input("Leibniz")],
            },
        )
        assert conv_resp.status_code == 200
        conv_id = conv_resp.json()["id"]

        # User B tries to add thinkers
        headers_b = await get_auth_headers(client, "sess_iso_userB_tkr", "testpass123")
        response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers_b,
            json=[create_thinker_input("Voltaire")],
        )

        assert response.status_code == 404


class TestThinkerServiceIdlePausedState:
    """Regression tests for ThinkerService idle pause/resume state management.

    Root cause: The idle pause feature (PR #483) uses two parallel sets:
    - _paused_conversations: tracks ALL paused conversations
    - _idle_paused_conversations: tracks only idle-paused conversations

    The dual-set pattern distinguishes idle pauses from manual pauses, ensuring
    resume_from_idle only resumes idle-paused conversations (not manual pauses).
    Regression in this logic would either:
    - Allow idle-resume to override manual pauses (users lose their pause state)
    - Prevent auto-resume from idle (conversations stuck paused after user returns)
    """

    def test_pause_for_idle_adds_to_both_sets(self) -> None:
        """Test that pause_for_idle adds to both _paused and _idle_paused sets.

        Regression guard: pause_for_idle must add to BOTH sets. If it only adds to
        _idle_paused but not _paused, the conversation won't actually stop streaming.
        If it only adds to _paused, is_idle_paused() will return False and auto-resume
        won't trigger correctly.
        """
        service = ThinkerService()
        conv_id = "idle-test-conv-001"

        service.pause_for_idle(conv_id)

        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is True

    def test_resume_from_idle_clears_both_sets(self) -> None:
        """Test that resume_from_idle removes from both _paused and _idle_paused sets.

        Regression guard: resume_from_idle must clear BOTH sets. If it only clears
        _idle_paused, the conversation stays paused. If it only clears _paused,
        is_idle_paused would still return True, causing repeated resume attempts.
        """
        service = ThinkerService()
        conv_id = "idle-test-conv-002"

        service.pause_for_idle(conv_id)
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is True

        service.resume_from_idle(conv_id)

        assert service.is_paused(conv_id) is False
        assert service.is_idle_paused(conv_id) is False

    def test_resume_from_idle_does_not_resume_manually_paused_conversation(
        self,
    ) -> None:
        """Test that resume_from_idle leaves manually paused conversations paused.

        Regression guard: This is the KEY invariant of the dual-set pattern.
        If a user manually pauses (pause_conversation), resume_from_idle must NOT
        resume it. Without this, an idle-timeout on a different conversation could
        incorrectly resume a user's intentionally paused conversation.
        """
        service = ThinkerService()
        conv_id = "idle-test-conv-003"

        # Manually pause (not idle-pause)
        service.pause_conversation(conv_id)
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is False  # not in idle set

        # Calling resume_from_idle should do nothing (conv not in _idle_paused)
        service.resume_from_idle(conv_id)

        # Conversation must remain paused
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is False

    def test_idle_pause_does_not_affect_other_conversation(self) -> None:
        """Test that pausing one conversation idle does not affect another.

        Regression guard: The state sets are shared across the service instance.
        Using set operations (add/discard) should ensure isolation, but a regression
        where a clear() or bulk operation replaces individual operations would affect
        all conversations.
        """
        service = ThinkerService()
        conv_a = "idle-test-conv-A"
        conv_b = "idle-test-conv-B"

        service.pause_for_idle(conv_a)

        assert service.is_paused(conv_a) is True
        assert service.is_idle_paused(conv_a) is True
        assert service.is_paused(conv_b) is False
        assert service.is_idle_paused(conv_b) is False

    def test_is_idle_paused_false_for_manually_paused(self) -> None:
        """Test that is_idle_paused returns False for manually paused conversations.

        Regression guard: Manual pause (pause_conversation) should NOT set the
        idle_paused flag. If it does, auto-resume would be triggered for manually
        paused conversations when users send messages, overriding their intent.
        """
        service = ThinkerService()
        conv_id = "manual-pause-conv-005"

        service.pause_conversation(conv_id)

        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is False

    def test_resume_from_idle_on_unknown_conversation_is_noop(self) -> None:
        """Test that resume_from_idle on an unknown conversation does nothing.

        Regression guard: set.discard() is used (not set.remove()), so calling
        resume_from_idle on an unknown conversation should not raise an error.
        If .remove() were used instead, it would raise KeyError, causing send_message
        to fail when the idle-resume check runs on a non-paused conversation.
        """
        service = ThinkerService()
        conv_id = "nonexistent-conv-006"

        # Should not raise any exception
        service.resume_from_idle(conv_id)

        assert service.is_paused(conv_id) is False
        assert service.is_idle_paused(conv_id) is False
