"""Tests for the feedback API endpoints."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_submit_feedback_success(client: AsyncClient) -> None:
    """Test successful feedback submission."""
    response = await client.post(
        "/api/feedback",
        json={
            "feedback_type": "bug",
            "message": "This is a test bug report with enough characters.",
            "email": "test@example.com",
            "name": "Test User",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "message" in data
    assert "Thank you" in data["message"]


@pytest.mark.asyncio
async def test_submit_feedback_minimal(client: AsyncClient) -> None:
    """Test feedback submission with only required fields."""
    response = await client.post(
        "/api/feedback",
        json={
            "message": "This is a minimal test feedback submission.",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data


@pytest.mark.asyncio
async def test_submit_feedback_feature_request(client: AsyncClient) -> None:
    """Test feature request feedback type."""
    response = await client.post(
        "/api/feedback",
        json={
            "feedback_type": "feature",
            "message": "Please add a dark mode toggle to the settings.",
        },
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_submit_feedback_other_type(client: AsyncClient) -> None:
    """Test 'other' feedback type."""
    response = await client.post(
        "/api/feedback",
        json={
            "feedback_type": "other",
            "message": "I have some general comments about the app.",
        },
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_submit_feedback_message_too_short(client: AsyncClient) -> None:
    """Test that short messages are rejected."""
    response = await client.post(
        "/api/feedback",
        json={
            "message": "Too short",
        },
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_submit_feedback_no_message(client: AsyncClient) -> None:
    """Test that missing message is rejected."""
    response = await client.post(
        "/api/feedback",
        json={
            "feedback_type": "bug",
        },
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_submit_feedback_invalid_type(client: AsyncClient) -> None:
    """Test that invalid feedback type is rejected."""
    response = await client.post(
        "/api/feedback",
        json={
            "feedback_type": "invalid_type",
            "message": "This should fail due to invalid type.",
        },
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_submit_feedback_with_user_agent(client: AsyncClient) -> None:
    """Test feedback submission with user agent."""
    response = await client.post(
        "/api/feedback",
        json={
            "message": "Testing with user agent information included.",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        },
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_submit_feedback_rate_limit(client: AsyncClient) -> None:
    """Test rate limiting on feedback submissions."""
    # Submit 5 feedback items (should succeed)
    for i in range(5):
        response = await client.post(
            "/api/feedback",
            json={
                "message": f"Test feedback submission number {i + 1} for rate limiting test.",
            },
        )
        assert response.status_code == 201, f"Submission {i + 1} failed"

    # The 6th submission should be rate limited
    response = await client.post(
        "/api/feedback",
        json={
            "message": "This submission should be rate limited by the server.",
        },
    )
    assert response.status_code == 429  # Too Many Requests


@pytest.mark.asyncio
async def test_submit_feedback_email_optional(client: AsyncClient) -> None:
    """Test that email is optional and can be empty."""
    response = await client.post(
        "/api/feedback",
        json={
            "message": "This feedback has no email address provided.",
            "email": None,
        },
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_submit_feedback_name_optional(client: AsyncClient) -> None:
    """Test that name is optional and can be empty."""
    response = await client.post(
        "/api/feedback",
        json={
            "message": "This feedback has no name provided by user.",
            "name": None,
        },
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_submit_feedback_with_screenshot(client: AsyncClient) -> None:
    """Test feedback submission with screenshot data."""
    # Base64 encoded small test image (1x1 PNG)
    test_screenshot = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    response = await client.post(
        "/api/feedback",
        json={
            "feedback_type": "bug",
            "message": "This is a bug report with a screenshot attached.",
            "screenshot_data": test_screenshot,
            "screenshot_filename": "bug-screenshot.png",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data


@pytest.mark.asyncio
async def test_submit_feedback_screenshot_without_filename(client: AsyncClient) -> None:
    """Test feedback submission with screenshot data but no filename."""
    test_screenshot = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    response = await client.post(
        "/api/feedback",
        json={
            "message": "This is a feedback with screenshot but no filename.",
            "screenshot_data": test_screenshot,
        },
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_submit_feedback_screenshot_too_large(client: AsyncClient) -> None:
    """Test that overly large screenshots are rejected."""
    # Create a string larger than 7MB (the limit)
    large_data = "a" * (7_000_001)

    response = await client.post(
        "/api/feedback",
        json={
            "message": "This feedback has a screenshot that is too large.",
            "screenshot_data": large_data,
        },
    )

    assert response.status_code == 422  # Validation error


# =========================================
# Tests for feedback processor endpoints
# =========================================


TEST_SECRET = "test-feedback-processor-secret"


@pytest.mark.asyncio
async def test_get_pending_feedback_no_secret(client: AsyncClient) -> None:
    """Test that GET /api/feedback/pending requires a secret."""
    response = await client.get("/api/feedback/pending")
    assert response.status_code == 422  # Missing required query param


@pytest.mark.asyncio
async def test_get_pending_feedback_invalid_secret(client: AsyncClient) -> None:
    """Test that GET /api/feedback/pending rejects invalid secrets."""
    with patch("app.api.feedback.get_settings") as mock_settings:
        mock_settings.return_value.feedback_processor_secret = TEST_SECRET
        response = await client.get("/api/feedback/pending?secret=wrong-secret")
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_pending_feedback_not_configured(client: AsyncClient) -> None:
    """Test that GET /api/feedback/pending returns 503 when not configured."""
    with patch("app.api.feedback.get_settings") as mock_settings:
        mock_settings.return_value.feedback_processor_secret = ""
        response = await client.get("/api/feedback/pending?secret=any-secret")
        assert response.status_code == 503


@pytest.mark.asyncio
async def test_get_pending_feedback_success(client: AsyncClient) -> None:
    """Test successful GET /api/feedback/pending."""
    with patch("app.api.feedback.get_settings") as mock_settings:
        mock_settings.return_value.feedback_processor_secret = TEST_SECRET

        # First create some feedback
        await client.post(
            "/api/feedback",
            json={"message": "Test feedback for pending endpoint test."},
        )

        response = await client.get(f"/api/feedback/pending?secret={TEST_SECRET}")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "feedbacks" in data
        assert isinstance(data["feedbacks"], list)


@pytest.mark.asyncio
async def test_get_pending_feedback_with_limit(client: AsyncClient) -> None:
    """Test GET /api/feedback/pending with limit parameter."""
    with patch("app.api.feedback.get_settings") as mock_settings:
        mock_settings.return_value.feedback_processor_secret = TEST_SECRET

        response = await client.get(f"/api/feedback/pending?secret={TEST_SECRET}&limit=5")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_mark_processed_no_secret(client: AsyncClient) -> None:
    """Test that PATCH /api/feedback/{id}/processed requires a secret."""
    response = await client.patch(
        "/api/feedback/test-id/processed",
        json={"github_issue_url": "https://github.com/test/test/issues/1"},
    )
    assert response.status_code == 422  # Missing required query param


@pytest.mark.asyncio
async def test_mark_processed_invalid_secret(client: AsyncClient) -> None:
    """Test that PATCH /api/feedback/{id}/processed rejects invalid secrets."""
    with patch("app.api.feedback.get_settings") as mock_settings:
        mock_settings.return_value.feedback_processor_secret = TEST_SECRET
        response = await client.patch(
            "/api/feedback/test-id/processed?secret=wrong-secret",
            json={"github_issue_url": "https://github.com/test/test/issues/1"},
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_mark_processed_not_found(client: AsyncClient) -> None:
    """Test that PATCH /api/feedback/{id}/processed returns 404 for unknown ID."""
    with patch("app.api.feedback.get_settings") as mock_settings:
        mock_settings.return_value.feedback_processor_secret = TEST_SECRET
        response = await client.patch(
            f"/api/feedback/nonexistent-id/processed?secret={TEST_SECRET}",
            json={"github_issue_url": "https://github.com/test/test/issues/1"},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_mark_processed_success(client: AsyncClient) -> None:
    """Test successful PATCH /api/feedback/{id}/processed."""
    with patch("app.api.feedback.get_settings") as mock_settings:
        mock_settings.return_value.feedback_processor_secret = TEST_SECRET

        # First create feedback
        create_response = await client.post(
            "/api/feedback",
            json={"message": "Test feedback for mark processed endpoint test."},
        )
        feedback_id = create_response.json()["id"]

        # Now mark it as processed
        response = await client.patch(
            f"/api/feedback/{feedback_id}/processed?secret={TEST_SECRET}",
            json={"github_issue_url": "https://github.com/test/test/issues/123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["feedback_id"] == feedback_id
        assert data["github_issue_url"] == "https://github.com/test/test/issues/123"


@pytest.mark.asyncio
async def test_mark_processed_missing_url(client: AsyncClient) -> None:
    """Test that PATCH /api/feedback/{id}/processed requires github_issue_url."""
    with patch("app.api.feedback.get_settings") as mock_settings:
        mock_settings.return_value.feedback_processor_secret = TEST_SECRET
        response = await client.patch(
            f"/api/feedback/test-id/processed?secret={TEST_SECRET}",
            json={},
        )
        assert response.status_code == 422  # Validation error
