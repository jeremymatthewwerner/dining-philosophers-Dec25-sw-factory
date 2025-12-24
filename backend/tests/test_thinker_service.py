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


class TestPauseResumeConversation:
    """Tests for conversation pause/resume functionality."""

    def test_pause_conversation(self) -> None:
        """Test pausing a conversation."""
        service = ThinkerService()
        conversation_id = "test-conv-123"

        assert not service.is_paused(conversation_id)

        service.pause_conversation(conversation_id)

        assert service.is_paused(conversation_id)

    def test_resume_conversation(self) -> None:
        """Test resuming a paused conversation."""
        service = ThinkerService()
        conversation_id = "test-conv-123"

        service.pause_conversation(conversation_id)
        assert service.is_paused(conversation_id)

        service.resume_conversation(conversation_id)
        assert not service.is_paused(conversation_id)

    def test_resume_conversation_not_paused(self) -> None:
        """Test resuming a conversation that wasn't paused."""
        service = ThinkerService()
        conversation_id = "test-conv-123"

        # Should not error when resuming a conversation that wasn't paused
        service.resume_conversation(conversation_id)
        assert not service.is_paused(conversation_id)

    def test_is_paused_returns_false_for_unknown_conversation(self) -> None:
        """Test that is_paused returns False for unknown conversations."""
        service = ThinkerService()
        assert not service.is_paused("unknown-conversation")


class TestChooseResponseStyle:
    """Tests for _choose_response_style method."""

    def test_choose_style_with_empty_messages(self) -> None:
        """Test choosing response style with no messages."""
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        style, max_tokens = service._choose_response_style(thinker, [])

        assert isinstance(style, str)
        assert isinstance(max_tokens, int)
        assert max_tokens > 0

    def test_choose_style_when_addressed(self) -> None:
        """Test that thinker gets more substantive style when addressed."""
        import random

        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = MagicMock()
        message.content = "Socrates, what do you think about this?"
        message.sender_name = "User"
        messages: Any = [message]

        # Test multiple times to check distribution
        token_counts = []
        for seed in range(20):
            random.seed(seed)
            style, max_tokens = service._choose_response_style(thinker, messages)
            token_counts.append(max_tokens)

        # When addressed, should have variety but generally higher token counts
        assert min(token_counts) >= 30
        assert max(token_counts) <= 350
        # Should have some variety in token counts
        assert len(set(token_counts)) > 1

    def test_choose_style_after_own_message(self) -> None:
        """Test response style when thinker just spoke."""
        import random

        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = MagicMock()
        message.content = "I believe this is true."
        message.sender_name = "Socrates"
        messages: Any = [message]

        # Test multiple times - should sometimes choose brief follow-up
        brief_count = 0
        for seed in range(50):
            random.seed(seed)
            style, max_tokens = service._choose_response_style(thinker, messages)
            if max_tokens == 50:
                brief_count += 1

        # Should have some brief follow-ups (around 40% chance)
        assert brief_count > 0
        assert brief_count < 50


class TestGetWikipediaImage:
    """Tests for get_wikipedia_image method."""

    async def test_get_image_with_no_results(self) -> None:
        """Test get_wikipedia_image when no search results found."""
        service = ThinkerService()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock search response with no results
            mock_response = AsyncMock()
            mock_response.json.return_value = {"query": {"search": []}}
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await service.get_wikipedia_image("NonexistentPerson123")

            assert result is None

    async def test_get_image_with_exception(self) -> None:
        """Test get_wikipedia_image handles exceptions gracefully."""
        service = ThinkerService()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock to raise an exception
            mock_client.get = AsyncMock(side_effect=Exception("Network error"))

            result = await service.get_wikipedia_image("Socrates")

            # Should return None on error, not raise
            assert result is None

    async def test_get_image_with_valid_result(self) -> None:
        """Test get_wikipedia_image with valid Wikipedia response."""
        service = ThinkerService()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            # Mock search response
            search_response = MagicMock()
            search_response.json.return_value = {"query": {"search": [{"title": "Socrates"}]}}

            # Mock image response
            image_response = MagicMock()
            image_response.json.return_value = {
                "query": {
                    "pages": {"123": {"thumbnail": {"source": "https://example.com/socrates.jpg"}}}
                }
            }

            mock_client.get = AsyncMock(side_effect=[search_response, image_response])

            result = await service.get_wikipedia_image("Socrates")

            assert result == "https://example.com/socrates.jpg"


class TestShouldPromptUser:
    """Tests for _should_prompt_user method."""

    def test_should_not_prompt_with_few_messages(self) -> None:
        """Test that we don't prompt user when conversation is short."""
        service = ThinkerService()
        messages: Any = [MagicMock() for _ in range(3)]

        result = service._should_prompt_user(messages, 1.0)

        assert result is False

    def test_should_not_prompt_if_user_spoke_recently(self) -> None:
        """Test that we don't prompt if user spoke recently."""
        service = ThinkerService()

        # Create messages with user speaking recently
        user_message = MagicMock()
        user_message.sender_type = "user"
        user_message.content = "I think so"

        thinker_message = MagicMock()
        thinker_message.sender_type = "thinker"
        thinker_message.content = "Interesting"

        messages: Any = [user_message, thinker_message, thinker_message]

        # With only 2 thinker messages since user, threshold not met
        result = service._should_prompt_user(messages, 1.0)
        assert result is False

    def test_should_prompt_probability_after_many_thinker_messages(self) -> None:
        """Test that prompt probability increases after many thinker messages."""
        import random

        service = ThinkerService()

        # Create conversation with user spoke long ago
        user_message = MagicMock()
        user_message.sender_type = "user"
        user_message.content = "What about X?"

        thinker_message = MagicMock()
        thinker_message.sender_type = "thinker"
        thinker_message.content = "I think..."

        # User spoke, then 10 thinker messages
        messages: Any = [user_message] + [thinker_message] * 10

        # Test with multiple seeds - should prompt sometimes
        prompts = []
        for seed in range(100):
            random.seed(seed)
            result = service._should_prompt_user(messages, 1.0)
            prompts.append(result)

        # Should prompt at least once out of 100 tries given threshold is met
        assert any(prompts)


class TestGetUserNameFromMessages:
    """Tests for _get_user_name_from_messages method."""

    def test_get_user_name_from_recent_message(self) -> None:
        """Test extracting user name from message history."""
        service = ThinkerService()

        user_message = MagicMock()
        user_message.sender_type = "user"
        user_message.sender_name = "Alice"

        thinker_message = MagicMock()
        thinker_message.sender_type = "thinker"
        thinker_message.sender_name = "Socrates"

        messages: Any = [user_message, thinker_message, thinker_message]

        result = service._get_user_name_from_messages(messages)

        assert result == "Alice"

    def test_get_user_name_returns_none_if_no_user(self) -> None:
        """Test that method returns None if no user messages found."""
        service = ThinkerService()

        thinker_message = MagicMock()
        thinker_message.sender_type = "thinker"
        thinker_message.sender_name = "Socrates"

        messages: Any = [thinker_message, thinker_message]

        result = service._get_user_name_from_messages(messages)

        assert result is None


class TestCountMessagesSinceUser:
    """Tests for _count_messages_since_user method."""

    def test_count_thinker_messages_since_user(self) -> None:
        """Test counting thinker messages since last user message."""
        service = ThinkerService()

        user_message = MagicMock()
        user_message.sender_type = "user"

        thinker_message = MagicMock()
        thinker_message.sender_type = "thinker"

        messages: Any = [user_message, thinker_message, thinker_message, thinker_message]

        result = service._count_messages_since_user(messages)

        assert result == 3

    def test_count_returns_zero_if_user_spoke_last(self) -> None:
        """Test that count is 0 if user spoke last."""
        service = ThinkerService()

        user_message = MagicMock()
        user_message.sender_type = "user"

        messages: Any = [user_message]

        result = service._count_messages_since_user(messages)

        assert result == 0


class TestGenerateUserPrompt:
    """Tests for generate_user_prompt method."""

    async def test_generate_user_prompt_without_client(self) -> None:
        """Test that generate_user_prompt returns empty without client."""
        service = ThinkerService()

        thinker = MagicMock()
        messages: Any = []

        with patch.object(type(service), "client", new_callable=PropertyMock) as mock_client:
            mock_client.return_value = None
            response, cost = await service.generate_user_prompt(thinker, messages, "test", "Alice")

            assert response == ""
            assert cost == 0.0

    async def test_generate_user_prompt_with_mock_response(self) -> None:
        """Test generate_user_prompt with mocked API response."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_response.content = [
            TextBlock(type="text", text="Alice, I'm curious what you think about this.")
        ]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 15

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        thinker = MagicMock()
        thinker.name = "Socrates"
        thinker.bio = "Ancient philosopher"
        thinker.positions = "Socratic method"
        thinker.style = "Questions everything"

        user_message = MagicMock()
        user_message.sender_type = SenderType.USER
        user_message.sender_name = "Alice"
        user_message.content = "What is truth?"
        messages: Any = [user_message]

        response, cost = await service.generate_user_prompt(
            thinker, messages, "philosophy", "Alice"
        )

        assert "Alice" in response
        assert cost > 0


class TestSuggestThinkersErrorHandling:
    """Tests for error handling in suggest_thinkers."""

    async def test_suggest_handles_json_decode_error(self) -> None:
        """Test that suggest_thinkers handles invalid JSON gracefully."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text="Invalid JSON {]")]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.suggest_thinkers("test", 1)

        # Should return empty list on JSON error
        assert result == []

    async def test_suggest_handles_empty_response(self) -> None:
        """Test that suggest_thinkers handles empty response."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text="")]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.suggest_thinkers("test", 1)

        assert result == []

    async def test_suggest_handles_non_text_block(self) -> None:
        """Test that suggest_thinkers handles non-text response blocks."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_non_text_block = MagicMock()
        mock_non_text_block.__class__.__name__ = "ThinkingBlock"
        mock_response.content = [mock_non_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.suggest_thinkers("test", 1)

        assert result == []

    async def test_suggest_strips_markdown_code_fences(self) -> None:
        """Test that suggest_thinkers strips markdown code fences from response."""
        service = ThinkerService()

        json_data = """[{
            "name": "Socrates",
            "reason": "Master of questioning",
            "profile": {
                "name": "Socrates",
                "bio": "Ancient Greek philosopher",
                "positions": "Socratic method",
                "style": "Questions everything"
            }
        }]"""

        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text=f"```json\n{json_data}\n```")]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.suggest_thinkers("test", 1)

        assert len(result) == 1
        assert result[0].name == "Socrates"

    async def test_suggest_with_exclude_list(self) -> None:
        """Test that suggest_thinkers properly excludes specified thinkers."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_response.content = [
            TextBlock(
                type="text",
                text="""[{
                    "name": "Plato",
                    "reason": "Student of Socrates",
                    "profile": {
                        "name": "Plato",
                        "bio": "Greek philosopher",
                        "positions": "Theory of forms",
                        "style": "Dialogues"
                    }
                }]""",
            )
        ]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.suggest_thinkers("philosophy", 1, exclude=["Socrates", "Aristotle"])

        # Should still return results, just not the excluded ones
        assert len(result) == 1
        assert result[0].name == "Plato"

    async def test_suggest_parallel_batch_with_errors(self) -> None:
        """Test parallel batch suggestions when some batches fail."""

        service = ThinkerService()

        # Mock multiple batch responses - one success, one error, one exception
        mock_response = MagicMock()
        mock_response.content = [
            TextBlock(
                type="text",
                text="""[{
                    "name": "Socrates",
                    "reason": "Master of questioning",
                    "profile": {
                        "name": "Socrates",
                        "bio": "Ancient Greek philosopher",
                        "positions": "Socratic method",
                        "style": "Questions everything"
                    }
                }]""",
            )
        ]

        mock_client = AsyncMock()
        # First batch succeeds, second raises error
        mock_client.messages.create = AsyncMock(
            side_effect=[mock_response, Exception("Network error")]
        )
        service._client = mock_client

        # Request 3 thinkers to trigger parallel batches
        result = await service.suggest_thinkers("philosophy", 3)

        # Should return partial results from successful batch
        assert len(result) > 0

    async def test_suggest_api_quota_error_propagates(self) -> None:
        """Test that API quota errors are properly detected and propagated."""
        from app.exceptions import ThinkerAPIError

        service = ThinkerService()

        mock_request = MagicMock()
        mock_request.url = "https://api.anthropic.com/v1/messages"
        mock_request.method = "POST"

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=APIError("Your credit balance is too low", mock_request, body=None)
        )
        service._client = mock_client

        with pytest.raises(ThinkerAPIError) as exc_info:
            await service.suggest_thinkers("test", 1)

        assert exc_info.value.is_quota_error


class TestValidateThinkerErrorHandling:
    """Tests for error handling in validate_thinker."""

    async def test_validate_handles_non_text_block(self) -> None:
        """Test that validate_thinker handles non-text response blocks."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_non_text_block = MagicMock()
        mock_non_text_block.__class__.__name__ = "ThinkingBlock"
        mock_response.content = [mock_non_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        is_valid, profile = await service.validate_thinker("Test Person")

        assert is_valid is False
        assert profile is None

    async def test_validate_handles_json_decode_error(self) -> None:
        """Test that validate_thinker handles invalid JSON."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text="Invalid JSON {]")]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        is_valid, profile = await service.validate_thinker("Test Person")

        assert is_valid is False
        assert profile is None

    async def test_validate_api_quota_error(self) -> None:
        """Test that validate_thinker properly handles quota errors."""
        from app.exceptions import ThinkerAPIError

        service = ThinkerService()

        mock_request = MagicMock()
        mock_request.url = "https://api.anthropic.com/v1/messages"
        mock_request.method = "POST"

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=APIError("credit balance is too low", mock_request, body=None)
        )
        service._client = mock_client

        with pytest.raises(ThinkerAPIError) as exc_info:
            await service.validate_thinker("Test Person")

        assert exc_info.value.is_quota_error


class TestWikipediaImage:
    """Tests for Wikipedia image fetching."""

    async def test_get_image_with_no_thumbnail(self) -> None:
        """Test get_wikipedia_image when page has no thumbnail."""
        service = ThinkerService()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            # Mock search response
            search_response = MagicMock()
            search_response.json.return_value = {"query": {"search": [{"title": "Test Person"}]}}

            # Mock image response WITHOUT thumbnail
            image_response = MagicMock()
            image_response.json.return_value = {
                "query": {"pages": {"123": {"title": "Test Person"}}}
            }

            mock_client.get = AsyncMock(side_effect=[search_response, image_response])

            result = await service.get_wikipedia_image("Test Person")

            assert result is None

    async def test_get_image_with_timeout(self) -> None:
        """Test get_wikipedia_image handles timeout gracefully."""

        service = ThinkerService()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_client.get = AsyncMock(side_effect=TimeoutError())

            result = await service.get_wikipedia_image("Test Person")

            # Should return None on timeout
            assert result is None


class TestGenerateResponseErrorHandling:
    """Tests for error handling in generate_response."""

    async def test_generate_response_api_error(self) -> None:
        """Test that generate_response properly handles API errors."""
        from app.exceptions import ThinkerAPIError

        service = ThinkerService()

        mock_request = MagicMock()
        mock_request.url = "https://api.anthropic.com/v1/messages"
        mock_request.method = "POST"

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=APIError("Rate limit exceeded", mock_request, body=None)
        )
        service._client = mock_client

        thinker = MagicMock()
        thinker.name = "Socrates"
        thinker.bio = "Ancient philosopher"
        thinker.positions = "Socratic method"
        thinker.style = "Questions everything"
        messages: Any = []

        with pytest.raises(ThinkerAPIError):
            await service.generate_response(thinker, messages, "test")

    async def test_generate_response_handles_non_text_block(self) -> None:
        """Test that generate_response handles non-text response blocks."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_non_text_block = MagicMock()
        mock_non_text_block.__class__.__name__ = "ThinkingBlock"
        mock_response.content = [mock_non_text_block]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 10

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        thinker = MagicMock()
        thinker.name = "Socrates"
        thinker.bio = "Ancient philosopher"
        thinker.positions = "Socratic method"
        thinker.style = "Questions everything"
        messages: Any = []

        response, cost = await service.generate_response(thinker, messages, "test")

        assert response == ""
        assert cost == 0.0


class TestGenerateUserPromptErrorHandling:
    """Tests for error handling in generate_user_prompt."""

    async def test_generate_user_prompt_handles_exception(self) -> None:
        """Test that generate_user_prompt handles exceptions gracefully."""
        service = ThinkerService()

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("Network error"))
        service._client = mock_client

        thinker = MagicMock()
        thinker.name = "Socrates"
        thinker.bio = "Ancient philosopher"
        thinker.positions = "Socratic method"
        thinker.style = "Questions everything"
        messages: Any = []

        response, cost = await service.generate_user_prompt(thinker, messages, "test", "Alice")

        # Should return empty on error
        assert response == ""
        assert cost == 0.0

    async def test_generate_user_prompt_handles_non_text_block(self) -> None:
        """Test that generate_user_prompt handles non-text response blocks."""
        service = ThinkerService()

        mock_response = MagicMock()
        mock_non_text_block = MagicMock()
        mock_non_text_block.__class__.__name__ = "ThinkingBlock"
        mock_response.content = [mock_non_text_block]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 10

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        thinker = MagicMock()
        thinker.name = "Socrates"
        thinker.bio = "Ancient philosopher"
        thinker.positions = "Socratic method"
        thinker.style = "Questions everything"
        messages: Any = []

        response, cost = await service.generate_user_prompt(thinker, messages, "test", "Alice")

        assert response == ""
        assert cost == 0.0
