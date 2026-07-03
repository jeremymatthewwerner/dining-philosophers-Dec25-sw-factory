"""Coverage sprint tests for ``_run_thinker_agent`` bubble path (May 18, 2026 - Monday QA).

Targets the lowest-coverage module ``app/services/thinker.py`` (92% → ≥98%).

The previous Monday sprint (may11) covered the streaming-thinking event handler
(lines 616-672) and the four exception handlers at the end of
``_run_thinker_agent`` (lines 1338-1410). What remains uncovered is the
**post-generation bubble-sending path** inside the agent loop:

- Lines 1184-1187 - min-interval gating sleep+continue (after a previous send)
- Line 1258 - ``should_prompt and user_name`` → call ``generate_user_prompt``
- Lines 1269-1271 - pause flips True between ``generate`` and the bubble loop
- Lines 1281-1287 - pause check at the start of each bubble iteration (break)
- Lines 1289-1296 - happy-path ``save_message`` + first-bubble send
- Lines 1298-1302 - pause between ``save_message`` and ``send_thinker_message``
- Lines 1305-1322 - full bubble send + ``last_message_time`` update
- Lines 1315-1320 - multi-bubble case: sleep + typing for next bubble
- Lines 1324-1325 - empty ``response_text`` → stop typing only
- Lines 1332-1336 - ``consecutive_silence > 3`` → longer quiet-wait branch

The tests drive ``_run_thinker_agent`` for one or two iterations using the same
"cancel on iter N via CancelledError from is_conversation_active" pattern as
the may11 file, then assert the manager mock saw the expected calls.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.thinker import ThinkerService
from tests.mock_factories import make_thinker as _make_thinker


def _make_user_message() -> MagicMock:
    """Minimal user-message mock without a created_at timestamp.

    A None ``created_at`` causes ``_get_last_user_message_timestamp`` to return
    0.0, which skips the idle-timeout pause branch — leaving the loop free to
    reach the ``_should_respond``/bubble path.
    """
    msg = MagicMock()
    msg.content = "Hello, thinker"
    msg.sender_name = "User"
    sender = MagicMock()
    sender.value = "user"
    msg.sender_type = sender
    msg.created_at = None
    return msg


def _patch_manager() -> Any:
    """Patch ``app.services.thinker.manager`` with AsyncMock methods.

    Returns ``(patcher, mock_manager)``; caller is responsible for ``patcher.stop()``.
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
    conversation_id: str = "conv-bubble",
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


class TestRunThinkerAgentBubblePath:
    """Cover the post-generation bubble-sending branches of ``_run_thinker_agent``."""

    @pytest.mark.asyncio
    async def test_happy_path_single_bubble_sends_message(self) -> None:
        """Generate→split→save→send: the bubble is persisted and broadcast (lines 1273-1312, 1322-1323)."""
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        saved: list[Any] = []

        async def save_message(_conv_id: str, _name: str, content: str, _cost: float) -> Any:
            m = MagicMock()
            m.id = f"msg-{len(saved) + 1}"
            saved.append(content)
            return m

        patcher, mock_manager = _patch_manager()
        # Iter 1 completes one full bubble. Iter 2 cancels.
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]
        try:
            with (
                patch.object(service, "_should_respond", return_value=True),
                patch.object(service, "_should_prompt_user", return_value=False),
                patch.object(
                    service,
                    "_split_response_into_bubbles",
                    return_value=["Hello there."],
                ),
                patch.object(
                    service,
                    "generate_response_with_streaming_thinking",
                    new=AsyncMock(return_value=("Hello there.", 0.001)),
                ) as mock_generate,
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # Bubble was saved and sent exactly once.
        mock_generate.assert_awaited()
        assert saved == ["Hello there."]
        assert mock_manager.send_thinker_message.await_count == 1
        send_args = mock_manager.send_thinker_message.await_args_list[0].args
        assert send_args[0] == "conv-bubble"
        assert send_args[1] == "Socrates"
        assert send_args[2] == "Hello there."

    @pytest.mark.asyncio
    async def test_multi_bubble_response_sends_each_with_typing_between(self) -> None:
        """Multi-bubble response: typing+sleep between bubbles (lines 1315-1320)."""
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        async def save_message(_conv_id: str, _name: str, _content: str, _cost: float) -> Any:
            m = MagicMock()
            m.id = "msg-x"
            return m

        patcher, mock_manager = _patch_manager()
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]
        try:
            with (
                patch.object(service, "_should_respond", return_value=True),
                patch.object(service, "_should_prompt_user", return_value=False),
                patch.object(
                    service,
                    "_split_response_into_bubbles",
                    return_value=["First bubble.", "Second bubble.", "Third bubble."],
                ),
                patch.object(
                    service,
                    "generate_response_with_streaming_thinking",
                    new=AsyncMock(return_value=("response", 0.002)),
                ),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # Three bubbles → three send_thinker_message awaits.
        assert mock_manager.send_thinker_message.await_count == 3
        # The "show typing for next bubble" path fires (n-1) times: at least 2 typing calls
        # come from the inter-bubble gap (plus the initial typing at the start of the response).
        assert mock_manager.send_thinker_typing.await_count >= 3

    @pytest.mark.asyncio
    async def test_pause_after_generation_skips_bubble_send(self) -> None:
        """When pause flips True after generate, bubble loop is skipped (lines 1269-1271)."""
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        save_calls = {"count": 0}

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            save_calls["count"] += 1
            return MagicMock(id="msg-1")

        patcher, mock_manager = _patch_manager()
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]

        # is_paused returns False initially (outer check + before-generate check),
        # then True at the post-generation check (line 1269).
        is_paused_values = iter([False, False, True])
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
                    new=AsyncMock(return_value=("Hello.", 0.0)),
                ),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # save_message was never called because pause was detected post-generation.
        assert save_calls["count"] == 0
        assert mock_manager.send_thinker_message.await_count == 0
        # stopped-typing was emitted to flush the indicator (line 1270).
        assert mock_manager.send_thinker_stopped_typing.await_count >= 1

    @pytest.mark.asyncio
    async def test_pause_inside_bubble_loop_breaks_iteration(self) -> None:
        """Pause flipping True at the start of a bubble iteration breaks the loop (lines 1283-1287)."""
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        save_calls = {"count": 0}

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            save_calls["count"] += 1
            return MagicMock(id="msg-1")

        patcher, mock_manager = _patch_manager()
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]

        # is_paused sequence:
        # 1: outer is_paused check (False)
        # 2: pre-generate check (False)
        # 3: post-generate check (False)
        # 4: top-of-first-bubble check (True → break)
        is_paused_values = iter([False, False, False, True])
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
                    "_split_response_into_bubbles",
                    return_value=["A.", "B."],
                ),
                patch.object(
                    service,
                    "generate_response_with_streaming_thinking",
                    new=AsyncMock(return_value=("A. B.", 0.0)),
                ),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # Loop broke before any save_message ran.
        assert save_calls["count"] == 0
        assert mock_manager.send_thinker_message.await_count == 0

    @pytest.mark.asyncio
    async def test_pause_between_save_and_send_breaks_iteration(self) -> None:
        """Pause flipping True between save_message and send_thinker_message breaks the loop (lines 1298-1302).

        We save the first bubble (counted), then pause is detected before sending,
        so no send_thinker_message is emitted for that bubble.
        """
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        save_calls = {"count": 0}

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            save_calls["count"] += 1
            return MagicMock(id=f"msg-{save_calls['count']}")

        patcher, mock_manager = _patch_manager()
        mock_manager.is_conversation_active.side_effect = [True, asyncio.CancelledError()]

        # is_paused sequence:
        # 1: outer is_paused (False)
        # 2: pre-generate (False)
        # 3: post-generate (False)
        # 4: top of bubble iter 0 (False — proceed to save)
        # 5: between save and send (True → break)
        is_paused_values = iter([False, False, False, False, True])
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
                    "_split_response_into_bubbles",
                    return_value=["A.", "B."],
                ),
                patch.object(
                    service,
                    "generate_response_with_streaming_thinking",
                    new=AsyncMock(return_value=("A. B.", 0.0)),
                ),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # Exactly one save_message ran (for the first bubble), but no send_thinker_message:
        # the loop broke between save and send.
        assert save_calls["count"] == 1
        assert mock_manager.send_thinker_message.await_count == 0

    @pytest.mark.asyncio
    async def test_empty_response_text_stops_typing(self) -> None:
        """Generate returning '' → only send_thinker_stopped_typing, no save/send (lines 1324-1325)."""
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        save_calls = {"count": 0}

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            save_calls["count"] += 1
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
                    new=AsyncMock(return_value=("", 0.0)),
                ),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # No save and no send_thinker_message — empty response only stops typing.
        assert save_calls["count"] == 0
        assert mock_manager.send_thinker_message.await_count == 0
        assert mock_manager.send_thinker_stopped_typing.await_count >= 1

    @pytest.mark.asyncio
    async def test_should_prompt_user_calls_generate_user_prompt(self) -> None:
        """should_prompt=True + user_name → generate_user_prompt path is taken (line 1258)."""
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
                patch.object(service, "_should_prompt_user", return_value=True),
                patch.object(service, "_get_user_name_from_messages", return_value="Alice"),
                patch.object(
                    service,
                    "_split_response_into_bubbles",
                    return_value=["Alice, what do you think?"],
                ),
                patch.object(
                    service,
                    "generate_user_prompt",
                    new=AsyncMock(return_value=("Alice, what do you think?", 0.001)),
                ) as mock_prompt,
                patch.object(
                    service,
                    "generate_response_with_streaming_thinking",
                    new=AsyncMock(return_value=("should not be called", 0.0)),
                ) as mock_generate,
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # generate_user_prompt was used; normal generate was skipped.
        mock_prompt.assert_awaited()
        call = mock_prompt.await_args_list[0]
        assert call.args[0].name == "Socrates"
        assert call.args[3] == "Alice"
        assert mock_generate.await_count == 0
        # And the prompt was actually saved + broadcast as a bubble.
        assert mock_manager.send_thinker_message.await_count == 1

    @pytest.mark.asyncio
    async def test_min_interval_gating_after_successful_response(self) -> None:
        """After a response, next iter hits ``elapsed < min_interval`` and sleeps (lines 1183-1187).

        Iteration 1 completes one bubble, setting ``last_message_time``. Because
        ``asyncio.sleep`` is no-op (event-loop time barely moves) and
        ``min_interval = 15s``, iteration 2 enters the gating branch and sleeps
        via the ``await asyncio.sleep(min_interval - elapsed)`` call. We assert
        that iter 2 never reaches ``_should_respond`` again.
        """
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            return MagicMock(id="msg-min")

        should_respond_calls = {"count": 0}

        def fake_should_respond(*_args: Any, **_kwargs: Any) -> bool:
            should_respond_calls["count"] += 1
            return True

        patcher, mock_manager = _patch_manager()
        # iter 1: True (active) → completes bubble.
        # iter 2: True (active) → gating triggers sleep+continue (no _should_respond call).
        # iter 3: cancel.
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

        # _should_respond was only called once: iter 2 short-circuited via the
        # min-interval gate before reaching the should_respond check.
        assert should_respond_calls["count"] == 1
        # The first iteration succeeded → exactly one bubble was sent.
        assert mock_manager.send_thinker_message.await_count == 1

    @pytest.mark.asyncio
    async def test_consecutive_silence_exceeds_threshold_uses_quiet_wait(self) -> None:
        """should_respond=False ≥4 iters → enters the consecutive_silence>3 branch (line 1332).

        We just need to drive the loop through five iterations where
        ``_should_respond`` returns False, ensuring the consecutive_silence
        counter crosses the threshold of 3. Then we cancel.
        """
        service = ThinkerService()

        async def get_messages(_cid: str) -> list[Any]:
            return [_make_user_message()]

        async def save_message(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("save_message should not be called on silent path")

        should_respond_calls = {"count": 0}

        def fake_should_respond(*_args: Any, **_kwargs: Any) -> bool:
            should_respond_calls["count"] += 1
            return False

        patcher, mock_manager = _patch_manager()
        # 5 silent iters, then cancel.
        mock_manager.is_conversation_active.side_effect = [
            True,
            True,
            True,
            True,
            True,
            asyncio.CancelledError(),
        ]
        try:
            with (
                patch.object(service, "_should_respond", side_effect=fake_should_respond),
                patch.object(service, "_should_prompt_user", return_value=False),
            ):
                await _run_agent(service, get_messages, save_message)
        finally:
            patcher.stop()

        # All 5 iterations called _should_respond (no message was sent so the
        # min-interval gate never fires — last_message_time stays at 0).
        assert should_respond_calls["count"] == 5
        # No messages emitted on a silent run.
        assert mock_manager.send_thinker_message.await_count == 0
