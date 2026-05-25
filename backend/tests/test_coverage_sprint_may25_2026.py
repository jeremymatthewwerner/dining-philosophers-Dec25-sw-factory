"""Coverage sprint tests for May 25, 2026 (Monday QA).

Target file: app/services/knowledge_research.py

These tests fill specific branch/line gaps in the KnowledgeResearchService
that are not currently exercised by the existing test suite:

- trigger_research cleanup callback when the name has already been removed
  from _active_tasks before the task finishes (line 107->exit branch)
- _research_thinker when _fetch_wikipedia_data returns None — the "no
  wikipedia data" branch (140->149) where research_data stays empty but
  status still flips to COMPLETE
- _research_thinker outer-except where get_knowledge inside the error
  handler returns None (the failed_knowledge falsy branch, 162->exit)
- _fetch_wikipedia_data: continue when page_id == "-1" sentinel (line 215)
- _fetch_wikipedia_data: returns None when every page is the "-1" sentinel
  (line 236)
- _fetch_wikipedia_sections: iteration over real "interesting" section
  titles (lines 292-312), including a non-matching section that is skipped
- _fetch_wikipedia_sections: exception path returns None (lines 316-318)

All tests use mocks for httpx.AsyncClient / async_session so they run fast
and offline (no Wikipedia traffic).
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import ResearchStatus, ThinkerKnowledge
from app.services.knowledge_research import KnowledgeResearchService

# ---------------------------------------------------------------------------
# trigger_research cleanup callback — name absent branch (line 107->exit)
# ---------------------------------------------------------------------------


class TestTriggerResearchCleanup:
    """Cleanup callback edge cases for trigger_research."""

    @pytest.mark.asyncio
    async def test_cleanup_callback_when_name_already_removed(self) -> None:
        """When the cleanup callback fires after the entry was already cleared
        from _active_tasks (e.g. by a second trigger that replaced it), the
        ``if name in self._active_tasks`` guard short-circuits without raising.

        Covers the 107->exit branch.
        """
        service = KnowledgeResearchService()

        completed = asyncio.Event()

        async def fake_research(_name: str) -> None:
            # Wait until we explicitly let the task finish so we can mutate
            # _active_tasks under the callback's nose.
            await completed.wait()

        with patch.object(service, "_research_thinker", side_effect=fake_research):
            service.trigger_research("Plato")
            assert "Plato" in service._active_tasks

            # Simulate a race: another caller cleared the dict before the
            # done-callback runs.
            del service._active_tasks["Plato"]

            # Let the task complete; the cleanup callback should *not* raise.
            completed.set()
            # Yield enough to run the callback and any pending callbacks.
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        assert "Plato" not in service._active_tasks


# ---------------------------------------------------------------------------
# _research_thinker — wikipedia returns None branch (line 140->149)
# ---------------------------------------------------------------------------


class TestResearchThinkerNoWikipedia:
    """Cover _research_thinker when no wikipedia data is found."""

    @pytest.mark.asyncio
    async def test_research_thinker_marks_complete_with_empty_data_when_wikipedia_none(
        self, db_session: Any
    ) -> None:
        """If _fetch_wikipedia_data returns None, the service must still flip
        status to COMPLETE and leave research_data empty (the falsy branch
        of ``if wikipedia_data:`` on line 140).
        """
        service = KnowledgeResearchService()

        # Pre-seed a pending entry so get_or_create_knowledge returns it.
        knowledge = ThinkerKnowledge(
            name="ObscurePerson",
            status=ResearchStatus.PENDING,
            research_data={},
        )
        db_session.add(knowledge)
        await db_session.commit()

        # Build an async-context-manager wrapper around our actual db_session
        # so the production code's ``async with async_session() as db`` works.
        @asynccontextmanager
        async def session_cm() -> Any:
            yield db_session

        with (
            patch.object(service, "_fetch_wikipedia_data", AsyncMock(return_value=None)),
            patch("app.services.knowledge_research.async_session", session_cm),
        ):
            await service._research_thinker("ObscurePerson")

        await db_session.refresh(knowledge)
        assert knowledge.status == ResearchStatus.COMPLETE
        # The falsy branch means wikipedia key was never added.
        assert "wikipedia" not in (knowledge.research_data or {})
        assert knowledge.error_message is None


# ---------------------------------------------------------------------------
# _research_thinker — failure path, get_knowledge returns None (162->exit)
# ---------------------------------------------------------------------------


class TestResearchThinkerFailureWithoutKnowledge:
    """Cover the inner failure path when no row exists to mark FAILED."""

    @pytest.mark.asyncio
    async def test_failure_handler_no_op_when_get_knowledge_returns_none(self) -> None:
        """If the primary flow raises but the error-handler's get_knowledge()
        returns None (e.g. the row was deleted concurrently), the handler
        silently skips the status update and does NOT re-raise.

        Covers the 162->exit branch (``if failed_knowledge:`` falsy).
        """
        service = KnowledgeResearchService()

        primary_db = MagicMock()
        primary_db.commit = AsyncMock()
        error_db = MagicMock()
        error_db.commit = AsyncMock()

        sessions: list[MagicMock] = [primary_db, error_db]

        @asynccontextmanager
        async def session_cm() -> Any:
            yield sessions.pop(0)

        with (
            patch("app.services.knowledge_research.async_session", session_cm),
            patch.object(
                service,
                "get_or_create_knowledge",
                AsyncMock(side_effect=RuntimeError("primary boom")),
            ),
            patch.object(
                service,
                "get_knowledge",
                AsyncMock(return_value=None),
            ),
        ):
            # Must not raise — the failure path swallows everything when
            # there's no row to update.
            await service._research_thinker("GhostPerson")

        # The error db's commit should NOT have been called since
        # failed_knowledge was None.
        error_db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# _fetch_wikipedia_data — page_id == "-1" sentinel handling (lines 215, 236)
# ---------------------------------------------------------------------------


class TestFetchWikipediaSentinelPage:
    """Cover the page_id == "-1" Wikipedia "missing page" sentinel."""

    @pytest.mark.asyncio
    async def test_returns_none_when_only_sentinel_page_present(self) -> None:
        """When Wikipedia returns a single page keyed by "-1" (its sentinel
        for "no real page"), the loop's ``continue`` skips it and the
        function returns None (lines 215 and 236).
        """
        service = KnowledgeResearchService()

        search_response = MagicMock()
        search_response.json = MagicMock(return_value={"query": {"search": [{"title": "Unknown"}]}})
        content_response = MagicMock()
        content_response.json = MagicMock(
            return_value={
                "query": {
                    "pages": {
                        "-1": {"title": "Unknown", "missing": ""},
                    }
                }
            }
        )

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = False
        mock_client.get = AsyncMock(side_effect=[search_response, content_response])

        with patch(
            "app.services.knowledge_research.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await service._fetch_wikipedia_data("Unknown")

        assert result is None
        # Both API calls were made.
        assert mock_client.get.await_count == 2


# ---------------------------------------------------------------------------
# _fetch_wikipedia_sections — interesting-section iteration (lines 292-312)
# ---------------------------------------------------------------------------


class TestFetchWikipediaSectionsIteration:
    """Cover the section-filtering loop in _fetch_wikipedia_sections."""

    @pytest.mark.asyncio
    async def test_includes_only_interesting_sections_and_skips_others(self) -> None:
        """The section loop keeps section titles that match a known-interesting
        keyword (Philosophy, Works, etc.) and skips ones that don't (e.g.
        References). Covers the matched/unmatched branches in the loop body
        (lines 292-312).
        """
        service = KnowledgeResearchService()

        sections_response = MagicMock()
        sections_response.json = MagicMock(
            return_value={
                "parse": {
                    "sections": [
                        {"line": "Philosophy", "index": "1"},
                        # Not in the interesting list — must be skipped.
                        {"line": "References", "index": "2"},
                        {"line": "Major works", "index": "3"},
                        {"line": "External links", "index": "4"},
                    ]
                }
            }
        )
        # The follow-up extract call is fired for each matched section but
        # its body isn't parsed in detail; the function only stores the
        # title marker.
        extract_response = MagicMock()
        extract_response.json = MagicMock(return_value={"query": {"pages": {}}})

        mock_client = AsyncMock()
        # 1 sections call + 2 follow-up extract calls (Philosophy + Major works)
        mock_client.get = AsyncMock(
            side_effect=[sections_response, extract_response, extract_response]
        )

        result = await service._fetch_wikipedia_sections(
            mock_client, "https://en.wikipedia.org/w/api.php", "Socrates"
        )

        assert result is not None
        # Interesting titles preserved with the expected marker format.
        assert result.get("Philosophy") == "Section 1: Philosophy"
        assert result.get("Major works") == "Section 3: Major works"
        # Non-interesting titles dropped.
        assert "References" not in result
        assert "External links" not in result
        # 1 sections query + 2 content queries for the matched sections.
        assert mock_client.get.await_count == 3

    @pytest.mark.asyncio
    async def test_returns_none_when_no_interesting_sections_match(self) -> None:
        """If every section title is uninteresting, the function returns None
        rather than an empty dict (the ``result if result else None`` branch).
        """
        service = KnowledgeResearchService()

        sections_response = MagicMock()
        sections_response.json = MagicMock(
            return_value={
                "parse": {
                    "sections": [
                        {"line": "References", "index": "1"},
                        {"line": "External links", "index": "2"},
                        {"line": "See also", "index": "3"},
                    ]
                }
            }
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=sections_response)

        result = await service._fetch_wikipedia_sections(
            mock_client, "https://en.wikipedia.org/w/api.php", "Obscure"
        )

        assert result is None
        # Only the initial sections query — no per-section fetches.
        assert mock_client.get.await_count == 1


# ---------------------------------------------------------------------------
# _fetch_wikipedia_sections — exception swallowed (lines 316-318)
# ---------------------------------------------------------------------------


class TestFetchWikipediaSectionsExceptionPath:
    """Cover the broad-except in _fetch_wikipedia_sections."""

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self) -> None:
        """If the HTTP client raises, _fetch_wikipedia_sections swallows the
        exception and returns None (lines 316-318).

        This guards against transient Wikipedia failures crashing the
        background research loop.
        """
        service = KnowledgeResearchService()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("network down"))

        result = await service._fetch_wikipedia_sections(
            mock_client, "https://en.wikipedia.org/w/api.php", "Anyone"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_malformed_response(self) -> None:
        """If the JSON response is missing the ``parse`` key shape entirely,
        the iteration is empty and returns None — verifying the result-falsy
        return at the end of the function.
        """
        service = KnowledgeResearchService()

        empty_response = MagicMock()
        # No ``parse`` key at all.
        empty_response.json = MagicMock(return_value={})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=empty_response)

        result = await service._fetch_wikipedia_sections(
            mock_client, "https://en.wikipedia.org/w/api.php", "Anyone"
        )

        assert result is None


# ---------------------------------------------------------------------------
# _fetch_wikipedia_data — sentinel-then-real-page combination
# ---------------------------------------------------------------------------


class TestFetchWikipediaMixedPages:
    """Mixed -1 and real page IDs in Wikipedia response."""

    @pytest.mark.asyncio
    async def test_skips_sentinel_then_processes_real_page(self) -> None:
        """When pages contain both the ``-1`` sentinel and a real page id,
        the loop continues past the sentinel and processes the real page.

        This guards both the line-215 ``continue`` and the success-path
        early-return at line 234.
        """
        service = KnowledgeResearchService()

        search_response = MagicMock()
        search_response.json = MagicMock(
            return_value={"query": {"search": [{"title": "RealPerson"}]}}
        )
        # Mix of "-1" (sentinel) and a real page id. Dict iteration order in
        # Python 3.7+ is insertion order, so "-1" comes first — that
        # exercises the ``continue`` before we land on the real entry.
        content_response = MagicMock()
        content_response.json = MagicMock(
            return_value={
                "query": {
                    "pages": {
                        "-1": {"title": "Stub", "missing": ""},
                        "42": {
                            "title": "RealPerson",
                            "extract": "A real person summary.",
                        },
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
            # Bypass the sections call — not under test here.
            patch.object(service, "_fetch_wikipedia_sections", AsyncMock(return_value=None)),
        ):
            result = await service._fetch_wikipedia_data("RealPerson")

        assert result is not None
        assert result["title"] == "RealPerson"
        assert result["page_id"] == "42"
        # fetched_at is a fresh ISO timestamp — just confirm shape, not value.
        datetime.fromisoformat(result["fetched_at"])
        # No thumbnail key when the page didn't include one.
        assert "image_url" not in result
        # No sections key when the helper returned None.
        assert "sections" not in result
        # The summary is truncated/limited but for a short input is unchanged.
        assert result["summary"] == "A real person summary."


# ---------------------------------------------------------------------------
# Sanity: confirm UTC timestamp shape (defensive — guards datetime.now(UTC)
# usage in result construction)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_wikipedia_data_timestamp_is_utc_aware() -> None:
    """The ``fetched_at`` timestamp on a successful fetch is a UTC-aware
    ISO-8601 string. Regression guard for ``datetime.now(UTC)`` calls.
    """
    service = KnowledgeResearchService()

    search_response = MagicMock()
    search_response.json = MagicMock(return_value={"query": {"search": [{"title": "Person"}]}})
    content_response = MagicMock()
    content_response.json = MagicMock(
        return_value={
            "query": {
                "pages": {
                    "7": {"title": "Person", "extract": "Summary."},
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
        patch.object(service, "_fetch_wikipedia_sections", AsyncMock(return_value=None)),
    ):
        result = await service._fetch_wikipedia_data("Person")

    assert result is not None
    parsed = datetime.fromisoformat(result["fetched_at"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == UTC.utcoffset(parsed)
