"""Regression tests for recent features and bug fixes.

This module contains regression tests for features added in the past month
that don't have adequate test coverage yet.

Test Organization:
- TestConversationColorCycling: Tests for thinker color assignment logic
- TestConversationCostCalculation: Tests for message cost summation
- TestLanguagePreferenceValidation: Tests for language preference edge cases
"""

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


async def get_auth_headers(
    client: AsyncClient,
    username: str = "testuser",
    password: str = "testpass123",
) -> dict[str, str]:
    """Helper to get authorization headers for an authenticated user."""
    register_response = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": username.title(),
            "password": password,
        },
    )
    assert register_response.status_code == 200
    token = register_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_thinker_data(name: str = "Aristotle", color: str | None = None) -> dict[str, str]:
    """Helper to create thinker data for conversation creation."""
    data = {
        "name": name,
        "bio": f"Biography of {name}",
        "positions": f"Positions of {name}",
        "style": f"Style of {name}",
    }
    if color is not None:
        data["color"] = color
    return data


class TestConversationColorCycling:
    """Regression tests for thinker color assignment logic.

    Feature: When creating conversations, thinkers get colors from a predefined palette.
    If a thinker has a custom color (not the default #6366f1), use it.
    Otherwise, cycle through colors: #6366f1, #ec4899, #10b981, #f59e0b, #8b5cf6.

    Code: conversations.py:46-56
    Current coverage: 39%
    """

    async def test_default_color_cycles_through_palette(self, client: AsyncClient) -> None:
        """Test that default color (#6366f1) causes cycling through color palette.

        Regression test for conversations.py:54-56 - when thinker_data.color
        is the default #6366f1, we use colors[i % len(colors)] instead.
        """
        headers = await get_auth_headers(client, "coloruser1", "password123")

        # Create conversation with 5 thinkers (max allowed)
        # All use default color to trigger cycling
        thinkers = [create_thinker_data(f"Thinker{i}", "#6366f1") for i in range(5)]

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Color cycling test", "thinkers": thinkers},
        )

        assert response.status_code == 200
        data = response.json()

        # Expected colors based on cycling: [0]=#6366f1, [1]=#ec4899, [2]=#10b981,
        # [3]=#f59e0b, [4]=#8b5cf6
        expected_colors = [
            "#6366f1",  # i=0: 0 % 5 = 0
            "#ec4899",  # i=1: 1 % 5 = 1
            "#10b981",  # i=2: 2 % 5 = 2
            "#f59e0b",  # i=3: 3 % 5 = 3
            "#8b5cf6",  # i=4: 4 % 5 = 4
        ]

        thinkers_data = data["thinkers"]
        assert len(thinkers_data) == 5

        for i, thinker in enumerate(thinkers_data):
            assert thinker["color"] == expected_colors[i], (
                f"Thinker {i} expected color {expected_colors[i]}, got {thinker['color']}"
            )

    async def test_custom_color_preserved(self, client: AsyncClient) -> None:
        """Test that custom colors (not #6366f1) are preserved.

        Regression test for conversations.py:54-55 - if thinker_data.color
        is NOT #6366f1, use it directly without cycling.
        """
        headers = await get_auth_headers(client, "coloruser2", "password123")

        # Create conversation with mix of default and custom colors
        thinkers = [
            create_thinker_data("Default1", "#6366f1"),  # Should cycle to index 0
            create_thinker_data("Custom1", "#ff0000"),  # Should preserve red
            create_thinker_data("Default2", "#6366f1"),  # Should cycle to index 2
            create_thinker_data("Custom2", "#00ff00"),  # Should preserve green
        ]

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Mixed colors test", "thinkers": thinkers},
        )

        assert response.status_code == 200
        data = response.json()

        # Expected: cycle for defaults, preserve customs
        expected_colors = [
            "#6366f1",  # Default -> cycles to index 0
            "#ff0000",  # Custom -> preserved
            "#10b981",  # Default -> cycles to index 2
            "#00ff00",  # Custom -> preserved
        ]

        thinkers_data = data["thinkers"]
        assert len(thinkers_data) == 4

        for i, thinker in enumerate(thinkers_data):
            assert thinker["color"] == expected_colors[i], (
                f"Thinker {i} ({thinker['name']}) expected color "
                f"{expected_colors[i]}, got {thinker['color']}"
            )

    async def test_all_custom_colors_no_cycling(self, client: AsyncClient) -> None:
        """Test that all custom colors bypass cycling entirely.

        Regression test - when no thinker has the default color,
        no cycling should occur.
        """
        headers = await get_auth_headers(client, "coloruser3", "password123")

        # All thinkers have custom colors
        custom_colors = ["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff"]
        thinkers = [
            create_thinker_data(f"Custom{i}", color) for i, color in enumerate(custom_colors)
        ]

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "All custom colors", "thinkers": thinkers},
        )

        assert response.status_code == 200
        data = response.json()
        thinkers_data = data["thinkers"]

        # All should preserve their custom colors
        for i, thinker in enumerate(thinkers_data):
            assert thinker["color"] == custom_colors[i]

    async def test_color_cycling_with_max_thinkers(self, client: AsyncClient) -> None:
        """Test color cycling with maximum thinkers (5).

        Regression test - validates cycling works correctly at boundary.
        """
        headers = await get_auth_headers(client, "coloruser4", "password123")

        # 5 thinkers with default color
        thinkers = [create_thinker_data(f"T{i}", "#6366f1") for i in range(5)]

        response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Max thinkers", "thinkers": thinkers},
        )

        assert response.status_code == 200
        data = response.json()

        # Should cycle through all 5 colors exactly once
        expected_colors = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]

        thinkers_data = data["thinkers"]
        for i, thinker in enumerate(thinkers_data):
            assert thinker["color"] == expected_colors[i]


class TestConversationCostCalculation:
    """Regression tests for conversation cost calculation.

    Feature: List conversations endpoint calculates total_cost by summing
    message costs, handling None values correctly.

    Code: conversations.py:87-105
    Current coverage: 39%
    """

    async def test_cost_calculation_with_zero_cost_messages(self, client: AsyncClient) -> None:
        """Test that zero-cost messages are handled correctly in total_cost.

        Regression test for conversations.py:90 - ensures cost or 0.0
        handles messages with cost=None or cost=0.0 correctly.
        """
        headers = await get_auth_headers(client, "costuser1", "password123")

        # Create conversation
        thinkers = [create_thinker_data("Socrates")]
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Cost test", "thinkers": thinkers},
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # Send a user message (typically has no cost)
        msg_response = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "Test message with no cost"},
        )
        assert msg_response.status_code == 200

        # List conversations - should calculate total_cost correctly
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200
        conversations = list_response.json()

        # Find our conversation
        conv = next((c for c in conversations if c["id"] == conversation_id), None)
        assert conv is not None

        # Total cost should be 0.0 (or a small number from AI messages)
        # The key test is that it doesn't error on None values
        assert "total_cost" in conv
        assert isinstance(conv["total_cost"], (int, float))
        assert conv["total_cost"] >= 0.0

    async def test_cost_calculation_empty_conversation(self, client: AsyncClient) -> None:
        """Test that conversations with no messages have total_cost=0.0.

        Regression test for conversations.py:90 - empty message list
        should sum to 0.0, not cause errors.
        """
        headers = await get_auth_headers(client, "costuser2", "password123")

        # Create conversation with no messages
        thinkers = [create_thinker_data("Plato")]
        conv_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Empty conversation", "thinkers": thinkers},
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["id"]

        # List conversations
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200
        conversations = list_response.json()

        conv = next((c for c in conversations if c["id"] == conversation_id), None)
        assert conv is not None

        # Empty conversation should have zero cost
        assert conv["total_cost"] == 0.0
        assert conv["message_count"] == 0

    async def test_multiple_conversations_cost_isolation(self, client: AsyncClient) -> None:
        """Test that costs are calculated independently for each conversation.

        Regression test for conversations.py:89-104 - ensures the loop
        correctly isolates costs per conversation.
        """
        headers = await get_auth_headers(client, "costuser3", "password123")

        # Create two conversations
        thinkers = [create_thinker_data("Aristotle")]

        conv1_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Conversation 1", "thinkers": thinkers},
        )
        assert conv1_response.status_code == 200
        conv1_id = conv1_response.json()["id"]

        conv2_response = await client.post(
            "/api/conversations",
            headers=headers,
            json={"topic": "Conversation 2", "thinkers": thinkers},
        )
        assert conv2_response.status_code == 200
        conv2_id = conv2_response.json()["id"]

        # Add messages to conv1 only
        await client.post(
            f"/api/conversations/{conv1_id}/messages",
            headers=headers,
            json={"content": "Message in conv1"},
        )

        # List conversations
        list_response = await client.get("/api/conversations", headers=headers)
        assert list_response.status_code == 200
        conversations = list_response.json()

        conv1 = next((c for c in conversations if c["id"] == conv1_id), None)
        conv2 = next((c for c in conversations if c["id"] == conv2_id), None)

        assert conv1 is not None
        assert conv2 is not None

        # Conv1 should have messages, conv2 should not
        assert conv1["message_count"] > 0
        assert conv2["message_count"] == 0

        # Costs should be independent (conv2 should be 0.0)
        assert conv2["total_cost"] == 0.0


class TestLanguagePreferenceValidation:
    """Regression tests for language preference validation.

    Feature: PATCH /api/auth/language validates language codes.
    Missing tests for: invalid codes, case sensitivity, empty strings.

    Code: auth.py:89-104
    Current coverage: 68%
    """

    async def test_invalid_language_code_rejected(self, client: AsyncClient) -> None:
        """Test that invalid language codes are rejected.

        Regression test for auth.py - ensures validation catches invalid codes.
        """
        headers = await get_auth_headers(client, "languser1", "password123")

        # Try to set invalid language
        response = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "invalid"},
        )

        # Should be rejected (422 Unprocessable Content)
        assert response.status_code == 422

    async def test_empty_language_code_rejected(self, client: AsyncClient) -> None:
        """Test that empty language codes are rejected.

        Regression test for auth.py - empty strings should not be accepted.
        """
        headers = await get_auth_headers(client, "languser2", "password123")

        # Try to set empty language
        response = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": ""},
        )

        # Should be rejected
        assert response.status_code == 422

    async def test_case_sensitive_language_codes(self, client: AsyncClient) -> None:
        """Test that language codes are case-sensitive (lowercase required).

        Regression test for auth.py - "EN" should be rejected, "en" accepted.
        """
        headers = await get_auth_headers(client, "languser3", "password123")

        # Uppercase should be rejected
        response_upper = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "EN"},
        )
        assert response_upper.status_code == 422

        # Lowercase should work
        response_lower = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "en"},
        )
        assert response_lower.status_code == 200

    async def test_all_valid_language_codes(self, client: AsyncClient) -> None:
        """Test that all valid language codes are accepted.

        Regression test for auth.py - validates en, es, fr, de.
        Note: Hindi ("hi") is supported in ThinkerService but not yet added to
        auth validation schema - this is a known gap.
        """
        headers = await get_auth_headers(client, "languser4", "password123")

        # Only test codes that are in the auth.py validation pattern
        valid_codes = ["en", "es", "fr", "de"]

        for code in valid_codes:
            response = await client.patch(
                "/api/auth/language",
                headers=headers,
                json={"language_preference": code},
            )
            assert response.status_code == 200, f"Language code '{code}' was rejected"
            assert response.json()["language_preference"] == code

    async def test_hindi_language_not_yet_validated_in_auth(self, client: AsyncClient) -> None:
        """Test that Hindi is not yet validated in auth schemas.

        Regression test documenting gap: Hindi ("hi") is supported in
        ThinkerService (for LLM responses) but not in auth.py validation.
        This test documents the discrepancy until Hindi is fully integrated.
        """
        headers = await get_auth_headers(client, "languser5", "password123")

        # Hindi should be rejected by auth validation (not in pattern)
        response = await client.patch(
            "/api/auth/language",
            headers=headers,
            json={"language_preference": "hi"},
        )

        # Currently rejected (422) - documents the gap
        assert response.status_code == 422

        # TODO: When Hindi is added to auth.py validation pattern,
        # move this test to test_all_valid_language_codes
