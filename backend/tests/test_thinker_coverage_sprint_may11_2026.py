"""Coverage sprint tests for app/services/thinker.py (May 11, 2026 - Monday QA).

Targets the two largest uncovered regions in thinker.py (77% before this file):

1. Streaming-thinking event handling inside ``generate_response_with_streaming_thinking``
   (lines 616-672): thinking-delta accumulation, text-delta accumulation,
   pause-during-stream branch, message_delta usage update, and the ThinkingBlock
   cost-calculation path.

2. The ``_run_thinker_agent`` driver loop (lines 1155-1410): inactive conversation
   wait, paused-conversation wait, idle-timeout pause flow, and the four
   exception handlers (SpendLimitExceeded, BillingError, ThinkerAPIError,
   generic Exception).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic.types import ThinkingBlock

from app.api.websocket import SpendLimitExceeded
from app.exceptions import BillingError, ThinkerAPIError
from app.services.thinker import ThinkerService
from tests.streaming_helpers import (
    make_delta,
    make_event,
    service_with_fake_stream,
)

# ---------------------------------------------------------------------------
# Streaming-thinking event handler tests (lines 616-672)
#
# The streaming test doubles (make_event / make_delta / FakeStream /
# service_with_fake_stream) live in tests/streaming_helpers.py so they are
# shared with the other thinker-streaming suites instead of copy-pasted.
# ---------------------------------------------------------------------------


def _make_thinker() -> MagicMock:
    t = MagicMock()
    t.name = "Socrates"
    t.bio = "Classical philosopher"
    t.positions = "Question everything"
    t.style = "Dialectic"
    return t


def _patch_manager() -> Any:
    """Patch app.services.thinker.manager with stub AsyncMock methods.

    Returns the patch context manager; callers do:
        with _patch_manager() as mock_manager:
            ...
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


class TestStreamingThinkingEventBranches:
    """Cover the event-handler branches inside the streaming loop (lines 616-672)."""

    @pytest.mark.asyncio
    async def test_text_delta_accumulates_response_text(self) -> None:
        """A content_block_delta with a text delta should append to response_text."""
        events = [
            make_event("content_block_start"),
            make_event("content_block_delta", delta=make_delta(text="Hello ")),
            make_event("content_block_delta", delta=make_delta(text="world")),
        ]
        service, _ = service_with_fake_stream(events)
        thinker = _make_thinker()

        patcher, _mock_manager = _patch_manager()
        try:
            response, cost = await service.generate_response_with_streaming_thinking(
                "conv-1", thinker, [], "philosophy"
            )
        finally:
            patcher.stop()

        assert response == "Hello world"
        assert cost > 0

    @pytest.mark.asyncio
    async def test_thinking_delta_sends_throttled_update(self) -> None:
        """A long-enough thinking delta should accumulate and emit a thinking update."""
        # _extract_thinking_display returns "" for text < 80 chars, so we use 200+.
        long_thought = (
            "Now I should consider the implications of this very carefully. "
            "Let me think about what the user is really asking. "
            "This requires more thought than initially apparent."
        )
        events = [
            make_event("content_block_delta", delta=make_delta(thinking=long_thought)),
            make_event("content_block_delta", delta=make_delta(text="Answer")),
        ]
        service, _ = service_with_fake_stream(events)
        thinker = _make_thinker()

        patcher, mock_manager = _patch_manager()
        try:
            response, _cost = await service.generate_response_with_streaming_thinking(
                "conv-2", thinker, [], "philosophy"
            )
        finally:
            patcher.stop()

        assert response == "Answer"
        # send_thinker_thinking should have been awaited at least once for the thinking delta.
        assert mock_manager.send_thinker_thinking.await_count >= 1
        first_call = mock_manager.send_thinker_thinking.await_args_list[0]
        assert first_call.args[0] == "conv-2"
        assert first_call.args[1] == "Socrates"

    @pytest.mark.asyncio
    async def test_pause_during_stream_sends_stopped_typing_once(self) -> None:
        """When paused mid-stream, send_thinker_stopped_typing fires exactly once."""
        service, _ = service_with_fake_stream(
            [
                make_event("content_block_delta", delta=make_delta(text="Start")),
                make_event("content_block_delta", delta=make_delta(text="More")),
            ]
        )
        thinker = _make_thinker()

        # Pause before streaming so every event hits the paused branch (lines 617-624).
        service.pause_conversation("conv-3")

        patcher, mock_manager = _patch_manager()
        try:
            response, _cost = await service.generate_response_with_streaming_thinking(
                "conv-3", thinker, [], "philosophy"
            )
        finally:
            patcher.stop()

        # No text accumulated because we were paused.
        assert response == ""
        # Stopped-typing fires exactly once (the paused_during_stream guard).
        assert mock_manager.send_thinker_stopped_typing.await_count == 1

    @pytest.mark.asyncio
    async def test_thinking_block_contributes_to_cost(self) -> None:
        """When final_message.content contains a ThinkingBlock, thinking tokens add cost."""
        thinking_block = ThinkingBlock(
            type="thinking",
            thinking="x" * 400,  # ~100 thinking tokens via the len // 4 estimate
            signature="sig",
        )
        events = [
            make_event("content_block_delta", delta=make_delta(text="Final answer.")),
        ]
        service, _ = service_with_fake_stream(
            events,
            final_content=[thinking_block],
            input_tokens=100,
            output_tokens=50,
        )
        thinker = _make_thinker()

        patcher, _mock_manager = _patch_manager()
        try:
            response, cost = await service.generate_response_with_streaming_thinking(
                "conv-4", thinker, [], "philosophy"
            )
        finally:
            patcher.stop()

        assert response == "Final answer."
        bare_cost = 100 * 0.000003 + 50 * 0.000015
        assert cost > bare_cost

    @pytest.mark.asyncio
    async def test_message_delta_event_updates_usage(self) -> None:
        """A message_delta event with usage info is consumed without error."""
        message_delta_event = MagicMock()
        message_delta_event.type = "message_delta"
        message_delta_event.usage = MagicMock(output_tokens=42)

        events = [
            make_event("content_block_delta", delta=make_delta(text="Hi")),
            message_delta_event,
        ]
        service, _ = service_with_fake_stream(events)
        thinker = _make_thinker()

        patcher, _mock_manager = _patch_manager()
        try:
            response, cost = await service.generate_response_with_streaming_thinking(
                "conv-5", thinker, [], "philosophy"
            )
        finally:
            patcher.stop()

        assert response == "Hi"
        assert cost > 0


# ---------------------------------------------------------------------------
# _run_thinker_agent loop tests (lines 1155-1410)
# ---------------------------------------------------------------------------


def _make_user_message(*, created_at_ts: float | None = None) -> MagicMock:
    """Build a user Message-like mock with optional created_at."""
    msg = MagicMock()
    msg.content = "Hello, thinker"
    msg.sender_name = "User"
    sender = MagicMock()
    sender.value = "user"
    msg.sender_type = sender
    if created_at_ts is not None:
        created_at = MagicMock()
        created_at.timestamp.return_value = created_at_ts
        msg.created_at = created_at
    else:
        msg.created_at = None
    return msg


async def _run_agent(
    service: ThinkerService,
    get_messages: Any,
    save_message: Any,
) -> None:
    """Drive ``_run_thinker_agent`` once. asyncio.sleep is replaced with a no-op.

    The loop is expected to exit on its own (via ``break`` after an unrecoverable
    error or via ``CancelledError`` propagation from a mock).
    """
    thinker = _make_thinker()

    async def _sleep_noop(_seconds: float) -> None:
        return None

    with patch("asyncio.sleep", side_effect=_sleep_noop):
        await service._run_thinker_agent(
            "conv-run",
            thinker,
            topic="philosophy",
            get_messages=get_messages,
            save_message=save_message,
        )


class TestRunThinkerAgentLoop:
    """Exercise the major control-flow branches of `_run_thinker_agent`."""

    @pytest.mark.asyncio
    async def test_exits_on_cancelled_error(self) -> None:
        """CancelledError raised inside the try block breaks cleanly (line 1338-1339)."""
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return []

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("save_message should not be called")

        patcher, mock_manager = _patch_manager()
        mock_manager.is_conversation_active.side_effect = asyncio.CancelledError()
        try:
            # Loop should swallow the CancelledError and return without raising.
            await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_waits_when_conversation_inactive(self) -> None:
        """When conversation is inactive, the loop sleeps then continues (lines 1162-1165).

        We let one inactive-iteration run, then have is_conversation_active raise
        CancelledError on the second call to break the loop cleanly.
        """
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return []

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            return MagicMock()

        patcher, mock_manager = _patch_manager()
        # First call: not active -> sleep and continue. Second: cancel.
        mock_manager.is_conversation_active.side_effect = [False, asyncio.CancelledError()]
        try:
            await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        assert mock_manager.is_conversation_active.call_count >= 2

    @pytest.mark.asyncio
    async def test_waits_when_conversation_paused(self) -> None:
        """When conversation is paused, the loop sleeps and continues (lines 1167-1171)."""
        service = ThinkerService()
        service.pause_conversation("conv-run")

        async def get_messages(_cid: str) -> list[Any]:
            return []

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            return MagicMock()

        patcher, mock_manager = _patch_manager()
        # Active=True on iter 1 (then we hit the paused branch and sleep). On
        # iter 2 we cancel via is_conversation_active.
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]
        try:
            await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        assert mock_manager.is_conversation_active.call_count >= 2

    @pytest.mark.asyncio
    async def test_idle_timeout_triggers_pause_flow(self) -> None:
        """When idle longer than timeout, the agent pauses & broadcasts (lines 1192-1227)."""
        service = ThinkerService()
        # Use a very short idle timeout so any positive timestamp far in the past
        # triggers the idle branch.
        service.settings.idle_timeout_seconds = 1

        # Last user message has a timestamp far in the past (must be > 0 to be considered).
        old_msg = _make_user_message(created_at_ts=time.time() - 3600)

        async def get_messages(_cid: str) -> list[Any]:
            return [old_msg]

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("save_message should not be called on idle path")

        patcher, mock_manager = _patch_manager()
        # Iter 1: process idle timeout (pauses), then sleeps. Iter 2: cancel.
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]
        try:
            await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # Conversation should now be idle-paused.
        assert service.is_idle_paused("conv-run")
        # Two broadcasts (IDLE_TIMEOUT and PAUSED) plus possibly more.
        assert mock_manager.broadcast_to_conversation.await_count >= 2

    @pytest.mark.asyncio
    async def test_spend_limit_exceeded_pauses_and_breaks(self) -> None:
        """SpendLimitExceeded handler pauses conversation and exits (lines 1340-1360)."""
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            return MagicMock(id="msg-1")

        patcher, mock_manager = _patch_manager()
        try:
            with (
                patch.object(service, "_should_respond", return_value=True),
                patch.object(service, "_should_prompt_user", return_value=False),
                patch.object(
                    service,
                    "generate_response_with_streaming_thinking",
                    new=AsyncMock(side_effect=SpendLimitExceeded(10.0, 5.0)),
                ),
            ):
                # The handler calls ``break``, so the loop exits on its own.
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        assert service.is_paused("conv-run")
        # ERROR + PAUSED broadcasts.
        assert mock_manager.broadcast_to_conversation.await_count >= 2

    @pytest.mark.asyncio
    async def test_billing_error_pauses_and_breaks(self) -> None:
        """BillingError handler pauses conversation and exits (lines 1361-1382)."""
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            return MagicMock(id="msg-1")

        patcher, mock_manager = _patch_manager()
        try:
            with (
                patch.object(service, "_should_respond", return_value=True),
                patch.object(service, "_should_prompt_user", return_value=False),
                patch.object(
                    service,
                    "generate_response_with_streaming_thinking",
                    new=AsyncMock(side_effect=BillingError("Credit limit reached")),
                ),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        assert service.is_paused("conv-run")
        assert mock_manager.broadcast_to_conversation.await_count >= 2

    @pytest.mark.asyncio
    async def test_thinker_api_error_broadcasts_then_retries(self) -> None:
        """ThinkerAPIError handler broadcasts error and waits before retry (lines 1383-1395).

        Strategy: let iter 1 run through the error handler. On iter 2, cancel by
        making is_conversation_active raise CancelledError (caught by the loop).
        """
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            return MagicMock(id="msg-1")

        patcher, mock_manager = _patch_manager()
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]
        try:
            with (
                patch.object(service, "_should_respond", return_value=True),
                patch.object(service, "_should_prompt_user", return_value=False),
                patch.object(
                    service,
                    "generate_response_with_streaming_thinking",
                    new=AsyncMock(side_effect=ThinkerAPIError("upstream blew up")),
                ),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # ERROR broadcast emitted, but conversation is NOT paused (this is recoverable).
        assert mock_manager.broadcast_to_conversation.await_count >= 1
        assert not service.is_paused("conv-run")

    @pytest.mark.asyncio
    async def test_generic_exception_broadcasts_then_retries(self) -> None:
        """A generic Exception logs + broadcasts + sleeps (lines 1396-1410)."""
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            return MagicMock(id="msg-1")

        patcher, mock_manager = _patch_manager()
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]
        try:
            with (
                patch.object(service, "_should_respond", return_value=True),
                patch.object(service, "_should_prompt_user", return_value=False),
                patch.object(
                    service,
                    "generate_response_with_streaming_thinking",
                    new=AsyncMock(side_effect=RuntimeError("boom")),
                ),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        assert mock_manager.broadcast_to_conversation.await_count >= 1
        assert not service.is_paused("conv-run")

    @pytest.mark.asyncio
    async def test_pause_before_generation_skips_generate(self) -> None:
        """If paused after typing/reading delay, generation is skipped (lines 1250-1253)."""
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        save_calls = {"count": 0}

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            save_calls["count"] += 1
            return MagicMock(id="msg-1")

        patcher, mock_manager = _patch_manager()
        # Cancel via is_conversation_active on iter 2 to exit the loop.
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]

        # is_paused returns: outer-check=False, after-reading=True. Then later iterations
        # are short-circuited by is_conversation_active raising CancelledError.
        is_paused_values = iter([False, True])
        original_is_paused = service.is_paused

        def fake_is_paused(cid: str) -> bool:
            try:
                return next(is_paused_values)
            except StopIteration:
                return original_is_paused(cid)

        try:
            with (
                patch.object(service, "_should_respond", return_value=True),
                patch.object(service, "_should_prompt_user", return_value=False),
                patch.object(service, "is_paused", side_effect=fake_is_paused),
                patch.object(
                    service,
                    "generate_response_with_streaming_thinking",
                    new=AsyncMock(return_value=("should not reach", 0.0)),
                ) as mock_generate,
            ):
                await _run_agent(service, get_messages, save_message)

                # When paused before generation, generate is never called.
                assert mock_generate.await_count == 0
        finally:
            patcher.stop()

        assert save_calls["count"] == 0
