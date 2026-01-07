"""Tests for the feedback API endpoints."""

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


# Tests for feedback processor endpoints


@pytest.mark.asyncio
async def test_get_pending_feedback_no_secret(client: AsyncClient) -> None:
    """Test that get pending feedback requires a secret."""
    response = await client.get("/api/feedback/pending")
    assert response.status_code == 422  # Missing required query param


@pytest.mark.asyncio
async def test_get_pending_feedback_invalid_secret(client: AsyncClient) -> None:
    """Test that get pending feedback rejects invalid secret."""
    response = await client.get("/api/feedback/pending?secret=wrong-secret")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_pending_feedback_secret_not_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that get pending feedback fails if secret not configured."""
    # Clear the settings cache and set empty secret
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("FEEDBACK_PROCESSOR_SECRET", "")

    response = await client.get("/api/feedback/pending?secret=any-secret")
    assert response.status_code == 403
    assert "not configured" in response.json()["detail"]

    # Reset for other tests
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_get_pending_feedback_success(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test successful retrieval of pending feedback."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("FEEDBACK_PROCESSOR_SECRET", "test-processor-secret")

    # First submit some feedback
    await client.post(
        "/api/feedback",
        json={"message": "Pending feedback for processor test one."},
    )
    await client.post(
        "/api/feedback",
        json={"message": "Pending feedback for processor test two."},
    )

    # Now get pending feedback
    response = await client.get("/api/feedback/pending?secret=test-processor-secret")
    assert response.status_code == 200

    data = response.json()
    assert "feedbacks" in data
    assert "count" in data
    assert data["count"] >= 2  # At least the two we just submitted

    # Verify feedback structure
    if data["count"] > 0:
        feedback = data["feedbacks"][0]
        assert "id" in feedback
        assert "feedback_type" in feedback
        assert "message" in feedback
        assert "status" in feedback
        assert feedback["status"] == "new"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_mark_feedback_processed_no_secret(client: AsyncClient) -> None:
    """Test that mark processed requires a secret."""
    response = await client.patch(
        "/api/feedback/some-id/processed",
        json={"github_issue_url": "https://github.com/test/test/issues/1"},
    )
    assert response.status_code == 422  # Missing required query param


@pytest.mark.asyncio
async def test_mark_feedback_processed_invalid_secret(client: AsyncClient) -> None:
    """Test that mark processed rejects invalid secret."""
    response = await client.patch(
        "/api/feedback/some-id/processed?secret=wrong-secret",
        json={"github_issue_url": "https://github.com/test/test/issues/1"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_mark_feedback_processed_not_found(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that mark processed returns 404 for non-existent feedback."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("FEEDBACK_PROCESSOR_SECRET", "test-processor-secret")

    response = await client.patch(
        "/api/feedback/non-existent-id/processed?secret=test-processor-secret",
        json={"github_issue_url": "https://github.com/test/test/issues/1"},
    )
    assert response.status_code == 404

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_mark_feedback_processed_success(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test successful marking of feedback as processed."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("FEEDBACK_PROCESSOR_SECRET", "test-processor-secret")

    # First submit feedback
    submit_response = await client.post(
        "/api/feedback",
        json={"message": "Feedback to be marked as processed."},
    )
    assert submit_response.status_code == 201
    feedback_id = submit_response.json()["id"]

    # Mark as processed
    issue_url = (
        "https://github.com/jeremymatthewwerner/dining-philosophers-Dec25-sw-factory/issues/999"
    )
    response = await client.patch(
        f"/api/feedback/{feedback_id}/processed?secret=test-processor-secret",
        json={"github_issue_url": issue_url},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == feedback_id
    assert data["status"] == "reviewed"
    assert data["github_issue_url"] == issue_url
    assert "processed" in data["message"].lower()

    # Verify it no longer appears in pending list
    pending_response = await client.get("/api/feedback/pending?secret=test-processor-secret")
    pending_ids = [f["id"] for f in pending_response.json()["feedbacks"]]
    assert feedback_id not in pending_ids

    get_settings.cache_clear()
