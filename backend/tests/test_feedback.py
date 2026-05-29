"""Tests for the feedback API endpoints."""

from httpx import AsyncClient

from tests.conftest import (
    TEST_FEEDBACK_PROCESSOR_SECRET,
    TEST_SCREENSHOT_PNG_B64,
    submit_feedback,
)


async def test_submit_feedback_success(client: AsyncClient) -> None:
    """Test successful feedback submission."""
    response = await submit_feedback(
        client,
        feedback_type="bug",
        message="This is a test bug report with enough characters.",
        email="test@example.com",
        name="Test User",
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "message" in data
    assert "Thank you" in data["message"]


async def test_submit_feedback_minimal(client: AsyncClient) -> None:
    """Test feedback submission with only required fields."""
    response = await submit_feedback(client, message="This is a minimal test feedback submission.")

    assert response.status_code == 201
    data = response.json()
    assert "id" in data


async def test_submit_feedback_feature_request(client: AsyncClient) -> None:
    """Test feature request feedback type."""
    response = await submit_feedback(
        client,
        feedback_type="feature",
        message="Please add a dark mode toggle to the settings.",
    )

    assert response.status_code == 201


async def test_submit_feedback_other_type(client: AsyncClient) -> None:
    """Test 'other' feedback type."""
    response = await submit_feedback(
        client,
        feedback_type="other",
        message="I have some general comments about the app.",
    )

    assert response.status_code == 201


async def test_submit_feedback_message_too_short(client: AsyncClient) -> None:
    """Test that short messages are rejected."""
    response = await submit_feedback(client, message="Too short")

    assert response.status_code == 422  # Validation error


async def test_submit_feedback_no_message(client: AsyncClient) -> None:
    """Test that missing message is rejected."""
    # Bypass the helper here because the test specifically omits `message`.
    response = await client.post(
        "/api/feedback",
        json={"feedback_type": "bug"},
    )

    assert response.status_code == 422  # Validation error


async def test_submit_feedback_invalid_type(client: AsyncClient) -> None:
    """Test that invalid feedback type is rejected."""
    response = await submit_feedback(
        client,
        feedback_type="invalid_type",
        message="This should fail due to invalid type.",
    )

    assert response.status_code == 422  # Validation error


async def test_submit_feedback_with_user_agent(client: AsyncClient) -> None:
    """Test feedback submission with user agent."""
    response = await submit_feedback(
        client,
        message="Testing with user agent information included.",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    )

    assert response.status_code == 201


async def test_submit_feedback_rate_limit(client: AsyncClient) -> None:
    """Test rate limiting on feedback submissions."""
    # Submit 5 feedback items (should succeed)
    for i in range(5):
        response = await submit_feedback(
            client,
            message=f"Test feedback submission number {i + 1} for rate limiting test.",
        )
        assert response.status_code == 201, f"Submission {i + 1} failed"

    # The 6th submission should be rate limited
    response = await submit_feedback(
        client,
        message="This submission should be rate limited by the server.",
    )
    assert response.status_code == 429  # Too Many Requests


async def test_submit_feedback_email_optional(client: AsyncClient) -> None:
    """Test that email is optional and can be empty."""
    response = await submit_feedback(
        client,
        message="This feedback has no email address provided.",
        email=None,
    )

    assert response.status_code == 201


async def test_submit_feedback_name_optional(client: AsyncClient) -> None:
    """Test that name is optional and can be empty."""
    response = await submit_feedback(
        client,
        message="This feedback has no name provided by user.",
        name=None,
    )

    assert response.status_code == 201


async def test_submit_feedback_with_username(client: AsyncClient) -> None:
    """Test feedback submission with a Dining Philosophers username."""
    response = await submit_feedback(
        client,
        feedback_type="bug",
        message="This is a bug report from a logged-in user.",
        email="test@example.com",
        name="Test User",
        username="testuser123",
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data


async def test_submit_feedback_username_optional(client: AsyncClient) -> None:
    """Test that username is optional (anonymous users can submit feedback)."""
    response = await submit_feedback(
        client,
        message="This feedback is from an anonymous user.",
        username=None,
    )

    assert response.status_code == 201


async def test_submit_feedback_with_screenshot(client: AsyncClient) -> None:
    """Test feedback submission with screenshot data."""
    response = await submit_feedback(
        client,
        feedback_type="bug",
        message="This is a bug report with a screenshot attached.",
        screenshot_data=TEST_SCREENSHOT_PNG_B64,
        screenshot_filename="bug-screenshot.png",
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data


async def test_submit_feedback_screenshot_without_filename(client: AsyncClient) -> None:
    """Test feedback submission with screenshot data but no filename."""
    response = await submit_feedback(
        client,
        message="This is a feedback with screenshot but no filename.",
        screenshot_data=TEST_SCREENSHOT_PNG_B64,
    )

    assert response.status_code == 201


async def test_submit_feedback_screenshot_too_large(client: AsyncClient) -> None:
    """Test that overly large screenshots are rejected."""
    # Create a string larger than 7MB (the limit)
    large_data = "a" * (7_000_001)

    response = await submit_feedback(
        client,
        message="This feedback has a screenshot that is too large.",
        screenshot_data=large_data,
    )

    assert response.status_code == 422  # Validation error


# =========================================
# Tests for feedback processor endpoints
# =========================================


async def test_get_pending_feedback_no_secret(client: AsyncClient) -> None:
    """Test that GET /api/feedback/pending requires a secret."""
    response = await client.get("/api/feedback/pending")
    assert response.status_code == 422  # Missing required query param


async def test_get_pending_feedback_invalid_secret(
    client: AsyncClient,
    mock_feedback_processor_secret: str,  # noqa: ARG001 — fixture activates the get_settings patch
) -> None:
    """Test that GET /api/feedback/pending rejects invalid secrets."""
    response = await client.get("/api/feedback/pending?secret=wrong-secret")
    assert response.status_code == 403


async def test_get_pending_feedback_not_configured(
    client: AsyncClient,
    mock_feedback_processor_unconfigured: None,  # noqa: ARG001 — fixture activates the unconfigured patch
) -> None:
    """Test that GET /api/feedback/pending returns 503 when not configured."""
    response = await client.get("/api/feedback/pending?secret=any-secret")
    assert response.status_code == 503


async def test_get_pending_feedback_success(
    client: AsyncClient, mock_feedback_processor_secret: str
) -> None:
    """Test successful GET /api/feedback/pending."""
    secret = mock_feedback_processor_secret

    # First create some feedback
    await submit_feedback(client, message="Test feedback for pending endpoint test.")

    response = await client.get(f"/api/feedback/pending?secret={secret}")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "feedbacks" in data
    assert isinstance(data["feedbacks"], list)


async def test_get_pending_feedback_includes_username(
    client: AsyncClient, mock_feedback_processor_secret: str
) -> None:
    """Test that GET /api/feedback/pending includes the username field."""
    secret = mock_feedback_processor_secret

    # Create feedback with a username
    await submit_feedback(
        client,
        message="Test feedback with username for pending endpoint.",
        username="testuser456",
    )

    response = await client.get(f"/api/feedback/pending?secret={secret}")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1

    # Find our feedback with the username
    feedbacks_with_username = [f for f in data["feedbacks"] if f.get("username") == "testuser456"]
    assert len(feedbacks_with_username) >= 1
    assert "username" in feedbacks_with_username[0]


async def test_get_pending_feedback_with_limit(
    client: AsyncClient, mock_feedback_processor_secret: str
) -> None:
    """Test GET /api/feedback/pending with limit parameter."""
    secret = mock_feedback_processor_secret
    response = await client.get(f"/api/feedback/pending?secret={secret}&limit=5")
    assert response.status_code == 200


async def test_mark_processed_no_secret(client: AsyncClient) -> None:
    """Test that PATCH /api/feedback/{id}/processed requires a secret."""
    response = await client.patch(
        "/api/feedback/test-id/processed",
        json={"github_issue_url": "https://github.com/test/test/issues/1"},
    )
    assert response.status_code == 422  # Missing required query param


async def test_mark_processed_invalid_secret(
    client: AsyncClient,
    mock_feedback_processor_secret: str,  # noqa: ARG001 — fixture activates the get_settings patch
) -> None:
    """Test that PATCH /api/feedback/{id}/processed rejects invalid secrets."""
    response = await client.patch(
        "/api/feedback/test-id/processed?secret=wrong-secret",
        json={"github_issue_url": "https://github.com/test/test/issues/1"},
    )
    assert response.status_code == 403


async def test_mark_processed_not_found(
    client: AsyncClient, mock_feedback_processor_secret: str
) -> None:
    """Test that PATCH /api/feedback/{id}/processed returns 404 for unknown ID."""
    secret = mock_feedback_processor_secret
    response = await client.patch(
        f"/api/feedback/nonexistent-id/processed?secret={secret}",
        json={"github_issue_url": "https://github.com/test/test/issues/1"},
    )
    assert response.status_code == 404


async def test_mark_processed_success(
    client: AsyncClient, mock_feedback_processor_secret: str
) -> None:
    """Test successful PATCH /api/feedback/{id}/processed."""
    secret = mock_feedback_processor_secret

    # First create feedback
    create_response = await submit_feedback(
        client, message="Test feedback for mark processed endpoint test."
    )
    feedback_id = create_response.json()["id"]

    # Now mark it as processed
    response = await client.patch(
        f"/api/feedback/{feedback_id}/processed?secret={secret}",
        json={"github_issue_url": "https://github.com/test/test/issues/123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["feedback_id"] == feedback_id
    assert data["github_issue_url"] == "https://github.com/test/test/issues/123"


async def test_mark_processed_missing_url(
    client: AsyncClient, mock_feedback_processor_secret: str
) -> None:
    """Test that PATCH /api/feedback/{id}/processed requires github_issue_url."""
    secret = mock_feedback_processor_secret
    response = await client.patch(
        f"/api/feedback/test-id/processed?secret={secret}",
        json={},
    )
    assert response.status_code == 422  # Validation error


# =========================================
# Tests for the test helpers themselves (locks in behavior so future
# refactors of the helpers don't silently break dozens of call sites)
# =========================================


async def test_submit_feedback_helper_default_message_valid(client: AsyncClient) -> None:
    """submit_feedback default message must pass min-length validation.

    Locks in the helper's default so a future shortening of it doesn't
    silently make every test that omits `message` start failing with 422.
    """
    response = await submit_feedback(client)
    assert response.status_code == 201


def test_feedback_processor_secret_constant_is_nonempty() -> None:
    """The shared processor-secret constant must be non-empty.

    An empty value would conflict with the unconfigured 503 branch and
    cause the mock fixture to behave like the "not configured" fixture.
    """
    assert TEST_FEEDBACK_PROCESSOR_SECRET
    assert isinstance(TEST_FEEDBACK_PROCESSOR_SECRET, str)
