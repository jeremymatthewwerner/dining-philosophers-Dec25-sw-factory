"""Knowledge research service for gathering and caching thinker information."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models import ResearchStatus, ThinkerKnowledge

logger = logging.getLogger(__name__)

# Cache staleness threshold - research older than this will be refreshed
CACHE_STALENESS_DAYS = 30


class KnowledgeResearchService:
    """Service for asynchronously researching and caching thinker knowledge.

    This service handles:
    - Background research tasks that don't block user interactions
    - Fetching from multiple sources (Wikipedia, etc.)
    - Persistent caching of research results
    - Cache invalidation and refresh
    """

    def __init__(self) -> None:
        self._active_tasks: dict[str, asyncio.Task[None]] = {}

    async def get_knowledge(self, db: AsyncSession, name: str) -> ThinkerKnowledge | None:
        """Get cached knowledge for a thinker by name.

        Args:
            db: Database session
            name: Thinker's canonical name

        Returns:
            ThinkerKnowledge if found, None otherwise
        """
        result = await db.execute(select(ThinkerKnowledge).where(ThinkerKnowledge.name == name))
        return result.scalar_one_or_none()

    async def get_or_create_knowledge(self, db: AsyncSession, name: str) -> ThinkerKnowledge:
        """Get existing knowledge or create a new pending entry.

        Args:
            db: Database session
            name: Thinker's canonical name

        Returns:
            Existing or newly created ThinkerKnowledge entry
        """
        knowledge = await self.get_knowledge(db, name)
        if knowledge:
            return knowledge

        # Create new entry with pending status
        knowledge = ThinkerKnowledge(
            name=name,
            status=ResearchStatus.PENDING,
            research_data={},
        )
        db.add(knowledge)
        await db.commit()
        await db.refresh(knowledge)
        return knowledge

    def is_stale(self, knowledge: ThinkerKnowledge) -> bool:
        """Check if knowledge is stale and needs refresh.

        Args:
            knowledge: The ThinkerKnowledge entry to check

        Returns:
            True if knowledge should be refreshed
        """
        if knowledge.status != ResearchStatus.COMPLETE:
            return True

        staleness_threshold = datetime.now(UTC) - timedelta(days=CACHE_STALENESS_DAYS)
        return knowledge.updated_at.replace(tzinfo=UTC) < staleness_threshold

    def trigger_research(self, name: str) -> None:
        """Trigger background research for a thinker (fire-and-forget).

        This is a non-blocking call that starts research in the background.
        Multiple calls for the same thinker are deduplicated.

        Args:
            name: Thinker's canonical name
        """
        # Deduplicate - don't start if already researching
        if name in self._active_tasks and not self._active_tasks[name].done():
            logger.debug(f"Research already in progress for {name}")
            return

        # Start background task
        task = asyncio.create_task(self._research_thinker(name))
        self._active_tasks[name] = task

        # Clean up task reference when done
        def cleanup(_: asyncio.Task[None]) -> None:
            if name in self._active_tasks:
                del self._active_tasks[name]

        task.add_done_callback(cleanup)
        logger.info(f"Started background research for {name}")

    async def _research_thinker(self, name: str) -> None:
        """Perform research on a thinker and cache results.

        This method runs in the background and:
        1. Updates status to IN_PROGRESS
        2. Fetches data from various sources
        3. Saves results and updates status to COMPLETE
        4. Handles errors gracefully

        Args:
            name: Thinker's canonical name
        """
        async with async_session() as db:
            try:
                # Get or create knowledge entry
                knowledge = await self.get_or_create_knowledge(db, name)

                # Update status to in_progress
                knowledge.status = ResearchStatus.IN_PROGRESS
                knowledge.error_message = None
                await db.commit()

                # Gather research from various sources
                research_data: dict[str, Any] = {}

                # Fetch Wikipedia data
                wikipedia_data = await self._fetch_wikipedia_data(name)
                if wikipedia_data:
                    research_data["wikipedia"] = wikipedia_data

                # Future: Add more sources here
                # - MCP servers for public domain texts
                # - Quotes databases
                # - Academic sources

                # Save results
                knowledge.research_data = research_data
                knowledge.status = ResearchStatus.COMPLETE
                knowledge.error_message = None
                await db.commit()

                logger.info(f"Completed research for {name}")

            except Exception as e:
                logger.error(f"Research failed for {name}: {e}", exc_info=True)
                # Mark as failed
                try:
                    async with async_session() as error_db:
                        failed_knowledge = await self.get_knowledge(error_db, name)
                        if failed_knowledge:
                            failed_knowledge.status = ResearchStatus.FAILED
                            failed_knowledge.error_message = str(e)
                            await error_db.commit()
                except Exception as inner_e:
                    logger.error(f"Failed to update error status for {name}: {inner_e}")

    async def _fetch_wikipedia_data(self, name: str) -> dict[str, Any] | None:
        """Fetch detailed information from Wikipedia.

        Args:
            name: Thinker's name to search for

        Returns:
            Dictionary with Wikipedia data or None if not found
        """
        try:
            headers = {"User-Agent": "DiningPhilosophersApp/1.0 (https://diningphilosophers.ai)"}
            async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
                # Search for the Wikipedia page
                search_url = "https://en.wikipedia.org/w/api.php"
                search_params: dict[str, str | int] = {
                    "action": "query",
                    "list": "search",
                    "srsearch": name,
                    "format": "json",
                    "srlimit": 1,
                }
                response = await client.get(search_url, params=search_params)
                data = response.json()

                if not data.get("query", {}).get("search"):
                    logger.debug(f"No Wikipedia page found for {name}")
                    return None

                page_title = data["query"]["search"][0]["title"]

                # Get detailed page content
                content_params: dict[str, str | int] = {
                    "action": "query",
                    "titles": page_title,
                    "prop": "extracts|pageimages|info",
                    "exintro": True,  # Get introduction only
                    "explaintext": True,  # Plain text, not HTML
                    "pithumbsize": 300,
                    "format": "json",
                }
                response = await client.get(search_url, params=content_params)
                data = response.json()

                pages = data.get("query", {}).get("pages", {})
                for page_id, page in pages.items():
                    if page_id == "-1":
                        continue

                    result: dict[str, Any] = {
                        "title": page.get("title"),
                        "summary": page.get("extract", "")[:2000],  # Limit summary length
                        "page_id": page_id,
                        "fetched_at": datetime.now(UTC).isoformat(),
                    }

                    if "thumbnail" in page:
                        result["image_url"] = page["thumbnail"]["source"]

                    # Get additional sections for more detailed knowledge
                    sections_data = await self._fetch_wikipedia_sections(
                        client, search_url, page_title
                    )
                    if sections_data:
                        result["sections"] = sections_data

                    return result

                return None

        except Exception as e:
            logger.warning(f"Failed to fetch Wikipedia data for {name}: {e}")
            return None

    async def _fetch_wikipedia_sections(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        page_title: str,
    ) -> dict[str, str] | None:
        """Fetch relevant sections from a Wikipedia page.

        Args:
            client: HTTP client
            base_url: Wikipedia API base URL
            page_title: Title of the page

        Returns:
            Dictionary of section titles to content
        """
        try:
            # Get page sections
            params: dict[str, str | int] = {
                "action": "parse",
                "page": page_title,
                "prop": "sections",
                "format": "json",
            }
            response = await client.get(base_url, params=params)
            data = response.json()

            sections = data.get("parse", {}).get("sections", [])

            # Filter for interesting sections
            interesting_sections = [
                "Philosophy",
                "Works",
                "Legacy",
                "Contributions",
                "Ideas",
                "Thought",
                "Beliefs",
                "Views",
                "Major works",
                "Notable works",
                "Influence",
                "Career",
                "Life",
                "Early life",
                "Biography",
            ]

            result: dict[str, str] = {}
            for section in sections:
                section_title = section.get("line", "")
                if any(
                    interesting.lower() in section_title.lower()
                    for interesting in interesting_sections
                ):
                    # Fetch section content
                    section_index = section.get("index")
                    content_params: dict[str, str | int] = {
                        "action": "query",
                        "titles": page_title,
                        "prop": "extracts",
                        "exsectionformat": "plain",
                        "explaintext": True,
                        "format": "json",
                    }
                    # Make the API call (content fetched but not parsed in detail yet)
                    await client.get(base_url, params=content_params)

                    # Just store the section title as a marker for now
                    # Full section extraction requires more complex parsing
                    result[section_title] = f"Section {section_index}: {section_title}"

            return result if result else None

        except Exception as e:
            logger.debug(f"Failed to fetch Wikipedia sections for {page_title}: {e}")
            return None

    async def refresh_stale_knowledge(self, db: AsyncSession) -> int:
        """Refresh all stale knowledge entries.

        This can be called periodically (e.g., daily) to keep cache fresh.

        Args:
            db: Database session

        Returns:
            Number of entries queued for refresh
        """
        staleness_threshold = datetime.now(UTC) - timedelta(days=CACHE_STALENESS_DAYS)

        result = await db.execute(
            select(ThinkerKnowledge).where(
                (ThinkerKnowledge.status == ResearchStatus.COMPLETE)
                & (ThinkerKnowledge.updated_at < staleness_threshold)
            )
        )
        stale_entries = result.scalars().all()

        for entry in stale_entries:
            self.trigger_research(entry.name)

        return len(stale_entries)


# Global service instance
knowledge_service = KnowledgeResearchService()
