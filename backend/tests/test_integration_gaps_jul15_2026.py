"""Integration-gap tests for the idle-timeout path of ``_run_thinker_agent``
(July 15, 2026 - Wednesday QA / integration-gaps focus).

Backend coverage is already ~99.7% with every API endpoint at 100% line
coverage. The remaining measurable gaps are **untested branches inside the
autonomous conversation loop** ``ThinkerService._run_thinker_agent``. The
happy-path (bubble-send) and the "user is idle → pause" path were already
covered by earlier sprints; what remained uncovered were the three *negative*
idle-timeout decision branches:

- ``1194->1230`` - idle-timeout is **disabled** (``idle_timeout_seconds == 0``),
  so the whole idle block is skipped and the loop proceeds to ``_should_respond``.
- ``1198->1230`` - the user is **recently active** (``idle_duration < timeout``),
  so no idle pause happens and the loop proceeds normally.
- ``1200->1226`` - the conversation is **already idle-paused**, so the loop must
  NOT re-broadcast the IDLE_TIMEOUT / PAUSED events, it just sleeps and continues.

These branches encode real product behavior (an idle conversation is paused
exactly once, an active one is never paused, and disabling the feature turns the
whole thing off), so they are worth pinning with integration-style tests that
drive the real loop for one iteration.

The tests reuse the "run one iteration then cancel via CancelledError from
``is_conversation_active``" pattern established by the may18 coverage sprint.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.websocket import WSMessageType
from app.services.thinker import ThinkerService


def _make_thinker() -> MagicMock:
    t = MagicMock()
    t.name = "Socrates"
    t.bio = "Classical philosopher"
    t.positions = "Question everything"
    t.style = "Dialectic"
    return t


def _make_user_message(created_at: datetime | None) -> MagicMock:
    """A user message whose ``created_at`` drives the idle-timeout calculation."""
    msg = MagicMock()
    msg.content = "Hello, thinker"
    msg.sender_name = "User"
    sender = MagicMock()
    sender.value = "user"
    msg.sender_type = sender
    msg.created_at = created_at
    return msg


def _patch_manager() -> Any:
    """Patch ``app.services.thinker.manager``; caller must ``patcher.stop()``."""
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
    conversation_id: str = "conv-idle",
) -> None:
    """Drive ``_run_thinker_agent`` with ``asyncio.sleep`` no-opped."""
    thinker = _make_thinker()

    async def _sleep_noop(_seconds: float) -> None:
        return None

    async def save_message(_conv_id: str, _name: str, _content: str, _cost: float) -> Any:
        return MagicMock(id="msg-1")

    with patch("asyncio.sleep", side_effect=_sleep_noop):
        await service._run_thinker_agent(
            conversation_id,
            thinker,
            topic="philosophy",
            get_messages=get_messages,
            save_message=save_message,
        )


def _broadcast_types(mock_manager: MagicMock) -> list[WSMessageType]:
    """Collect the ``type`` of every WSMessage broadcast to the conversation."""
    types: list[WSMessageType] = []
    for call in mock_manager.broadcast_to_conversation.await_args_list:
        ws_message = call.args[1]
        types.append(ws_message.type)
    return types


class TestIdleTimeoutNegativeBranches:
    """Cover the three negative idle-timeout decision branches of the loop."""

    @pytest.mark.asyncio
    async def test_idle_timeout_disabled_skips_idle_logic(self) -> None:
        """idle_timeout_seconds == 0 → idle block skipped, loop reaches _should_respond.

        Covers branch 1194->1230: ``if idle_timeout > 0 and messages`` is False.
        Even with an ancient user message that would otherwise trigger an idle
        pause, disabling the feature means the conversation is never idle-paused.
        """
        service = ThinkerService()
        old = datetime.now(UTC) - timedelta(seconds=100_000)

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message(old)]

        patcher, mock_manager = _patch_manager()
        # One iteration, then cancel on the second is_conversation_active check.
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]
        try:
            with (
                patch.object(service.settings, "idle_timeout_seconds", 0),
                patch.object(service, "_should_respond", return_value=False),
            ):
                await _run_agent(service, get_messages)
        finally:
            patcher.stop()

        # Feature disabled → conversation never idle-paused, no pause broadcast.
        assert service.is_idle_paused("conv-idle") is False
        assert WSMessageType.IDLE_TIMEOUT not in _broadcast_types(mock_manager)

    @pytest.mark.asyncio
    async def test_recent_user_activity_does_not_idle_pause(self) -> None:
        """Recent user message (idle_duration < timeout) → no idle pause.

        Covers branch 1198->1230: ``if idle_duration >= idle_timeout`` is False.
        The loop should fall through to the normal ``_should_respond`` decision
        without pausing the conversation.
        """
        service = ThinkerService()
        recent = datetime.now(UTC)  # ~0s ago, well under the 300s timeout

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message(recent)]

        patcher, mock_manager = _patch_manager()
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]
        try:
            with (
                patch.object(service.settings, "idle_timeout_seconds", 300),
                patch.object(service, "_should_respond", return_value=False),
            ):
                await _run_agent(service, get_messages)
        finally:
            patcher.stop()

        # Active user → not idle-paused, and no IDLE_TIMEOUT/PAUSED broadcast.
        assert service.is_idle_paused("conv-idle") is False
        broadcast_types = _broadcast_types(mock_manager)
        assert WSMessageType.IDLE_TIMEOUT not in broadcast_types
        assert WSMessageType.PAUSED not in broadcast_types

    @pytest.mark.asyncio
    async def test_already_idle_paused_conversation_does_not_rebroadcast(self) -> None:
        """Already idle-paused conversation → no duplicate IDLE_TIMEOUT/PAUSED events.

        Covers branch 1200->1226: ``if not self.is_idle_paused(...)`` is False.

        We reconstruct a realistic state where ``is_paused`` is False but
        ``is_idle_paused`` is True: the conversation was idle-paused (both flags
        set), then ``resume_conversation`` was called (which clears only the
        manual-pause flag, per its implementation). The user is still past the
        idle timeout, so the loop re-enters the idle block, but because the idle
        pause was already announced it must just sleep+continue rather than
        re-broadcasting IDLE_TIMEOUT/PAUSED.
        """
        service = ThinkerService()
        old = datetime.now(UTC) - timedelta(seconds=100_000)

        # Idle-paused, then manually resumed → is_paused False, is_idle_paused True.
        service.pause_for_idle("conv-idle")
        service.resume_conversation("conv-idle")
        assert service.is_paused("conv-idle") is False
        assert service.is_idle_paused("conv-idle") is True

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message(old)]

        patcher, mock_manager = _patch_manager()
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]
        try:
            with patch.object(service.settings, "idle_timeout_seconds", 300):
                await _run_agent(service, get_messages)
        finally:
            patcher.stop()

        # Still idle-paused, but NO new pause notifications were broadcast because
        # the pause had already been announced.
        assert service.is_idle_paused("conv-idle") is True
        broadcast_types = _broadcast_types(mock_manager)
        assert WSMessageType.IDLE_TIMEOUT not in broadcast_types
        assert WSMessageType.PAUSED not in broadcast_types
        # The re-broadcast path also would have called stopped-typing; ensure it didn't.
        mock_manager.send_thinker_stopped_typing.assert_not_awaited()
