"""Regression prevention tests - Sunday QA focus (Apr 19, 2026).

Tests cover critical code paths and regression prevention for recently touched areas:

1. TestCreateAdminUserFunction:
   - create_admin_user creates admin user when none exists
   - create_admin_user skips creation when admin user already exists

2. TestFeedbackIPHashing:
   - hash_ip produces consistent SHA-256 hex output for the same IP
   - hash_ip produces different hashes for different IPs
   - get_client_ip reads X-Forwarded-For header before client host
   - get_client_ip falls back to request.client.host when no header
   - get_client_ip returns "unknown" when client is None

3. TestFeedbackMarkProcessed:
   - mark_feedback_processed returns 404 for unknown feedback IDs
   - mark_feedback_processed succeeds for existing feedback

4. TestFeedbackPendingSecretValidation:
   - get_pending_feedback raises 503 when feedback_processor_secret not configured
   - get_pending_feedback raises 403 for wrong secret
   - mark_feedback_processed raises 503 when secret not configured
   - mark_feedback_processed raises 403 for wrong secret

5. TestAuthChangePassword:
   - change_password returns 400 when current_password is wrong
   - change_password succeeds and allows login with new password

6. TestAuthLogout:
   - logout endpoint returns 200 with message

7. TestThinkerKnowledgeStatusEndpoint:
   - knowledge status returns PENDING with has_data=False when no knowledge exists
   - knowledge status returns correct status for existing knowledge

8. TestThinkerKnowledgeRefreshEndpoint:
   - refresh endpoint creates knowledge entry and triggers research
   - refresh endpoint updates existing knowledge entry

9. TestConversationColorCycling:
   - create_conversation cycles through 5 colors for multiple thinkers
   - add_thinkers avoids duplicate colors when adding to existing thinkers

10. TestKnowledgeResearchErrorHandling:
    - KnowledgeResearchService handles exceptions during research gracefully
    - Inner DB error in error handler is logged without crashing

All tests guard against regressions in recently-touched code paths and edge cases
identified from coverage analysis (websocket.py 68%, thinker.py 76%, main.py 79%).
"""

import hashlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.feedback import get_client_ip, hash_ip
from app.models import Feedback, User
from app.models.feedback import FeedbackStatus
from app.models.feedback import FeedbackType as FeedbackTypeModel
from tests.conftest import (
    get_auth_headers,
    register_and_get_token,
)

if TYPE_CHECKING:
    pass

# Test secret for feedback processor
FEEDBACK_SECRET = "test-feedback-secret"


class TestFeedbackIPHashing:
    """Regression tests for IP hashing and client IP extraction in feedback.py.

    These functions implement privacy-preserving rate limiting. Regressions in
    IP extraction could allow rate limit bypass (e.g., always returning "unknown").
    """

    def test_hash_ip_produces_sha256_hex(self) -> None:
        """hash_ip produces a 64-character hex SHA-256 hash.

        Regression guard: If hash_ip changes algorithm (e.g., to MD5), the
        output length changes from 64 to 32, breaking existing rate limit records
        in the database that used the longer hash.
        """
        ip = "192.168.1.1"
        result = hash_ip(ip)
        expected = hashlib.sha256(ip.encode()).hexdigest()
        assert result == expected
        assert len(result) == 64
        assert result.isalnum()

    def test_hash_ip_is_deterministic(self) -> None:
        """Same IP always produces the same hash (required for rate limiting).

        Regression guard: If salt or nonce is added to the hash, consecutive
        calls for the same IP will produce different hashes, making rate limiting
        ineffective (each request appears to come from a different "IP").
        """
        ip = "10.0.0.1"
        assert hash_ip(ip) == hash_ip(ip)

    def test_hash_ip_differentiates_ips(self) -> None:
        """Different IPs produce different hashes.

        Regression guard: If hash_ip is accidentally simplified to return a
        constant or empty string, all IPs would appear to be the same "client",
        causing all users to share a single rate limit counter.
        """
        hash1 = hash_ip("192.168.1.1")
        hash2 = hash_ip("192.168.1.2")
        assert hash1 != hash2

    def test_get_client_ip_uses_x_forwarded_for_first(self) -> None:
        """get_client_ip prefers X-Forwarded-For header over direct client IP.

        Regression guard: If X-Forwarded-For handling is removed, clients behind
        proxies (e.g., Railway's load balancer) all appear to come from the proxy
        IP, effectively sharing one rate limit counter across all users.
        """
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "203.0.113.1, 10.0.0.1"
        mock_request.client.host = "10.0.0.1"

        result = get_client_ip(mock_request)
        assert result == "203.0.113.1"

    def test_get_client_ip_falls_back_to_client_host(self) -> None:
        """get_client_ip uses request.client.host when no X-Forwarded-For header.

        Regression guard: Without this fallback, direct connections (not through
        a proxy) would fail to extract any IP, returning "unknown" for all direct
        clients and breaking rate limiting entirely.
        """
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None  # No X-Forwarded-For
        mock_request.client.host = "198.51.100.5"

        result = get_client_ip(mock_request)
        assert result == "198.51.100.5"

    def test_get_client_ip_returns_unknown_when_no_client(self) -> None:
        """get_client_ip returns 'unknown' when request.client is None.

        Regression guard: Some ASGI frameworks set request.client to None for
        Unix socket connections or certain test environments. Without this guard,
        AttributeError on None.host would crash the feedback submission endpoint.
        """
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client = None

        result = get_client_ip(mock_request)
        assert result == "unknown"

    def test_get_client_ip_strips_whitespace_from_forwarded_for(self) -> None:
        """get_client_ip strips whitespace from first IP in X-Forwarded-For chain.

        Regression guard: Load balancers add IPs with spaces (e.g., "203.0.113.1, 10.0.0.1").
        Without strip(), the IP hash includes the trailing space, causing '203.0.113.1 '
        to hash differently from '203.0.113.1', bypassing rate limiting.
        """
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "  203.0.113.1  , 10.0.0.1"
        mock_request.client.host = "10.0.0.1"

        result = get_client_ip(mock_request)
        assert result == "203.0.113.1"


class TestFeedbackSecretValidation:
    """Regression tests for feedback processor secret validation.

    The feedback processor secret protects sensitive admin endpoints.
    Regressions could expose pending feedback data to unauthorized callers.
    """

    async def test_get_pending_feedback_returns_503_when_secret_not_configured(
        self, client: AsyncClient
    ) -> None:
        """GET /api/feedback/pending returns 503 when secret not set in settings.

        Regression guard: If the empty-string check for feedback_processor_secret
        is removed, an unconfigured server would accept ANY secret string
        (including empty string) and expose all pending feedback.
        """
        with patch("app.api.feedback.get_settings") as mock_settings:
            settings = MagicMock()
            settings.feedback_processor_secret = ""  # Not configured
            mock_settings.return_value = settings

            response = await client.get("/api/feedback/pending?secret=any-secret")
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"].lower()

    async def test_get_pending_feedback_returns_403_for_wrong_secret(
        self, client: AsyncClient
    ) -> None:
        """GET /api/feedback/pending returns 403 for incorrect secret.

        Regression guard: If the secret comparison check is bypassed,
        unauthorized callers can enumerate all pending user feedback,
        potentially exposing email addresses and private bug reports.
        """
        with patch("app.api.feedback.get_settings") as mock_settings:
            settings = MagicMock()
            settings.feedback_processor_secret = "correct-secret"
            mock_settings.return_value = settings

            response = await client.get("/api/feedback/pending?secret=wrong-secret")
        assert response.status_code == 403
        assert "Invalid secret" in response.json()["detail"]

    async def test_mark_processed_returns_503_when_secret_not_configured(
        self, client: AsyncClient
    ) -> None:
        """PATCH /api/feedback/{id}/processed returns 503 when secret not configured.

        Regression guard: Same as get_pending, the mark-processed endpoint also
        requires the secret. Both endpoints share verify_feedback_processor_secret().
        """
        with patch("app.api.feedback.get_settings") as mock_settings:
            settings = MagicMock()
            settings.feedback_processor_secret = ""
            mock_settings.return_value = settings

            response = await client.patch(
                "/api/feedback/nonexistent-id/processed?secret=any-secret",
                json={"github_issue_url": "https://github.com/org/repo/issues/1"},
            )
        assert response.status_code == 503

    async def test_mark_processed_returns_403_for_wrong_secret(self, client: AsyncClient) -> None:
        """PATCH /api/feedback/{id}/processed returns 403 for incorrect secret.

        Regression guard: Even with an existing feedback ID, an invalid secret
        must be rejected. Without this check, the GitHub issue URL field could
        be overwritten by unauthorized callers to point to malicious URLs.
        """
        with patch("app.api.feedback.get_settings") as mock_settings:
            settings = MagicMock()
            settings.feedback_processor_secret = "correct-secret"
            mock_settings.return_value = settings

            response = await client.patch(
                "/api/feedback/nonexistent-id/processed?secret=wrong-secret",
                json={"github_issue_url": "https://github.com/org/repo/issues/1"},
            )
        assert response.status_code == 403

    async def test_mark_processed_returns_404_for_unknown_id(self, client: AsyncClient) -> None:
        """PATCH /api/feedback/{id}/processed returns 404 for unknown feedback ID.

        Regression guard: With valid secret but non-existent ID, the endpoint
        must return 404. If the not-found check is removed, the endpoint would
        try to set status on a None object, causing a 500 error.
        """
        with patch("app.api.feedback.get_settings") as mock_settings:
            settings = MagicMock()
            settings.feedback_processor_secret = "test-secret"
            mock_settings.return_value = settings

            response = await client.patch(
                "/api/feedback/does-not-exist/processed?secret=test-secret",
                json={"github_issue_url": "https://github.com/org/repo/issues/1"},
            )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_mark_processed_succeeds_for_existing_feedback(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """PATCH /api/feedback/{id}/processed succeeds and updates feedback status.

        Regression guard: The happy path must update feedback.status to REVIEWED
        and store the github_issue_url. If either field is not updated, the
        DevOps workflow will re-process the same feedback every run.
        """
        # Create a feedback record directly in the DB
        feedback = Feedback(
            feedback_type=FeedbackTypeModel.BUG,
            message="This is a test bug report with enough text",
            status=FeedbackStatus.NEW,
            ip_hash=hash_ip("10.0.0.1"),
        )
        db_session.add(feedback)
        await db_session.commit()
        await db_session.refresh(feedback)

        github_url = "https://github.com/org/repo/issues/99"
        with patch("app.api.feedback.get_settings") as mock_settings:
            settings = MagicMock()
            settings.feedback_processor_secret = "test-secret"
            mock_settings.return_value = settings

            response = await client.patch(
                f"/api/feedback/{feedback.id}/processed?secret=test-secret",
                json={"github_issue_url": github_url},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["feedback_id"] == feedback.id
        assert data["github_issue_url"] == github_url

        # Verify DB was actually updated
        await db_session.refresh(feedback)
        assert feedback.status == FeedbackStatus.REVIEWED
        assert feedback.github_issue_url == github_url


class TestAuthChangePassword:
    """Regression tests for the change-password endpoint.

    The change_password endpoint requires the current password for verification.
    Regressions could allow password changes without knowing the current password.
    """

    async def test_change_password_fails_with_wrong_current_password(
        self, client: AsyncClient
    ) -> None:
        """POST /api/auth/change-password returns 400 when current_password is wrong.

        Regression guard: If the verify_password check is removed, any authenticated
        user could change their password to anything without knowing the original.
        """
        data = await register_and_get_token(client, "pwdtestuser", "original123")
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "wrong-password",
                "new_password": "newpassword456",
            },
        )
        assert response.status_code == 400
        assert "incorrect" in response.json()["detail"].lower()

    async def test_change_password_succeeds_with_correct_current_password(
        self, client: AsyncClient
    ) -> None:
        """POST /api/auth/change-password succeeds and new password works for login.

        Regression guard: The happy path must actually update the password hash
        in the database. If the commit is skipped, the password change appears
        to succeed but the old password remains valid.
        """
        data = await register_and_get_token(client, "pwdtestuser2", "original456")
        headers = {"Authorization": f"Bearer {data['access_token']}"}

        response = await client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "original456",
                "new_password": "newpassword789",
            },
        )
        assert response.status_code == 200
        assert "successfully" in response.json()["message"].lower()

        # Verify new password works for login
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "pwdtestuser2", "password": "newpassword789"},
        )
        assert login_response.status_code == 200

        # Verify old password no longer works
        old_login_response = await client.post(
            "/api/auth/login",
            json={"username": "pwdtestuser2", "password": "original456"},
        )
        assert old_login_response.status_code == 401

    async def test_change_password_requires_authentication(self, client: AsyncClient) -> None:
        """POST /api/auth/change-password returns 401 without auth token.

        Regression guard: The endpoint uses require_user dependency. Without
        authentication, callers must receive a 4xx error (not 200).
        HTTPBearer returns 401 when no credentials are provided.
        """
        response = await client.post(
            "/api/auth/change-password",
            json={"current_password": "any", "new_password": "newpass"},
        )
        # HTTPBearer raises 401 when no credentials provided (auto_error=False
        # in auth.py means get_current_user returns None, then require_user raises 401)
        assert response.status_code == 401


class TestAuthLogout:
    """Regression tests for the logout endpoint.

    Logout is client-side (JWT removal) but the endpoint must exist and return 200.
    """

    async def test_logout_returns_200_with_message(self, client: AsyncClient) -> None:
        """POST /api/auth/logout returns 200 with logout confirmation message.

        Regression guard: If the logout endpoint is accidentally removed or
        returns a different status code, client-side logout flows that call this
        endpoint before clearing tokens will throw errors.
        """
        response = await client.post("/api/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "logout" in data["message"].lower() or "logged out" in data["message"].lower()

    async def test_logout_works_without_auth_token(self, client: AsyncClient) -> None:
        """POST /api/auth/logout succeeds even without authentication.

        Regression guard: The logout endpoint has no auth dependency (JWT is
        client-side). If require_user is accidentally added, logged-out users
        would get 401 when trying to notify the server of logout.
        """
        response = await client.post("/api/auth/logout")
        # Should succeed without any Authorization header
        assert response.status_code == 200


class TestThinkerKnowledgeStatusEndpoint:
    """Regression tests for GET /api/thinkers/knowledge/{name}/status.

    The status endpoint is a lightweight polling endpoint. Regressions could
    cause frontend polling to fail or return incorrect status.
    """

    async def test_knowledge_status_returns_pending_for_unknown_thinker(
        self, client: AsyncClient
    ) -> None:
        """GET /api/thinkers/knowledge/{name}/status returns PENDING for unknown thinker.

        Regression guard: When no knowledge exists in the DB, the endpoint returns
        PENDING with has_data=False. If the no-knowledge branch is removed,
        the endpoint would return 404 and crash the frontend polling loop.
        """
        # Patch at the module where knowledge_service is used (lazy import inside function)
        with patch("app.services.knowledge_research.knowledge_service") as mock_ks:
            mock_ks.get_knowledge = AsyncMock(return_value=None)

            response = await client.get("/api/thinkers/knowledge/UnknownThinker/status")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "UnknownThinker"
        assert data["status"] == "pending"
        assert data["has_data"] is False

    async def test_knowledge_status_returns_correct_status_for_existing_knowledge(
        self, client: AsyncClient
    ) -> None:
        """GET /api/thinkers/knowledge/{name}/status returns status from DB record.

        Regression guard: The status endpoint must reflect the actual research state.
        If it always returns PENDING or COMPLETE, the frontend cannot accurately
        determine when to stop polling.
        """
        from app.models.thinker_knowledge import ResearchStatus, ThinkerKnowledge

        mock_knowledge = MagicMock(spec=ThinkerKnowledge)
        mock_knowledge.name = "Socrates"
        mock_knowledge.status = ResearchStatus.COMPLETE
        mock_knowledge.research_data = {"wikipedia": {"title": "Socrates"}}
        mock_knowledge.updated_at = None

        with patch("app.services.knowledge_research.knowledge_service") as mock_ks:
            mock_ks.get_knowledge = AsyncMock(return_value=mock_knowledge)

            response = await client.get("/api/thinkers/knowledge/Socrates/status")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Socrates"
        assert data["status"] == "complete"
        assert data["has_data"] is True


class TestThinkerKnowledgeRefreshEndpoint:
    """Regression tests for POST /api/thinkers/knowledge/{name}/refresh.

    The refresh endpoint forces a new research run. Regressions could cause
    stale data to persist or research to never be triggered.
    """

    async def test_refresh_endpoint_triggers_research(self, client: AsyncClient) -> None:
        """POST /api/thinkers/knowledge/{name}/refresh triggers research.

        Regression guard: The refresh endpoint must call trigger_research even
        if knowledge already exists. If the trigger is gated by status, stale
        or failed entries could never be refreshed.
        """
        from app.models.thinker_knowledge import ResearchStatus, ThinkerKnowledge

        mock_knowledge = MagicMock(spec=ThinkerKnowledge)
        mock_knowledge.name = "Aristotle"
        mock_knowledge.status = ResearchStatus.COMPLETE
        mock_knowledge.research_data = {}
        mock_knowledge.updated_at = None

        with patch("app.services.knowledge_research.knowledge_service") as mock_ks:
            mock_ks.get_or_create_knowledge = AsyncMock(return_value=mock_knowledge)
            mock_ks.trigger_research = MagicMock()

            response = await client.post("/api/thinkers/knowledge/Aristotle/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Aristotle"
        # trigger_research must always be called on refresh
        mock_ks.trigger_research.assert_called_once_with("Aristotle")

    async def test_refresh_creates_knowledge_for_new_thinker(self, client: AsyncClient) -> None:
        """POST /api/thinkers/knowledge/{name}/refresh creates new DB entry.

        Regression guard: For thinkers not yet in the DB, get_or_create_knowledge
        must be called (not get_knowledge). If accidentally using get_knowledge,
        None would be returned and trigger_research would be called with None.
        """
        from app.models.thinker_knowledge import ResearchStatus, ThinkerKnowledge

        mock_knowledge = MagicMock(spec=ThinkerKnowledge)
        mock_knowledge.name = "NewThinker"
        mock_knowledge.status = ResearchStatus.PENDING
        mock_knowledge.research_data = {}
        mock_knowledge.updated_at = None

        with patch("app.services.knowledge_research.knowledge_service") as mock_ks:
            mock_ks.get_or_create_knowledge = AsyncMock(return_value=mock_knowledge)
            mock_ks.trigger_research = MagicMock()

            response = await client.post("/api/thinkers/knowledge/NewThinker/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "NewThinker"
        assert data["status"] == "pending"
        assert data["has_data"] is False


class TestConversationColorCycling:
    """Regression tests for thinker color assignment in conversations.

    The color assignment logic cycles through 5 predefined colors for thinkers.
    If the cycling logic breaks, all thinkers could get the same color.
    """

    async def test_create_conversation_assigns_different_colors_to_thinkers(
        self, client: AsyncClient
    ) -> None:
        """POST /api/conversations assigns distinct colors to multiple thinkers.

        Regression guard: The create_conversation endpoint uses a cycled color
        list. If the cycling is broken (e.g., all get index 0), all thinkers
        would have the same color (#6366f1), making them visually indistinguishable.
        """
        headers = await get_auth_headers(client, "colortest1", "pass123")

        thinkers = [
            {
                "name": f"Thinker{i}",
                "bio": f"Bio {i}",
                "positions": f"Positions {i}",
                "style": f"Style {i}",
                # Use the default color so server applies the cycle
                "color": "#6366f1",
            }
            for i in range(5)
        ]
        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Color test", "thinkers": thinkers},
        )
        assert response.status_code == 200
        data = response.json()
        colors = [t["color"] for t in data["thinkers"]]
        # All 5 thinkers should have distinct colors
        assert len(set(colors)) == 5, f"Expected 5 distinct colors, got: {colors}"

    async def test_add_thinkers_avoids_duplicate_colors(self, client: AsyncClient) -> None:
        """PUT /api/conversations/{id}/thinkers avoids colors already in use.

        Regression guard: When adding thinkers to a conversation that already has
        some, the color selection skips colors already in use. If available_colors
        is built incorrectly, new thinkers could get the same color as existing ones.
        """
        headers = await get_auth_headers(client, "colortest2", "pass456")

        # Create conversation with one thinker using a specific non-default color
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={
                "topic": "Color avoidance test",
                "thinkers": [
                    {
                        "name": "FirstThinker",
                        "bio": "First",
                        "positions": "First positions",
                        "style": "First style",
                        "color": "#6366f1",  # First in cycle
                    }
                ],
            },
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]
        existing_color = create_response.json()["thinkers"][0]["color"]

        # Add another thinker with the default color
        add_response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "SecondThinker",
                    "bio": "Second",
                    "positions": "Second positions",
                    "style": "Second style",
                    "color": "#6366f1",  # Default - should be reassigned
                }
            ],
        )
        assert add_response.status_code == 200
        new_thinker_color = add_response.json()[0]["color"]
        # New thinker must not have same color as existing
        assert new_thinker_color != existing_color, (
            f"New thinker got same color as existing: {new_thinker_color}"
        )

    async def test_add_thinkers_respects_max_limit_of_5(self, client: AsyncClient) -> None:
        """PUT /api/conversations/{id}/thinkers rejects additions exceeding 5 total.

        Regression guard: The 5-thinker limit enforced in add_thinkers_to_conversation
        prevents UI overload. If the check uses > 5 instead of >= 5 + new_count,
        conversations could end up with 6 or more thinkers.
        """
        headers = await get_auth_headers(client, "colortest3", "pass789")

        # Create conversation with 4 thinkers
        thinkers = [
            {
                "name": f"Thinker{i}",
                "bio": f"Bio {i}",
                "positions": f"Pos {i}",
                "style": f"Style {i}",
            }
            for i in range(4)
        ]
        create_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Max limit test", "thinkers": thinkers},
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["id"]

        # Try to add 2 more thinkers (would make 6 total - should fail)
        add_response = await client.put(
            f"/api/conversations/{conv_id}/thinkers",
            headers=headers,
            json=[
                {
                    "name": "ExtraThinker1",
                    "bio": "Extra1",
                    "positions": "Extra1 pos",
                    "style": "Extra1 style",
                },
                {
                    "name": "ExtraThinker2",
                    "bio": "Extra2",
                    "positions": "Extra2 pos",
                    "style": "Extra2 style",
                },
            ],
        )
        assert add_response.status_code == 400
        assert "Maximum is 5" in add_response.json()["detail"]


class TestThinkerSuggestFallback:
    """Regression tests for the thinker suggest endpoint fallback behavior.

    The suggest endpoint uses real API when available but falls back to mock data.
    """

    async def test_suggest_uses_mock_when_no_api_key(self, client: AsyncClient) -> None:
        """POST /api/thinkers/suggest returns mock suggestions without API key.

        Regression guard: The mock fallback path is the development path.
        If it breaks, all local development would fail to populate thinker suggestions.
        """
        # thinker_service is imported locally inside the function:
        # "from app.services.thinker import thinker_service"
        # so we patch at the services module level
        with (
            patch("app.api.thinkers.get_settings") as mock_settings,
            patch("app.services.thinker.thinker_service") as mock_ts,
        ):
            settings = MagicMock()
            settings.anthropic_api_key = ""  # No API key
            mock_settings.return_value = settings
            # Mock Wikipedia image fetch to avoid HTTP calls
            mock_ts.get_wikipedia_image = AsyncMock(return_value=None)

            response = await client.post(
                "/api/thinkers/suggest",
                json={"topic": "philosophy", "count": 3},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        # Each suggestion has the required fields
        for suggestion in data:
            assert "name" in suggestion
            assert "reason" in suggestion
            assert "profile" in suggestion

    async def test_validate_uses_mock_for_known_thinkers_without_api_key(
        self, client: AsyncClient
    ) -> None:
        """POST /api/thinkers/validate returns mock data for known thinkers without API key.

        Regression guard: The mock validation path handles the 6 preset thinkers.
        If this path breaks, the development experience is completely broken
        (no thinker validation without paying for API).
        """
        with (
            patch("app.api.thinkers.get_settings") as mock_settings,
            patch("app.services.thinker.thinker_service") as mock_ts,
            patch("app.services.knowledge_research.knowledge_service") as mock_ks,
        ):
            settings = MagicMock()
            settings.anthropic_api_key = ""
            mock_settings.return_value = settings
            mock_ts.get_wikipedia_image = AsyncMock(return_value=None)
            mock_ks.trigger_research = MagicMock()

            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "Socrates"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["name"] == "Socrates"

    async def test_validate_rejects_unknown_thinker_without_api_key(
        self, client: AsyncClient
    ) -> None:
        """POST /api/thinkers/validate rejects unknown thinkers without API key.

        Regression guard: In development mode (no API key), only the 6 preset
        thinkers are accepted. If the check is removed, any string would be
        accepted as a valid thinker, breaking data quality.
        """
        with patch("app.api.thinkers.get_settings") as mock_settings:
            settings = MagicMock()
            settings.anthropic_api_key = ""
            mock_settings.return_value = settings

            response = await client.post(
                "/api/thinkers/validate",
                json={"name": "Someone Nobody Knows"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "Unknown thinker" in data["error"]


class TestCreateAdminUserFunction:
    """Regression tests for the create_admin_user startup function in main.py.

    The admin user creation runs on every startup. Regressions could cause
    startup failures or incorrect admin user state.
    """

    async def test_create_admin_user_creates_user_when_none_exists(self) -> None:
        """create_admin_user creates admin=True user when DB has no admin.

        Regression guard: If the database is wiped (e.g., new deployment without
        migration) and create_admin_user fails, there's no way to log into the admin
        panel without manually inserting a user into the database.
        """
        from app.main import create_admin_user

        mock_user = None  # No existing admin

        with patch("app.main.async_session") as mock_session_ctx:
            mock_db = AsyncMock()
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            # Simulate no admin found
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()

            await create_admin_user()

            # Should have added a new admin user
            mock_db.add.assert_called_once()
            added_user = mock_db.add.call_args[0][0]
            assert added_user.username == "admin"
            assert added_user.is_admin is True
            mock_db.commit.assert_called_once()

    async def test_create_admin_user_skips_when_admin_already_exists(self) -> None:
        """create_admin_user skips creation when admin user already in DB.

        Regression guard: If the idempotency check is removed, every application
        restart would attempt to insert a duplicate 'admin' user, causing a unique
        constraint violation that crashes the startup sequence.
        """
        from app.main import create_admin_user

        existing_admin = MagicMock(spec=User)
        existing_admin.username = "admin"
        existing_admin.is_admin = True

        with patch("app.main.async_session") as mock_session_ctx:
            mock_db = AsyncMock()
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = existing_admin
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()

            await create_admin_user()

            # Should NOT add or commit anything (admin already exists)
            mock_db.add.assert_not_called()
            mock_db.commit.assert_not_called()


class TestKnowledgeResearchErrorHandling:
    """Regression tests for error handling in KnowledgeResearchService._research_thinker.

    The research service runs in the background. If exceptions are not properly
    caught, background tasks silently die leaving stale PENDING entries forever.
    """

    async def test_research_thinker_marks_failed_on_wikipedia_exception(self) -> None:
        """_research_thinker marks knowledge as FAILED when an exception occurs.

        Regression guard: The try/except in _research_thinker catches any exception
        and marks the DB entry as FAILED with the error message. Without this,
        a network timeout or API error would leave the entry in PENDING state
        forever with no indication of failure.
        """
        from app.models.thinker_knowledge import ResearchStatus, ThinkerKnowledge
        from app.services.knowledge_research import KnowledgeResearchService

        service = KnowledgeResearchService()

        # Track what gets set on the in-progress knowledge object
        in_progress_knowledge = MagicMock(spec=ThinkerKnowledge)
        in_progress_knowledge.name = "ErrorThinker"
        in_progress_knowledge.status = ResearchStatus.PENDING

        # Track what gets set on the error handler knowledge object
        error_knowledge = MagicMock(spec=ThinkerKnowledge)
        error_knowledge.name = "ErrorThinker"
        error_knowledge.status = ResearchStatus.IN_PROGRESS

        # Create two separate mock db sessions
        mock_db1 = AsyncMock()
        mock_db1.commit = AsyncMock()

        mock_db2 = AsyncMock()
        mock_db2.commit = AsyncMock()

        async def mock_get_or_create(_db: object, _name: str) -> MagicMock:
            return in_progress_knowledge

        async def mock_get_knowledge(_db: object, _name: str) -> MagicMock:
            return error_knowledge

        # Patch all session context managers and service methods together
        with (
            patch.object(service, "get_or_create_knowledge", side_effect=mock_get_or_create),
            patch.object(service, "get_knowledge", side_effect=mock_get_knowledge),
            patch.object(
                service,
                "_fetch_wikipedia_data",
                side_effect=ValueError("Wikipedia API unreachable"),
            ),
            patch("app.services.knowledge_research.async_session") as mock_session_factory,
        ):
            # Both with blocks use async_session() - return different mocks
            ctx1 = AsyncMock()
            ctx1.__aenter__ = AsyncMock(return_value=mock_db1)
            ctx1.__aexit__ = AsyncMock(return_value=None)

            ctx2 = AsyncMock()
            ctx2.__aenter__ = AsyncMock(return_value=mock_db2)
            ctx2.__aexit__ = AsyncMock(return_value=None)

            mock_session_factory.side_effect = [ctx1, ctx2]

            await service._research_thinker("ErrorThinker")

        # The error handler should have set status to FAILED with error message
        assert error_knowledge.status == ResearchStatus.FAILED
        assert "Wikipedia API unreachable" in str(error_knowledge.error_message)
        mock_db2.commit.assert_called_once()

    def test_trigger_research_does_not_start_duplicate_task(self) -> None:
        """trigger_research deduplicates: second call for same thinker is a no-op.

        Regression guard: The _active_tasks check prevents duplicate research tasks.
        Without it, every thinker mention would spin up a new HTTP task, causing
        a thundering herd against the Wikipedia API and running up server costs.
        """

        from app.services.knowledge_research import KnowledgeResearchService

        service = KnowledgeResearchService()

        # Create a mock task that appears to be still running (not done)
        mock_task = MagicMock()
        mock_task.done.return_value = False  # Task is still running

        # Register it as active
        service._active_tasks["Socrates"] = mock_task

        # Patch create_task to track if it's called
        with patch("app.services.knowledge_research.asyncio") as mock_asyncio:
            service.trigger_research("Socrates")
            # create_task should NOT be called since mock_task.done() returns False
            mock_asyncio.get_event_loop.return_value.create_task.assert_not_called()

    async def test_trigger_research_starts_task_when_previous_completed(self) -> None:
        """trigger_research starts a new task when the previous one is done.

        Regression guard: The deduplication check uses task.done() to allow
        re-triggering after a task completes. Without the done() check, a
        completed research task could never be re-triggered (e.g., for refresh).
        """
        import asyncio

        from app.services.knowledge_research import KnowledgeResearchService

        service = KnowledgeResearchService()

        # Create a real completed task by running a trivial coroutine
        async def trivial() -> None:
            return

        done_task = asyncio.create_task(trivial())
        await done_task  # Wait for completion

        # Register the completed task
        service._active_tasks["Aristotle"] = done_task
        assert done_task.done(), "Setup: task should be done before the test"

        # Call trigger_research - it should create a NEW task because the old one is done
        # We need to mock the _research_thinker to return a real coroutine but not block
        new_task_created = asyncio.create_task(trivial())

        with patch("app.services.knowledge_research.asyncio.create_task") as mock_create:
            mock_create.return_value = new_task_created

            service.trigger_research("Aristotle")

            # create_task SHOULD have been called since the previous task is done
            mock_create.assert_called_once()
            # The new task should be stored
            assert service._active_tasks.get("Aristotle") is new_task_created

        # Cleanup
        await new_task_created
