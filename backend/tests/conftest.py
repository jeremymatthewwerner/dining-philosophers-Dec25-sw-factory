"""Shared test fixtures for all test files."""

import gc
from collections.abc import AsyncGenerator, Generator
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.fixture(autouse=True)
def mock_knowledge_service_trigger() -> Generator[MagicMock, None, None]:
    """Mock knowledge_service.trigger_research globally for all tests.

    Without this, creating a conversation triggers a real asyncio background
    task that makes HTTP requests to Wikipedia. This causes the event loop to
    hang while waiting for the HTTP task to complete, making any test that
    calls POST /api/conversations hang indefinitely.

    Tests that need to verify trigger_research behavior can override this
    fixture or use their own patch decorator.
    """
    with patch(
        "app.services.knowledge_research.knowledge_service.trigger_research"
    ) as mock_trigger:
        mock_trigger.return_value = None
        yield mock_trigger


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


def make_simple_thinker_list(
    name: str = "Thinker",
    bio: str = "Bio",
    positions: str = "Positions",
    style: str = "Style",
) -> list[dict[str, Any]]:
    """Create a single-thinker list for conversation creation in tests.

    Reduces duplication of the identical inline pattern that appears 9+ times
    in test_api.py where conversations are created with a minimal placeholder
    thinker (name="Thinker", bio="Bio", positions="Positions", style="Style").

    Instead of repeating:
        "thinkers": [{"name": "Thinker", "bio": "Bio",
                      "positions": "Positions", "style": "Style"}]

    Tests can use:
        "thinkers": make_simple_thinker_list()

    Args:
        name: Thinker name (default: "Thinker")
        bio: Bio string (default: "Bio")
        positions: Positions string (default: "Positions")
        style: Style string (default: "Style")

    Returns:
        List containing a single thinker dict with the given values

    Example:
        >>> response = await client.post("/api/conversations",
        ...     json={"topic": "test", "thinkers": make_simple_thinker_list()})
    """
    return [{"name": name, "bio": bio, "positions": positions, "style": style}]


async def create_conversation_with_thinker(
    client: "AsyncClient",
    headers: dict[str, str],
    topic: str = "Test Topic",
    thinker_name: str = "Thinker",
) -> str:
    """Create a conversation with a single placeholder thinker, return its ID.

    Reduces duplication of the create-conversation-then-extract-id pattern
    that appears 10+ times in test_api.py with minimal variation.

    Instead of:
        conv_response = await client.post("/api/conversations", headers=headers,
            json={"topic": topic, "thinkers": [{"name": "Thinker", ...}]})
        conv_id = conv_response.json()["id"]

    Tests can use:
        conv_id = await create_conversation_with_thinker(client, headers, topic)

    Args:
        client: AsyncClient for making requests
        headers: Auth headers
        topic: Conversation topic (default: "Test Topic")
        thinker_name: Name for the single thinker (default: "Thinker")

    Returns:
        The conversation ID string

    Example:
        >>> headers = await get_auth_headers(client, "user", "pass")
        >>> conv_id = await create_conversation_with_thinker(client, headers, "My topic")
    """
    response = await client.post(
        "/api/conversations",
        headers=headers,
        json={
            "topic": topic,
            "thinkers": make_simple_thinker_list(thinker_name),
        },
    )
    assert response.status_code == 200, f"Failed to create conversation: {response.text}"
    return str(response.json()["id"])


# ThinkerService test helpers
def create_mock_anthropic_response(
    text: str,
    input_tokens: int = 100,
    output_tokens: int = 10,
) -> MagicMock:
    """Create a mock Anthropic API response with TextBlock content.

    Reduces duplication of mock response creation pattern that appears 15+ times
    in test_thinker_service.py.

    Args:
        text: The response text content
        input_tokens: Input token count for usage tracking (default: 100)
        output_tokens: Output token count for usage tracking (default: 10)

    Returns:
        MagicMock configured as Anthropic API response

    Example:
        >>> mock_response = create_mock_anthropic_response("Hello world")
        >>> mock_response.content[0].text
        'Hello world'
    """
    from anthropic.types import TextBlock

    mock_response = MagicMock()
    mock_response.content = [TextBlock(type="text", text=text)]
    mock_response.usage.input_tokens = input_tokens
    mock_response.usage.output_tokens = output_tokens
    return mock_response


def create_mock_thinker_profile(
    name: str,
    bio: str | None = None,
    positions: str | None = None,
    style: str | None = None,
) -> dict[str, Any]:
    """Create a mock thinker profile dictionary for testing.

    Reduces duplication of thinker profile creation in test_thinker_service.py.

    Args:
        name: Thinker name
        bio: Biography (defaults to "Bio of {name}")
        positions: Philosophical positions (defaults to "Positions of {name}")
        style: Communication style (defaults to "Style of {name}")

    Returns:
        Dictionary with thinker profile fields

    Example:
        >>> profile = create_mock_thinker_profile("Socrates")
        >>> profile["bio"]
        'Bio of Socrates'
    """
    return {
        "name": name,
        "bio": bio or f"Bio of {name}",
        "positions": positions or f"Positions of {name}",
        "style": style or f"Style of {name}",
    }


def create_mock_thinker_suggestion_json(
    name: str,
    reason: str | None = None,
    bio: str | None = None,
    positions: str | None = None,
    style: str | None = None,
) -> str:
    """Create JSON string for thinker suggestion API response.

    Reduces duplication of thinker suggestion JSON creation in test_thinker_service.py.

    Args:
        name: Thinker name
        reason: Reason for suggestion (defaults to "Expert in {name}")
        bio: Biography (defaults to "Bio of {name}")
        positions: Philosophical positions (defaults to "Positions of {name}")
        style: Communication style (defaults to "Style of {name}")

    Returns:
        JSON string formatted for suggest_thinkers API response

    Example:
        >>> json_str = create_mock_thinker_suggestion_json("Socrates")
        >>> assert "Socrates" in json_str
        >>> assert "profile" in json_str
    """
    import json

    return json.dumps(
        [
            {
                "name": name,
                "reason": reason or f"Expert in {name}",
                "profile": {
                    "name": name,
                    "bio": bio or f"Bio of {name}",
                    "positions": positions or f"Positions of {name}",
                    "style": style or f"Style of {name}",
                },
            }
        ]
    )


# WebSocket test helpers
async def create_test_user_session_conversation(
    db_session: AsyncSession,
) -> tuple[Any, Any, Any]:
    """Create test user, session, and conversation for WebSocket tests.

    Reduces duplication of database setup pattern that appears in test_websocket.py.

    Args:
        db_session: Database session

    Returns:
        Tuple of (user, session, conversation)
    """
    from app.models import Conversation, Session, User

    # Create a user
    user = User(
        username="test_user",
        password_hash="test_hash",
        total_spend=0.0,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create a session for the user
    session = Session(
        user_id=user.id,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    # Create a conversation for the session
    conversation = Conversation(
        session_id=session.id,
        topic="Test conversation about philosophy",
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    return user, session, conversation


# Error assertion helpers for test refactoring (Friday QA focus)
def assert_error_response(
    response: Any,
    expected_status: int,
    expected_detail_substring: str | None = None,
) -> None:
    """Assert that a response is an error with expected status and detail.

    Reduces duplication of error assertion pattern that appears 50+ times:
        assert response.status_code == 400
        assert "error message" in response.json()["detail"]

    Args:
        response: HTTP response object
        expected_status: Expected HTTP status code
        expected_detail_substring: Optional substring to check in error detail

    Example:
        >>> assert_error_response(response, 400, "already taken")
        >>> assert_error_response(response, 404)  # just check status
    """
    assert response.status_code == expected_status
    if expected_detail_substring:
        detail = response.json().get("detail", "")
        assert expected_detail_substring in detail, (
            f"Expected '{expected_detail_substring}' in error detail, but got: {detail}"
        )


def assert_success_response(
    response: Any,
    expected_status: int = 200,
    expected_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Assert that a response is successful and optionally validate keys.

    Reduces duplication of success assertion + key validation pattern.

    Args:
        response: HTTP response object
        expected_status: Expected HTTP status code (default: 200)
        expected_keys: Optional list of keys that must be present in response JSON

    Returns:
        Response JSON data

    Example:
        >>> data = assert_success_response(response, 200, ["id", "username"])
        >>> assert data["username"] == "testuser"
    """
    assert response.status_code == expected_status
    data: dict[str, Any] = response.json()

    if expected_keys:
        for key in expected_keys:
            assert key in data, f"Expected key '{key}' not found in response: {data}"

    return data


# Additional assertion helpers for test refactoring (Feb 13, 2026)
def assert_json_keys(
    data: dict[str, Any],
    required_keys: list[str],
    optional_keys: list[str] | None = None,
) -> None:
    """Assert that a dictionary contains required keys and only allowed keys.

    Reduces duplication of key validation logic across test files.

    Args:
        data: Dictionary to validate
        required_keys: Keys that must be present
        optional_keys: Keys that may be present (default: allow any extra keys)

    Raises:
        AssertionError: If required keys are missing or disallowed keys present

    Example:
        >>> assert_json_keys(data, ["id", "name"], ["email"])
    """
    for key in required_keys:
        assert key in data, f"Required key '{key}' not found in data: {list(data.keys())}"

    if optional_keys is not None:
        allowed_keys = set(required_keys + optional_keys)
        for key in data:
            assert key in allowed_keys, f"Unexpected key '{key}' in data. Allowed: {allowed_keys}"


def assert_list_response(
    response: Any,
    min_length: int = 0,
    max_length: int | None = None,
    expected_status: int = 200,
) -> list[Any]:
    """Assert response is a successful list with expected length constraints.

    Reduces duplication of list response validation pattern.

    Args:
        response: HTTP response object
        min_length: Minimum expected list length (default: 0)
        max_length: Maximum expected list length (default: no limit)
        expected_status: Expected HTTP status code (default: 200)

    Returns:
        Response JSON list data

    Example:
        >>> items = assert_list_response(response, min_length=1, max_length=10)
        >>> assert all("id" in item for item in items)
    """
    assert response.status_code == expected_status
    data: list[Any] = response.json()
    assert isinstance(data, list), f"Expected list, got {type(data)}"
    assert len(data) >= min_length, f"Expected at least {min_length} items, got {len(data)}"
    if max_length is not None:
        assert len(data) <= max_length, f"Expected at most {max_length} items, got {len(data)}"
    return data


def assert_unauthorized(response: Any, expected_detail_substring: str | None = None) -> None:
    """Assert response is 401 Unauthorized with optional detail check.

    Reduces duplication of 401 assertion pattern (appears 25+ times).

    Args:
        response: HTTP response object
        expected_detail_substring: Optional substring to check in error detail

    Example:
        >>> assert_unauthorized(response, "Invalid token")
    """
    assert_error_response(response, 401, expected_detail_substring)


def assert_forbidden(response: Any, expected_detail_substring: str | None = None) -> None:
    """Assert response is 403 Forbidden with optional detail check.

    Reduces duplication of 403 assertion pattern.

    Args:
        response: HTTP response object
        expected_detail_substring: Optional substring to check in error detail

    Example:
        >>> assert_forbidden(response, "not authorized")
    """
    assert_error_response(response, 403, expected_detail_substring)


def assert_not_found(response: Any, expected_detail_substring: str | None = None) -> None:
    """Assert response is 404 Not Found with optional detail check.

    Reduces duplication of 404 assertion pattern (appears 20+ times).

    Args:
        response: HTTP response object
        expected_detail_substring: Optional substring to check in error detail

    Example:
        >>> assert_not_found(response, "Conversation not found")
    """
    assert_error_response(response, 404, expected_detail_substring)


def assert_validation_error(response: Any, expected_detail_substring: str | None = None) -> None:
    """Assert response is 422 Unprocessable Entity with optional detail check.

    Reduces duplication of 422 assertion pattern (appears 15+ times).

    Args:
        response: HTTP response object
        expected_detail_substring: Optional substring to check in error detail

    Example:
        >>> assert_validation_error(response, "Invalid language")
    """
    assert_error_response(response, 422, expected_detail_substring)


async def create_admin_user(
    client: "AsyncClient",
    db_session: AsyncSession,
    username: str = "adminuser",
    password: str = "adminpass123",
) -> Any:
    """Create an admin user and return auth data.

    Reduces duplication of the admin user creation pattern that appears 5+ times
    in test_edge_cases_admin_auth_feedback.py and test_api.py:
        1. Register a regular user
        2. Promote to admin via direct database update

    The require_admin dependency in the API fetches is_admin from the DB at
    request time (not from the JWT), so no re-login is needed after DB update.

    Args:
        client: AsyncClient for making requests
        db_session: Database session for direct DB operations
        username: Admin username (default: "adminuser")
        password: Admin password (default: "adminpass123")

    Returns:
        Auth response dict with access_token and user info (from registration)

    Example:
        >>> admin_data = await create_admin_user(client, db_session)
        >>> admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}
    """
    from sqlalchemy import update

    from app.models import User

    # Register as regular user
    data = await register_and_get_token(client, username, password)

    # Promote to admin directly in the DB
    # (require_admin reads is_admin from DB at request time, no re-login needed)
    await db_session.execute(
        update(User).where(User.id == data["user"]["id"]).values(is_admin=True)
    )
    await db_session.commit()

    return data


async def create_admin_headers(
    client: "AsyncClient",
    db_session: AsyncSession,
    username: str = "adminuser",
    password: str = "adminpass123",
) -> dict[str, str]:
    """Create an admin user and return Authorization headers.

    Convenience wrapper around create_admin_user that returns just the
    headers dict, for tests that only need to make authenticated admin requests.

    Eliminates the repeated 2-step pattern:
        admin_data = await create_admin_user(client, db_session, "user", "pass")
        admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

    This pattern appeared 5+ times in test_edge_cases_admin_auth_feedback.py
    (once per test method). Using this helper reduces each from ~8 lines to 1.

    Args:
        client: AsyncClient for making requests
        db_session: Database session for direct DB operations
        username: Admin username (default: "adminuser")
        password: Admin password (default: "adminpass123")

    Returns:
        Dictionary with Authorization header for admin user

    Example:
        >>> headers = await create_admin_headers(client, db_session, "myadmin", "pass123")
        >>> response = await client.get("/api/admin/users", headers=headers)
    """
    admin_data = await create_admin_user(client, db_session, username, password)
    return {"Authorization": f"Bearer {admin_data['access_token']}"}
