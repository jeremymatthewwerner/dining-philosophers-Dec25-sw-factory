"""Integration tests for the DevOps API endpoints.

Tests the protected DevOps API used by autonomous agents for database maintenance,
including authentication, stats retrieval, and cleanup operations.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, Session
from app.models.base import generate_uuid
from tests.conftest import get_auth_headers

# Test secret for DevOps API authentication
TEST_DEVOPS_SECRET = "test-devops-secret"


# ============================================================================
# Authentication Tests
# ============================================================================


@pytest.mark.asyncio
async def test_devops_health_with_valid_secret(client: AsyncClient) -> None:
    """Test DevOps health endpoint with valid secret."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        response = await client.get(
            "/api/devops/health",
            headers={"X-DevOps-Secret": TEST_DEVOPS_SECRET},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "devops-api"


@pytest.mark.asyncio
async def test_devops_health_without_secret(client: AsyncClient) -> None:
    """Test DevOps health endpoint without secret header (403)."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        response = await client.get("/api/devops/health")

        assert response.status_code == 403
        assert "Invalid or missing" in response.json()["detail"]


@pytest.mark.asyncio
async def test_devops_health_with_invalid_secret(client: AsyncClient) -> None:
    """Test DevOps health endpoint with wrong secret (403)."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        response = await client.get(
            "/api/devops/health",
            headers={"X-DevOps-Secret": "wrong-secret"},
        )

        assert response.status_code == 403
        assert "Invalid or missing" in response.json()["detail"]


@pytest.mark.asyncio
async def test_devops_health_not_configured(client: AsyncClient) -> None:
    """Test DevOps health endpoint when DEVOPS_API_SECRET not set (503)."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = ""

        response = await client.get(
            "/api/devops/health",
            headers={"X-DevOps-Secret": "any-secret"},
        )

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]


# ============================================================================
# Stats Endpoint Tests
# ============================================================================


@pytest.mark.asyncio
async def test_stats_with_valid_secret(client: AsyncClient) -> None:
    """Test stats endpoint with valid secret returns database counts."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        # Get auth headers
        auth_headers = await get_auth_headers(client)

        # Create some data first
        await client.post(
            "/api/conversations",
            json={
                "topic": "Test conversation for stats",
                "thinkers": [
                    {
                        "name": "Socrates",
                        "bio": "Ancient Greek philosopher",
                        "positions": "Socratic method",
                        "style": "Dialectic questioning",
                    },
                    {
                        "name": "Plato",
                        "bio": "Student of Socrates",
                        "positions": "Theory of forms",
                        "style": "Dialogue",
                    },
                ],
            },
            headers=auth_headers,
        )

        response = await client.get(
            "/api/devops/stats",
            headers={"X-DevOps-Secret": TEST_DEVOPS_SECRET},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "users" in data
        assert "sessions" in data
        assert "conversations" in data
        assert "messages" in data
        assert "thinkers" in data
        assert "timestamp" in data

        # Verify all counts are non-negative integers
        assert isinstance(data["users"], int)
        assert isinstance(data["sessions"], int)
        assert isinstance(data["conversations"], int)
        assert isinstance(data["messages"], int)
        assert isinstance(data["thinkers"], int)

        # Since we created data, counts should be > 0
        assert data["users"] > 0
        assert data["sessions"] > 0
        assert data["conversations"] > 0


@pytest.mark.asyncio
async def test_stats_without_secret(client: AsyncClient) -> None:
    """Test stats endpoint without secret header (403)."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        response = await client.get("/api/devops/stats")

        assert response.status_code == 403


@pytest.mark.asyncio
async def test_stats_with_invalid_secret(client: AsyncClient) -> None:
    """Test stats endpoint with wrong secret (403)."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        response = await client.get(
            "/api/devops/stats",
            headers={"X-DevOps-Secret": "wrong-secret"},
        )

        assert response.status_code == 403


# ============================================================================
# Stale Sessions Cleanup Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cleanup_stale_sessions_dry_run(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    """Test stale session cleanup with dry_run=True (preview mode)."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        # Get auth headers (this creates a user and session)
        await get_auth_headers(client)

        # Create an old session by manually inserting with old timestamp
        result = await async_session.execute(select(Session))
        sessions_before = result.scalars().all()
        count_before = len(sessions_before)

        # Create an old session
        old_session = Session(
            user_id=sessions_before[0].user_id,
            created_at=datetime.now(UTC) - timedelta(days=10),
        )
        async_session.add(old_session)
        await async_session.commit()

        # Dry run should preview without deleting
        response = await client.delete(
            "/api/devops/cleanup/stale-sessions?older_than_hours=168&dry_run=true",
            headers={"X-DevOps-Secret": TEST_DEVOPS_SECRET},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["dry_run"] is True
        assert data["deleted_count"] >= 1  # Should find at least our old session

        # Verify nothing was actually deleted
        result = await async_session.execute(select(Session))
        sessions_after = result.scalars().all()
        assert len(sessions_after) == count_before + 1  # Still has the old session


@pytest.mark.asyncio
async def test_cleanup_stale_sessions_actually_deletes(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    """Test stale session cleanup actually deletes old sessions."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        # Get auth headers (creates a user and session)
        await get_auth_headers(client)

        # Get existing session
        result = await async_session.execute(select(Session))
        sessions = result.scalars().all()
        user_id = sessions[0].user_id

        # Create 3 old sessions
        for _ in range(3):
            old_session = Session(
                user_id=user_id,
                created_at=datetime.now(UTC) - timedelta(days=8),
            )
            async_session.add(old_session)
        await async_session.commit()

        # Get count before cleanup
        result = await async_session.execute(select(Session))
        count_before = len(result.scalars().all())

        # Run cleanup without dry_run
        response = await client.delete(
            "/api/devops/cleanup/stale-sessions?older_than_hours=168",
            headers={"X-DevOps-Secret": TEST_DEVOPS_SECRET},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["dry_run"] is False
        assert data["deleted_count"] >= 3

        # Verify sessions were actually deleted
        result = await async_session.execute(select(Session))
        count_after = len(result.scalars().all())
        assert count_after < count_before


@pytest.mark.asyncio
async def test_cleanup_stale_sessions_respects_threshold(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    """Test stale session cleanup respects older_than_hours parameter."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        # Get auth headers (creates a user and session)
        await get_auth_headers(client)

        # Get existing session
        result = await async_session.execute(select(Session))
        sessions = result.scalars().all()
        user_id = sessions[0].user_id

        # Create one recent session (2 days old) and one old session (10 days old)
        recent_session = Session(
            user_id=user_id,
            created_at=datetime.now(UTC) - timedelta(days=2),
        )
        old_session = Session(
            user_id=user_id,
            created_at=datetime.now(UTC) - timedelta(days=10),
        )
        async_session.add(recent_session)
        async_session.add(old_session)
        await async_session.commit()

        # Cleanup sessions older than 5 days
        response = await client.delete(
            "/api/devops/cleanup/stale-sessions?older_than_hours=120",
            headers={"X-DevOps-Secret": TEST_DEVOPS_SECRET},
        )

        assert response.status_code == 200

        # Should delete only the 10-day-old session, not the 2-day-old one
        # Get all remaining sessions
        result = await async_session.execute(select(Session))
        remaining_sessions = result.scalars().all()

        # The recent session should still exist (check by comparing creation time)
        # We should have at least 2 sessions (the one from get_auth_headers + our recent one)
        assert len(remaining_sessions) >= 2

        # Verify at least one session is less than 4 days old (our recent session)
        # Handle both timezone-aware and naive datetimes from SQLite
        def days_since_creation(s: Session) -> int:
            if s.created_at.tzinfo is None:
                return (datetime.now(UTC).replace(tzinfo=None) - s.created_at).days
            return (datetime.now(UTC) - s.created_at).days

        recent_found = any(days_since_creation(s) < 4 for s in remaining_sessions)
        assert recent_found, "Recent session was incorrectly deleted"


@pytest.mark.asyncio
async def test_cleanup_stale_sessions_without_secret(client: AsyncClient) -> None:
    """Test stale session cleanup without secret (403)."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        response = await client.delete("/api/devops/cleanup/stale-sessions")

        assert response.status_code == 403


# ============================================================================
# Orphan Cleanup Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cleanup_orphans_dry_run(client: AsyncClient, async_session: AsyncSession) -> None:
    """Test orphan cleanup with dry_run=True (preview mode)."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        # Get counts before
        result = await async_session.execute(select(Conversation))
        conv_count_before = len(result.scalars().all())

        # Dry run should preview without deleting
        response = await client.delete(
            "/api/devops/cleanup/orphans?dry_run=true",
            headers={"X-DevOps-Secret": TEST_DEVOPS_SECRET},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["dry_run"] is True
        assert "details" in data
        assert "orphan_conversations" in data["details"]
        assert "orphan_messages" in data["details"]

        # Verify nothing was actually deleted
        result = await async_session.execute(select(Conversation))
        conv_count_after = len(result.scalars().all())
        assert conv_count_after == conv_count_before


@pytest.mark.asyncio
async def test_cleanup_orphans_deletes_orphaned_conversations(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    """Test orphan cleanup deletes conversations with non-existent sessions."""
    from sqlalchemy import text

    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        # Create an orphan conversation directly in the DB with a non-existent session_id
        # This bypasses foreign key checks and creates a true orphan
        orphan_id = "orphan-conv-" + generate_uuid()[:8]
        fake_session_id = "nonexistent-session-" + generate_uuid()[:8]

        await async_session.execute(
            text(
                "INSERT INTO conversations (id, session_id, topic, is_active, created_at, updated_at) "
                "VALUES (:id, :session_id, :topic, :is_active, datetime('now'), datetime('now'))"
            ),
            {
                "id": orphan_id,
                "session_id": fake_session_id,
                "topic": "Orphan conversation for cleanup test",
                "is_active": True,
            },
        )
        await async_session.commit()

        # Verify the orphan was created
        result = await async_session.execute(
            select(Conversation).where(Conversation.id == orphan_id)
        )
        orphan_conv = result.scalar_one_or_none()
        assert orphan_conv is not None, "Orphan conversation was not created"

        # Run orphan cleanup
        response = await client.delete(
            "/api/devops/cleanup/orphans",
            headers={"X-DevOps-Secret": TEST_DEVOPS_SECRET},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] > 0
        assert data["details"]["orphan_conversations"] >= 1

        # Verify the orphaned conversation was deleted
        result = await async_session.execute(
            select(Conversation).where(Conversation.id == orphan_id)
        )
        deleted_conversation = result.scalar_one_or_none()
        assert deleted_conversation is None


@pytest.mark.asyncio
async def test_cleanup_orphans_deletes_orphaned_messages(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    """Test orphan cleanup deletes messages with non-existent conversations."""
    from sqlalchemy import text

    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        # Create an orphan message directly in the DB with a non-existent conversation_id
        # This bypasses foreign key checks and creates a true orphan
        orphan_msg_id = "orphan-msg-" + generate_uuid()[:8]
        fake_conv_id = "nonexistent-conv-" + generate_uuid()[:8]

        await async_session.execute(
            text(
                "INSERT INTO messages (id, conversation_id, sender_type, sender_name, content, created_at, updated_at) "
                "VALUES (:id, :conv_id, :sender_type, :sender_name, :content, datetime('now'), datetime('now'))"
            ),
            {
                "id": orphan_msg_id,
                "conv_id": fake_conv_id,
                "sender_type": "user",
                "sender_name": "TestUser",
                "content": "Orphan message for cleanup test",
            },
        )
        await async_session.commit()

        # Verify the orphan was created
        result = await async_session.execute(select(Message).where(Message.id == orphan_msg_id))
        orphan_msg = result.scalar_one_or_none()
        assert orphan_msg is not None, "Orphan message was not created"

        # Run orphan cleanup
        response = await client.delete(
            "/api/devops/cleanup/orphans",
            headers={"X-DevOps-Secret": TEST_DEVOPS_SECRET},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["details"]["orphan_messages"] >= 1

        # Verify the orphaned message was deleted
        result = await async_session.execute(select(Message).where(Message.id == orphan_msg_id))
        deleted_msg = result.scalar_one_or_none()
        assert deleted_msg is None


@pytest.mark.asyncio
async def test_cleanup_orphans_without_secret(client: AsyncClient) -> None:
    """Test orphan cleanup without secret (403)."""
    with patch("app.api.devops.get_settings") as mock_settings:
        mock_settings.return_value.devops_api_secret = TEST_DEVOPS_SECRET

        response = await client.delete("/api/devops/cleanup/orphans")

        assert response.status_code == 403
