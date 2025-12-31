"""Integration tests for thinker knowledge API endpoints.

Tests the full knowledge research lifecycle:
1. GET /knowledge/{name} - Fetch cached knowledge
2. GET /knowledge/{name}/status - Check research status
3. POST /knowledge/{name}/refresh - Force refresh research
"""

import typing
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.core.database import get_db
from app.main import app
from app.models import ThinkerKnowledge
from app.models.thinker_knowledge import ResearchStatus


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database override."""
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_knowledge_service() -> typing.Generator[MagicMock, None, None]:
    """Mock the knowledge service to avoid real API calls."""
    with patch("app.services.knowledge_research.knowledge_service") as mock:
        # Configure default behavior
        mock.trigger_research = MagicMock(return_value=None)
        mock.is_stale = MagicMock(return_value=False)
        yield mock


class TestGetThinkerKnowledge:
    """Tests for GET /api/thinkers/knowledge/{name}."""

    async def test_get_existing_knowledge_success(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Happy path: fetch existing completed knowledge."""
        # Create knowledge entry in database
        knowledge = ThinkerKnowledge(
            name="Socrates",
            status=ResearchStatus.COMPLETE,
            research_data={"bio": "Ancient Greek philosopher", "works": ["Apology"]},
        )
        async_session.add(knowledge)
        await async_session.commit()
        await async_session.refresh(knowledge)

        # Mock service to return the knowledge
        mock_knowledge_service.get_knowledge = AsyncMock(return_value=knowledge)

        # Make request
        response = await client.get("/api/thinkers/knowledge/Socrates")

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Socrates"
        assert data["status"] == "complete"
        assert data["research_data"] is not None
        assert data["research_data"]["bio"] == "Ancient Greek philosopher"
        assert data["error_message"] is None

    async def test_get_knowledge_triggers_research_for_new_thinker(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Edge case: requesting knowledge for new thinker triggers research."""
        # Mock: no existing knowledge
        mock_knowledge_service.get_knowledge = AsyncMock(return_value=None)

        # Mock: create new knowledge entry
        new_knowledge = ThinkerKnowledge(
            name="Marie Curie",
            status=ResearchStatus.PENDING,
        )
        async_session.add(new_knowledge)
        await async_session.commit()
        await async_session.refresh(new_knowledge)

        mock_knowledge_service.get_or_create_knowledge = AsyncMock(return_value=new_knowledge)

        # Make request
        response = await client.get("/api/thinkers/knowledge/Marie Curie")

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Marie Curie"
        assert data["status"] == "pending"
        assert data["research_data"] == {} or data["research_data"] is None

        # Verify research was triggered
        mock_knowledge_service.trigger_research.assert_called_with("Marie Curie")

    async def test_get_knowledge_refreshes_stale_data(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Edge case: stale knowledge triggers background refresh."""
        # Create stale knowledge entry
        stale_knowledge = ThinkerKnowledge(
            name="Aristotle",
            status=ResearchStatus.COMPLETE,
            research_data={"bio": "Ancient Greek philosopher"},
        )
        async_session.add(stale_knowledge)
        await async_session.commit()
        await async_session.refresh(stale_knowledge)

        # Mock service
        mock_knowledge_service.get_knowledge = AsyncMock(return_value=stale_knowledge)
        mock_knowledge_service.is_stale = MagicMock(return_value=True)

        # Make request
        response = await client.get("/api/thinkers/knowledge/Aristotle")

        # Assert response (returns stale data but triggers refresh)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Aristotle"
        assert data["status"] == "complete"

        # Verify refresh was triggered
        mock_knowledge_service.is_stale.assert_called_once_with(stale_knowledge)
        mock_knowledge_service.trigger_research.assert_called_with("Aristotle")

    async def test_get_knowledge_returns_failed_research(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Edge case: failed research returns error message."""
        # Create failed knowledge entry
        failed_knowledge = ThinkerKnowledge(
            name="Unknown Person",
            status=ResearchStatus.FAILED,
            error_message="Not found in external sources",
        )
        async_session.add(failed_knowledge)
        await async_session.commit()
        await async_session.refresh(failed_knowledge)

        # Mock service
        mock_knowledge_service.get_knowledge = AsyncMock(return_value=failed_knowledge)

        # Make request
        response = await client.get("/api/thinkers/knowledge/Unknown Person")

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Unknown Person"
        assert data["status"] == "failed"
        assert data["error_message"] == "Not found in external sources"
        assert data["research_data"] == {} or data["research_data"] is None


class TestGetThinkerKnowledgeStatus:
    """Tests for GET /api/thinkers/knowledge/{name}/status."""

    async def test_get_status_for_completed_research(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Happy path: check status of completed research."""
        # Create complete knowledge entry
        knowledge = ThinkerKnowledge(
            name="Albert Einstein",
            status=ResearchStatus.COMPLETE,
            research_data={"bio": "Theoretical physicist"},
        )
        async_session.add(knowledge)
        await async_session.commit()
        await async_session.refresh(knowledge)

        # Mock service
        mock_knowledge_service.get_knowledge = AsyncMock(return_value=knowledge)

        # Make request
        response = await client.get("/api/thinkers/knowledge/Albert Einstein/status")

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Albert Einstein"
        assert data["status"] == "complete"
        assert data["has_data"] is True
        assert "updated_at" in data

    async def test_get_status_for_pending_research(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Edge case: check status of pending research."""
        # Create pending knowledge entry
        knowledge = ThinkerKnowledge(
            name="Maya Angelou",
            status=ResearchStatus.PENDING,
        )
        async_session.add(knowledge)
        await async_session.commit()
        await async_session.refresh(knowledge)

        # Mock service
        mock_knowledge_service.get_knowledge = AsyncMock(return_value=knowledge)

        # Make request
        response = await client.get("/api/thinkers/knowledge/Maya Angelou/status")

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Maya Angelou"
        assert data["status"] == "pending"
        assert data["has_data"] is False

    async def test_get_status_for_nonexistent_thinker(
        self,
        client: AsyncClient,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Edge case: nonexistent thinker returns PENDING status."""
        # Mock: no knowledge exists
        mock_knowledge_service.get_knowledge = AsyncMock(return_value=None)

        # Make request
        response = await client.get("/api/thinkers/knowledge/Nonexistent Person/status")

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Nonexistent Person"
        assert data["status"] == "pending"
        assert data["has_data"] is False
        # updated_at may be None if not in database
        assert data.get("updated_at") is None

    async def test_get_status_for_in_progress_research(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Edge case: research in progress returns correct status."""
        # Create in-progress knowledge entry
        knowledge = ThinkerKnowledge(
            name="Confucius",
            status=ResearchStatus.IN_PROGRESS,
        )
        async_session.add(knowledge)
        await async_session.commit()
        await async_session.refresh(knowledge)

        # Mock service
        mock_knowledge_service.get_knowledge = AsyncMock(return_value=knowledge)

        # Make request
        response = await client.get("/api/thinkers/knowledge/Confucius/status")

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Confucius"
        assert data["status"] == "in_progress"
        assert data["has_data"] is False


class TestRefreshThinkerKnowledge:
    """Tests for POST /api/thinkers/knowledge/{name}/refresh."""

    async def test_refresh_existing_knowledge(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Happy path: force refresh of existing knowledge."""
        # Create existing complete knowledge
        knowledge = ThinkerKnowledge(
            name="Socrates",
            status=ResearchStatus.COMPLETE,
            research_data={"bio": "Ancient Greek philosopher"},
        )
        async_session.add(knowledge)
        await async_session.commit()
        await async_session.refresh(knowledge)

        # Mock service
        mock_knowledge_service.get_or_create_knowledge = AsyncMock(return_value=knowledge)

        # Make request
        response = await client.post("/api/thinkers/knowledge/Socrates/refresh")

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Socrates"
        assert data["status"] == "complete"
        assert data["has_data"] is True

        # Verify research was triggered
        mock_knowledge_service.trigger_research.assert_called_with("Socrates")

    async def test_refresh_creates_entry_for_new_thinker(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Edge case: refresh for new thinker creates entry and triggers research."""
        # Mock: create new knowledge entry
        new_knowledge = ThinkerKnowledge(
            name="Ada Lovelace",
            status=ResearchStatus.PENDING,
        )
        async_session.add(new_knowledge)
        await async_session.commit()
        await async_session.refresh(new_knowledge)

        mock_knowledge_service.get_or_create_knowledge = AsyncMock(return_value=new_knowledge)

        # Make request
        response = await client.post("/api/thinkers/knowledge/Ada Lovelace/refresh")

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Ada Lovelace"
        assert data["status"] == "pending"
        assert data["has_data"] is False

        # Verify entry was created and research triggered
        mock_knowledge_service.get_or_create_knowledge.assert_called_once()
        mock_knowledge_service.trigger_research.assert_called_with("Ada Lovelace")

    async def test_refresh_retriggers_failed_research(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Edge case: refresh can retry failed research."""
        # Create failed knowledge entry
        failed_knowledge = ThinkerKnowledge(
            name="Unknown Person",
            status=ResearchStatus.FAILED,
            error_message="Previous failure",
        )
        async_session.add(failed_knowledge)
        await async_session.commit()
        await async_session.refresh(failed_knowledge)

        # Mock service
        mock_knowledge_service.get_or_create_knowledge = AsyncMock(return_value=failed_knowledge)

        # Make request
        response = await client.post("/api/thinkers/knowledge/Unknown Person/refresh")

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Unknown Person"
        assert data["status"] == "failed"

        # Verify research was re-triggered
        mock_knowledge_service.trigger_research.assert_called_with("Unknown Person")


class TestKnowledgeIntegrationLifecycle:
    """Integration tests for full knowledge lifecycle."""

    async def test_full_lifecycle_trigger_poll_retrieve(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Integration: Full lifecycle from trigger → poll → retrieve."""
        thinker_name = "Marie Curie"

        # Step 1: First GET triggers research (knowledge doesn't exist)
        mock_knowledge_service.get_knowledge = AsyncMock(return_value=None)

        pending_knowledge = ThinkerKnowledge(
            name=thinker_name,
            status=ResearchStatus.PENDING,
        )
        async_session.add(pending_knowledge)
        await async_session.commit()
        await async_session.refresh(pending_knowledge)

        mock_knowledge_service.get_or_create_knowledge = AsyncMock(return_value=pending_knowledge)

        response1 = await client.get(f"/api/thinkers/knowledge/{thinker_name}")
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        assert data1["status"] == "pending"
        mock_knowledge_service.trigger_research.assert_called_with(thinker_name)

        # Step 2: Poll status while research is in progress
        pending_knowledge.status = ResearchStatus.IN_PROGRESS
        await async_session.commit()
        await async_session.refresh(pending_knowledge)

        mock_knowledge_service.get_knowledge = AsyncMock(return_value=pending_knowledge)

        response2 = await client.get(f"/api/thinkers/knowledge/{thinker_name}/status")
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        assert data2["status"] == "in_progress"
        assert data2["has_data"] is False

        # Step 3: Retrieve completed knowledge
        pending_knowledge.status = ResearchStatus.COMPLETE
        pending_knowledge.research_data = {
            "bio": "Polish-French physicist",
            "works": ["Research on radioactivity"],
        }
        await async_session.commit()
        await async_session.refresh(pending_knowledge)

        mock_knowledge_service.get_knowledge = AsyncMock(return_value=pending_knowledge)

        response3 = await client.get(f"/api/thinkers/knowledge/{thinker_name}")
        assert response3.status_code == status.HTTP_200_OK
        data3 = response3.json()
        assert data3["status"] == "complete"
        assert data3["research_data"] is not None
        assert "bio" in data3["research_data"]

    async def test_refresh_updates_stale_completed_knowledge(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        mock_knowledge_service: typing.Any,
    ) -> None:
        """Integration: Refresh endpoint updates stale completed knowledge."""
        thinker_name = "Aristotle"

        # Create stale completed knowledge
        knowledge = ThinkerKnowledge(
            name=thinker_name,
            status=ResearchStatus.COMPLETE,
            research_data={"bio": "Old data"},
        )
        async_session.add(knowledge)
        await async_session.commit()
        await async_session.refresh(knowledge)

        # Mock service
        mock_knowledge_service.get_or_create_knowledge = AsyncMock(return_value=knowledge)

        # Force refresh
        response = await client.post(f"/api/thinkers/knowledge/{thinker_name}/refresh")
        assert response.status_code == status.HTTP_200_OK

        # Verify research was re-triggered
        mock_knowledge_service.trigger_research.assert_called_with(thinker_name)

        # Simulate research completion with new data
        knowledge.research_data = {"bio": "Updated data"}
        await async_session.commit()
        await async_session.refresh(knowledge)

        # Retrieve updated knowledge
        mock_knowledge_service.get_knowledge = AsyncMock(return_value=knowledge)
        response2 = await client.get(f"/api/thinkers/knowledge/{thinker_name}")
        assert response2.status_code == status.HTTP_200_OK
        data = response2.json()
        assert data["research_data"]["bio"] == "Updated data"
