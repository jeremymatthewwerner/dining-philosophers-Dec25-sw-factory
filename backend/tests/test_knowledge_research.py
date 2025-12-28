"""Tests for the knowledge research service and API endpoints."""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ResearchStatus, ThinkerKnowledge
from app.services.knowledge_research import KnowledgeResearchService


class TestThinkerKnowledgeModel:
    """Tests for the ThinkerKnowledge database model."""

    @pytest.mark.asyncio
    async def test_create_thinker_knowledge(self, async_session: AsyncSession) -> None:
        """Test creating a ThinkerKnowledge entry."""
        knowledge = ThinkerKnowledge(
            name="Test Thinker",
            status=ResearchStatus.PENDING,
            research_data={},
        )
        async_session.add(knowledge)
        await async_session.commit()

        assert knowledge.id is not None
        assert knowledge.name == "Test Thinker"
        assert knowledge.status == ResearchStatus.PENDING
        assert knowledge.research_data == {}
        assert knowledge.created_at is not None
        assert knowledge.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_research_data(self, async_session: AsyncSession) -> None:
        """Test updating research data in ThinkerKnowledge."""
        knowledge = ThinkerKnowledge(
            name="Socrates",
            status=ResearchStatus.PENDING,
            research_data={},
        )
        async_session.add(knowledge)
        await async_session.commit()

        # Update with research data
        knowledge.status = ResearchStatus.COMPLETE
        knowledge.research_data = {
            "wikipedia": {
                "summary": "Ancient Greek philosopher",
                "title": "Socrates",
            }
        }
        await async_session.commit()
        await async_session.refresh(knowledge)

        assert knowledge.status == ResearchStatus.COMPLETE
        assert "wikipedia" in knowledge.research_data
        assert knowledge.research_data["wikipedia"]["summary"] == "Ancient Greek philosopher"

    @pytest.mark.asyncio
    async def test_unique_name_constraint(self, async_session: AsyncSession) -> None:
        """Test that name must be unique."""
        from sqlalchemy.exc import IntegrityError

        knowledge1 = ThinkerKnowledge(
            name="Unique Name",
            status=ResearchStatus.PENDING,
            research_data={},
        )
        async_session.add(knowledge1)
        await async_session.commit()

        knowledge2 = ThinkerKnowledge(
            name="Unique Name",  # Same name
            status=ResearchStatus.PENDING,
            research_data={},
        )
        async_session.add(knowledge2)

        with pytest.raises(IntegrityError):
            await async_session.commit()


class TestKnowledgeResearchService:
    """Tests for the KnowledgeResearchService."""

    @pytest.mark.asyncio
    async def test_get_knowledge_returns_none_when_not_found(
        self, async_session: AsyncSession
    ) -> None:
        """Test get_knowledge returns None for unknown thinker."""
        service = KnowledgeResearchService()
        knowledge = await service.get_knowledge(async_session, "Unknown Person")
        assert knowledge is None

    @pytest.mark.asyncio
    async def test_get_or_create_creates_new_entry(self, async_session: AsyncSession) -> None:
        """Test get_or_create_knowledge creates a new pending entry."""
        service = KnowledgeResearchService()
        knowledge = await service.get_or_create_knowledge(async_session, "New Thinker")

        assert knowledge is not None
        assert knowledge.name == "New Thinker"
        assert knowledge.status == ResearchStatus.PENDING
        assert knowledge.research_data == {}

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing(self, async_session: AsyncSession) -> None:
        """Test get_or_create_knowledge returns existing entry."""
        service = KnowledgeResearchService()

        # Create first entry
        knowledge1 = await service.get_or_create_knowledge(async_session, "Existing Thinker")
        knowledge_id = knowledge1.id

        # Try to get or create again - should return existing
        knowledge2 = await service.get_or_create_knowledge(async_session, "Existing Thinker")

        assert knowledge2.id == knowledge_id

    def test_is_stale_pending_entry(self) -> None:
        """Test is_stale returns True for pending entries."""
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.PENDING,
            research_data={},
        )
        assert service.is_stale(knowledge) is True

    def test_is_stale_in_progress_entry(self) -> None:
        """Test is_stale returns True for in-progress entries."""
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.IN_PROGRESS,
            research_data={},
        )
        assert service.is_stale(knowledge) is True

    def test_is_stale_complete_recent_entry(self) -> None:
        """Test is_stale returns False for recently completed entries."""
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.COMPLETE,
            research_data={"test": "data"},
        )
        # Manually set updated_at to recent time
        knowledge.updated_at = datetime.now(UTC)
        assert service.is_stale(knowledge) is False

    def test_is_stale_complete_old_entry(self) -> None:
        """Test is_stale returns True for old completed entries."""
        service = KnowledgeResearchService()
        knowledge = ThinkerKnowledge(
            name="Test",
            status=ResearchStatus.COMPLETE,
            research_data={"test": "data"},
        )
        # Set updated_at to 60 days ago
        knowledge.updated_at = datetime.now(UTC) - timedelta(days=60)
        assert service.is_stale(knowledge) is True

    @pytest.mark.asyncio
    async def test_trigger_research_starts_background_task(self) -> None:
        """Test trigger_research starts a background task."""
        service = KnowledgeResearchService()

        with patch.object(service, "_research_thinker", new_callable=AsyncMock) as mock_research:
            # Create a real asyncio task for the test
            mock_research.return_value = None

            service.trigger_research("Test Person")

            # Task should be created
            assert "Test Person" in service._active_tasks

    def test_trigger_research_deduplicates(self) -> None:
        """Test trigger_research doesn't start duplicate tasks."""
        service = KnowledgeResearchService()

        # Create a mock task that's not done
        mock_task: Any = MagicMock()
        mock_task.done.return_value = False
        service._active_tasks["Test Person"] = mock_task

        with patch("asyncio.create_task") as mock_create_task:
            service.trigger_research("Test Person")

            # Should not create a new task
            mock_create_task.assert_not_called()


# Note: API endpoint integration tests are in test_api.py
# These tests require the full app context which is complex to set up in isolation


class TestWikipediaFetching:
    """Tests for Wikipedia data fetching."""

    @pytest.mark.asyncio
    async def test_fetch_wikipedia_data_success(self) -> None:
        """Test successful Wikipedia data fetch."""
        service = KnowledgeResearchService()

        # Mock the HTTP response
        mock_search_response: Any = MagicMock()
        mock_search_response.json.return_value = {"query": {"search": [{"title": "Socrates"}]}}

        mock_content_response: Any = MagicMock()
        mock_content_response.json.return_value = {
            "query": {
                "pages": {
                    "123": {
                        "title": "Socrates",
                        "extract": "Socrates was an ancient Greek philosopher.",
                        "thumbnail": {"source": "https://example.com/image.jpg"},
                    }
                }
            }
        }

        mock_sections_response: Any = MagicMock()
        mock_sections_response.json.return_value = {"parse": {"sections": []}}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client: Any = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.side_effect = [
                mock_search_response,
                mock_content_response,
                mock_sections_response,
            ]
            mock_client_class.return_value = mock_client

            result = await service._fetch_wikipedia_data("Socrates")

            assert result is not None
            assert result["title"] == "Socrates"
            assert "summary" in result
            assert "image_url" in result

    @pytest.mark.asyncio
    async def test_fetch_wikipedia_data_not_found(self) -> None:
        """Test Wikipedia data fetch when page not found."""
        service = KnowledgeResearchService()

        mock_response: Any = MagicMock()
        mock_response.json.return_value = {
            "query": {
                "search": []  # No results
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client: Any = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await service._fetch_wikipedia_data("Nonexistent Person XYZ123")

            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_wikipedia_data_handles_errors(self) -> None:
        """Test Wikipedia data fetch handles errors gracefully."""
        service = KnowledgeResearchService()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client: Any = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.side_effect = Exception("Network error")
            mock_client_class.return_value = mock_client

            result = await service._fetch_wikipedia_data("Socrates")

            # Should return None on error, not raise
            assert result is None


# Note: TestResearchTaskExecution tests are integration tests that require
# the full database context with migrations applied. They would be better
# suited for E2E tests that run against the actual application.
