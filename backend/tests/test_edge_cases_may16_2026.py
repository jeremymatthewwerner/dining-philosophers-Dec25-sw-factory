"""Edge case tests for Saturday QA focus (May 16, 2026).

Targets remaining uncovered error/edge branches surfaced by the full-suite
coverage report:

- app/core/database.py lines 54-57: get_db rollback on exception inside the
  dependency yield block.
- app/main.py lines 63-65: lifespan handler logs and re-raises a startup
  exception.
- app/services/knowledge_research.py line 232: Wikipedia data merging includes
  the "sections" key when sub-fetch returns data.
- app/services/knowledge_research.py lines 166-167: nested error during the
  failed-status update is logged but not propagated.
- app/services/thinker.py line 1465: _should_prompt_user returns False when
  messages_since_user is below the dynamic threshold.
- app/services/thinker.py line 1431: _get_last_user_message_timestamp returns
  0.0 when no user messages are present.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from app.services.knowledge_research import KnowledgeResearchService
from app.services.thinker import ThinkerService

# ---------------------------------------------------------------------------
# app/core/database.py - get_db rollback path
# ---------------------------------------------------------------------------


class TestGetDbRollbackPath:
    """Verify get_db rolls back on exception inside the dependency."""

    @pytest.mark.asyncio
    async def test_get_db_rolls_back_on_exception(self) -> None:
        """get_db must call rollback (not commit) when the consumer raises.

        Edge case: error path of an async generator dependency. The rollback
        + re-raise lines (55-57) only execute when the caller throws inside
        the `async with` block.
        """
        from app.core import database as db_module

        # Fake session capturing whether commit/rollback was invoked.
        fake_session = MagicMock()
        fake_session.commit = AsyncMock()
        fake_session.rollback = AsyncMock()

        @asynccontextmanager
        async def fake_sessionmaker():  # type: ignore[no-untyped-def]
            yield fake_session

        with patch.object(db_module, "async_session_maker", fake_sessionmaker):
            gen = db_module.get_db()
            session = await gen.__anext__()
            assert session is fake_session

            # Simulate the FastAPI dependency consumer raising.
            with pytest.raises(RuntimeError, match="boom"):
                await gen.athrow(RuntimeError("boom"))

        fake_session.rollback.assert_awaited_once()
        fake_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_db_commits_on_clean_exit(self) -> None:
        """Companion test: clean exit takes the commit branch (line 54).

        Ensures we are not accidentally swallowing the happy path while
        exercising the failure branch.
        """
        from app.core import database as db_module

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()
        fake_session.rollback = AsyncMock()

        @asynccontextmanager
        async def fake_sessionmaker():  # type: ignore[no-untyped-def]
            yield fake_session

        with patch.object(db_module, "async_session_maker", fake_sessionmaker):
            gen = db_module.get_db()
            await gen.__anext__()
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

        fake_session.commit.assert_awaited_once()
        fake_session.rollback.assert_not_called()


# ---------------------------------------------------------------------------
# app/main.py - lifespan exception propagation
# ---------------------------------------------------------------------------


class TestLifespanStartupFailure:
    """Verify the lifespan handler logs and re-raises startup errors."""

    @pytest.mark.asyncio
    async def test_lifespan_reraises_init_db_error(self) -> None:
        """If init_db() raises, lifespan must log the failure and re-raise.

        Edge case: startup error path. Without this branch covered, a broken
        DB at boot would be silently swallowed.
        """
        from app import main as main_module

        with (
            patch.object(main_module, "init_db", AsyncMock(side_effect=RuntimeError("db down"))),
            patch.object(main_module, "create_admin_user", AsyncMock()) as mock_admin,
            patch.object(main_module.logger, "error") as mock_log_error,
        ):
            cm = main_module.lifespan(FastAPI())
            with pytest.raises(RuntimeError, match="db down"):
                await cm.__aenter__()

            # create_admin_user should NOT have run if init_db failed.
            mock_admin.assert_not_called()
            # logger.error must have been called with the failure context.
            assert mock_log_error.called
            err_args = mock_log_error.call_args
            assert "Startup failed" in err_args.args[0]
            assert err_args.kwargs.get("exc_info") is True


# ---------------------------------------------------------------------------
# app/services/knowledge_research.py - _fetch_wikipedia_data sections + nested
# error handler
# ---------------------------------------------------------------------------


class TestKnowledgeResearchEdgeCases:
    """Edge cases for the knowledge research service."""

    @pytest.mark.asyncio
    async def test_fetch_wikipedia_data_includes_sections(self) -> None:
        """When _fetch_wikipedia_sections returns data, it's merged into the
        result under the 'sections' key (line 232).

        Edge case: many Wikipedia pages have rich section data; coverage only
        previously hit the no-sections branch.
        """
        service = KnowledgeResearchService()

        # Mock the search + content responses to drive into the "page found"
        # branch. The page id must NOT be "-1".
        search_response = MagicMock()
        search_response.json = MagicMock(
            return_value={
                "query": {"search": [{"title": "Socrates"}]},
            }
        )
        content_response = MagicMock()
        content_response.json = MagicMock(
            return_value={
                "query": {
                    "pages": {
                        "12345": {
                            "title": "Socrates",
                            "extract": "Ancient Greek philosopher.",
                            "thumbnail": {"source": "https://example.com/socrates.jpg"},
                        }
                    }
                }
            }
        )

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = False
        mock_client.get = AsyncMock(side_effect=[search_response, content_response])

        with (
            patch(
                "app.services.knowledge_research.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch.object(
                service,
                "_fetch_wikipedia_sections",
                AsyncMock(return_value={"Philosophy": "Section 1: Philosophy"}),
            ) as mock_sections,
        ):
            result = await service._fetch_wikipedia_data("Socrates")

        assert result is not None
        assert result["title"] == "Socrates"
        assert result["image_url"] == "https://example.com/socrates.jpg"
        # The sections branch must have populated the dict.
        assert "sections" in result
        assert result["sections"] == {"Philosophy": "Section 1: Philosophy"}
        mock_sections.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_research_thinker_swallows_nested_error_during_failure_update(
        self,
    ) -> None:
        """If marking knowledge FAILED itself errors, the inner exception is
        logged but does not propagate (lines 166-167).

        Edge case: cascading DB failure should not crash the background task.
        """
        service = KnowledgeResearchService()

        # async_session() is called once for the outer try (raises during
        # get_or_create_knowledge) and again from inside the except handler
        # (raises immediately, hitting the inner-except on lines 166-167).
        call_count = {"n": 0}

        @asynccontextmanager
        async def stateful_session():  # type: ignore[no-untyped-def]
            call_count["n"] += 1
            if call_count["n"] == 1:
                fake_db = MagicMock()
                fake_db.commit = AsyncMock()
                yield fake_db
            else:
                raise RuntimeError("session unavailable")

        with (
            patch("app.services.knowledge_research.async_session", stateful_session),
            patch.object(
                service,
                "get_or_create_knowledge",
                AsyncMock(side_effect=RuntimeError("primary failure")),
            ),
        ):
            # Must NOT raise; nested-error path swallows everything.
            await service._research_thinker("Socrates")

        # Both sessions were attempted (outer success + inner failing).
        assert call_count["n"] >= 2


# ---------------------------------------------------------------------------
# app/services/thinker.py - small helper edge cases
# ---------------------------------------------------------------------------


class TestThinkerHelperEdgeCases:
    """Pure-function edge cases on ThinkerService helpers."""

    def _make_message(self, sender_type: str, when: datetime | None = None) -> MagicMock:
        msg = MagicMock()
        msg.sender_type = sender_type
        msg.created_at = when
        return msg

    def test_get_last_user_message_timestamp_no_user_messages(self) -> None:
        """_get_last_user_message_timestamp returns 0.0 when no user has
        spoken (line 1431).

        Edge case: brand-new conversations and thinker-only logs.
        """
        service = ThinkerService.__new__(ThinkerService)
        messages = [
            self._make_message("thinker", datetime(2026, 5, 16, tzinfo=UTC)),
            self._make_message("thinker", datetime(2026, 5, 16, tzinfo=UTC)),
        ]
        assert service._get_last_user_message_timestamp(messages) == 0.0

    def test_get_last_user_message_timestamp_returns_latest_user_msg(self) -> None:
        """Companion happy path: returns the most recent user message ts."""
        service = ThinkerService.__new__(ThinkerService)
        first_user_ts = datetime(2026, 5, 16, 10, 0, tzinfo=UTC)
        last_user_ts = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
        messages = [
            self._make_message("user", first_user_ts),
            self._make_message("thinker", datetime(2026, 5, 16, 11, 0, tzinfo=UTC)),
            self._make_message("user", last_user_ts),
            self._make_message("thinker", datetime(2026, 5, 16, 13, 0, tzinfo=UTC)),
        ]
        assert service._get_last_user_message_timestamp(messages) == last_user_ts.timestamp()

    def test_should_prompt_user_below_threshold_returns_false(self) -> None:
        """_should_prompt_user returns False when messages_since_user is below
        the dynamic threshold (line 1465).

        Edge case: protects against premature user-prompting in active chats.
        """
        service = ThinkerService.__new__(ThinkerService)

        # 6 total messages but the user just spoke — only 1 thinker message
        # since user, well below threshold=max(4, int(8/speed^0.3)).
        messages = [
            self._make_message("user"),
            self._make_message("thinker"),
            self._make_message("thinker"),
            self._make_message("thinker"),
            self._make_message("user"),  # most recent
            self._make_message("thinker"),
        ]
        # speed_mult=1.0 → threshold=8; messages_since_user=1.
        assert service._should_prompt_user(messages, 1.0) is False

    def test_should_prompt_user_too_few_messages_returns_false(self) -> None:
        """Short conversations never prompt (covers line 1457 guard)."""
        service = ThinkerService.__new__(ThinkerService)
        messages = [self._make_message("thinker") for _ in range(3)]
        assert service._should_prompt_user(messages, 1.0) is False

    def test_should_prompt_user_threshold_met_respects_random(self) -> None:
        """When threshold is met, random.random() controls the outcome —
        force True/False to lock down both branches deterministically.
        """
        service = ThinkerService.__new__(ThinkerService)
        # 10 thinker messages since user.
        messages = [self._make_message("user")] + [self._make_message("thinker") for _ in range(10)]

        with patch("app.services.thinker.random.random", return_value=0.0):
            assert service._should_prompt_user(messages, 1.0) is True
        with patch("app.services.thinker.random.random", return_value=0.99):
            assert service._should_prompt_user(messages, 1.0) is False

    def test_count_messages_since_user_counts_trailing_thinkers(self) -> None:
        """Sanity check for _count_messages_since_user used by the prompt
        decision: counts only trailing thinker messages.
        """
        service = ThinkerService.__new__(ThinkerService)
        messages = [
            self._make_message("user"),
            self._make_message("thinker"),
            self._make_message("user"),
            self._make_message("thinker"),
            self._make_message("thinker"),
            self._make_message("thinker"),
        ]
        assert service._count_messages_since_user(messages) == 3
