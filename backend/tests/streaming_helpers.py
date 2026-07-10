"""Shared Anthropic streaming test doubles.

These helpers mimic the ``client.messages.stream(...)`` async-context-manager /
async-iterator protocol that ``ThinkerService.generate_response_with_streaming_thinking``
consumes. Before this module they were copy-pasted (byte-for-byte in several
cases) across:

- ``test_thinker_coverage_sprint_may11_2026.py``
- ``test_edge_cases_saturday_jun13_2026.py``
- ``test_integration_gaps_jul1_2026.py``

Centralizing them removes ~120 lines of duplication and gives every streaming
test one canonical, documented fake to build on.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.services.thinker import ThinkerService


def make_event(event_type: str, **fields: Any) -> MagicMock:
    """Build a streaming event mock with ``.type`` set and the given attributes.

    Example::

        make_event("content_block_delta", delta=make_delta(text="hi"))
    """
    event = MagicMock()
    event.type = event_type
    for key, value in fields.items():
        setattr(event, key, value)
    return event


def make_delta(*, thinking: str | None = None, text: str | None = None) -> MagicMock:
    """Build a ``content_block_delta`` delta exposing only the requested fields.

    The streaming handler probes ``hasattr(delta, "thinking")`` and
    ``hasattr(delta, "text")``. Because a plain ``MagicMock`` auto-creates
    attributes on access, ``spec`` is used to limit which attributes exist so
    each branch (thinking-only, text-only, or an "empty" delta that is neither)
    can be exercised in isolation.
    """
    spec: list[str] = []
    if thinking is not None:
        spec.append("thinking")
    if text is not None:
        spec.append("text")
    delta = MagicMock(spec=spec)
    if thinking is not None:
        delta.thinking = thinking
    if text is not None:
        delta.text = text
    return delta


class FakeStream:
    """An async context manager + async iterator mimicking Anthropic streaming."""

    def __init__(self, events: list[MagicMock], final_message: MagicMock) -> None:
        self._events = events
        self._final_message = final_message

    async def __aenter__(self) -> FakeStream:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def __aiter__(self) -> FakeStream:
        self._iter = iter(self._events)
        return self

    async def __anext__(self) -> MagicMock:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def get_final_message(self) -> MagicMock:
        return self._final_message


def service_with_fake_stream(
    events: list[MagicMock],
    final_content: list[Any] | None = None,
    input_tokens: int = 50,
    output_tokens: int = 30,
) -> tuple[ThinkerService, MagicMock]:
    """Build a ThinkerService whose Anthropic client returns a :class:`FakeStream`.

    Returns ``(service, stream_mock)`` so callers can both drive the streaming
    handler and inspect the arguments the prompt was streamed with via
    ``stream_mock.call_args``.
    """
    final_message = MagicMock()
    final_message.usage.input_tokens = input_tokens
    final_message.usage.output_tokens = output_tokens
    final_message.content = final_content if final_content is not None else []

    fake_stream = FakeStream(events, final_message)
    stream_mock = MagicMock(return_value=fake_stream)
    mock_client = MagicMock()
    mock_client.messages.stream = stream_mock

    service = ThinkerService()
    service._client = mock_client
    return service, stream_mock
