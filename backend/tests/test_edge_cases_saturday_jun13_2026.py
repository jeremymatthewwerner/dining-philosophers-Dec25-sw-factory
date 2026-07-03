"""Edge-case tests (June 13, 2026 - Saturday QA).

Targets the remaining reachable partial-branch gaps in the codebase:

1. ``ThinkerService.generate_response_with_streaming_thinking`` streaming loop
   (``app/services/thinker.py`` lines ~616-664):
   - throttled thinking delta (no update sent because the interval has not elapsed)
   - thinking delta too short for a meaningful display preview
   - a content_block_delta carrying neither ``thinking`` nor ``text``
   - a ``message_delta`` event without ``usage``
   - a final-message content block that is not a ``ThinkingBlock``

2. ``init_db`` (``app/core/database.py`` line 98->107): the fall-back to
   ``create_all`` when ``alembic.ini`` is absent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.thinker import ThinkerService
from tests.mock_factories import make_content_delta as _make_delta
from tests.mock_factories import make_streaming_event as _make_event
from tests.mock_factories import make_thinker as _make_thinker

# ---------------------------------------------------------------------------
# Streaming helpers (mirrors test_thinker_coverage_sprint_may11_2026.py)
# ---------------------------------------------------------------------------


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


def _service_with_fake_stream(
    events: list[MagicMock],
    final_content: list[Any] | None = None,
    input_tokens: int = 50,
    output_tokens: int = 30,
) -> ThinkerService:
    """Build a ThinkerService whose Anthropic client returns a FakeStream."""
    final_message = MagicMock()
    final_message.usage.input_tokens = input_tokens
    final_message.usage.output_tokens = output_tokens
    final_message.content = final_content if final_content is not None else []

    fake_stream = _FakeStream(events, final_message)
    mock_client = MagicMock()
    mock_client.messages.stream = MagicMock(return_value=fake_stream)

    service = ThinkerService()
    service._client = mock_client
    return service


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


# ---------------------------------------------------------------------------
# Streaming event-handler edge cases
# ---------------------------------------------------------------------------


class TestStreamingThinkingEdgeBranches:
    """Cover the partial branches inside the streaming event loop."""

    @pytest.mark.asyncio
    async def test_second_thinking_delta_is_throttled(self) -> None:
        """A second thinking delta arriving within the interval is throttled (636->616).

        The first long thinking delta passes the throttle and records the
        timestamp; the second arrives microseconds later (well under the 2s
        interval) so no additional update is sent for it.
        """
        long_thought = (
            "Now I should consider the implications of this very carefully. "
            "Let me think about what the user is really asking here today. "
            "This requires more thought than initially apparent to me."
        )
        events = [
            _make_event("content_block_delta", delta=_make_delta(thinking=long_thought)),
            _make_event("content_block_delta", delta=_make_delta(thinking=" And more.")),
            _make_event("content_block_delta", delta=_make_delta(text="Answer")),
        ]
        service = _service_with_fake_stream(events)
        thinker = _make_thinker()

        patcher, mock_manager = _patch_manager()
        try:
            response, _cost = await service.generate_response_with_streaming_thinking(
                "conv-throttle", thinker, [], "philosophy"
            )
        finally:
            patcher.stop()

        assert response == "Answer"
        # Exactly one update sent: the first delta. The second was throttled.
        assert mock_manager.send_thinker_thinking.await_count == 1

    @pytest.mark.asyncio
    async def test_short_thinking_delta_sends_no_update(self) -> None:
        """A thinking delta too short for a preview skips the send (641->645).

        ``_extract_thinking_display`` returns "" for text < 80 chars, so the
        throttle passes but ``display_thinking`` is falsy and no update fires.
        """
        events = [
            _make_event("content_block_delta", delta=_make_delta(thinking="Hmm.")),
            _make_event("content_block_delta", delta=_make_delta(text="Done")),
        ]
        service = _service_with_fake_stream(events)
        thinker = _make_thinker()

        patcher, mock_manager = _patch_manager()
        try:
            response, _cost = await service.generate_response_with_streaming_thinking(
                "conv-short", thinker, [], "philosophy"
            )
        finally:
            patcher.stop()

        assert response == "Done"
        # Thinking text was too short to display, so nothing was sent.
        assert mock_manager.send_thinker_thinking.await_count == 0

    @pytest.mark.asyncio
    async def test_empty_delta_is_ignored(self) -> None:
        """A content_block_delta with neither thinking nor text is a no-op (646->616)."""
        events = [
            _make_event("content_block_delta", delta=_make_delta()),
            _make_event("content_block_delta", delta=_make_delta(text="Hello")),
        ]
        service = _service_with_fake_stream(events)
        thinker = _make_thinker()

        patcher, _mock_manager = _patch_manager()
        try:
            response, _cost = await service.generate_response_with_streaming_thinking(
                "conv-empty", thinker, [], "philosophy"
            )
        finally:
            patcher.stop()

        # Only the text delta contributed.
        assert response == "Hello"

    @pytest.mark.asyncio
    async def test_message_delta_without_usage_is_ignored(self) -> None:
        """A message_delta event lacking usage info does not update tokens (649->616)."""
        no_usage_event = MagicMock()
        no_usage_event.type = "message_delta"
        no_usage_event.usage = None

        events = [
            _make_event("content_block_delta", delta=_make_delta(text="Hi")),
            no_usage_event,
        ]
        service = _service_with_fake_stream(events)
        thinker = _make_thinker()

        patcher, _mock_manager = _patch_manager()
        try:
            response, cost = await service.generate_response_with_streaming_thinking(
                "conv-nousage", thinker, [], "philosophy"
            )
        finally:
            patcher.stop()

        assert response == "Hi"
        # Final usage still comes from get_final_message(), so cost is positive.
        assert cost > 0

    @pytest.mark.asyncio
    async def test_non_thinking_block_does_not_add_thinking_cost(self) -> None:
        """A final content block that is not a ThinkingBlock adds no thinking tokens (662->661)."""
        non_thinking_block = MagicMock()  # not an instance of ThinkingBlock

        events = [
            _make_event("content_block_delta", delta=_make_delta(text="Plain answer.")),
        ]
        service = _service_with_fake_stream(
            events,
            final_content=[non_thinking_block],
            input_tokens=100,
            output_tokens=50,
        )
        thinker = _make_thinker()

        patcher, _mock_manager = _patch_manager()
        try:
            response, cost = await service.generate_response_with_streaming_thinking(
                "conv-noblock", thinker, [], "philosophy"
            )
        finally:
            patcher.stop()

        assert response == "Plain answer."
        # With no thinking tokens, cost is exactly input + output cost.
        expected = 100 * 0.000003 + 50 * 0.000015
        assert cost == pytest.approx(expected)


# ---------------------------------------------------------------------------
# init_db fall-back branch (database.py 98->107)
# ---------------------------------------------------------------------------


class TestInitDbNoAlembic:
    """Cover init_db's create_all fall-back when alembic.ini is absent."""

    @pytest.mark.asyncio
    async def test_init_db_uses_create_all_when_no_alembic_ini(self, tmp_path: Path) -> None:
        """init_db should skip migrations and call create_all when alembic.ini is missing."""
        from app.core import database

        # Point backend_dir at an empty tmp dir so ``alembic.ini`` does not exist.
        assert not (tmp_path / "alembic.ini").exists()

        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.core.database.Path") as mock_path_cls,
            patch("app.core.database.run_migrations") as mock_run,
            patch("app.core.database.engine") as mock_engine,
        ):
            mock_file_path = MagicMock()
            mock_file_path.parent.parent.parent = tmp_path
            mock_path_cls.return_value = mock_file_path
            mock_engine.begin.return_value = mock_ctx

            await database.init_db()

            # Migrations are never attempted because alembic.ini is absent.
            mock_run.assert_not_called()
            # create_all is invoked via run_sync on the connection.
            mock_conn.run_sync.assert_called_once()
