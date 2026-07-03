"""Shared ``MagicMock`` factories for backend unit tests.

Many test modules (the flaky-hunt suites, edge-case suites, and thinker
streaming coverage suites) each grew their own private ``_make_thinker``,
``_make_message``, ``_make_event`` and ``_make_delta`` helpers. The bodies were
near-identical but drifted slightly over time, so a bug fixed in one copy was
easily missed in the others.

This module is the single home for those builders. Test modules import the
factory they need and alias it back to the local ``_make_*`` name they already
use, so call sites stay unchanged:

    from tests.mock_factories import make_thinker as _make_thinker

All factories return plain ``MagicMock`` objects (or ``spec``-limited mocks
where a test needs ``hasattr`` probing to behave), matching what the original
inline helpers produced.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock


def make_thinker(
    name: str = "Socrates",
    *,
    bio: str = "Classical philosopher",
    positions: str = "Question everything",
    style: str = "Dialectic",
) -> MagicMock:
    """Build a mock thinker with stable profile attributes.

    ``name`` is the only field most callers care about; ``bio``/``positions``/
    ``style`` are populated with sensible defaults so tests that read them get
    real strings instead of auto-generated ``MagicMock`` attributes.
    """
    thinker = MagicMock()
    thinker.name = name
    thinker.bio = bio
    thinker.positions = positions
    thinker.style = style
    return thinker


def make_message(content: str, sender_name: str = "User") -> MagicMock:
    """Build a mock message exposing ``.content`` and ``.sender_name``."""
    message = MagicMock()
    message.content = content
    message.sender_name = sender_name
    return message


def make_streaming_event(event_type: str, **fields: Any) -> MagicMock:
    """Build a streaming event mock with ``.type`` and the given attributes."""
    event = MagicMock()
    event.type = event_type
    for key, value in fields.items():
        setattr(event, key, value)
    return event


def make_content_delta(*, thinking: str | None = None, text: str | None = None) -> MagicMock:
    """Build a ``content_block_delta`` delta exposing only the requested fields.

    The streaming handler probes ``hasattr(delta, "thinking")`` and
    ``hasattr(delta, "text")``; ``spec`` limits which attributes exist so an
    "empty" delta (neither field) can be constructed for the else-fall-through.
    """
    spec = []
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


def make_text_delta(text: str) -> MagicMock:
    """Build a ``content_block_delta`` delta exposing only ``text`` (no ``thinking``)."""
    delta = MagicMock(spec=["text"])
    delta.text = text
    return delta
