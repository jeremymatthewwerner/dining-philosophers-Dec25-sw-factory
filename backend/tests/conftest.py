"""Shared test fixtures for all test files."""

import gc
from collections.abc import AsyncGenerator, Generator
from typing import TYPE_CHECKING, Any
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

if TYPE_CHECKING:
    from httpx import AsyncClient


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


# Test client fixture for API tests
@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncGenerator["AsyncClient", None]:
    """Create a test client with database override.

    Centralizes client fixture previously duplicated in test_api.py and
    test_api_edge_cases.py.
    """
    from httpx import ASGITransport, AsyncClient

    from app.core.database import get_db
    from app.main import app

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


# Test helper functions
async def register_and_get_token(
    client: "AsyncClient",
    username: str = "testuser",
    password: str = "testpass123",
    display_name: str | None = None,
) -> Any:
    """Helper to register a user and get their auth token.

    Centralized from test_api.py where it was defined but imported by other test files.

    Args:
        client: AsyncClient for making requests
        username: Username for registration
        password: Password for registration
        display_name: Optional display name (defaults to title-cased username)

    Returns:
        Response data dict containing access_token and user info
    """
    response = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": display_name or username.title(),
            "password": password,
        },
    )
    assert response.status_code == 200
    return response.json()


async def get_auth_headers(
    client: "AsyncClient",
    username: str = "testuser",
    password: str = "testpass123",
) -> dict[str, str]:
    """Helper to get authorization headers for an authenticated user.

    Centralized from test_api.py where it was defined but imported by other test files.

    Args:
        client: AsyncClient for making requests
        username: Username for authentication
        password: Password for authentication

    Returns:
        Dictionary with Authorization header
    """
    data = await register_and_get_token(client, username, password)
    return {"Authorization": f"Bearer {data['access_token']}"}


async def create_test_conversation(
    client: "AsyncClient",
    headers: dict[str, str],
    topic: str = "Test Topic",
    num_thinkers: int = 2,
) -> str:
    """Helper to create a test conversation and return its ID.

    Reduces duplication of conversation creation pattern that appears 10+ times
    in test_api.py with nearly identical structure.

    Args:
        client: AsyncClient for making requests
        headers: Auth headers
        topic: Conversation topic
        num_thinkers: Number of thinkers to create (default 2)

    Returns:
        The conversation ID
    """
    thinkers = []
    thinker_names = ["Socrates", "Einstein", "Plato", "Darwin", "Curie"]
    for i in range(num_thinkers):
        name = thinker_names[i] if i < len(thinker_names) else f"Thinker{i}"
        thinkers.append(
            {
                "name": name,
                "bio": f"Bio for {name}",
                "positions": f"Positions of {name}",
                "style": f"Style of {name}",
            }
        )

    response = await client.post(
        "/api/conversations",
        headers=headers,
        json={"topic": topic, "thinkers": thinkers},
    )
    assert response.status_code == 200, f"Failed to create conversation: {response.text}"
    data: Any = response.json()
    return str(data["id"])


def create_thinker_input(
    name: str = "Socrates",
    bio: str | None = None,
    positions: str | list[str] | None = None,
    style: str | None = None,
) -> dict[str, Any]:
    """Create a thinker input dict for API requests.

    Reduces duplication of thinker object creation across test files.

    Args:
        name: Thinker name
        bio: Bio (defaults to "Bio of {name}")
        positions: Positions (defaults to "Positions of {name}")
        style: Style (defaults to "Style of {name}")

    Returns:
        Dictionary with thinker fields
    """
    return {
        "name": name,
        "bio": bio or f"Bio of {name}",
        "positions": positions or f"Positions of {name}",
        "style": style or f"Style of {name}",
    }
