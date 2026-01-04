"""Tests for the test user cleanup endpoint."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import get_db
from app.main import app
from app.models import Base, User


@pytest.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite engine for testing."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session_maker() as session:
        yield session


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database override."""
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


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


@pytest.mark.asyncio
async def test_cleanup_without_secret_configured(client: AsyncClient) -> None:
    """Test cleanup fails when secret is not configured."""
    # The default settings have empty test_cleanup_secret
    response = await client.delete("/api/test/cleanup-test-users?secret=any-secret")

    assert response.status_code == 403
    assert "not configured" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cleanup_with_invalid_secret(client: AsyncClient) -> None:
    """Test cleanup fails with invalid secret."""
    with patch("app.api.test_helpers.get_settings") as mock_settings:
        mock_settings.return_value.test_cleanup_secret = "correct-secret"

        response = await client.delete("/api/test/cleanup-test-users?secret=wrong-secret")

        assert response.status_code == 403
        assert "invalid" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cleanup_deletes_smoketest_users(client: AsyncClient, session: AsyncSession) -> None:
    """Test cleanup deletes users with smoketest_ prefix."""
    # Create test users
    await create_test_user(session, "smoketest_123456")
    await create_test_user(session, "smoketest_789")
    await create_test_user(session, "real_user")  # Should not be deleted

    with patch("app.api.test_helpers.get_settings") as mock_settings:
        mock_settings.return_value.test_cleanup_secret = "test-secret"

        response = await client.delete("/api/test/cleanup-test-users?secret=test-secret")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2
        assert "smoketest_123456" in data["deleted_users"]
        assert "smoketest_789" in data["deleted_users"]
        assert "real_user" not in data["deleted_users"]


@pytest.mark.asyncio
async def test_cleanup_deletes_canary_users(client: AsyncClient, session: AsyncSession) -> None:
    """Test cleanup deletes users with canary_ prefix."""
    # Create test users
    await create_test_user(session, "canary_1704412800_12345")
    await create_test_user(session, "canary_1704412900")
    await create_test_user(session, "real_user")  # Should not be deleted

    with patch("app.api.test_helpers.get_settings") as mock_settings:
        mock_settings.return_value.test_cleanup_secret = "test-secret"

        response = await client.delete("/api/test/cleanup-test-users?secret=test-secret")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2
        assert "canary_1704412800_12345" in data["deleted_users"]
        assert "canary_1704412900" in data["deleted_users"]


@pytest.mark.asyncio
async def test_cleanup_deletes_mixed_test_users(client: AsyncClient, session: AsyncSession) -> None:
    """Test cleanup deletes both smoketest_ and canary_ users."""
    # Create test users
    await create_test_user(session, "smoketest_abc")
    await create_test_user(session, "canary_xyz")
    await create_test_user(session, "regular_user")

    with patch("app.api.test_helpers.get_settings") as mock_settings:
        mock_settings.return_value.test_cleanup_secret = "test-secret"

        response = await client.delete("/api/test/cleanup-test-users?secret=test-secret")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2


@pytest.mark.asyncio
async def test_cleanup_no_test_users(client: AsyncClient, session: AsyncSession) -> None:
    """Test cleanup returns zero when no test users exist."""
    # Create only regular users
    await create_test_user(session, "regular_user1")
    await create_test_user(session, "regular_user2")

    with patch("app.api.test_helpers.get_settings") as mock_settings:
        mock_settings.return_value.test_cleanup_secret = "test-secret"

        response = await client.delete("/api/test/cleanup-test-users?secret=test-secret")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 0
        assert data["deleted_users"] == []


@pytest.mark.asyncio
async def test_cleanup_missing_secret_param(client: AsyncClient) -> None:
    """Test cleanup fails when secret parameter is missing."""
    response = await client.delete("/api/test/cleanup-test-users")

    # FastAPI returns 422 for missing required query params
    assert response.status_code == 422
