"""Integration-gap tests (June 17, 2026 - Wednesday QA).

All API endpoints already sit at 100% line + branch coverage, so this run
targets the last reachable *behavioral* gap in the streaming response path.

``ThinkerService.generate_response_with_streaming_thinking`` builds the LLM
prompt with a one-time "DO NOT INTRODUCE YOURSELF" instruction that must only
appear for the very first message of a conversation (``len(messages) <= 1``).

The non-streaming sibling ``generate_response`` already has both-branch
coverage (see ``test_regression_prevention.py``), but the streaming method
carries its *own copy* of that logic at ``app/services/thinker.py`` line 557.
Every existing streaming test passes an empty history, so only the
initial-message branch was exercised; the non-initial branch (``557->563``)
was an untested partial.

These tests lock the contract for the streaming path in both directions:
- initial message  -> the first-message instruction IS present
- established chat  -> the first-message instruction is OMITTED, and the prior
  conversation history is woven into the prompt instead.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.thinker import ThinkerService

# ---------------------------------------------------------------------------
# Streaming helpers (mirror test_edge_cases_saturday_jun13_2026.py)
# ---------------------------------------------------------------------------


def _make_event(event_type: str, **fields: Any) -> MagicMock:
    """Build a streaming event mock with the given attributes."""
    event = MagicMock()
    event.type = event_type
    for key, value in fields.items():
        setattr(event, key, value)
    return event


def _make_text_delta(text: str) -> MagicMock:
    """Build a content_block_delta delta that exposes only ``text``."""
    delta = MagicMock(spec=["text"])
    delta.text = text
    return delta


class _FakeStream:
    """An async context manager + async iterator mimicking anthropic streaming."""

    def __init__(self, events: list[MagicMock], final_message: MagicMock) -> None:
        self._events = events
        self._final_message = final_message

    async def __aenter__(self) -> _FakeStream:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def __aiter__(self) -> _FakeStream:
        self._iter = iter(self._events)
        return self

    async def __anext__(self) -> MagicMock:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def get_final_message(self) -> MagicMock:
        return self._final_message


def _service_with_capturing_stream() -> tuple[ThinkerService, MagicMock]:
    """Build a ThinkerService whose client records the prompt it is called with.

    Returns the service and the mock ``messages.stream`` so the test can read
    back the prompt via ``stream.call_args``.
    """
    final_message = MagicMock()
    final_message.usage.input_tokens = 50
    final_message.usage.output_tokens = 30
    final_message.content = []

    events = [_make_event("content_block_delta", delta=_make_text_delta("A thoughtful reply."))]
    fake_stream = _FakeStream(events, final_message)

    mock_client = MagicMock()
    mock_client.messages.stream = MagicMock(return_value=fake_stream)

    service = ThinkerService()
    service._client = mock_client
    return service, mock_client.messages.stream


def _make_thinker() -> MagicMock:
    t = MagicMock()
    t.name = "Socrates"
    t.bio = "Classical philosopher"
    t.positions = "Question everything"
    t.style = "Dialectic"
    return t


def _make_message(sender_name: str, content: str, sender_type: str = "user") -> MagicMock:
    msg = MagicMock()
    msg.sender_name = sender_name
    msg.content = content
    msg.sender_type = sender_type
    return msg


def _prompt_from(stream_mock: MagicMock) -> str:
    """Extract the user prompt the streaming client was invoked with."""
    return str(stream_mock.call_args.kwargs["messages"][0]["content"])


def _patch_manager() -> Any:
    patcher = patch("app.services.thinker.manager")
    mock_manager = patcher.start()
    mock_manager.get_speed_multiplier.return_value = 1.0
    mock_manager.is_conversation_active.return_value = True
    mock_manager.send_thinker_typing = AsyncMock()
    mock_manager.send_thinker_stopped_typing = AsyncMock()
    mock_manager.send_thinker_thinking = AsyncMock()
    mock_manager.send_thinker_message = AsyncMock()
    mock_manager.broadcast_to_conversation = AsyncMock()
    return patcher


class TestStreamingFirstMessageInstruction:
    """Lock the first-message anti-self-introduction contract for streaming."""

    @pytest.mark.asyncio
    async def test_initial_message_includes_no_introduce_instruction(self) -> None:
        """With empty history the streaming prompt carries the first-message rule.

        Covers the ``is_initial_message`` True branch of
        ``generate_response_with_streaming_thinking`` and asserts the exact
        instruction text reaches the model.
        """
        service, stream_mock = _service_with_capturing_stream()
        thinker = _make_thinker()

        patcher = _patch_manager()
        try:
            response, _cost = await service.generate_response_with_streaming_thinking(
                "conv-initial", thinker, [], "the examined life"
            )
        finally:
            patcher.stop()

        assert response == "A thoughtful reply."
        prompt = _prompt_from(stream_mock)
        assert "CRITICAL FOR FIRST MESSAGE - DO NOT INTRODUCE YOURSELF" in prompt
        assert f'Do NOT say things like "I am {thinker.name}"' in prompt

    @pytest.mark.asyncio
    async def test_non_initial_message_omits_no_introduce_instruction(self) -> None:
        """With prior history the streaming prompt omits the first-message rule.

        Covers the previously-untested ``is_initial_message`` False branch
        (``thinker.py`` 557->563): once a conversation has more than one
        message the anti-self-introduction block must be dropped, and the
        existing exchange should be present as conversation context.
        """
        service, stream_mock = _service_with_capturing_stream()
        thinker = _make_thinker()
        messages = [
            _make_message("Ada", "What is justice?"),
            _make_message("Plato", "Justice is harmony of the soul."),
        ]

        patcher = _patch_manager()
        try:
            response, _cost = await service.generate_response_with_streaming_thinking(
                "conv-established", thinker, messages, "the examined life"
            )
        finally:
            patcher.stop()

        assert response == "A thoughtful reply."
        prompt = _prompt_from(stream_mock)
        # The first-message instruction must NOT leak into an ongoing chat.
        assert "CRITICAL FOR FIRST MESSAGE - DO NOT INTRODUCE YOURSELF" not in prompt
        # ...and the prior exchange should be threaded into the prompt as context.
        assert "What is justice?" in prompt
        assert "Justice is harmony of the soul." in prompt
