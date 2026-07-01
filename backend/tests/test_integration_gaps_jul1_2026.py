"""Integration-gap tests (July 1, 2026 - Wednesday QA).

The backend is already at ~99.66% coverage with every ``app/api/*`` endpoint
fully covered, so there are no wholly-untested endpoints left. What remains are
a couple of *reachable* branch paths inside ``app/services/thinker.py`` that the
existing suite never drives through a real integration path:

1. ``ThinkerService.generate_response_with_streaming_thinking`` line 557->563:
   the ``is_initial_message`` **False** branch. Every prior streaming test calls
   the method with an empty ``messages`` list (a brand-new conversation), so the
   "this is a continuing conversation, do NOT introduce yourself" prompt path
   (i.e. the branch where the special first-message instruction is *omitted*)
   was never exercised.

2. ``ThinkerService.suggest_thinkers`` line 250->242: the defensive branch taken
   when a parallel ``asyncio.gather(..., return_exceptions=True)`` task result is
   neither a ``list`` nor an ``Exception``. This guards against a malformed batch
   result silently corrupting the aggregation; it should be skipped without a
   crash.

Note on ``thinker.py:733`` (``if not sentence: continue`` in
``_split_response_into_bubbles``): this is effectively dead defensive code. The
method strips the whole text up front and then splits on ``(?<=[.!?])\\s+``; a
brute-force search over 200k random inputs found no text that yields a
strip-empty fragment, so the ``continue`` is unreachable and intentionally left
uncovered.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.thinker import ThinkerService

# ---------------------------------------------------------------------------
# Streaming fakes (mirrors test_edge_cases_saturday_jun13_2026.py)
# ---------------------------------------------------------------------------


def _make_event(event_type: str, **fields: Any) -> MagicMock:
    """Build a streaming event mock with the given attributes."""
    event = MagicMock()
    event.type = event_type
    for key, value in fields.items():
        setattr(event, key, value)
    return event


def _make_text_delta(text: str) -> MagicMock:
    """A content_block_delta delta exposing only ``text`` (no ``thinking``)."""
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


def _service_with_capturing_stream(events: list[MagicMock]) -> tuple[ThinkerService, MagicMock]:
    """Build a ThinkerService whose client records the ``stream`` call args.

    Returns ``(service, stream_mock)`` so tests can inspect the prompt that was
    handed to Anthropic via ``stream_mock.call_args``.
    """
    final_message = MagicMock()
    final_message.usage.input_tokens = 50
    final_message.usage.output_tokens = 30
    final_message.content = []

    fake_stream = _FakeStream(events, final_message)
    stream_mock = MagicMock(return_value=fake_stream)
    mock_client = MagicMock()
    mock_client.messages.stream = stream_mock

    service = ThinkerService()
    service._client = mock_client
    return service, stream_mock


def _make_thinker() -> MagicMock:
    t = MagicMock()
    t.name = "Socrates"
    t.bio = "Classical philosopher"
    t.positions = "Question everything"
    t.style = "Dialectic"
    return t


def _make_message(sender_type: str, sender_name: str, content: str) -> MagicMock:
    """Build a Message-like mock understood by the prompt/style builders."""
    msg = MagicMock()
    msg.sender_type = sender_type
    msg.sender_name = sender_name
    msg.content = content
    return msg


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
    return patcher, mock_manager


# Marker text from the first-message-only instruction in the prompt builder.
_FIRST_MESSAGE_MARKER = "DO NOT INTRODUCE YOURSELF"


def _captured_prompt(stream_mock: MagicMock) -> str:
    """Extract the user prompt string handed to ``messages.stream``."""
    kwargs = stream_mock.call_args.kwargs
    return str(kwargs["messages"][0]["content"])


class TestStreamingInitialMessageBranch:
    """Cover thinker.py 557->563 (``is_initial_message`` True vs False)."""

    async def test_multi_message_history_omits_introduce_instruction(self) -> None:
        """With >1 prior message the first-message instruction is omitted (557->563).

        ``is_initial_message`` is ``len(messages) <= 1``; supplying a real
        two-message history makes it False, so the special "do not introduce
        yourself" block must NOT appear in the prompt, and the actual
        conversation history should be threaded in instead.
        """
        events = [_make_event("content_block_delta", delta=_make_text_delta("A reply."))]
        service, stream_mock = _service_with_capturing_stream(events)
        thinker = _make_thinker()
        messages = [
            _make_message("user", "Alice", "What is virtue?"),
            _make_message("thinker", "Plato", "Virtue is knowledge of the good."),
        ]

        patcher, _mock_manager = _patch_manager()
        try:
            response, _cost = await service.generate_response_with_streaming_thinking(
                "conv-multi", thinker, messages, "philosophy"
            )
        finally:
            patcher.stop()

        assert response == "A reply."
        prompt = _captured_prompt(stream_mock)
        # The first-message-only instruction is absent on a continuing convo.
        assert _FIRST_MESSAGE_MARKER not in prompt
        # The real conversation history was woven into the prompt.
        assert "What is virtue?" in prompt
        assert "Virtue is knowledge of the good." in prompt

    async def test_single_message_history_includes_introduce_instruction(self) -> None:
        """The True side of 557 as a contrast: a fresh convo keeps the guard.

        A single opening user message is still treated as the initial message
        (``len(messages) <= 1``), so the "do not introduce yourself" block is
        present. This pins the branch's two sides against each other.
        """
        events = [_make_event("content_block_delta", delta=_make_text_delta("Hello there."))]
        service, stream_mock = _service_with_capturing_stream(events)
        thinker = _make_thinker()
        messages = [_make_message("user", "Alice", "Kick things off.")]

        patcher, _mock_manager = _patch_manager()
        try:
            response, _cost = await service.generate_response_with_streaming_thinking(
                "conv-single", thinker, messages, "philosophy"
            )
        finally:
            patcher.stop()

        assert response == "Hello there."
        assert _FIRST_MESSAGE_MARKER in _captured_prompt(stream_mock)


class TestSuggestThinkersMalformedTaskResult:
    """Cover thinker.py 250->242 (non-list / non-exception gather result)."""

    async def test_non_list_task_result_is_skipped(self) -> None:
        """A parallel task returning ``None`` is ignored, not crashed on (250->242).

        ``suggest_thinkers`` with ``count > 2`` fans out to
        ``_suggest_single_batch`` and gathers with ``return_exceptions=True``.
        If a batch resolves to something that is neither a ``list`` nor an
        ``Exception`` (here ``None``), the aggregation loop must skip it via the
        ``elif isinstance(result, Exception)`` being False and fall through back
        to the loop — leaving only the valid batch's suggestions.
        """
        service = ThinkerService()
        # A truthy client so we take the real fan-out path (not the empty guard).
        service._client = MagicMock()

        good = MagicMock()
        good.name = "Plato"

        # count=3 -> two batches (2 + 1). First resolves to a malformed None,
        # second returns a valid single-suggestion list.
        batch_mock = AsyncMock(side_effect=[None, [good]])
        with patch.object(service, "_suggest_single_batch", batch_mock):
            result = await service.suggest_thinkers("ethics", count=3)

        # The None batch was skipped without error; only the valid one survived.
        assert result == [good]
        assert batch_mock.await_count == 2

    async def test_all_non_list_results_yield_empty(self) -> None:
        """When every batch is malformed, the result is empty (no crash).

        Both gathered tasks return non-list, non-exception values, so the
        aggregation loop skips both and ``suggest_thinkers`` returns ``[]``
        rather than raising.
        """
        service = ThinkerService()
        service._client = MagicMock()

        batch_mock = AsyncMock(side_effect=[None, None])
        with patch.object(service, "_suggest_single_batch", batch_mock):
            result = await service.suggest_thinkers("ethics", count=3)

        assert result == []
        assert batch_mock.await_count == 2
