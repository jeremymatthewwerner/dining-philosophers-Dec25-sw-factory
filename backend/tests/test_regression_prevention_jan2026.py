"""
Regression prevention tests for January 2026 bug fixes.

These tests ensure that previously fixed bugs do not regress.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.knowledge_research import KnowledgeResearchService


class TestConversationKnowledgeResearch:
    """Regression tests for issue #102 and commit ed94937.

    Bug: StatusLine only showed research for manually validated thinkers, not
    for thinkers suggested by the AI when creating conversations.

    Fix: Added knowledge_service.trigger_research() call in create_conversation
    endpoint (conversations.py:59) to trigger research for all thinkers in a
    new conversation.
    """

    @pytest.mark.asyncio
    async def test_create_conversation_triggers_knowledge_research(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that creating a conversation triggers knowledge research for all thinkers.

        Regression test for issue #102 (commit ed94937):
        - Bug: Knowledge research was only triggered for manually validated thinkers
        - Fix: Now triggers research for all thinkers when conversation is created
        - Validates: knowledge_service.trigger_research() is called for each thinker
        """
        # Import the helper function directly
        from tests.conftest import register_and_get_token

        data = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        # Mock the knowledge service to verify trigger_research is called
        # knowledge_service is imported inside the function, so patch at import site
        with patch(
            "app.services.knowledge_research.knowledge_service.trigger_research"
        ) as mock_trigger:
            mock_trigger.return_value = None  # trigger_research returns None

            # Create a conversation with 2 thinkers
            response = await client.post(
                "/api/conversations",
                json={
                    "topic": "The nature of consciousness",
                    "thinkers": [
                        {
                            "name": "Socrates",
                            "bio": "Ancient Greek philosopher",
                            "positions": "Socratic method",
                            "style": "Questioning",
                            "color": "#6366f1",
                        },
                        {
                            "name": "Aristotle",
                            "bio": "Student of Plato",
                            "positions": "Logic and metaphysics",
                            "style": "Systematic",
                            "color": "#ec4899",
                        },
                    ],
                },
                headers=headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["topic"] == "The nature of consciousness"
            assert len(data["thinkers"]) == 2

            # CRITICAL: Verify trigger_research was called for each thinker
            assert mock_trigger.call_count == 2
            mock_trigger.assert_any_call("Socrates")
            mock_trigger.assert_any_call("Aristotle")

    @pytest.mark.asyncio
    async def test_create_conversation_with_single_thinker_triggers_research(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that creating a conversation with a single thinker triggers research.

        Edge case: Single thinker conversation should still trigger research.
        """
        from tests.conftest import register_and_get_token

        data = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        with patch(
            "app.services.knowledge_research.knowledge_service.trigger_research"
        ) as mock_trigger:
            mock_trigger.return_value = None

            # Create a conversation with 1 thinker
            response = await client.post(
                "/api/conversations",
                json={
                    "topic": "Ethics",
                    "thinkers": [
                        {
                            "name": "Confucius",
                            "bio": "Chinese philosopher",
                            "positions": "Ethics and morality",
                            "style": "Aphoristic",
                            "color": "#10b981",
                        },
                    ],
                },
                headers=headers,
            )

            assert response.status_code == 200

            # Verify trigger_research was called once
            assert mock_trigger.call_count == 1
            mock_trigger.assert_called_once_with("Confucius")

    @pytest.mark.asyncio
    async def test_create_conversation_with_max_thinkers_triggers_research(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that creating a conversation with maximum thinkers (5) triggers research.

        Edge case: All 5 thinkers should have research triggered.
        """
        from tests.conftest import register_and_get_token

        data = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        with patch(
            "app.services.knowledge_research.knowledge_service.trigger_research"
        ) as mock_trigger:
            mock_trigger.return_value = None

            # Create a conversation with 5 thinkers (maximum)
            response = await client.post(
                "/api/conversations",
                json={
                    "topic": "Philosophy of language",
                    "thinkers": [
                        {
                            "name": f"Thinker{i}",
                            "bio": f"Bio {i}",
                            "positions": f"Position {i}",
                            "style": f"Style {i}",
                            "color": "#6366f1",
                        }
                        for i in range(1, 6)
                    ],
                },
                headers=headers,
            )

            assert response.status_code == 200

            # Verify trigger_research was called 5 times
            assert mock_trigger.call_count == 5
            for i in range(1, 6):
                mock_trigger.assert_any_call(f"Thinker{i}")
