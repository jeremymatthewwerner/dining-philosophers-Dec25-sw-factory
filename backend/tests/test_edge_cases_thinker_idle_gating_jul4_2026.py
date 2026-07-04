"""Edge-case tests for idle-timeout / min-interval gating in ``_run_thinker_agent``.

Saturday QA (Jul 4, 2026) - Edge Case Analysis focus.

Backend coverage is already ~99.7%. The only reachable uncovered branches live in
``app/services/thinker.py``'s ``_run_thinker_agent`` loop, all in the timing/idle
gating logic that runs *before* the ``_should_respond`` decision. Prior sprints
covered the "gate fires" side of each branch; these tests exercise the
*opposite* (edge) side:

- ``1185->1190`` - ``elapsed >= min_interval``: enough time has passed since the
  thinker's last message, so the min-interval sleep gate does NOT fire and the
  loop proceeds to fetch messages.
- ``1194->1230`` - ``idle_timeout <= 0``: idle detection is disabled, so the
  whole idle-pause block is skipped straight to the ``_should_respond`` decision.
- ``1198->1230`` - ``idle_duration < idle_timeout``: the user spoke recently, so
  no idle pause is triggered.
- ``1200->1226`` - idle timeout reached but the conversation is ALREADY
  idle-paused, so the re-pause / broadcast block is skipped (just sleep+continue).

The tests reuse the "cancel on iteration N via CancelledError from
is_conversation_active" driving pattern from the may18 bubble-path sprint.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.thinker import ThinkerService


def _make_thinker() -> MagicMock:
    t = MagicMock()
    t.name = "Socrates"
    t.bio = "Classical philosopher"
    t.positions = "Question everything"
    t.style = "Dialectic"
    return t


def _make_user_message(created_at: datetime | None = None) -> MagicMock:
    """User-message mock with an optional real ``created_at`` timestamp.

    When ``created_at`` is provided the idle-timeout branch can read a positive
    ``last_user_msg_time`` and compute an ``idle_duration``; when ``None`` the
    idle block is short-circuited by the ``last_user_msg_time > 0`` guard.
    """
    msg = MagicMock()
    msg.content = "Hello, thinker"
    msg.sender_name = "User"
    sender = MagicMock()
    sender.value = "user"
    msg.sender_type = sender
    msg.created_at = created_at
    return msg


def _patch_manager() -> Any:
    """Patch ``app.services.thinker.manager`` with AsyncMock methods.

    Returns ``(patcher, mock_manager)``; caller must call ``patcher.stop()``.
    """
    patcher = patch("app.services.thinker.manager")
    mock_manager = patcher.start()
    mock_manager.get_speed_multiplier.return_value = 1.0
    mock_manager.is_conversation_active.return_value = True
    mock_manager.send_thinker_typing = AsyncMock()
    mock_manager.send_thinker_stopped_typing = AsyncMock()
    mock_manager.send_thinker_thinking = AsyncMock()
    mock_manager.send_thinker_message = AsyncMock()
    mock_manager.broadcast_to_conversation = AsyncMock()
    return patcher, mock_manager


async def _run_agent(
    service: ThinkerService,
    get_messages: Any,
    save_message: Any,
    conversation_id: str = "conv-idle",
) -> None:
    """Drive ``_run_thinker_agent`` once with ``asyncio.sleep`` no-opped."""
    thinker = _make_thinker()

    async def _sleep_noop(_seconds: float) -> None:
        return None

    with patch("asyncio.sleep", side_effect=_sleep_noop):
        await service._run_thinker_agent(
            conversation_id,
            thinker,
            topic="philosophy",
            get_messages=get_messages,
            save_message=save_message,
        )


class TestRunThinkerAgentIdleGatingEdges:
    """Cover the *edge* side of the timing/idle gating branches."""

    @pytest.mark.asyncio
    async def test_min_interval_gate_not_fired_when_elapsed_exceeds_interval(self) -> None:
        """``elapsed >= min_interval`` → gate does NOT fire, loop proceeds (branch 1185->1190).

        Iteration 1 sends a bubble, setting ``last_message_time``. With
        ``get_speed_multiplier`` returning 0.0, ``min_interval`` is 0.0s, so on
        iteration 2 ``elapsed`` (>= 0) is never ``< min_interval`` and the loop
        continues to ``_should_respond`` again instead of sleeping. We assert
        ``_should_respond`` is reached on BOTH iterations.
        """
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            return MagicMock(id="msg-1")

        should_respond_calls = {"count": 0}

        def fake_should_respond(*_args: Any, **_kwargs: Any) -> bool:
            should_respond_calls["count"] += 1
            return True

        patcher, mock_manager = _patch_manager()
        # min_interval = 15 * speed_mult; speed_mult 0.0 → min_interval 0.0.
        mock_manager.get_speed_multiplier.return_value = 0.0
        # iter 1: send bubble. iter 2: gate does NOT fire → reaches should_respond
        # again → sends again. iter 3: cancel.
        mock_manager.is_conversation_active.side_effect = [
            True,
            True,
            asyncio.CancelledError(),
        ]
        try:
            with (
                patch.object(service, "_should_respond", side_effect=fake_should_respond),
                patch.object(service, "_should_prompt_user", return_value=False),
                patch.object(
                    service,
                    "_split_response_into_bubbles",
                    return_value=["Quick reply."],
                ),
                patch.object(
                    service,
                    "generate_response_with_streaming_thinking",
                    new=AsyncMock(return_value=("Quick reply.", 0.001)),
                ),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # Both iterations reached _should_respond — the min-interval gate never
        # short-circuited iteration 2.
        assert should_respond_calls["count"] == 2
        # Both iterations sent a bubble.
        assert mock_manager.send_thinker_message.await_count == 2

    @pytest.mark.asyncio
    async def test_idle_detection_disabled_skips_idle_block(self) -> None:
        """``idle_timeout <= 0`` → idle block skipped entirely (branch 1194->1230).

        With ``idle_timeout_seconds`` set to 0, ``idle_timeout > 0`` is False so
        the loop jumps straight to ``_should_respond`` even though the user
        message carries an old timestamp that would otherwise trigger an idle
        pause. We assert the idle-pause side effects never fire.
        """
        service = ThinkerService()

        old_ts = datetime.now(UTC) - timedelta(hours=1)

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message(created_at=old_ts)]

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            return MagicMock(id="msg-1")

        pause_for_idle_calls = {"count": 0}

        def fake_pause_for_idle(_cid: str) -> None:
            pause_for_idle_calls["count"] += 1

        should_respond_calls = {"count": 0}

        def fake_should_respond(*_args: Any, **_kwargs: Any) -> bool:
            should_respond_calls["count"] += 1
            return False

        patcher, mock_manager = _patch_manager()
        mock_manager.is_conversation_active.side_effect = [
            True,
            asyncio.CancelledError(),
        ]
        try:
            with (
                patch.object(service.settings, "idle_timeout_seconds", 0),
                patch.object(service, "_should_respond", side_effect=fake_should_respond),
                patch.object(service, "_should_prompt_user", return_value=False),
                patch.object(service, "pause_for_idle", side_effect=fake_pause_for_idle),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # Idle detection disabled: reached _should_respond, never idle-paused.
        assert should_respond_calls["count"] == 1
        assert pause_for_idle_calls["count"] == 0

    @pytest.mark.asyncio
    async def test_recent_user_activity_does_not_trigger_idle_pause(self) -> None:
        """``idle_duration < idle_timeout`` → no idle pause (branch 1198->1230).

        The user's last message is timestamped "now", so ``idle_duration`` is ~0,
        well under the 300s timeout. The idle-pause block is skipped and the loop
        proceeds to ``_should_respond``.
        """
        service = ThinkerService()

        recent_ts = datetime.now(UTC)

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message(created_at=recent_ts)]

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            return MagicMock(id="msg-1")

        pause_for_idle_calls = {"count": 0}

        def fake_pause_for_idle(_cid: str) -> None:
            pause_for_idle_calls["count"] += 1

        should_respond_calls = {"count": 0}

        def fake_should_respond(*_args: Any, **_kwargs: Any) -> bool:
            should_respond_calls["count"] += 1
            return False

        patcher, mock_manager = _patch_manager()
        mock_manager.is_conversation_active.side_effect = [
            True,
            asyncio.CancelledError(),
        ]
        try:
            with (
                patch.object(service.settings, "idle_timeout_seconds", 300),
                patch.object(service, "_should_respond", side_effect=fake_should_respond),
                patch.object(service, "_should_prompt_user", return_value=False),
                patch.object(service, "pause_for_idle", side_effect=fake_pause_for_idle),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # Recent activity: reached _should_respond, no idle pause triggered.
        assert should_respond_calls["count"] == 1
        assert pause_for_idle_calls["count"] == 0

    @pytest.mark.asyncio
    async def test_already_idle_paused_skips_repause(self) -> None:
        """Idle reached but ALREADY idle-paused → skip re-pause block (branch 1200->1226).

        With an old user timestamp and a short timeout, ``idle_duration >=
        idle_timeout`` is True. But ``is_idle_paused`` returns True, so the
        ``not is_idle_paused`` guard is False and the logging / ``pause_for_idle``
        / broadcast block is skipped — the loop just sleeps and continues. We
        assert ``pause_for_idle`` and the PAUSED broadcast never fire, and
        ``_should_respond`` is never reached (the idle branch ``continue``s).
        """
        service = ThinkerService()

        old_ts = datetime.now(UTC) - timedelta(minutes=10)

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message(created_at=old_ts)]

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            return MagicMock(id="msg-1")

        pause_for_idle_calls = {"count": 0}

        def fake_pause_for_idle(_cid: str) -> None:
            pause_for_idle_calls["count"] += 1

        should_respond_calls = {"count": 0}

        def fake_should_respond(*_args: Any, **_kwargs: Any) -> bool:
            should_respond_calls["count"] += 1
            return False

        patcher, mock_manager = _patch_manager()
        mock_manager.is_conversation_active.side_effect = [
            True,
            asyncio.CancelledError(),
        ]
        try:
            with (
                patch.object(service.settings, "idle_timeout_seconds", 60),
                patch.object(service, "_should_respond", side_effect=fake_should_respond),
                patch.object(service, "_should_prompt_user", return_value=False),
                patch.object(service, "is_idle_paused", return_value=True),
                patch.object(service, "pause_for_idle", side_effect=fake_pause_for_idle),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # Already idle-paused: re-pause block skipped, loop continued past the
        # idle branch without ever reaching _should_respond.
        assert pause_for_idle_calls["count"] == 0
        assert should_respond_calls["count"] == 0
        # No new PAUSED / IDLE_TIMEOUT broadcast was emitted.
        assert mock_manager.broadcast_to_conversation.await_count == 0
