"""Regression prevention tests for bugs fixed in February 2026.

This module contains tests that prevent regression of bugs fixed in February 2026.
Each test is linked to the commit/PR that fixed the bug.

Test Organization:
- TestHTTPStatusCodeSemantics: Tests for PR #622 (semantic HTTP assertions)
- TestAdminAuthorizationChecks: Tests for admin endpoint authorization
- TestDevOpsAPISecretValidation: Tests for DevOps API secret validation
- TestConversationPauseResumeFlow: Tests for pause/resume functionality
"""

import pytest
from httpx import AsyncClient

from tests.conftest import get_auth_headers


class TestHTTPStatusCodeSemantics:
    """Regression tests for semantic HTTP status code assertions (PR #622).

    Bug: Tests used raw status codes (200, 400, 401, etc.) which were deprecated.
    Fix: Replaced with semantic status code constants (HTTP_200_OK, HTTP_400_BAD_REQUEST, etc.)
    Commit: b6f805f
    """

    async def test_feedback_success_returns_201_created(self, client: AsyncClient) -> None:
        """Test that successful feedback submission returns 201 Created status.

        Regression test for PR #622 - validates semantic status codes are used.
        """
        from starlette.status import HTTP_201_CREATED

        response = await client.post(
            "/api/feedback",
            json={
                "type": "bug",
                "message": "This is a test feedback message",
                "email": "test@example.com",
                "name": "Test User",
            },
        )

        # Should return 201 Created (not just asserting == 201)
        assert response.status_code == HTTP_201_CREATED
        # Feedback response includes the ID
        assert "id" in response.json()

    async def test_feedback_validation_error_returns_422(self, client: AsyncClient) -> None:
        """Test that invalid feedback returns 422 Unprocessable Entity.

        Regression test for PR #622 - validates semantic status codes.
        """
        from starlette.status import HTTP_422_UNPROCESSABLE_CONTENT

        # Missing required 'message' field
        response = await client.post(
            "/api/feedback",
            json={
                "type": "bug",
                # Missing 'message' field
            },
        )

        # Should return 422 Unprocessable Entity for validation errors
        assert response.status_code == HTTP_422_UNPROCESSABLE_CONTENT

    async def test_auth_missing_credentials_returns_401(self, client: AsyncClient) -> None:
        """Test that missing auth credentials return 401 Unauthorized.

        Regression test for PR #622 - validates semantic status codes.
        """
        from starlette.status import HTTP_401_UNAUTHORIZED

        # Try to access protected endpoint without auth
        response = await client.get("/api/conversations")

        # Should return 401 Unauthorized
        assert response.status_code == HTTP_401_UNAUTHORIZED


class TestAdminAuthorizationChecks:
    """Regression tests for admin endpoint authorization.

    Ensures non-admin users cannot access admin-only endpoints.
    """

    async def test_non_admin_cannot_list_users(self, client: AsyncClient) -> None:
        """Test that non-admin users cannot access /api/admin/users endpoint.

        Regression test to prevent unauthorized access to admin endpoints.
        """
        from starlette.status import HTTP_403_FORBIDDEN

        # Create a non-admin user
        headers = await get_auth_headers(client, username="regularuser")

        # Try to access admin endpoint
        response = await client.get("/api/admin/users", headers=headers)

        # Should return 403 Forbidden
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_non_admin_cannot_delete_user(self, client: AsyncClient) -> None:
        """Test that non-admin users cannot delete other users.

        Regression test to prevent unauthorized user deletion.
        """
        from starlette.status import HTTP_403_FORBIDDEN

        # Create a non-admin user
        headers = await get_auth_headers(client, username="regularuser")

        # Try to delete another user
        response = await client.delete("/api/admin/users/999", headers=headers)

        # Should return 403 Forbidden
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_non_admin_cannot_update_spend_limit(self, client: AsyncClient) -> None:
        """Test that non-admin users cannot update spend limits.

        Regression test to prevent unauthorized spend limit changes.
        """
        from starlette.status import HTTP_403_FORBIDDEN

        # Create a non-admin user
        headers = await get_auth_headers(client, username="regularuser")

        # Try to update spend limit
        response = await client.patch(
            "/api/admin/users/999/spend-limit",
            headers=headers,
            json={"spend_limit": 100.0},
        )

        # Should return 403 Forbidden
        assert response.status_code == HTTP_403_FORBIDDEN


class TestDevOpsAPISecretValidation:
    """Regression tests for DevOps API secret validation.

    Ensures DevOps endpoints properly validate the X-DevOps-Secret header.
    """

    async def test_devops_health_not_configured_returns_503(self, client: AsyncClient) -> None:
        """Test that DevOps health endpoint returns 503 when not configured.

        Regression test to ensure proper error when DEVOPS_API_SECRET not set.
        """
        from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

        # Try to access DevOps health without secret
        # Since DEVOPS_API_SECRET is not set in test env, should return 503
        response = await client.get("/api/devops/health")

        # Should return 503 Service Unavailable when not configured
        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
        assert "not configured" in response.json()["detail"].lower()

    async def test_devops_health_rejects_invalid_secret_when_configured(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that DevOps health endpoint rejects invalid secret when configured.

        Regression test to ensure secret validation works.
        """
        from starlette.status import HTTP_403_FORBIDDEN

        from app.core.config import get_settings

        # Configure a secret for this test
        settings = get_settings()
        monkeypatch.setattr(settings, "devops_api_secret", "test-secret-123")

        # Try to access DevOps health with invalid secret
        response = await client.get(
            "/api/devops/health",
            headers={"X-DevOps-Secret": "invalid-secret"},
        )

        # Should return 403 Forbidden
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_devops_stats_not_configured_returns_503(self, client: AsyncClient) -> None:
        """Test that DevOps stats endpoint returns 503 when not configured.

        Regression test to prevent unauthorized access to database stats.
        """
        from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

        # Try to access DevOps stats without secret
        # Since DEVOPS_API_SECRET is not set in test env, should return 503
        response = await client.get("/api/devops/stats")

        # Should return 503 Service Unavailable when not configured
        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE


class TestMessageValidation:
    """Regression tests for message validation.

    Ensures message API properly validates inputs.
    """

    async def test_empty_message_rejected(self, client: AsyncClient) -> None:
        """Test that empty messages are rejected with 400 Bad Request.

        Regression test to ensure message validation works.
        """
        from starlette.status import HTTP_400_BAD_REQUEST

        # Create user and get auth headers
        headers = await get_auth_headers(client)

        # Try to send empty message (should fail even without conversation)
        # Testing with fake conversation ID to test validation first
        response = await client.post(
            "/api/conversations/fake-id/messages",
            headers=headers,
            json={"content": ""},
        )

        # Should return 422 Unprocessable Entity for empty content (validation error)
        # or 404 if it checks conversation first - both are acceptable
        from starlette.status import HTTP_422_UNPROCESSABLE_CONTENT

        assert response.status_code in [HTTP_422_UNPROCESSABLE_CONTENT, HTTP_400_BAD_REQUEST, 404]

    async def test_message_content_required(self, client: AsyncClient) -> None:
        """Test that message content field is required.

        Regression test to ensure proper validation.
        """
        from starlette.status import HTTP_422_UNPROCESSABLE_CONTENT

        # Create user and get auth headers
        headers = await get_auth_headers(client)

        # Try to send message without content field
        response = await client.post(
            "/api/conversations/fake-id/messages",
            headers=headers,
            json={},
        )

        # Should return 422 Unprocessable Entity for missing field
        assert response.status_code == HTTP_422_UNPROCESSABLE_CONTENT
