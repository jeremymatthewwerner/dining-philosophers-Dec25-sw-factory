"""Unit test to verify test helper endpoint exists and works correctly."""

from collections.abc import AsyncGenerator

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
from app.models import Base


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


@pytest.mark.asyncio
async def test_billing_error_endpoint_exists(client: AsyncClient) -> None:
    """Test that /api/test/billing-error endpoint exists and raises BillingError."""
    # Act: Call the test endpoint
    response = await client.get("/api/test/billing-error")

    # Assert: Verify HTTP 503 response (BillingError is caught and returns 503)
    assert response.status_code == 503

    # Assert: Verify response contains billing-related error message
    response_json = response.json()
    assert "detail" in response_json
    detail = response_json["detail"].lower()
    assert "billing" in detail or "quota" in detail
    assert "unavailable" in detail


@pytest.mark.asyncio
async def test_billing_error_handler_returns_proper_response(client: AsyncClient) -> None:
    """Test that BillingError exception handler returns proper 503 response."""
    # Act: Call endpoint that raises BillingError
    response = await client.get("/api/test/billing-error")

    # Assert: Status code is 503
    assert response.status_code == 503

    # Assert: Response is JSON
    response_json = response.json()
    assert isinstance(response_json, dict)

    # Assert: Response has detail field
    assert "detail" in response_json
    assert isinstance(response_json["detail"], str)

    # Assert: Detail message is user-friendly and informative
    detail = response_json["detail"]
    assert len(detail) > 0
    assert "Service temporarily unavailable" in detail or "service" in detail.lower()
