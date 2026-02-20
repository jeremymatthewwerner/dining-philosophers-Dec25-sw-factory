"""Unit test to verify test helper endpoint exists and works correctly."""

import pytest
from httpx import AsyncClient


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
