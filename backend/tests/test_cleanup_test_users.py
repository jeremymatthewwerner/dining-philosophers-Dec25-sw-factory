"""Tests for the test user cleanup endpoint.

Fixtures (engine, db_session, client) are inherited from conftest.py,
eliminating ~50 lines of boilerplate that was duplicated here.
"""

from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def create_test_user(
    session: AsyncSession, username: str, password_hash: str = "hash123"
) -> User:
    """Helper to create a user in the database."""
    user = User(
        username=username,
        password_hash=password_hash,
        display_name=username,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def test_cleanup_without_secret_configured(client: AsyncClient) -> None:
    """Test cleanup fails when secret is not configured."""
    # The default settings have empty test_cleanup_secret
    response = await client.delete("/api/test/cleanup-test-users?secret=any-secret")

    assert response.status_code == 403
    assert "not configured" in response.json()["detail"].lower()


async def test_cleanup_with_invalid_secret(client: AsyncClient) -> None:
    """Test cleanup fails with invalid secret."""
    with patch("app.api.test_helpers.get_settings") as mock_settings:
        mock_settings.return_value.test_cleanup_secret = "correct-secret"

        response = await client.delete("/api/test/cleanup-test-users?secret=wrong-secret")

        assert response.status_code == 403
        assert "invalid" in response.json()["detail"].lower()


async def test_cleanup_deletes_smoketest_users(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test cleanup deletes users with smoketest_ prefix."""
    # Create test users
    await create_test_user(db_session, "smoketest_123456")
    await create_test_user(db_session, "smoketest_789")
    await create_test_user(db_session, "real_user")  # Should not be deleted

    with patch("app.api.test_helpers.get_settings") as mock_settings:
        mock_settings.return_value.test_cleanup_secret = "test-secret"

        response = await client.delete("/api/test/cleanup-test-users?secret=test-secret")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2
        assert "smoketest_123456" in data["deleted_users"]
        assert "smoketest_789" in data["deleted_users"]
        assert "real_user" not in data["deleted_users"]


async def test_cleanup_deletes_canary_users(client: AsyncClient, db_session: AsyncSession) -> None:
    """Test cleanup deletes users with canary_ prefix."""
    # Create test users
    await create_test_user(db_session, "canary_1704412800_12345")
    await create_test_user(db_session, "canary_1704412900")
    await create_test_user(db_session, "real_user")  # Should not be deleted

    with patch("app.api.test_helpers.get_settings") as mock_settings:
        mock_settings.return_value.test_cleanup_secret = "test-secret"

        response = await client.delete("/api/test/cleanup-test-users?secret=test-secret")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2
        assert "canary_1704412800_12345" in data["deleted_users"]
        assert "canary_1704412900" in data["deleted_users"]


async def test_cleanup_deletes_testuser_users(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test cleanup deletes users with testuser_ prefix (E2E test users)."""
    # Create test users following the E2E pattern: testuser_{timestamp}_{random}
    await create_test_user(db_session, "testuser_1704412800_abc123")
    await create_test_user(db_session, "testuser_1704412900_xyz456")
    await create_test_user(db_session, "real_user")  # Should not be deleted

    with patch("app.api.test_helpers.get_settings") as mock_settings:
        mock_settings.return_value.test_cleanup_secret = "test-secret"

        response = await client.delete("/api/test/cleanup-test-users?secret=test-secret")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2
        assert "testuser_1704412800_abc123" in data["deleted_users"]
        assert "testuser_1704412900_xyz456" in data["deleted_users"]
        assert "real_user" not in data["deleted_users"]


async def test_cleanup_deletes_mixed_test_users(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test cleanup deletes smoketest_, canary_, and testuser_ users."""
    # Create test users
    await create_test_user(db_session, "smoketest_abc")
    await create_test_user(db_session, "canary_xyz")
    await create_test_user(db_session, "testuser_123_def")
    await create_test_user(db_session, "regular_user")

    with patch("app.api.test_helpers.get_settings") as mock_settings:
        mock_settings.return_value.test_cleanup_secret = "test-secret"

        response = await client.delete("/api/test/cleanup-test-users?secret=test-secret")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 3


async def test_cleanup_no_test_users(client: AsyncClient, db_session: AsyncSession) -> None:
    """Test cleanup returns zero when no test users exist."""
    # Create only regular users
    await create_test_user(db_session, "regular_user1")
    await create_test_user(db_session, "regular_user2")

    with patch("app.api.test_helpers.get_settings") as mock_settings:
        mock_settings.return_value.test_cleanup_secret = "test-secret"

        response = await client.delete("/api/test/cleanup-test-users?secret=test-secret")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 0
        assert data["deleted_users"] == []


async def test_cleanup_missing_secret_param(client: AsyncClient) -> None:
    """Test cleanup fails when secret parameter is missing."""
    response = await client.delete("/api/test/cleanup-test-users")

    # FastAPI returns 422 for missing required query params
    assert response.status_code == 422
