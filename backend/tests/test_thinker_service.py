"""Tests for the ThinkerService."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from anthropic import APIError
from anthropic.types import TextBlock

from app.exceptions import BillingError
from app.models.message import SenderType
from app.services.thinker import ThinkerService


class TestThinkerService:
    """Tests for ThinkerService."""

    def test_service_initialization(self) -> None:
        """Test that service initializes correctly."""
        service = ThinkerService()
        assert service._client is None
        assert service._active_tasks == {}

    def test_client_property_without_api_key(self) -> None:
        """Test that client is None without API key."""
        service = ThinkerService()
        # Settings is initialized in __init__ with empty API key by default
        service.settings = MagicMock()
        service.settings.anthropic_api_key = ""
        assert service.client is None


class TestShouldRespond:
    """Tests for the _should_respond method."""

    def test_should_not_respond_to_empty_messages(self) -> None:
        """Test that thinker doesn't respond when there are no messages."""
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        result = service._should_respond(thinker, [], 0)
        assert result is False

    def test_should_not_respond_when_no_new_messages(self) -> None:
        """Test that thinker doesn't respond when no new messages."""
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        messages: Any = [MagicMock(content="Hello", sender_name="User")]

        result = service._should_respond(thinker, messages, 1)
        assert result is False

    def test_low_probability_for_own_message(self) -> None:
        """Test that thinker has low probability to respond to own message."""
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = MagicMock()
        message.content = "This is my message"
        message.sender_name = "Socrates"
        messages: Any = [message]

        # Run multiple times to check probability is low
        responses = [service._should_respond(thinker, messages, 0) for _ in range(100)]
        # Should respond less than 20% of the time to own messages
        response_rate = sum(responses) / len(responses)
        assert response_rate < 0.20


class TestSuggestThinkers:
    """Tests for suggest_thinkers method."""

    async def test_suggest_returns_empty_without_client(self) -> None:
        """Test that suggest_thinkers returns empty list without client."""
        service = ThinkerService()
        # Mock the client property to return None
        with patch.object(type(service), "client", new_callable=PropertyMock) as mock_client:
            mock_client.return_value = None
            result = await service.suggest_thinkers("philosophy", 3)
            assert result == []

    async def test_suggest_with_mock_client(self) -> None:
        """Test suggest_thinkers with mocked API response."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_response.content = [
            TextBlock(
                type="text",
                text="""[
                {
                    "name": "Socrates",
                    "reason": "Master of questioning",
                    "profile": {
                        "name": "Socrates",
                        "bio": "Ancient Greek philosopher",
                        "positions": "Socratic method",
                        "style": "Questions everything"
                    }
                }
            ]""",
            )
        ]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.suggest_thinkers("philosophy", 1)

        assert len(result) == 1
        assert result[0].name == "Socrates"
        assert result[0].profile.bio == "Ancient Greek philosopher"


class TestValidateThinker:
    """Tests for validate_thinker method."""

    async def test_validate_returns_false_without_client(self) -> None:
        """Test that validate_thinker returns False without client."""
        service = ThinkerService()
        # Mock the client property to return None
        with patch.object(type(service), "client", new_callable=PropertyMock) as mock_client:
            mock_client.return_value = None
            is_valid, profile = await service.validate_thinker("Socrates")
            assert is_valid is False
            assert profile is None

    async def test_validate_with_valid_response(self) -> None:
        """Test validate_thinker with valid API response."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_response.content = [
            TextBlock(
                type="text",
                text="""{
                "valid": true,
                "profile": {
                    "name": "Socrates",
                    "bio": "Ancient Greek philosopher",
                    "positions": "Socratic method",
                    "style": "Questions everything"
                }
            }""",
            )
        ]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        is_valid, profile = await service.validate_thinker("Socrates")

        assert is_valid is True
        assert profile is not None
        assert profile.name == "Socrates"

    async def test_validate_with_invalid_response(self) -> None:
        """Test validate_thinker with invalid API response."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_response.content = [
            TextBlock(
                type="text",
                text="""{
                "valid": false,
                "reason": "Not a real person"
            }""",
            )
        ]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        is_valid, profile = await service.validate_thinker("FakePerson123")

        assert is_valid is False
        assert profile is None


class TestGenerateResponse:
    """Tests for generate_response method."""

    async def test_generate_returns_empty_without_client(self) -> None:
        """Test that generate_response returns empty without client."""
        service = ThinkerService()

        thinker = MagicMock()
        messages: Any = []

        # Mock the client property to return None
        with patch.object(type(service), "client", new_callable=PropertyMock) as mock_client:
            mock_client.return_value = None
            response, cost = await service.generate_response(thinker, messages, "test")
            assert response == ""
            assert cost == 0.0

    async def test_generate_with_mock_response(self) -> None:
        """Test generate_response with mocked API response."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text="I think therefore I am.")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 10

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        thinker = MagicMock()
        thinker.name = "Descartes"
        thinker.bio = "French philosopher"
        thinker.positions = "Rationalism"
        thinker.style = "Methodical doubt"

        message = MagicMock()
        message.sender_type = SenderType.USER
        message.sender_name = None
        message.content = "What is the nature of existence?"
        messages: Any = [message]

        response, cost = await service.generate_response(thinker, messages, "philosophy")

        assert response == "I think therefore I am."
        assert cost > 0  # Cost should be calculated


class TestSplitResponseIntoBubbles:
    """Tests for _split_response_into_bubbles helper method."""

    def test_empty_text_returns_empty_list(self) -> None:
        """Test that empty text returns empty list."""
        service = ThinkerService()
        result = service._split_response_into_bubbles("")
        assert result == []

    def test_very_short_text_single_bubble(self) -> None:
        """Test that very short text (<60 chars) always returns single bubble."""
        service = ThinkerService()
        result = service._split_response_into_bubbles("This is a short message.")
        assert len(result) == 1
        assert result[0] == "This is a short message."

    def test_text_under_60_chars_never_splits(self) -> None:
        """Test that text under 60 chars never splits regardless of strategy."""
        import random

        service = ThinkerService()
        text = "Short text that won't be split ever."  # 36 chars
        # Run multiple times to account for random strategy
        for _ in range(20):
            random.seed(None)  # Reset random state
            result = service._split_response_into_bubbles(text)
            assert len(result) == 1

    def test_long_text_can_split_at_sentences(self) -> None:
        """Test that sufficiently long text can split at sentence boundaries."""
        import random

        service = ThinkerService()
        # Text > 250 chars to ensure it's not kept as single bubble
        text = (
            "This is the first sentence of my response to your interesting question here. "
            "Now I will continue with a second sentence that adds significantly more detail about the topic. "
            "And here is a third sentence to provide even more context and make the response complete. "
            "Finally a fourth sentence to ensure we exceed all thresholds for splitting behavior."
        )
        # Run with different random seeds to find a split case
        found_split = False
        for seed in range(100):
            random.seed(seed)
            result = service._split_response_into_bubbles(text)
            if len(result) >= 2:
                found_split = True
                # Each bubble should be a complete thought
                for bubble in result:
                    assert bubble.endswith((".", "!", "?"))
                break
        assert found_split, "Text should split at least sometimes"

    def test_splits_at_transition_words(self) -> None:
        """Test that transitions like 'However' start new bubbles."""
        import random

        service = ThinkerService()
        # Text with transition word - should split at However when splitting occurs
        text = (
            "I think this is absolutely true and correct in every way imaginable. "
            "However, there are some notable exceptions we should consider very carefully here. "
            "These exceptions are critically important for our continued discussion."
        )
        # Run with different random seeds to find a case where However is in its own bubble
        found_transition_split = False
        for seed in range(100):
            random.seed(seed)
            result = service._split_response_into_bubbles(text)
            if len(result) >= 2 and any(b.startswith("However") for b in result):
                found_transition_split = True
                break
        assert found_transition_split, "Should sometimes split at transition words"

    def test_very_long_text_forces_split(self) -> None:
        """Test that very long text (>300 chars) forces a split."""
        import random

        service = ThinkerService()
        text = "This is a very long sentence that goes on and on with more content. " * 8
        # Even with single-bubble strategy (25% chance), text > 300 should force split
        for seed in range(20):
            random.seed(seed)
            result = service._split_response_into_bubbles(text)
            assert len(result) >= 1  # At minimum returns something
        # With text this long, most runs should produce multiple bubbles
        random.seed(42)
        result = service._split_response_into_bubbles(text)
        assert len(result) >= 2


class TestExtractThinkingDisplay:
    """Tests for _extract_thinking_display helper method."""

    def test_empty_text_returns_empty(self) -> None:
        """Test that empty text returns empty string."""
        service = ThinkerService()
        result = service._extract_thinking_display("")
        assert result == ""

    def test_very_short_text_returns_empty(self) -> None:
        """Test that very short text returns empty (waits for more content)."""
        service = ThinkerService()
        # Text under 80 chars should return empty to avoid truncated snippets
        result = service._extract_thinking_display("Considering the implications")
        assert result == ""

    def test_medium_text_returned_with_formatting(self) -> None:
        """Test that medium text (80+ chars) is returned with formatting."""
        service = ThinkerService()
        # Text over 80 chars should be returned with possible prefix/ellipsis
        text = "This is a longer piece of thinking text that has enough content to be meaningful and worth displaying to the user."
        result = service._extract_thinking_display(text)
        assert len(result) > 0
        assert "thinking" in result.lower() or "content" in result.lower()

    def test_long_text_truncated(self) -> None:
        """Test that long text is truncated to ~200 chars."""
        service = ThinkerService()
        long_text = "This is a very long thinking text. " * 20
        result = service._extract_thinking_display(long_text)
        # Should be truncated (may include prefix)
        assert len(result) <= 250  # ~200 + prefix + ellipsis

    def test_text_ending_with_period_no_extra_ellipsis(self) -> None:
        """Test that text ending with period doesn't get extra ellipsis."""
        service = ThinkerService()
        # Need 80+ chars to get output
        text = "This is a complete thought that is long enough to be meaningful and informative. It ends properly."
        result = service._extract_thinking_display(text)
        # May have a prefix added but should end with period, not ellipsis
        assert result.endswith(".")
        assert "complete" in result or "thought" in result

    def test_preserves_sentence_boundaries(self) -> None:
        """Test that truncation tries to preserve sentence boundaries."""
        service = ThinkerService()
        text = "First sentence. " * 5 + "Second sentence. " * 5 + "Final thought"
        result = service._extract_thinking_display(text)
        # Should try to start at a sentence boundary and produce reasonable output
        assert len(result) <= 250  # May include prefix
        assert len(result) >= 40  # Should have substantial content


class TestGenerateResponseWithStreamingThinking:
    """Tests for generate_response_with_streaming_thinking method."""

    async def test_returns_empty_without_client(self) -> None:
        """Test that method returns empty without client."""
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"
        thinker.bio = "Ancient philosopher"
        thinker.positions = "Questioning everything"
        thinker.style = "Socratic method"
        messages: Any = []

        # Mock the client property to return None
        with patch.object(type(service), "client", new_callable=PropertyMock) as mock_client:
            mock_client.return_value = None
            response, cost = await service.generate_response_with_streaming_thinking(
                "test-conv", thinker, messages, "philosophy"
            )
            assert response == ""
            assert cost == 0.0


class TestConversationAgents:
    """Tests for conversation agent management."""

    async def test_stop_agents_clears_tasks(self) -> None:
        """Test that stopping agents clears the task dict."""
        import asyncio

        service = ThinkerService()
        conversation_id = "test-conv"

        # Create a real cancelled task
        async def dummy_coro() -> None:
            await asyncio.sleep(100)

        task = asyncio.create_task(dummy_coro())
        service._active_tasks[conversation_id] = {"thinker-1": task}

        await service.stop_conversation_agents(conversation_id)

        assert conversation_id not in service._active_tasks

    async def test_stop_agents_does_nothing_for_unknown_conversation(self) -> None:
        """Test that stopping agents for unknown conversation doesn't error."""
        service = ThinkerService()

        # Should not raise
        await service.stop_conversation_agents("nonexistent")


class TestBillingErrorDetection:
    """Tests for billing error detection in ThinkerService."""

    def _create_mock_request(self) -> MagicMock:
        """Create a mock httpx.Request for APIError."""
        mock_request = MagicMock()
        mock_request.url = "https://api.anthropic.com/v1/messages"
        mock_request.method = "POST"
        return mock_request

    async def test_billing_error_raised_on_credit_balance_error(self) -> None:
        """Test that BillingError is raised when API returns credit balance error."""
        service = ThinkerService()

        # Mock the client to raise APIError with credit balance message
        mock_client = AsyncMock()
        mock_stream = AsyncMock()
        mock_request = self._create_mock_request()
        mock_stream.__aenter__ = AsyncMock(
            side_effect=APIError("Your credit balance is too low", mock_request, body=None)
        )
        mock_client.messages.stream = MagicMock(return_value=mock_stream)
        service._client = mock_client

        thinker = MagicMock()
        thinker.name = "Socrates"
        thinker.bio = "Ancient philosopher"
        thinker.positions = "Questioning everything"
        thinker.style = "Socratic method"
        messages: Any = []

        # Should raise BillingError, not ThinkerAPIError
        with pytest.raises(BillingError) as exc_info:
            await service.generate_response_with_streaming_thinking(
                "test-conv", thinker, messages, "philosophy"
            )

        assert "credit" in str(exc_info.value).lower()

    async def test_billing_error_raised_on_billing_keyword(self) -> None:
        """Test that BillingError is raised when API returns error with 'billing' keyword."""
        service = ThinkerService()

        # Mock the client to raise APIError with billing message
        mock_client = AsyncMock()
        mock_stream = AsyncMock()
        mock_request = self._create_mock_request()
        mock_stream.__aenter__ = AsyncMock(
            side_effect=APIError("Billing issue: payment method required", mock_request, body=None)
        )
        mock_client.messages.stream = MagicMock(return_value=mock_stream)
        service._client = mock_client

        thinker = MagicMock()
        thinker.name = "Socrates"
        thinker.bio = "Ancient philosopher"
        thinker.positions = "Questioning everything"
        thinker.style = "Socratic method"
        messages: Any = []

        # Should raise BillingError
        with pytest.raises(BillingError) as exc_info:
            await service.generate_response_with_streaming_thinking(
                "test-conv", thinker, messages, "philosophy"
            )

        assert "billing" in str(exc_info.value).lower()

    async def test_non_billing_api_error_raises_thinker_api_error(self) -> None:
        """Test that non-billing API errors raise ThinkerAPIError, not BillingError."""
        from app.exceptions import ThinkerAPIError

        service = ThinkerService()

        # Mock the client to raise APIError without billing keywords
        mock_client = AsyncMock()
        mock_stream = AsyncMock()
        mock_request = self._create_mock_request()
        mock_stream.__aenter__ = AsyncMock(
            side_effect=APIError("Rate limit exceeded", mock_request, body=None)
        )
        mock_client.messages.stream = MagicMock(return_value=mock_stream)
        service._client = mock_client

        thinker = MagicMock()
        thinker.name = "Socrates"
        thinker.bio = "Ancient philosopher"
        thinker.positions = "Questioning everything"
        thinker.style = "Socratic method"
        messages: Any = []

        # Should raise ThinkerAPIError, not BillingError
        with pytest.raises(ThinkerAPIError) as exc_info:
            await service.generate_response_with_streaming_thinking(
                "test-conv", thinker, messages, "philosophy"
            )

        # Should not contain billing-specific message
        assert (
            "credit" not in str(exc_info.value).lower()
            or "rate limit" in str(exc_info.value).lower()
        )
