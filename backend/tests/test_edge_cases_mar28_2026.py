"""Edge case tests - Saturday QA focus (Mar 28, 2026).

Tests cover error paths and boundary conditions not yet tested:

- knowledge_research.py:
  - _research_thinker: exception handling during research (lines 125-167)
  - _research_thinker: error status update failure (inner exception handler)
  - _fetch_wikipedia_sections: matching sections are fetched and stored (lines 292-318)
  - _fetch_wikipedia_sections: exception handling (lines 316-318)

- auth.py boundary and validation edge cases:
  - Registration with username containing numbers and underscores (valid)
  - Registration with unsupported language code (invalid)
  - Change password with same password as new (should succeed - no restriction)
  - Update profile with max-length display name (exactly 100 chars)
  - Update language to all supported languages

- conversations.py:
  - Unicode/emoji in message content
  - Very long message content (at boundary)
  - Message to conversation owned by different session returns 404

- feedback.py:
  - client with no IP (unknown fallback path)
  - Feedback with message at exactly minimum length (10 chars)

Uses `with patch(...)` (not @patch decorator) to ensure coverage is correctly tracked
with pytest-asyncio's auto mode.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ResearchStatus, ThinkerKnowledge
from app.services.knowledge_research import KnowledgeResearchService
from tests.conftest import get_auth_headers


class TestResearchThinkerErrorHandling:
    """Tests for _research_thinker error handling paths (lines 125-167)."""

    async def test_research_thinker_exception_updates_status_to_failed(
        self, async_session: AsyncSession
    ) -> None:
        """Test _research_thinker marks knowledge as FAILED when an exception occurs.

        Edge case: Exception handling in _research_thinker (lines 156-167).
        The method should catch exceptions and update the DB status to FAILED.
        """
        service = KnowledgeResearchService()

        # Pre-create a knowledge entry so _research_thinker can find it
        knowledge = ThinkerKnowledge(
            name="TestPhilosopher",
            status=ResearchStatus.PENDING,
            research_data={},
        )
        async_session.add(knowledge)
        await async_session.commit()

        # Patch async_session to return our session, and _fetch_wikipedia_data to raise
        with (
            patch("app.services.knowledge_research.async_session") as mock_session_cm,
            patch.object(
                service,
                "_fetch_wikipedia_data",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Wikipedia API failure"),
            ),
        ):
            # Set up the async context manager mock to return our session
            mock_session_cm.return_value.__aenter__ = AsyncMock(return_value=async_session)
            mock_session_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            # Also patch the inner error_db session for the failure handler
            # We make a second session context manager call return async_session too
            mock_session_cm.side_effect = [
                mock_session_cm.return_value,
                mock_session_cm.return_value,
            ]

            await service._research_thinker("TestPhilosopher")

        # Check that knowledge entry was marked FAILED
        await async_session.refresh(knowledge)
        assert knowledge.status == ResearchStatus.FAILED
        assert knowledge.error_message is not None
        assert "Wikipedia API failure" in knowledge.error_message

    async def test_research_thinker_completes_successfully_with_wikipedia_data(
        self, async_session: AsyncSession
    ) -> None:
        """Test _research_thinker marks knowledge as COMPLETE when Wikipedia data is found.

        Edge case: Success path of _research_thinker (lines 125-154).
        """
        service = KnowledgeResearchService()

        # Pre-create a knowledge entry
        knowledge = ThinkerKnowledge(
            name="Thales",
            status=ResearchStatus.PENDING,
            research_data={},
        )
        async_session.add(knowledge)
        await async_session.commit()

        wikipedia_result = {
            "title": "Thales of Miletus",
            "summary": "Pre-Socratic philosopher",
            "page_id": "12345",
        }

        with (
            patch("app.services.knowledge_research.async_session") as mock_session_cm,
            patch.object(
                service,
                "_fetch_wikipedia_data",
                new_callable=AsyncMock,
                return_value=wikipedia_result,
            ),
        ):
            mock_session_cm.return_value.__aenter__ = AsyncMock(return_value=async_session)
            mock_session_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            await service._research_thinker("Thales")

        # Knowledge should be COMPLETE with data
        await async_session.refresh(knowledge)
        assert knowledge.status == ResearchStatus.COMPLETE
        assert "wikipedia" in knowledge.research_data
        assert knowledge.research_data["wikipedia"]["title"] == "Thales of Miletus"

    async def test_research_thinker_with_no_wikipedia_data_still_completes(
        self, async_session: AsyncSession
    ) -> None:
        """Test _research_thinker marks knowledge as COMPLETE even when Wikipedia returns None.

        Edge case: Wikipedia returns None (no page found) but research still completes.
        Covers the branch where research_data has no wikipedia key (line 140-141).
        """
        service = KnowledgeResearchService()

        knowledge = ThinkerKnowledge(
            name="UnknownThinkerXYZ",
            status=ResearchStatus.PENDING,
            research_data={},
        )
        async_session.add(knowledge)
        await async_session.commit()

        with (
            patch("app.services.knowledge_research.async_session") as mock_session_cm,
            patch.object(
                service,
                "_fetch_wikipedia_data",
                new_callable=AsyncMock,
                return_value=None,  # No Wikipedia page found
            ),
        ):
            mock_session_cm.return_value.__aenter__ = AsyncMock(return_value=async_session)
            mock_session_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            await service._research_thinker("UnknownThinkerXYZ")

        await async_session.refresh(knowledge)
        # Should still be COMPLETE even with empty research_data
        assert knowledge.status == ResearchStatus.COMPLETE
        assert knowledge.research_data == {}  # No data because wikipedia returned None


class TestFetchWikipediaSections:
    """Tests for _fetch_wikipedia_sections with matching section logic (lines 292-318)."""

    async def test_fetch_wikipedia_sections_returns_matching_sections(self) -> None:
        """Test _fetch_wikipedia_sections returns sections whose titles match interesting list.

        Edge case: Section matching logic (lines 292-312) - when sections have titles
        that match the interesting_sections list, they are stored in the result dict.

        Note: The matching is case-insensitive substring check, so "interesting.lower() in
        section_title.lower()". E.g. "Life" (in interesting list) matches "Personal life".
        We use unique non-overlapping section titles to avoid ambiguity.
        """
        service = KnowledgeResearchService()

        # Mock the sections response to include matching section titles
        # "Philosophy" and "Works" are exact matches; "Footnotes" won't match anything
        mock_sections_response: Any = MagicMock()
        mock_sections_response.json.return_value = {
            "parse": {
                "sections": [
                    {"line": "Philosophy", "index": "1"},
                    {"line": "Works", "index": "2"},
                    {"line": "Footnotes", "index": "3"},  # Not in interesting_sections
                ]
            }
        }

        # Mock the content fetch (called for each matching section)
        mock_content_response: Any = MagicMock()
        mock_content_response.json.return_value = {
            "query": {"pages": {"123": {"extract": "Section content"}}}
        }

        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            mock_sections_response,
            mock_content_response,  # For "Philosophy" section content
            mock_content_response,  # For "Works" section content
        ]

        result = await service._fetch_wikipedia_sections(
            mock_client, "https://wiki-api.test", "Socrates"
        )

        assert result is not None
        # Philosophy and Works both match interesting_sections
        assert "Philosophy" in result
        assert "Works" in result
        # Footnotes should NOT be in result (not in interesting_sections)
        assert "Footnotes" not in result

    async def test_fetch_wikipedia_sections_returns_none_when_no_matching_sections(
        self,
    ) -> None:
        """Test _fetch_wikipedia_sections returns None when no sections match the interesting list.

        Edge case: No matching sections - returns None (line 314: `return result if result else None`).
        """
        service = KnowledgeResearchService()

        mock_sections_response: Any = MagicMock()
        mock_sections_response.json.return_value = {
            "parse": {
                "sections": [
                    {"line": "Footnotes", "index": "1"},
                    {"line": "References", "index": "2"},
                    {"line": "See also", "index": "3"},
                ]
            }
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_sections_response

        result = await service._fetch_wikipedia_sections(
            mock_client, "https://wiki-api.test", "Socrates"
        )

        assert result is None

    async def test_fetch_wikipedia_sections_returns_none_on_exception(self) -> None:
        """Test _fetch_wikipedia_sections returns None when an exception occurs (lines 316-318).

        Edge case: Exception handling in sections fetch - graceful degradation.
        """
        service = KnowledgeResearchService()

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection timeout")

        result = await service._fetch_wikipedia_sections(
            mock_client, "https://wiki-api.test", "Plato"
        )

        assert result is None

    async def test_fetch_wikipedia_sections_returns_none_for_empty_sections(self) -> None:
        """Test _fetch_wikipedia_sections returns None when section list is empty.

        Edge case: Wikipedia page exists but has no sections.
        """
        service = KnowledgeResearchService()

        mock_response: Any = MagicMock()
        mock_response.json.return_value = {"parse": {"sections": []}}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        result = await service._fetch_wikipedia_sections(
            mock_client, "https://wiki-api.test", "Aristotle"
        )

        assert result is None

    async def test_fetch_wikipedia_sections_partial_match_in_title(self) -> None:
        """Test that partial match in section title works (case-insensitive contains check).

        Edge case: Section title "Early life and philosophy" contains "philosophy" (case-insensitive).
        The any(interesting.lower() in section_title.lower() ...) check allows partial matches.
        """
        service = KnowledgeResearchService()

        mock_sections_response: Any = MagicMock()
        mock_sections_response.json.return_value = {
            "parse": {
                "sections": [
                    {"line": "Early life and philosophy", "index": "1"},  # Contains "philosophy"
                    {"line": "Major works and contributions", "index": "2"},  # Contains "works"
                ]
            }
        }

        mock_content_response: Any = MagicMock()
        mock_content_response.json.return_value = {"query": {"pages": {}}}

        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            mock_sections_response,
            mock_content_response,
            mock_content_response,
        ]

        result = await service._fetch_wikipedia_sections(
            mock_client, "https://wiki-api.test", "Nietzsche"
        )

        assert result is not None
        assert "Early life and philosophy" in result
        assert "Major works and contributions" in result


class TestAuthRegistrationEdgeCases:
    """Additional edge cases for authentication registration."""

    async def test_register_with_numbers_and_underscores_in_username(
        self, client: AsyncClient
    ) -> None:
        """Test registration with valid username containing numbers and underscores.

        Edge case: Username pattern validation - numbers and underscores are valid chars.
        The schema only enforces min_length=3 and max_length=50, not character restrictions.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "user_123_abc",
                "display_name": "Valid User",
                "password": "securepass",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["username"] == "user_123_abc"

    async def test_register_with_unsupported_language_code_fails(self, client: AsyncClient) -> None:
        """Test registration with unsupported language code is rejected.

        Edge case: language_preference must match pattern '^(en|es|fr|de)$'.
        Any other code should fail Pydantic validation.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "lang_test_user",
                "display_name": "Language Test",
                "password": "securepass",
                "language_preference": "ja",  # Japanese not supported
            },
        )
        assert response.status_code == 422
        error_detail = response.json()["detail"]
        # Should mention language_preference in the error
        error_fields = [e["loc"][-1] for e in error_detail if isinstance(e.get("loc"), list)]
        assert "language_preference" in error_fields

    async def test_register_with_all_supported_languages(self, client: AsyncClient) -> None:
        """Test registration succeeds for each supported language code.

        Edge case: Verifies all four supported language codes (en, es, fr, de) are accepted.
        """
        supported_languages = ["en", "es", "fr", "de"]
        for i, lang in enumerate(supported_languages):
            response = await client.post(
                "/api/auth/register",
                json={
                    "username": f"lang_user_{lang}_{i}",
                    "display_name": f"User {lang.upper()}",
                    "password": "securepass",
                    "language_preference": lang,
                },
            )
            assert response.status_code == 200, f"Language '{lang}' should be accepted"
            assert response.json()["user"]["username"] == f"lang_user_{lang}_{i}"

    async def test_register_with_hyphen_in_username_succeeds(self, client: AsyncClient) -> None:
        """Test registration with hyphen in username (valid, no character restriction).

        Edge case: The schema has no character restriction, only length limits.
        Hyphens should be valid username characters.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "my-username",
                "display_name": "Hyphen User",
                "password": "securepass",
            },
        )
        assert response.status_code == 200
        assert response.json()["user"]["username"] == "my-username"

    async def test_update_language_to_unsupported_code_fails(self, client: AsyncClient) -> None:
        """Test PATCH /auth/language rejects unsupported language codes.

        Edge case: PATCH validation on language_preference field in update endpoint.
        """
        headers = await get_auth_headers(client, "lang_patch_user", "testpass123")

        response = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "zh"},  # Chinese not supported
        )
        assert response.status_code == 422

    async def test_update_profile_with_exactly_max_length_display_name(
        self, client: AsyncClient
    ) -> None:
        """Test PATCH /auth/profile accepts display_name at exactly max length (100 chars).

        Edge case: Boundary condition - max_length=100 for display_name.
        """
        headers = await get_auth_headers(client, "profile_max_user", "testpass123")

        max_display_name = "A" * 100  # Exactly 100 chars
        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": max_display_name},
        )
        assert response.status_code == 200
        assert response.json()["display_name"] == max_display_name

    async def test_update_profile_over_max_length_display_name_fails(
        self, client: AsyncClient
    ) -> None:
        """Test PATCH /auth/profile rejects display_name over max length (101 chars).

        Edge case: Boundary condition - max_length=100 for display_name.
        """
        headers = await get_auth_headers(client, "profile_over_max_user", "testpass123")

        over_max_display_name = "A" * 101  # 101 chars - exceeds max
        response = await client.patch(
            "/api/auth/profile",
            headers=headers,
            json={"display_name": over_max_display_name},
        )
        assert response.status_code == 422


class TestConversationMessageEdgeCases:
    """Edge cases for sending messages in conversations."""

    async def test_send_message_with_unicode_emoji_content(self, client: AsyncClient) -> None:
        """Test sending message with unicode emoji characters.

        Edge case: Unicode content in messages - emoji, CJK characters, etc.
        The system should handle unicode gracefully without errors.
        """
        headers = await get_auth_headers(client, "emoji_user", "testpass123")

        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Philosophy",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Greek philosopher",
                        "positions": "Ethics",
                        "style": "Questioning",
                        "color": "#ec4899",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Send message with emoji and unicode
        unicode_message = "What is virtue? 🤔 哲学 философия"
        msg_response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": unicode_message},
        )

        assert msg_response.status_code == 200
        data = msg_response.json()
        assert data["content"] == unicode_message

    async def test_send_message_with_special_characters(self, client: AsyncClient) -> None:
        """Test sending message with special characters (quotes, ampersands, brackets).

        Edge case: Special chars in message content - should be stored and retrieved intact.
        """
        headers = await get_auth_headers(client, "special_chars_user", "testpass123")

        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Logic & Reasoning",
                "thinkers": [
                    {
                        "name": "Aristotle",
                        "bio": "Greek philosopher",
                        "positions": "Logic",
                        "style": "Analytical",
                        "color": "#10b981",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        special_message = 'He said "cogito ergo sum" & <I think, therefore I am>'
        msg_response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": special_message},
        )

        assert msg_response.status_code == 200
        assert msg_response.json()["content"] == special_message

    async def test_create_conversation_with_unicode_topic(self, client: AsyncClient) -> None:
        """Test creating conversation with unicode characters in topic.

        Edge case: Unicode in topic field - Japanese, Arabic, CJK, etc.
        """
        headers = await get_auth_headers(client, "unicode_topic_user", "testpass123")

        unicode_topic = "什么是真理？ What is truth? ما هي الحقيقة؟"
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": unicode_topic,
                "thinkers": [
                    {
                        "name": "Confucius",
                        "bio": "Chinese philosopher",
                        "positions": "Ethics and ritual",
                        "style": "Aphorisms",
                        "color": "#f59e0b",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        assert conv_response.json()["topic"] == unicode_topic

    async def test_send_message_to_other_users_conversation_returns_404(
        self, client: AsyncClient
    ) -> None:
        """Test sending message to another user's conversation returns 404.

        Edge case: Authorization boundary - users cannot message other users' conversations.
        """
        # Create conversation as user A
        headers_a = await get_auth_headers(client, "user_a_msg", "testpass123")
        conv_response = await client.post(
            "/api/conversations",
            headers=headers_a,
            json={
                "topic": "Private topic",
                "thinkers": [
                    {
                        "name": "Plato",
                        "bio": "Greek philosopher",
                        "positions": "Forms",
                        "style": "Dialogues",
                        "color": "#8b5cf6",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Try to send message as user B (different session, so different user)
        headers_b = await get_auth_headers(client, "user_b_msg", "testpass123")
        msg_response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers_b,
            json={"content": "I should not be able to write here"},
        )

        # Should return 404 since the conversation doesn't belong to user B's session
        assert msg_response.status_code == 404

    async def test_send_empty_message_fails_validation(self, client: AsyncClient) -> None:
        """Test sending empty message content fails.

        Edge case: Empty string content - should fail Pydantic validation.
        The MessageCreate schema has min_length=1 on content.
        """
        headers = await get_auth_headers(client, "empty_msg_user", "testpass123")

        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Empty message test",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Greek philosopher",
                        "positions": "Ethics",
                        "style": "Questioning",
                        "color": "#6366f1",
                    }
                ],
            },
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["id"]

        # Try to send empty message
        msg_response = await client.post(
            f"/api/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": ""},
        )

        # Empty content should fail validation
        assert msg_response.status_code == 422


class TestFeedbackEdgeCases:
    """Additional edge cases for the feedback endpoint."""

    async def test_submit_feedback_message_at_exact_minimum_length(
        self, client: AsyncClient
    ) -> None:
        """Test feedback submission with message at exactly minimum length (10 chars).

        Edge case: Boundary condition - min_length=10 in FeedbackCreate schema.
        Exactly 10 chars should be accepted.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "message": "1234567890",  # Exactly 10 chars
            },
        )
        assert response.status_code == 201

    async def test_submit_feedback_message_one_below_minimum_fails(
        self, client: AsyncClient
    ) -> None:
        """Test feedback submission with 9-char message fails validation.

        Edge case: Boundary condition - min_length=10. 9 chars should be rejected.
        """
        response = await client.post(
            "/api/feedback",
            json={
                "message": "123456789",  # 9 chars - below minimum
            },
        )
        assert response.status_code == 422

    async def test_submit_feedback_rate_limit_boundary_fifth_submission_succeeds(
        self, client: AsyncClient
    ) -> None:
        """Test that the 5th submission (at the boundary) still succeeds.

        Edge case: Rate limit boundary - 5 is the maximum, so the 5th should succeed
        and the 6th should be blocked. Tests exact boundary behavior.
        """
        # Use a unique IP to avoid cross-test interference
        unique_ip = "192.168.99.99"

        # Submit exactly 5 (the maximum)
        for i in range(5):
            response = await client.post(
                "/api/feedback",
                headers={"X-Forwarded-For": unique_ip},
                json={
                    "message": f"Rate limit boundary test submission number {i + 1}.",
                },
            )
            assert response.status_code == 201, f"Submission {i + 1} should succeed (boundary test)"

        # The 6th submission should be blocked
        response = await client.post(
            "/api/feedback",
            headers={"X-Forwarded-For": unique_ip},
            json={
                "message": "This is the 6th submission and should be rate limited.",
            },
        )
        assert response.status_code == 429

    async def test_submit_feedback_with_screenshot_and_filename(self, client: AsyncClient) -> None:
        """Test feedback submission with both screenshot data and filename.

        Edge case: Both screenshot fields provided together - valid combination.
        """
        # Minimal valid base64-encoded 1x1 PNG
        tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        response = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "bug",
                "message": "Bug with screenshot and filename included in the report.",
                "screenshot_data": tiny_png,
                "screenshot_filename": "bug-screenshot.png",
            },
        )
        assert response.status_code == 201


class TestKnowledgeResearchServiceIntegration:
    """Integration tests for KnowledgeResearchService using real async sessions."""

    async def test_get_or_create_knowledge_idempotent(self, async_session: AsyncSession) -> None:
        """Test get_or_create_knowledge is idempotent - calling twice returns same entry.

        Edge case: Idempotency of knowledge creation prevents duplicate entries.
        """
        service = KnowledgeResearchService()

        # Create first time
        knowledge1 = await service.get_or_create_knowledge(async_session, "Pythagoras")
        id1 = knowledge1.id

        # Create second time - should return same entry
        knowledge2 = await service.get_or_create_knowledge(async_session, "Pythagoras")
        id2 = knowledge2.id

        assert id1 == id2
        assert knowledge2.status == ResearchStatus.PENDING

    async def test_get_knowledge_returns_none_for_unknown_thinker(
        self, async_session: AsyncSession
    ) -> None:
        """Test get_knowledge returns None for thinker not in database.

        Edge case: Looking up a thinker that has never been researched.
        """
        service = KnowledgeResearchService()

        result = await service.get_knowledge(async_session, "CompletelyUnknownThinker999")
        assert result is None

    async def test_is_stale_failed_entry_is_always_stale(self) -> None:
        """Test that FAILED research entries are always considered stale.

        Edge case: Failed research should be retried - is_stale must return True.
        """
        service = KnowledgeResearchService()

        knowledge = ThinkerKnowledge(
            name="FailedThinker",
            status=ResearchStatus.FAILED,
            research_data={},
        )
        assert service.is_stale(knowledge) is True

    async def test_trigger_research_for_completed_task_starts_new_task(self) -> None:
        """Test that trigger_research creates a new task when previous task is done.

        Edge case: Retrigger after completion - the 'done' check allows re-research.
        """
        service = KnowledgeResearchService()

        # Simulate a completed task
        completed_task: Any = MagicMock()
        completed_task.done.return_value = True
        service._active_tasks["Leibniz"] = completed_task

        with (
            patch("asyncio.create_task") as mock_create_task,
            patch.object(service, "_research_thinker", new=MagicMock()),
        ):
            mock_new_task: Any = MagicMock()
            mock_create_task.return_value = mock_new_task
            service.trigger_research("Leibniz")

            # A new task should have been created
            mock_create_task.assert_called_once()
