"""Tests for main FastAPI application."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app import VERSION
from app.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_health_check(client: AsyncClient) -> None:
    """Test health check endpoint returns healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


async def test_version_endpoint(client: AsyncClient) -> None:
    """Test version endpoint returns correct version and name."""
    response = await client.get("/api/version")
    assert response.status_code == 200
    data = response.json()
    assert data == {"version": VERSION, "name": "Dining Philosophers API"}
    assert "version" in data
    assert "name" in data
    assert data["version"] == VERSION
