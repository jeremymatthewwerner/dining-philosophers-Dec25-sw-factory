"""Tests for main FastAPI application."""

from httpx import AsyncClient

from app import VERSION


async def test_health_check(client: AsyncClient) -> None:
    """Test health check endpoint returns healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


async def test_health_ready_endpoint(client: AsyncClient) -> None:
    """Test deep health check endpoint returns ready status with database check."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "checks" in data
    assert data["checks"]["database"] == "ok"


async def test_version_endpoint(client: AsyncClient) -> None:
    """Test version endpoint returns correct version and name."""
    response = await client.get("/api/version")
    assert response.status_code == 200
    data = response.json()
    assert data == {"version": VERSION, "name": "Dining Philosophers API"}
    assert "version" in data
    assert "name" in data
    assert data["version"] == VERSION
