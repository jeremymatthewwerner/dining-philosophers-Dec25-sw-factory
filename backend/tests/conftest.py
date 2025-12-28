"""Shared test fixtures for all test files."""

import gc
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from anthropic.types import TextBlock
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base


# Disable tracemalloc to avoid circular import issues in pytest's unraisable hook
# This fixes "AttributeError: partially initialized module 'tracemalloc'" errors
@pytest.fixture(autouse=True)
def disable_tracemalloc_for_unraisable() -> None:
    """Disable tracemalloc to prevent circular import errors during test cleanup."""
    import tracemalloc

    if tracemalloc.is_tracing():
        tracemalloc.stop()


@pytest.fixture(autouse=True)
def cleanup_gc() -> Generator[None, None, None]:
    """Force garbage collection after each test to clean up dangling connections."""
    yield
    gc.collect()


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
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


# Test data constants
TEST_USER_ID = "user-123"
TEST_TOKEN = "jwt-token-123"
TEST_TIMESTAMP = "2024-01-15T10:00:00Z"


# Thinker-related fixtures (for test_thinker_service.py)
@pytest.fixture
def mock_thinker() -> MagicMock:
    """Create a standard mock thinker object for testing.

    Reduces duplication across test_thinker_service.py where this pattern
    appears 25+ times with identical values.
    """
    thinker = MagicMock()
    thinker.name = "Socrates"
    thinker.bio = "Ancient philosopher"
    thinker.positions = "Questioning everything"
    thinker.style = "Socratic method"
    return thinker


@pytest.fixture
def mock_anthropic_client() -> AsyncMock:
    """Create a mock Anthropic API client.

    Reduces duplication of client mocking pattern that appears 15+ times.
    """
    mock_client = AsyncMock()
    mock_client.messages = AsyncMock()
    return mock_client


def create_text_block_response(json_content: str) -> MagicMock:
    """Create a mock API response with TextBlock content.

    Helper function to reduce duplication of response creation pattern
    that appears 15+ times in test_thinker_service.py.

    Args:
        json_content: The JSON string content for the TextBlock

    Returns:
        Mock response object with TextBlock in content list
    """
    mock_response = MagicMock()
    mock_response.content = [TextBlock(type="text", text=json_content)]
    return mock_response


def create_suggest_thinkers_response(
    names: list[str] | None = None,
) -> MagicMock:
    """Create a mock API response for suggest_thinkers endpoint.

    Args:
        names: List of thinker names to include (default: ["Socrates"])

    Returns:
        Mock response with formatted thinker suggestions
    """
    if names is None:
        names = ["Socrates"]

    thinkers_json = (
        "[\n"
        + ",\n".join(
            [
                '  {"name": "' + name + '", "bio": "Ancient philosopher", '
                '"positions": "Various", "style": "Dialectic"}'
                for name in names
            ]
        )
        + "\n]"
    )

    return create_text_block_response(thinkers_json)


def create_validate_thinker_response(is_valid: bool = True) -> MagicMock:
    """Create a mock API response for validate_thinker endpoint.

    Args:
        is_valid: Whether the thinker should be valid

    Returns:
        Mock response with validation result
    """
    response_json = (
        '{"valid": true, "bio": "Ancient philosopher"}'
        if is_valid
        else '{"valid": false, "error": "Not a real person"}'
    )
    return create_text_block_response(response_json)


# Async session fixture for knowledge research tests
@pytest.fixture
async def async_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create an async database session for testing."""
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


# Auth token fixture for API tests
@pytest.fixture
async def auth_token(async_session: AsyncSession) -> str:
    """Create a test user and return an auth token."""
    from app.core.auth import create_access_token, get_password_hash
    from app.models import User

    # Create test user
    user = User(
        username="testuser",
        password_hash=get_password_hash("testpass"),
        is_admin=False,
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    # Create JWT token with user ID in the 'sub' field
    token = create_access_token(data={"sub": user.id})
    return token
