"""Regression prevention tests - Sunday QA focus (Mar 1, 2026).

Tests cover uncovered code paths and regression prevention for recently fixed bugs:

1. TestThinkerSuggestAPIPath:
   - suggest_thinkers with API key set returns non-empty results (lines 140-141)
   - suggest_thinkers with API key set returns empty list → fallback to mock (line 148)
   - suggest_thinkers with non-quota API error returns 502 (line 144: status_code = 502)

2. TestThinkerValidateAPIPath:
   - validate_thinker unknown thinker without API key → error response (line 188)
   - validate_thinker with API key returns valid response + triggers research (lines 198-201)
   - validate_thinker with API key returns non-quota error → 502 (not 503)

3. TestJWTTokenEdgeCases:
   - JWT token with no 'sub' field → get_current_user returns None (auth.py line 50)

4. TestKnowledgeResearchRefreshStale:
   - refresh_stale_knowledge queues stale entries for refresh
   - refresh_stale_knowledge returns count of stale entries
   - refresh_stale_knowledge returns 0 when no stale entries

5. TestThinkerLastUserMessageTimestamp:
   - _get_last_user_message_timestamp returns 0.0 for empty messages
   - _get_last_user_message_timestamp finds last user message timestamp
   - _get_last_user_message_timestamp skips thinker messages

6. TestIdlePauseResumeCycle:
   - pause_for_idle/resume_from_idle cycle correctly clears idle flag
   - resume_from_idle does NOT resume manually paused conversations
   - is_idle_paused distinguishes between idle and manual pauses

Uses `with patch(...)` (not @patch decorator) to ensure coverage is correctly tracked
with pytest-asyncio's auto mode.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import register_and_get_token


class TestThinkerSuggestAPIPath:
    """Regression tests for suggest_thinkers API path (thinkers.py lines 135-148).

    These lines are only reached when anthropic_api_key is set. The mock path
    (lines 130-133) is tested in test_api.py::TestThinkerAPI::test_suggest_thinkers.

    Prevents regression where:
    - API path returns results but they're not returned to caller (lines 140-141)
    - Empty API response causes fallback to mock (line 148)
    - Non-quota API error returns 502 instead of 503 (line 144)
    """

    async def test_suggest_thinkers_with_api_key_returns_results(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that suggest_thinkers returns API results when API key is configured.

        Regression test: Lines 140-141 in thinkers.py - the `if suggestions: return suggestions`
        branch was previously uncovered. Without this test, a refactor could silently
        discard API results and always fall back to mock.
        """
        from app.schemas import ThinkerProfile, ThinkerSuggestion
        from app.services.thinker import thinker_service

        mock_profile = ThinkerProfile(
            name="Socrates",
            bio="Ancient Greek philosopher",
            positions="Socratic method",
            style="Dialectic questioning",
        )
        mock_suggestions = [
            ThinkerSuggestion(
                name="Socrates",
                reason="Expert at fundamental questioning",
                profile=mock_profile,
            )
        ]

        async def mock_suggest_with_results(*_args: Any, **_kwargs: Any) -> list[ThinkerSuggestion]:
            return mock_suggestions

        monkeypatch.setattr(thinker_service, "suggest_thinkers", mock_suggest_with_results)
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": "test-api-key"})(),
        )

        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "Philosophy of mind", "count": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Socrates"
        assert data[0]["reason"] == "Expert at fundamental questioning"

    async def test_suggest_thinkers_empty_api_result_falls_back_to_mock(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that empty API result falls back to mock suggestions.

        Regression test: Line 148 in thinkers.py - the fallback `return await
        get_mock_suggestions(...)` branch was previously uncovered. This path is
        reached when suggest_thinkers returns an empty list (not an error).
        """
        from app.schemas import ThinkerSuggestion
        from app.services.thinker import thinker_service

        async def mock_suggest_empty(*_args: Any, **_kwargs: Any) -> list[ThinkerSuggestion]:
            return []  # Empty list triggers fallback

        monkeypatch.setattr(thinker_service, "suggest_thinkers", mock_suggest_empty)
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": "test-api-key"})(),
        )
        # Mock Wikipedia image fetch to avoid network calls
        monkeypatch.setattr(
            thinker_service,
            "get_wikipedia_image",
            AsyncMock(return_value=None),
        )

        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "Philosophy of mind", "count": 3},
        )
        assert response.status_code == 200
        data = response.json()
        # Falls back to mock, which returns up to 5 known thinkers
        assert len(data) == 3
        assert all("name" in t for t in data)
        assert all("profile" in t for t in data)

    async def test_suggest_thinkers_non_quota_api_error_returns_502(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that non-quota API errors return 502 (not 503).

        Regression test: Line 144 in thinkers.py - the non-quota error path returns
        502 (Bad Gateway) while quota errors return 503 (Service Unavailable).
        Prevents regression where all API errors might return the same status code.
        """
        from app.exceptions import ThinkerAPIError
        from app.services.thinker import thinker_service

        async def mock_suggest_non_quota_error(*_args: Any, **_kwargs: Any) -> None:
            raise ThinkerAPIError(
                "API connection error - upstream service unavailable",
                is_quota_error=False,  # NOT a quota error → should return 502
            )

        monkeypatch.setattr(thinker_service, "suggest_thinkers", mock_suggest_non_quota_error)
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": "test-api-key"})(),
        )

        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "Ethics", "count": 3},
        )
        assert response.status_code == 502, (
            f"Non-quota API error should return 502 (Bad Gateway), got {response.status_code}"
        )
        data = response.json()
        assert "API connection error" in data["detail"]

    async def test_suggest_thinkers_quota_error_returns_503(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that quota errors return 503 (Service Unavailable).

        Regression test: Ensures quota errors return 503 (credits exhausted)
        rather than 502 (connection error). These have different user implications.
        """
        from app.exceptions import ThinkerAPIError
        from app.services.thinker import thinker_service

        async def mock_suggest_quota_error(*_args: Any, **_kwargs: Any) -> None:
            raise ThinkerAPIError(
                "API credit limit reached. Please check your Anthropic billing.",
                is_quota_error=True,  # Quota error → should return 503
            )

        monkeypatch.setattr(thinker_service, "suggest_thinkers", mock_suggest_quota_error)
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": "test-api-key"})(),
        )

        response = await client.post(
            "/api/thinkers/suggest",
            json={"topic": "Metaphysics", "count": 2},
        )
        assert response.status_code == 503, (
            f"Quota API error should return 503 (Service Unavailable), got {response.status_code}"
        )
        data = response.json()
        assert "credit limit" in data["detail"]


class TestThinkerValidateAPIPath:
    """Regression tests for validate_thinker API path (thinkers.py lines 185-213).

    These lines cover paths that only execute when anthropic_api_key is set
    but the thinker name is not in the MOCK_THINKERS dict.

    Prevents regression where:
    - Unknown thinker without API key returns correct error message (line 188)
    - Valid thinker via API path triggers knowledge research (lines 198-201)
    - Non-quota validation error returns 502 instead of 503 (line 211)
    """

    async def test_validate_unknown_thinker_without_api_key_returns_helpful_error(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that unknown thinker without API key returns helpful error with list.

        Regression test: Line 188 in thinkers.py - the ThinkerValidateResponse(valid=False)
        path with error message listing accepted thinkers was previously uncovered.
        """
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": None})(),
        )

        response = await client.post(
            "/api/thinkers/validate",
            json={"name": "Friedrich Nietzsche"},  # Not in MOCK_THINKERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "error" in data
        # Error should mention accepted thinkers (Socrates, Aristotle, etc.)
        assert "Socrates" in data["error"] or "Try one of" in data["error"]

    async def test_validate_known_thinker_with_api_key_triggers_knowledge_research(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that valid thinker via API path triggers knowledge research.

        Regression test: Lines 198-201 in thinkers.py - the knowledge_service.trigger_research
        call and ThinkerValidateResponse for API-validated thinkers was previously uncovered.
        This prevents regression where knowledge research is silently skipped for API-validated
        thinkers (vs. mock thinkers where it's always called).

        Note: knowledge_service is imported locally inside validate_thinker(), so we patch at
        the module level via app.services.knowledge_research.knowledge_service.
        """
        from app.schemas import ThinkerProfile
        from app.services.thinker import thinker_service

        mock_profile = ThinkerProfile(
            name="Friedrich Nietzsche",
            bio="German philosopher (1844-1900), author of Thus Spoke Zarathustra",
            positions="Will to power, eternal recurrence, Ubermensch",
            style="Aphoristic, poetic, provocative",
        )

        async def mock_validate_returns_valid(
            *_args: Any, **_kwargs: Any
        ) -> tuple[bool, ThinkerProfile]:
            return True, mock_profile

        monkeypatch.setattr(thinker_service, "validate_thinker", mock_validate_returns_valid)
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": "test-api-key"})(),
        )

        trigger_research_calls: list[str] = []

        def mock_trigger_research(name: str) -> None:
            trigger_research_calls.append(name)

        # knowledge_service is imported inside function body, so patch at module level
        with patch(
            "app.services.knowledge_research.knowledge_service.trigger_research",
            side_effect=mock_trigger_research,
        ):
            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "Friedrich Nietzsche"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["name"] == "Friedrich Nietzsche"
        assert data["profile"] is not None
        # Verify knowledge research was triggered
        assert len(trigger_research_calls) == 1
        assert trigger_research_calls[0] == "Friedrich Nietzsche"

    async def test_validate_thinker_non_quota_error_returns_502(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that non-quota validation error returns 502.

        Regression test: Line 211 in thinkers.py - ensures non-quota errors during
        validation return 502 (Bad Gateway) not 503 (Service Unavailable).
        """
        from app.exceptions import ThinkerAPIError
        from app.services.thinker import thinker_service

        async def mock_validate_non_quota_error(*_args: Any, **_kwargs: Any) -> None:
            raise ThinkerAPIError(
                "Connection timeout while validating thinker",
                is_quota_error=False,
            )

        monkeypatch.setattr(thinker_service, "validate_thinker", mock_validate_non_quota_error)
        monkeypatch.setattr(
            "app.api.thinkers.get_settings",
            lambda: type("Settings", (), {"anthropic_api_key": "test-api-key"})(),
        )

        response = await client.post(
            "/api/thinkers/validate",
            json={"name": "PlatoNotInMock"},
        )
        assert response.status_code == 502, (
            f"Non-quota validation error should return 502, got {response.status_code}"
        )
        assert "Connection timeout" in response.json()["detail"]


class TestJWTTokenEdgeCases:
    """Regression tests for JWT token edge cases (auth.py line 50).

    Tests the path where a valid JWT token exists but has no 'sub' field.
    This can happen with malformed tokens or tokens from different systems.
    """

    async def test_jwt_token_without_sub_field_returns_401(self, client: AsyncClient) -> None:
        """Test that a valid JWT with no 'sub' field returns 401 on protected routes.

        Regression test: auth.py line 50 - get_current_user returns None when
        payload has no 'sub' field. This ensures the no-sub path is tested.

        Uses /api/auth/me which calls require_user → get_current_user (uses 'sub' field).
        Conversations use get_session_from_token (uses 'session_id' field, different path).
        """
        from app.core.auth import create_access_token

        # Create a token with no 'sub' field - only has other fields
        token_no_sub = create_access_token(data={"username": "someone", "role": "user"})
        headers = {"Authorization": f"Bearer {token_no_sub}"}

        # /api/auth/me uses require_user → get_current_user (checks 'sub' field)
        response = await client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401, (
            f"JWT with no 'sub' should return 401, got {response.status_code}"
        )

    async def test_jwt_token_with_empty_string_sub_returns_401(self, client: AsyncClient) -> None:
        """Test that a JWT with empty string 'sub' returns 401.

        Regression test: auth.py line 50 - if sub is an empty string, the
        `if not user_id:` check should catch it and return None (falsy empty string).
        """
        from app.core.auth import create_access_token

        # Empty string is falsy in Python - should be caught by `if not user_id`
        token_empty_sub = create_access_token(data={"sub": ""})
        headers = {"Authorization": f"Bearer {token_empty_sub}"}

        response = await client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401, (
            f"JWT with empty 'sub' should return 401, got {response.status_code}"
        )

    async def test_valid_jwt_with_sub_grants_access_to_me_endpoint(
        self, client: AsyncClient
    ) -> None:
        """Test that a valid JWT with correct 'sub' grants access to /api/auth/me.

        Regression test: Ensures that the fix for no-sub tokens doesn't break
        the happy path where tokens do have a valid 'sub' field.
        """
        data = await register_and_get_token(
            client, username="jwt_sub_test_user", password="testpass123"
        )
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        response = await client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["username"] == "jwt_sub_test_user"


class TestKnowledgeResearchRefreshStale:
    """Regression tests for knowledge_research.py refresh_stale_knowledge method.

    Lines 331-344 in knowledge_research.py (refresh_stale_knowledge) are uncovered.
    These tests prevent regression of the stale data refresh logic.
    """

    async def test_refresh_stale_knowledge_returns_count(self, async_session: AsyncSession) -> None:
        """Test that refresh_stale_knowledge returns count of stale entries queued.

        Regression test: Lines 331-344 in knowledge_research.py - the refresh method
        queries stale entries and triggers research for each. This test verifies the
        count is returned correctly.

        Uses direct SQL UPDATE to set updated_at to a stale timestamp after initial
        commit, because SQLAlchemy's onupdate=func.now() overrides manual datetime
        assignments during commit.
        """
        from sqlalchemy import update

        from app.models.thinker_knowledge import ResearchStatus, ThinkerKnowledge
        from app.services.knowledge_research import (
            CACHE_STALENESS_DAYS,
            knowledge_service,
        )

        # Create a COMPLETE knowledge entry
        stale_entry = ThinkerKnowledge(
            name="Heraclitus",
            status=ResearchStatus.COMPLETE,
            research_data={"wikipedia": {"title": "Heraclitus", "summary": "Greek philosopher"}},
        )
        async_session.add(stale_entry)
        await async_session.commit()

        # Use direct SQL UPDATE to bypass SQLAlchemy's onupdate=func.now()
        stale_time = datetime.now(UTC) - timedelta(days=CACHE_STALENESS_DAYS + 1)
        await async_session.execute(
            update(ThinkerKnowledge)
            .where(ThinkerKnowledge.name == "Heraclitus")
            .values(updated_at=stale_time)
        )
        await async_session.commit()

        trigger_calls: list[str] = []

        with patch.object(
            knowledge_service,
            "trigger_research",
            side_effect=lambda name: trigger_calls.append(name),
        ):
            count = await knowledge_service.refresh_stale_knowledge(async_session)

        assert count >= 1, "Should find at least 1 stale entry"
        assert "Heraclitus" in trigger_calls

    async def test_refresh_stale_knowledge_returns_zero_when_no_stale_entries(
        self, async_session: AsyncSession
    ) -> None:
        """Test that refresh_stale_knowledge returns 0 when no stale entries exist.

        Regression test: The refresh method should handle empty result set gracefully.
        An empty DB (no stale COMPLETE entries) should return 0.
        """
        from app.services.knowledge_research import knowledge_service

        # No stale entries - should return 0
        with patch.object(knowledge_service, "trigger_research"):
            count = await knowledge_service.refresh_stale_knowledge(async_session)

        assert count == 0

    async def test_refresh_stale_skips_non_complete_entries(
        self, async_session: AsyncSession
    ) -> None:
        """Test that refresh_stale_knowledge skips entries that aren't COMPLETE status.

        Regression test: Only COMPLETE entries should be refreshed. PENDING, IN_PROGRESS,
        and FAILED entries should not be unnecessarily re-researched.
        """
        from sqlalchemy import update

        from app.models.thinker_knowledge import ResearchStatus, ThinkerKnowledge
        from app.services.knowledge_research import (
            CACHE_STALENESS_DAYS,
            knowledge_service,
        )

        stale_time = datetime.now(UTC) - timedelta(days=CACHE_STALENESS_DAYS + 1)

        # Create a PENDING entry (should be skipped - only COMPLETE entries are refreshed)
        pending_entry = ThinkerKnowledge(
            name="Xenophanes",
            status=ResearchStatus.PENDING,  # NOT complete - should be skipped
            research_data={},
        )
        async_session.add(pending_entry)
        await async_session.commit()

        # Make it stale via direct SQL UPDATE
        await async_session.execute(
            update(ThinkerKnowledge)
            .where(ThinkerKnowledge.name == "Xenophanes")
            .values(updated_at=stale_time)
        )
        await async_session.commit()

        trigger_calls: list[str] = []

        with patch.object(
            knowledge_service,
            "trigger_research",
            side_effect=lambda name: trigger_calls.append(name),
        ):
            count = await knowledge_service.refresh_stale_knowledge(async_session)

        assert count == 0, "PENDING entries should not be refreshed (only COMPLETE)"
        assert "Xenophanes" not in trigger_calls


class TestThinkerLastUserMessageTimestamp:
    """Regression tests for ThinkerService._get_last_user_message_timestamp.

    This method (thinker.py line 1421-1431) extracts the timestamp of the last user
    message. It's used by the idle timeout feature to detect when users are inactive.
    Tests prevent regression of the idle timeout behavior.
    """

    def test_get_last_user_message_timestamp_returns_zero_for_no_messages(self) -> None:
        """Test that _get_last_user_message_timestamp returns 0.0 for empty messages.

        Regression test: The method should return 0.0 (not raise) when messages list
        is empty. This is the "no messages" base case for idle timeout.
        """
        from app.services.thinker import ThinkerService

        service = ThinkerService()
        result = service._get_last_user_message_timestamp([])
        assert result == 0.0

    def test_get_last_user_message_timestamp_skips_thinker_messages(self) -> None:
        """Test that _get_last_user_message_timestamp skips thinker messages.

        Regression test: The method should iterate in reverse and skip thinker
        messages until it finds a user message. If all messages are from thinkers,
        it returns 0.0.
        """
        from app.services.thinker import ThinkerService

        service = ThinkerService()

        # Create mock messages - all from thinkers, no user messages
        thinker_msg1 = MagicMock()
        thinker_msg1.sender_type = "thinker"
        thinker_msg1.created_at = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)

        thinker_msg2 = MagicMock()
        thinker_msg2.sender_type = "thinker"
        thinker_msg2.created_at = datetime(2026, 3, 1, 10, 5, 0, tzinfo=UTC)

        result = service._get_last_user_message_timestamp([thinker_msg1, thinker_msg2])
        assert result == 0.0, "Should return 0.0 when no user messages exist"

    def test_get_last_user_message_timestamp_finds_user_message(self) -> None:
        """Test that _get_last_user_message_timestamp returns user message timestamp.

        Regression test: The method should correctly find and return the timestamp
        of the most recent user message, even when thinker messages follow it.
        """
        from app.services.thinker import ThinkerService

        service = ThinkerService()

        user_time = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
        thinker_time = datetime(2026, 3, 1, 10, 5, 0, tzinfo=UTC)

        user_msg = MagicMock()
        user_msg.sender_type = "user"
        user_msg.created_at = user_time

        thinker_msg = MagicMock()
        thinker_msg.sender_type = "thinker"
        thinker_msg.created_at = thinker_time

        # Thinker message is last in list, but user message should be found
        result = service._get_last_user_message_timestamp([user_msg, thinker_msg])
        assert result == user_time.timestamp(), (
            "Should return user message timestamp, not thinker message timestamp"
        )

    def test_get_last_user_message_timestamp_uses_enum_value(self) -> None:
        """Test that _get_last_user_message_timestamp handles enum sender_type.

        Regression test: The method checks both `sender.value == 'user'` (for enum)
        and `sender == 'user'` (for string). Tests the enum path.
        """
        from app.services.thinker import ThinkerService

        service = ThinkerService()

        user_time = datetime(2026, 3, 1, 9, 30, 0, tzinfo=UTC)

        # Create a message with enum-style sender_type
        enum_sender = MagicMock()
        enum_sender.value = "user"  # Mimics SenderType.USER enum

        user_msg = MagicMock()
        user_msg.sender_type = enum_sender
        user_msg.created_at = user_time

        result = service._get_last_user_message_timestamp([user_msg])
        assert result == user_time.timestamp(), (
            "Should handle enum sender_type with .value == 'user'"
        )

    def test_get_last_user_message_timestamp_returns_most_recent(self) -> None:
        """Test that _get_last_user_message_timestamp returns the LAST user message.

        Regression test: With multiple user messages, the method should return
        the timestamp of the most recent one (last in list), not the first.
        """
        from app.services.thinker import ThinkerService

        service = ThinkerService()

        earlier_time = datetime(2026, 3, 1, 9, 0, 0, tzinfo=UTC)
        later_time = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)

        user_msg1 = MagicMock()
        user_msg1.sender_type = "user"
        user_msg1.created_at = earlier_time

        user_msg2 = MagicMock()
        user_msg2.sender_type = "user"
        user_msg2.created_at = later_time

        result = service._get_last_user_message_timestamp([user_msg1, user_msg2])
        assert result == later_time.timestamp(), (
            "Should return timestamp of LAST user message, not first"
        )


class TestIdlePauseResumeCycle:
    """Regression tests for idle pause/resume cycle (thinker.py, PR #483).

    Bug: idle_timeout auto-pause was introduced but pause_for_idle and resume_from_idle
    needed to distinguish between idle pauses and manual pauses.
    Fix: Added separate idle pause flag so resume_from_idle doesn't clear manual pauses.

    Prevents regression where:
    - Manual pause is incorrectly cleared by user sending a message
    - Idle pause flag bleeds into manual pause detection
    """

    def test_pause_for_idle_sets_idle_flag(self) -> None:
        """Test that pause_for_idle marks conversation as both paused and idle-paused.

        Regression test: PR #483 - idle pause should set both is_paused and is_idle_paused.
        """
        from app.services.thinker import ThinkerService

        service = ThinkerService()
        conv_id = "idle-test-conv-1"

        service.pause_for_idle(conv_id)

        assert service.is_paused(conv_id), "pause_for_idle should mark conversation as paused"
        assert service.is_idle_paused(conv_id), (
            "pause_for_idle should mark conversation as idle-paused"
        )

    def test_resume_from_idle_clears_idle_pause(self) -> None:
        """Test that resume_from_idle clears the idle pause state.

        Regression test: PR #483 - after idle pause is cleared, conversation should
        no longer be paused or idle-paused.
        """
        from app.services.thinker import ThinkerService

        service = ThinkerService()
        conv_id = "idle-test-conv-2"

        service.pause_for_idle(conv_id)
        assert service.is_idle_paused(conv_id)

        service.resume_from_idle(conv_id)

        assert not service.is_paused(conv_id), "resume_from_idle should clear the paused state"
        assert not service.is_idle_paused(conv_id), (
            "resume_from_idle should clear the idle-paused state"
        )

    def test_resume_from_idle_does_not_clear_manual_pause(self) -> None:
        """Test that resume_from_idle does NOT clear a manually paused conversation.

        Regression test: PR #483 - critical to prevent user confusion. If user
        manually pauses a conversation, sending a message should NOT auto-resume it.
        Only conversations paused due to idle timeout should be auto-resumed.
        """
        from app.services.thinker import ThinkerService

        service = ThinkerService()
        conv_id = "manual-pause-conv"

        # Manually pause (not idle pause)
        service.pause_conversation(conv_id)
        assert service.is_paused(conv_id)
        assert not service.is_idle_paused(conv_id)  # Manual pause is NOT idle pause

        # Attempt to resume from idle - should NOT clear manual pause
        service.resume_from_idle(conv_id)

        assert service.is_paused(conv_id), (
            "resume_from_idle should NOT clear a manually paused conversation"
        )

    def test_is_idle_paused_is_false_for_manual_pause(self) -> None:
        """Test that is_idle_paused returns False for manually paused conversations.

        Regression test: Ensures the idle pause flag correctly distinguishes between
        idle and manual pauses. API can use is_idle_paused to inform frontend whether
        the pause was automatic or manual.
        """
        from app.services.thinker import ThinkerService

        service = ThinkerService()
        conv_id = "manual-only-conv"

        # Only manually pause
        service.pause_conversation(conv_id)

        assert service.is_paused(conv_id), "Manual pause should set is_paused"
        assert not service.is_idle_paused(conv_id), "Manual pause should NOT set is_idle_paused"

    def test_full_idle_pause_resume_cycle(self) -> None:
        """Test complete idle pause → user sends message → conversation resumes cycle.

        Regression test: Full lifecycle test for PR #483. Simulates the user experience
        where idle timeout pauses, then user sends message to resume.
        """
        from app.services.thinker import ThinkerService

        service = ThinkerService()
        conv_id = "full-cycle-conv"

        # Initial state: not paused
        assert not service.is_paused(conv_id)
        assert not service.is_idle_paused(conv_id)

        # Idle timeout triggers
        service.pause_for_idle(conv_id)
        assert service.is_paused(conv_id)
        assert service.is_idle_paused(conv_id)

        # User sends a message → auto-resume
        service.resume_from_idle(conv_id)
        assert not service.is_paused(conv_id)
        assert not service.is_idle_paused(conv_id)

    def test_multiple_idle_pauses_are_idempotent(self) -> None:
        """Test that calling pause_for_idle multiple times is safe.

        Regression test: Ensures that multiple idle timeout signals don't corrupt state.
        """
        from app.services.thinker import ThinkerService

        service = ThinkerService()
        conv_id = "idempotent-idle-conv"

        # Call pause_for_idle multiple times
        service.pause_for_idle(conv_id)
        service.pause_for_idle(conv_id)
        service.pause_for_idle(conv_id)

        # Should still be idle-paused, not in some corrupt state
        assert service.is_paused(conv_id)
        assert service.is_idle_paused(conv_id)

        # And resume should still work correctly
        service.resume_from_idle(conv_id)
        assert not service.is_paused(conv_id)
        assert not service.is_idle_paused(conv_id)


class TestThinkerAPIKnowledgeIntegration:
    """Regression tests for thinker knowledge integration (thinkers.py lines 168-184).

    Tests the validate_thinker path for MOCK_THINKERS where Wikipedia image is fetched
    and knowledge research is triggered. Lines 168-184 are covered, but these tests
    document the expected behavior for the mock thinker path and prevent regression.

    Note: knowledge_service is imported inside function body in thinkers.py, so we patch
    at the service module level: app.services.knowledge_research.knowledge_service
    """

    async def test_validate_mock_thinker_triggers_knowledge_research(
        self, client: AsyncClient
    ) -> None:
        """Test that validating a mock thinker triggers knowledge research.

        Regression test: When validating a well-known thinker (in MOCK_THINKERS dict),
        knowledge_service.trigger_research should be called. This ensures the AI
        has background knowledge to draw from for conversations.
        """
        from app.services.thinker import thinker_service

        trigger_calls: list[str] = []

        # Patch at module level since knowledge_service is imported inside function body
        with patch(
            "app.services.knowledge_research.knowledge_service.trigger_research",
            side_effect=lambda name: trigger_calls.append(name),
        ), patch.object(
            thinker_service,
            "get_wikipedia_image",
            AsyncMock(return_value="https://example.com/socrates.jpg"),
        ):
            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "Socrates"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["name"] == "Socrates"
        # Knowledge research should be triggered
        assert len(trigger_calls) >= 1
        assert "Socrates" in trigger_calls

    async def test_validate_mock_thinker_includes_wikipedia_image(
        self, client: AsyncClient
    ) -> None:
        """Test that validating a mock thinker fetches and includes Wikipedia image.

        Regression test: The validate endpoint should enrich mock thinker profiles
        with Wikipedia images. Without images, the UI shows placeholder avatars.
        """
        from app.services.thinker import thinker_service

        with patch(
            "app.services.knowledge_research.knowledge_service.trigger_research",
        ), patch.object(
            thinker_service,
            "get_wikipedia_image",
            AsyncMock(return_value="https://upload.wikimedia.org/aristotle.jpg"),
        ):
            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "Aristotle"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["profile"]["image_url"] == "https://upload.wikimedia.org/aristotle.jpg"

    async def test_validate_mock_thinker_handles_missing_wikipedia_image(
        self, client: AsyncClient
    ) -> None:
        """Test that validating a mock thinker handles missing Wikipedia image gracefully.

        Regression test: Wikipedia image fetch can return None (no image found).
        The validate endpoint should still succeed and return a valid profile.
        """
        from app.services.thinker import thinker_service

        with patch(
            "app.services.knowledge_research.knowledge_service.trigger_research",
        ), patch.object(
            thinker_service,
            "get_wikipedia_image",
            AsyncMock(return_value=None),  # No image found
        ):
            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "Maya Angelou"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        # Profile should exist but image_url may be None
        assert data["profile"] is not None
