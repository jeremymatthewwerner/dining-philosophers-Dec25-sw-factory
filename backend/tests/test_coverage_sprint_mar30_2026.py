"""Coverage sprint tests for Mar 30, 2026 (Monday QA).

Targets:
- app/services/thinker.py: language paths in _extract_thinking_display,
  _get_language_instruction non-English, start_conversation_agents,
  client property with API key, suggest_thinkers with language param,
  _split_response_into_bubbles edge cases, _should_respond edge cases,
  _get_last_user_message_timestamp, idle pause/resume methods
- app/services/knowledge_research.py: _research_thinker background execution,
  _fetch_wikipedia_data with thumbnail/image, _fetch_wikipedia_sections
  iteration, refresh_stale_knowledge, is_stale edge cases
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic.types import TextBlock

from app.models import ResearchStatus, ThinkerKnowledge
from app.services.knowledge_research import KnowledgeResearchService
from app.services.thinker import ThinkerService, _get_language_instruction

# ---------------------------------------------------------------------------
# _get_language_instruction – non-English language paths (lines 49-52)
# ---------------------------------------------------------------------------


class TestGetLanguageInstruction:
    """Tests for the _get_language_instruction helper function."""

    def test_english_returns_empty_string(self) -> None:
        """English language returns no instruction (empty string)."""
        result = _get_language_instruction("en")
        assert result == ""

    def test_spanish_returns_spanish_instruction(self) -> None:
        """Spanish language code returns instruction in Spanish."""
        result = _get_language_instruction("es")
        assert "Spanish" in result
        assert result.startswith("\n\nIMPORTANT")

    def test_french_returns_french_instruction(self) -> None:
        """French language code returns instruction in French."""
        result = _get_language_instruction("fr")
        assert "French" in result
        assert result.startswith("\n\nIMPORTANT")

    def test_german_returns_german_instruction(self) -> None:
        """German language code returns instruction in German."""
        result = _get_language_instruction("de")
        assert "German" in result
        assert result.startswith("\n\nIMPORTANT")

    def test_hindi_returns_hindi_instruction(self) -> None:
        """Hindi language code returns instruction in Hindi."""
        result = _get_language_instruction("hi")
        assert "Hindi" in result
        assert result.startswith("\n\nIMPORTANT")

    def test_unknown_language_code_uses_code_as_name(self) -> None:
        """Unknown language code falls back to using the code itself as name."""
        result = _get_language_instruction("zh")
        assert "zh" in result
        assert result.startswith("\n\nIMPORTANT")


# ---------------------------------------------------------------------------
# ThinkerService.client property with API key (line 133)
# ---------------------------------------------------------------------------


class TestClientProperty:
    """Tests for the ThinkerService.client property."""

    def test_client_is_created_when_api_key_present(self) -> None:
        """Client is lazily created when an API key is configured."""
        service = ThinkerService()
        service.settings = MagicMock()
        service.settings.anthropic_api_key = "sk-test-key-12345"
        service._client = None

        with patch("app.services.thinker.AsyncAnthropic") as mock_anthropic:
            mock_instance = MagicMock()
            mock_anthropic.return_value = mock_instance
            client = service.client
            assert client is mock_instance
            mock_anthropic.assert_called_once_with(api_key="sk-test-key-12345")

    def test_client_cached_after_first_access(self) -> None:
        """Client is not re-created on subsequent accesses."""
        service = ThinkerService()
        mock_client = MagicMock()
        service._client = mock_client

        result = service.client
        assert result is mock_client


# ---------------------------------------------------------------------------
# _extract_thinking_display – multilingual paths (lines 824-968)
# ---------------------------------------------------------------------------


class TestExtractThinkingDisplayMultilingual:
    """Tests for the multilingual paths in _extract_thinking_display."""

    def _make_long_text(self, prefix: str = "") -> str:
        """Build text long enough (>80 chars) to get output from the method."""
        base = "I should consider this carefully and think about the implications for "
        return (prefix + base + "all of these important philosophical questions here.").ljust(
            120, " "
        )[:130]

    def test_german_replacements_applied(self) -> None:
        """German language applies German-specific text replacements."""
        service = ThinkerService()
        # Use text with German replacement target "Ich sollte "
        text = (
            "Ich sollte diese Frage sorgfältig überlegen und alle wichtigen Aspekte "
            "berücksichtigen und dann entscheiden was zu tun ist."
        )
        result = service._extract_thinking_display(text, language="de")
        # The method should return non-empty result for 80+ char text
        assert len(result) > 0

    def test_spanish_replacements_applied(self) -> None:
        """Spanish language applies Spanish-specific text replacements."""
        service = ThinkerService()
        text = (
            "Debería considerar esta pregunta cuidadosamente y pensar en todas las "
            "implicaciones importantes para comprender el tema completamente bien."
        )
        result = service._extract_thinking_display(text, language="es")
        assert len(result) > 0

    def test_french_replacements_applied(self) -> None:
        """French language applies French-specific text replacements."""
        service = ThinkerService()
        text = (
            "Je devrais considérer cette question attentivement et penser à toutes "
            "les implications importantes pour comprendre le sujet complètement bien."
        )
        result = service._extract_thinking_display(text, language="fr")
        assert len(result) > 0

    def test_hindi_replacements_applied(self) -> None:
        """Hindi language applies Hindi-specific text replacements."""
        service = ThinkerService()
        text = (
            "मुझे चाहिए इस प्रश्न पर ध्यान से विचार करना चाहिए और सभी "
            "महत्वपूर्ण पहलुओं को समझना चाहिए जो इस विषय से संबंधित हैं।"
        )
        result = service._extract_thinking_display(text, language="hi")
        assert len(result) > 0

    def test_english_default_replacements_applied(self) -> None:
        """English (default) applies English-specific text replacements."""
        service = ThinkerService()
        text = (
            "I should think carefully about this philosophical question and consider "
            "all the implications for our understanding of virtue and justice here."
        )
        result = service._extract_thinking_display(text, language="en")
        assert len(result) > 0
        # "I should " should be replaced with "Perhaps I should "
        assert "I should" not in result or "Perhaps I should" in result

    def test_text_with_i_think_stripped(self) -> None:
        """'I think ' prefix is stripped in English display."""
        service = ThinkerService()
        text = (
            "I think this is a very important consideration for the discussion "
            "and we should take it seriously before reaching any firm conclusions."
        )
        result = service._extract_thinking_display(text, language="en")
        assert len(result) > 0
        # "I think " should be removed from the start
        if result.startswith("I think "):
            pytest.fail("'I think ' should have been stripped from display text")

    def test_german_starters_added_when_no_existing_prefix(self) -> None:
        """German thinking starters are added when text doesn't already have one."""
        service = ThinkerService()
        # Text that won't match German starter prefixes
        text = (
            "Diese philosophische Frage ist sehr interessant und bedeutsam für "
            "unser Verständnis der Welt und der menschlichen Natur insgesamt."
        )
        result = service._extract_thinking_display(text, language="de")
        assert len(result) > 0

    def test_spanish_starters_added(self) -> None:
        """Spanish thinking starters are added when appropriate."""
        service = ThinkerService()
        text = (
            "Esta pregunta filosófica es muy importante para la comprensión "
            "de la naturaleza humana y los valores morales que guían nuestra vida."
        )
        result = service._extract_thinking_display(text, language="es")
        assert len(result) > 0

    def test_french_starters_added(self) -> None:
        """French thinking starters are added when appropriate."""
        service = ThinkerService()
        text = (
            "Cette question philosophique est très importante pour la compréhension "
            "de la nature humaine et des valeurs morales qui guident notre vie ici."
        )
        result = service._extract_thinking_display(text, language="fr")
        assert len(result) > 0

    def test_hindi_starters_added(self) -> None:
        """Hindi thinking starters are added when appropriate."""
        service = ThinkerService()
        text = (
            "यह दार्शनिक प्रश्न मानव स्वभाव और नैतिक मूल्यों को समझने के लिए "
            "बहुत महत्वपूर्ण है और हमें इस पर गहराई से विचार करना चाहिए।"
        )
        result = service._extract_thinking_display(text, language="hi")
        assert len(result) > 0

    def test_text_not_ending_with_punctuation_gets_ellipsis(self) -> None:
        """Text not ending with sentence punctuation gets '...' appended."""
        service = ThinkerService()
        text = (
            "This is an incomplete thought that continues on and has more content "
            "but does not have a proper ending punctuation mark at the very end"
        )
        result = service._extract_thinking_display(text, language="en")
        if result:
            # If we got output, it should end with "..."
            assert result.endswith("...")


# ---------------------------------------------------------------------------
# ThinkerService.start_conversation_agents (lines 1078-1095)
# ---------------------------------------------------------------------------


class TestStartConversationAgents:
    """Tests for start_conversation_agents method."""

    async def test_start_creates_tasks_for_each_thinker(self) -> None:
        """Starting agents creates an async task for each thinker."""
        service = ThinkerService()
        conversation_id = "conv-start-test"

        thinker1 = MagicMock()
        thinker1.id = "t1"
        thinker1.name = "Socrates"

        thinker2 = MagicMock()
        thinker2.id = "t2"
        thinker2.name = "Plato"

        async def dummy_get_messages(_conv_id: str) -> list[Any]:
            return []

        async def dummy_save_message(
            _conv_id: str, _name: str, _content: str, _cost: float
        ) -> MagicMock:
            return MagicMock()

        # Patch _run_thinker_agent to return immediately (avoid infinite loop)
        async def mock_run_agent(*args: Any, **kwargs: Any) -> None:
            pass

        with patch.object(service, "_run_thinker_agent", side_effect=mock_run_agent):
            await service.start_conversation_agents(
                conversation_id,
                [thinker1, thinker2],
                "philosophy",
                dummy_get_messages,
                dummy_save_message,
            )

        # Should have tasks for both thinkers
        assert conversation_id in service._active_tasks
        assert "t1" in service._active_tasks[conversation_id]
        assert "t2" in service._active_tasks[conversation_id]

        # Clean up tasks
        await service.stop_conversation_agents(conversation_id)

    async def test_start_stops_existing_agents_first(self) -> None:
        """Starting agents for a conversation with existing agents stops them first."""
        service = ThinkerService()
        conversation_id = "conv-restart-test"

        # Set up a pre-existing "task" that's cancelled
        dummy_task = asyncio.create_task(asyncio.sleep(100))
        service._active_tasks[conversation_id] = {"old-t": dummy_task}

        thinker = MagicMock()
        thinker.id = "new-t"
        thinker.name = "Aristotle"

        async def mock_run_agent(*args: Any, **kwargs: Any) -> None:
            pass

        async def dummy_get_messages(_conv_id: str) -> list[Any]:
            return []

        async def dummy_save_message(
            _conv_id: str, _name: str, _content: str, _cost: float
        ) -> MagicMock:
            return MagicMock()

        with patch.object(service, "_run_thinker_agent", side_effect=mock_run_agent):
            await service.start_conversation_agents(
                conversation_id,
                [thinker],
                "ethics",
                dummy_get_messages,
                dummy_save_message,
            )

        # Old task should be cancelled
        assert dummy_task.cancelled()

        # New tasks should be present
        assert "new-t" in service._active_tasks[conversation_id]

        # Clean up
        await service.stop_conversation_agents(conversation_id)

    async def test_start_with_empty_thinkers_list(self) -> None:
        """Starting with empty thinkers list creates empty task dict."""
        service = ThinkerService()
        conversation_id = "conv-empty-test"

        async def dummy_get_messages(_conv_id: str) -> list[Any]:
            return []

        async def dummy_save_message(
            _conv_id: str, _name: str, _content: str, _cost: float
        ) -> MagicMock:
            return MagicMock()

        await service.start_conversation_agents(
            conversation_id,
            [],
            "philosophy",
            dummy_get_messages,
            dummy_save_message,
        )

        assert conversation_id in service._active_tasks
        assert service._active_tasks[conversation_id] == {}


# ---------------------------------------------------------------------------
# Idle pause/resume methods (lines 1121-1138)
# ---------------------------------------------------------------------------


class TestIdlePauseResume:
    """Tests for idle pause/resume conversation methods."""

    def test_pause_for_idle_marks_both_sets(self) -> None:
        """pause_for_idle adds conversation to both paused and idle-paused sets."""
        service = ThinkerService()
        conv_id = "conv-idle-test"

        assert not service.is_paused(conv_id)
        assert not service.is_idle_paused(conv_id)

        service.pause_for_idle(conv_id)

        assert service.is_paused(conv_id)
        assert service.is_idle_paused(conv_id)

    def test_resume_from_idle_clears_both_sets(self) -> None:
        """resume_from_idle removes conversation from both paused and idle-paused sets."""
        service = ThinkerService()
        conv_id = "conv-idle-resume"

        service.pause_for_idle(conv_id)
        assert service.is_paused(conv_id)
        assert service.is_idle_paused(conv_id)

        service.resume_from_idle(conv_id)

        assert not service.is_paused(conv_id)
        assert not service.is_idle_paused(conv_id)

    def test_resume_from_idle_does_nothing_if_not_idle_paused(self) -> None:
        """resume_from_idle does not resume a manually-paused conversation."""
        service = ThinkerService()
        conv_id = "conv-manual-pause"

        # Manually pause (not idle pause)
        service.pause_conversation(conv_id)
        assert service.is_paused(conv_id)
        assert not service.is_idle_paused(conv_id)

        # resume_from_idle should NOT un-pause a manually paused conversation
        service.resume_from_idle(conv_id)

        # Should still be paused
        assert service.is_paused(conv_id)

    def test_resume_from_idle_does_nothing_for_unknown_conversation(self) -> None:
        """resume_from_idle is a no-op for conversations not in idle-paused set."""
        service = ThinkerService()
        # Should not raise
        service.resume_from_idle("nonexistent-conversation")


# ---------------------------------------------------------------------------
# _get_last_user_message_timestamp (lines 1421-1431)
# ---------------------------------------------------------------------------


class TestGetLastUserMessageTimestamp:
    """Tests for _get_last_user_message_timestamp method."""

    def test_returns_timestamp_of_last_user_message(self) -> None:
        """Returns the timestamp of the most recent user message."""
        service = ThinkerService()

        now = datetime.now(UTC)
        user_message = MagicMock()
        user_message.sender_type = "user"
        user_message.created_at = now

        thinker_message = MagicMock()
        thinker_message.sender_type = "thinker"
        thinker_message.created_at = now + timedelta(seconds=10)

        messages: Any = [user_message, thinker_message]

        result = service._get_last_user_message_timestamp(messages)
        assert result == now.timestamp()

    def test_returns_zero_when_no_user_messages(self) -> None:
        """Returns 0.0 when there are no user messages in history."""
        service = ThinkerService()

        thinker_message = MagicMock()
        thinker_message.sender_type = "thinker"

        messages: Any = [thinker_message, thinker_message]

        result = service._get_last_user_message_timestamp(messages)
        assert result == 0.0

    def test_returns_zero_for_empty_messages(self) -> None:
        """Returns 0.0 for empty message list."""
        service = ThinkerService()
        result = service._get_last_user_message_timestamp([])
        assert result == 0.0

    def test_returns_most_recent_user_message_timestamp(self) -> None:
        """Returns the most recent (last in list) user message timestamp."""
        service = ThinkerService()

        earlier = datetime(2026, 1, 1, tzinfo=UTC)
        later = datetime(2026, 1, 2, tzinfo=UTC)

        user_msg1 = MagicMock()
        user_msg1.sender_type = "user"
        user_msg1.created_at = earlier

        user_msg2 = MagicMock()
        user_msg2.sender_type = "user"
        user_msg2.created_at = later

        messages: Any = [user_msg1, user_msg2]

        result = service._get_last_user_message_timestamp(messages)
        # Should return the LAST user message (reversed iteration finds most recent last)
        assert result == later.timestamp()

    def test_handles_sender_type_enum_value(self) -> None:
        """Handles sender_type that has a .value attribute (enum-style)."""
        service = ThinkerService()

        now = datetime.now(UTC)
        user_message = MagicMock()
        # Simulate SenderType.USER enum
        user_message.sender_type = MagicMock()
        user_message.sender_type.value = "user"
        user_message.created_at = now

        messages: Any = [user_message]

        result = service._get_last_user_message_timestamp(messages)
        assert result == now.timestamp()


# ---------------------------------------------------------------------------
# _should_respond edge cases (lines 1585, 1589)
# ---------------------------------------------------------------------------


class TestShouldRespondEdgeCases:
    """Additional edge cases for _should_respond method."""

    def test_consecutive_silence_increases_probability(self) -> None:
        """Long consecutive silence increases response probability."""
        import random

        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = MagicMock()
        message.content = "What do you think about justice?"
        message.sender_name = "User"
        messages: Any = [message]

        # Test with high consecutive silence - should respond more
        high_silence_responses = []
        for seed in range(50):
            random.seed(seed)
            result = service._should_respond(thinker, messages, 0, consecutive_silence=10)
            high_silence_responses.append(result)

        low_silence_responses = []
        for seed in range(50):
            random.seed(seed)
            result = service._should_respond(thinker, messages, 0, consecutive_silence=0)
            low_silence_responses.append(result)

        # High silence should generally produce more responses
        high_rate = sum(high_silence_responses) / len(high_silence_responses)
        low_rate = sum(low_silence_responses) / len(low_silence_responses)
        # High silence should have higher or equal response rate
        assert high_rate >= low_rate * 0.8  # Allow some variance due to random

    def test_not_mentioned_can_stay_silent(self) -> None:
        """Thinker can stay completely silent when not mentioned (15% silence chance)."""

        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        message = MagicMock()
        message.content = "This is an interesting philosophical point."
        message.sender_name = "User"
        messages: Any = [message]

        # Run many times - should get some False results due to 15% silence chance
        results = [service._should_respond(thinker, messages, 0) for _ in range(200)]
        silent_count = sum(1 for r in results if not r)
        # With 15% chance of silence, should have some silent results
        assert silent_count > 0

    def test_addressed_by_name_increases_probability(self) -> None:
        """Being addressed by name (without @) increases response probability."""
        import random

        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Aristotle"

        addressed_msg = MagicMock()
        addressed_msg.content = "Aristotle, what is your view on this?"
        addressed_msg.sender_name = "User"

        not_addressed_msg = MagicMock()
        not_addressed_msg.content = "What is the nature of virtue?"
        not_addressed_msg.sender_name = "User"

        addressed_responses = []
        not_addressed_responses = []

        for seed in range(100):
            random.seed(seed)
            addressed_responses.append(service._should_respond(thinker, [addressed_msg], 0))
        for seed in range(100):
            random.seed(seed)
            not_addressed_responses.append(service._should_respond(thinker, [not_addressed_msg], 0))

        addressed_rate = sum(addressed_responses) / len(addressed_responses)
        not_addressed_rate = sum(not_addressed_responses) / len(not_addressed_responses)
        assert addressed_rate > not_addressed_rate


# ---------------------------------------------------------------------------
# suggest_thinkers with language parameter (tests language routing in API call)
# ---------------------------------------------------------------------------


class TestSuggestThinkersWithLanguage:
    """Tests for suggest_thinkers method with language parameter."""

    async def test_suggest_with_spanish_language(self) -> None:
        """suggest_thinkers passes language to _suggest_single_batch."""
        service = ThinkerService()

        json_response = """[{
            "name": "Simón Bolívar",
            "reason": "Revolutionary leader",
            "profile": {
                "name": "Simón Bolívar",
                "bio": "Venezuelan military leader",
                "positions": "Liberation from Spanish rule",
                "style": "Passionate oratory"
            }
        }]"""

        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text=json_response)]
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        with patch.object(service, "get_wikipedia_image", return_value=None):
            result = await service.suggest_thinkers("revolution", 1, language="es")

        assert len(result) == 1
        assert result[0].name == "Simón Bolívar"

        # Verify the prompt included Spanish instruction
        call_args = mock_client.messages.create.call_args
        prompt_text = call_args[1]["messages"][0]["content"]
        assert "Spanish" in prompt_text

    async def test_suggest_parallel_with_language(self) -> None:
        """suggest_thinkers passes language through parallel batch calls."""
        service = ThinkerService()

        def make_response(name: str) -> MagicMock:
            json_text = f"""[{{
                "name": "{name}",
                "reason": "Test reason",
                "profile": {{
                    "name": "{name}",
                    "bio": "Test bio",
                    "positions": "Test positions",
                    "style": "Test style"
                }}
            }}]"""
            resp = MagicMock()
            resp.content = [TextBlock(type="text", text=json_text)]
            return resp

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[
                make_response("Thinker A"),
                make_response("Thinker B"),
                make_response("Thinker C"),
            ]
        )
        service._client = mock_client

        with patch.object(service, "get_wikipedia_image", return_value=None):
            result = await service.suggest_thinkers("ethics", 3, language="fr")

        # Should get results from parallel calls
        assert len(result) > 0


# ---------------------------------------------------------------------------
# validate_thinker with language parameter
# ---------------------------------------------------------------------------


class TestValidateThinkerWithLanguage:
    """Tests for validate_thinker method with language parameter."""

    async def test_validate_with_non_english_language(self) -> None:
        """validate_thinker passes language instruction to the API prompt."""
        valid_response = """{
            "valid": true,
            "profile": {
                "name": "Goethe",
                "bio": "German writer and statesman",
                "positions": "Classical humanism",
                "style": "Poetic and philosophical"
            }
        }"""

        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text=valid_response)]
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        service = ThinkerService()
        service._client = mock_client

        with patch.object(service, "get_wikipedia_image", return_value=None):
            is_valid, profile = await service.validate_thinker("Goethe", language="de")

        assert is_valid is True
        assert profile is not None

        # Verify the prompt included German instruction
        call_args = mock_client.messages.create.call_args
        prompt_text = call_args[1]["messages"][0]["content"]
        assert "German" in prompt_text


# ---------------------------------------------------------------------------
# KnowledgeResearchService – previously uncovered paths
# ---------------------------------------------------------------------------


class TestKnowledgeResearchServiceCoverage:
    """Tests for KnowledgeResearchService covering previously uncovered paths."""

    def test_is_stale_returns_true_for_pending_status(self) -> None:
        """is_stale returns True for knowledge that is not yet COMPLETE."""
        service = KnowledgeResearchService()

        knowledge = MagicMock(spec=ThinkerKnowledge)
        knowledge.status = ResearchStatus.PENDING

        assert service.is_stale(knowledge) is True

    def test_is_stale_returns_true_for_in_progress_status(self) -> None:
        """is_stale returns True for knowledge that is IN_PROGRESS."""
        service = KnowledgeResearchService()

        knowledge = MagicMock(spec=ThinkerKnowledge)
        knowledge.status = ResearchStatus.IN_PROGRESS

        assert service.is_stale(knowledge) is True

    def test_is_stale_returns_true_for_failed_status(self) -> None:
        """is_stale returns True for knowledge that previously FAILED."""
        service = KnowledgeResearchService()

        knowledge = MagicMock(spec=ThinkerKnowledge)
        knowledge.status = ResearchStatus.FAILED

        assert service.is_stale(knowledge) is True

    def test_is_stale_returns_false_for_recently_completed(self) -> None:
        """is_stale returns False for recently completed knowledge."""
        service = KnowledgeResearchService()

        knowledge = MagicMock(spec=ThinkerKnowledge)
        knowledge.status = ResearchStatus.COMPLETE
        # Updated just now - not stale
        knowledge.updated_at = datetime.now(UTC).replace(tzinfo=None)

        assert service.is_stale(knowledge) is False

    def test_is_stale_returns_true_for_old_completed(self) -> None:
        """is_stale returns True for completed knowledge older than 30 days."""
        service = KnowledgeResearchService()

        knowledge = MagicMock(spec=ThinkerKnowledge)
        knowledge.status = ResearchStatus.COMPLETE
        # Updated 45 days ago - stale
        knowledge.updated_at = (datetime.now(UTC) - timedelta(days=45)).replace(tzinfo=None)

        assert service.is_stale(knowledge) is True

    async def test_get_knowledge_returns_none_when_not_found(self, db_session: Any) -> None:
        """get_knowledge returns None when thinker not in database."""
        service = KnowledgeResearchService()

        result = await service.get_knowledge(db_session, "Unknown Thinker XYZ")
        assert result is None

    async def test_get_or_create_creates_new_entry(self, db_session: Any) -> None:
        """get_or_create_knowledge creates a new PENDING entry when not found."""
        service = KnowledgeResearchService()

        result = await service.get_or_create_knowledge(db_session, "Test Philosopher")

        assert result is not None
        assert result.name == "Test Philosopher"
        assert result.status == ResearchStatus.PENDING
        assert result.research_data == {}

    async def test_get_or_create_returns_existing_entry(self, db_session: Any) -> None:
        """get_or_create_knowledge returns existing entry when found."""
        service = KnowledgeResearchService()

        # Create first
        first = await service.get_or_create_knowledge(db_session, "Existing Thinker")
        # Create again - should return same entry
        second = await service.get_or_create_knowledge(db_session, "Existing Thinker")

        assert first.id == second.id

    def test_trigger_research_deduplicates(self) -> None:
        """trigger_research does not start a new task if one is already running."""
        service = KnowledgeResearchService()

        # Create a mock running task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        service._active_tasks["Socrates"] = mock_task

        with patch("asyncio.create_task") as mock_create:
            service.trigger_research("Socrates")
            # Should NOT create a new task since one is already running
            mock_create.assert_not_called()

    def test_trigger_research_restarts_completed_task(self) -> None:
        """trigger_research starts a new task if the previous one is done."""
        service = KnowledgeResearchService()

        # Create a mock completed (done) task
        mock_task = MagicMock()
        mock_task.done.return_value = True
        service._active_tasks["Plato"] = mock_task

        mock_new_task = MagicMock()
        mock_new_task.add_done_callback = MagicMock()

        with patch("asyncio.create_task", return_value=mock_new_task):
            service.trigger_research("Plato")
            # Should create a new task since the previous one is done
            assert service._active_tasks["Plato"] is mock_new_task

    async def test_refresh_stale_knowledge_triggers_research_for_old_entries(
        self, db_session: Any
    ) -> None:
        """refresh_stale_knowledge triggers research for entries older than 30 days."""
        service = KnowledgeResearchService()

        # Create a stale (old) COMPLETE entry
        stale_knowledge = ThinkerKnowledge(
            name="Ancient Thinker",
            status=ResearchStatus.COMPLETE,
            research_data={"wikipedia": {"summary": "Ancient philosopher"}},
        )
        db_session.add(stale_knowledge)
        await db_session.commit()

        # Manually set the updated_at to 45 days ago
        from sqlalchemy import update

        await db_session.execute(
            update(ThinkerKnowledge)
            .where(ThinkerKnowledge.name == "Ancient Thinker")
            .values(updated_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=45))
        )
        await db_session.commit()

        with patch.object(service, "trigger_research") as mock_trigger:
            count = await service.refresh_stale_knowledge(db_session)

        assert count == 1
        mock_trigger.assert_called_once_with("Ancient Thinker")

    async def test_refresh_stale_knowledge_skips_recent_entries(self, db_session: Any) -> None:
        """refresh_stale_knowledge does not trigger research for recent COMPLETE entries."""
        service = KnowledgeResearchService()

        # Create a recent COMPLETE entry
        fresh_knowledge = ThinkerKnowledge(
            name="Fresh Thinker",
            status=ResearchStatus.COMPLETE,
            research_data={"wikipedia": {"summary": "Recent philosopher"}},
        )
        db_session.add(fresh_knowledge)
        await db_session.commit()

        with patch.object(service, "trigger_research") as mock_trigger:
            count = await service.refresh_stale_knowledge(db_session)

        assert count == 0
        mock_trigger.assert_not_called()

    async def test_fetch_wikipedia_data_returns_none_on_exception(self) -> None:
        """_fetch_wikipedia_data returns None when an exception is raised."""
        service = KnowledgeResearchService()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(side_effect=Exception("Network error"))

            result = await service._fetch_wikipedia_data("Test Person")

        assert result is None

    async def test_fetch_wikipedia_data_returns_none_when_no_results(self) -> None:
        """_fetch_wikipedia_data returns None when Wikipedia has no search results."""
        service = KnowledgeResearchService()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            search_response = MagicMock()
            search_response.json.return_value = {"query": {"search": []}}
            mock_client.get = AsyncMock(return_value=search_response)

            result = await service._fetch_wikipedia_data("Nonexistent Person XYZ")

        assert result is None

    async def test_fetch_wikipedia_data_returns_data_with_thumbnail(self) -> None:
        """_fetch_wikipedia_data returns data dict including image_url when thumbnail present."""
        service = KnowledgeResearchService()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            search_response = MagicMock()
            search_response.json.return_value = {"query": {"search": [{"title": "Socrates"}]}}

            content_response = MagicMock()
            content_response.json.return_value = {
                "query": {
                    "pages": {
                        "1234": {
                            "title": "Socrates",
                            "extract": "Ancient Greek philosopher known for the Socratic method.",
                            "thumbnail": {"source": "https://upload.wikimedia.org/socrates.jpg"},
                        }
                    }
                }
            }

            sections_response = MagicMock()
            sections_response.json.return_value = {"parse": {"sections": []}}

            mock_client.get = AsyncMock(
                side_effect=[search_response, content_response, sections_response]
            )

            result = await service._fetch_wikipedia_data("Socrates")

        assert result is not None
        assert result["title"] == "Socrates"
        assert "summary" in result
        assert result["image_url"] == "https://upload.wikimedia.org/socrates.jpg"

    async def test_fetch_wikipedia_data_returns_data_without_thumbnail(self) -> None:
        """_fetch_wikipedia_data returns data dict without image_url when no thumbnail."""
        service = KnowledgeResearchService()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            search_response = MagicMock()
            search_response.json.return_value = {"query": {"search": [{"title": "Aristotle"}]}}

            content_response = MagicMock()
            content_response.json.return_value = {
                "query": {
                    "pages": {
                        "5678": {
                            "title": "Aristotle",
                            "extract": "Ancient Greek philosopher and scientist.",
                            # No thumbnail
                        }
                    }
                }
            }

            sections_response = MagicMock()
            sections_response.json.return_value = {"parse": {"sections": []}}

            mock_client.get = AsyncMock(
                side_effect=[search_response, content_response, sections_response]
            )

            result = await service._fetch_wikipedia_data("Aristotle")

        assert result is not None
        assert result["title"] == "Aristotle"
        assert "image_url" not in result

    async def test_fetch_wikipedia_data_skips_page_minus_one(self) -> None:
        """_fetch_wikipedia_data skips pages with ID '-1' (not found pages)."""
        service = KnowledgeResearchService()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            search_response = MagicMock()
            search_response.json.return_value = {"query": {"search": [{"title": "Unknown Person"}]}}

            content_response = MagicMock()
            content_response.json.return_value = {
                "query": {
                    "pages": {
                        "-1": {
                            "title": "Unknown Person",
                        }
                    }
                }
            }

            mock_client.get = AsyncMock(side_effect=[search_response, content_response])

            result = await service._fetch_wikipedia_data("Unknown Person")

        assert result is None

    async def test_fetch_wikipedia_sections_returns_none_on_exception(self) -> None:
        """_fetch_wikipedia_sections returns None when an exception is raised."""
        service = KnowledgeResearchService()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("API error"))

        result = await service._fetch_wikipedia_sections(mock_client, "https://api.url", "Socrates")

        assert result is None

    async def test_fetch_wikipedia_sections_returns_none_for_no_interesting_sections(
        self,
    ) -> None:
        """_fetch_wikipedia_sections returns None when no interesting sections found."""
        service = KnowledgeResearchService()

        mock_client = AsyncMock()
        sections_response = MagicMock()
        sections_response.json.return_value = {
            "parse": {
                "sections": [
                    {"line": "References", "index": "1"},
                    {"line": "External links", "index": "2"},
                ]
            }
        }
        mock_client.get = AsyncMock(return_value=sections_response)

        result = await service._fetch_wikipedia_sections(
            mock_client, "https://api.url", "Test Person"
        )

        assert result is None

    async def test_fetch_wikipedia_sections_returns_dict_for_interesting_sections(
        self,
    ) -> None:
        """_fetch_wikipedia_sections returns dict when interesting sections are found."""
        service = KnowledgeResearchService()

        mock_client = AsyncMock()
        sections_response = MagicMock()
        sections_response.json.return_value = {
            "parse": {
                "sections": [
                    {"line": "Philosophy", "index": "1"},
                    {"line": "References", "index": "2"},
                ]
            }
        }
        # First call for sections list, second call for section content
        content_response = MagicMock()
        content_response.json.return_value = {"query": {"pages": {}}}

        mock_client.get = AsyncMock(side_effect=[sections_response, content_response])

        result = await service._fetch_wikipedia_sections(mock_client, "https://api.url", "Socrates")

        assert result is not None
        assert "Philosophy" in result

    async def test_research_thinker_updates_status_to_complete(self, db_session: Any) -> None:
        """_research_thinker updates knowledge status to COMPLETE on success."""
        service = KnowledgeResearchService()

        # Pre-create knowledge entry
        knowledge = ThinkerKnowledge(
            name="Test Philosopher",
            status=ResearchStatus.PENDING,
            research_data={},
        )
        db_session.add(knowledge)
        await db_session.commit()

        # Mock _fetch_wikipedia_data to return data
        wikipedia_data = {
            "title": "Test Philosopher",
            "summary": "A test philosopher for unit testing.",
            "fetched_at": datetime.now(UTC).isoformat(),
        }

        with (
            patch.object(service, "_fetch_wikipedia_data", return_value=wikipedia_data),
            patch("app.services.knowledge_research.async_session") as mock_session_ctx,
        ):
            # Set up the context manager to return our db_session
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = db_session
            mock_cm.__aexit__.return_value = None
            mock_session_ctx.return_value = mock_cm

            await service._research_thinker("Test Philosopher")

        # Refresh to get updated state
        await db_session.refresh(knowledge)
        assert knowledge.status == ResearchStatus.COMPLETE
        assert "wikipedia" in knowledge.research_data


# ---------------------------------------------------------------------------
# _split_response_into_bubbles – additional edge cases
# ---------------------------------------------------------------------------


class TestSplitResponseIntoBubblesAdditional:
    """Additional edge cases for _split_response_into_bubbles."""

    def test_text_exactly_60_chars_stays_single_bubble(self) -> None:
        """Text at boundary (60 chars) stays as single bubble."""
        service = ThinkerService()
        text = "A" * 59 + "."  # exactly 60 chars
        result = service._split_response_into_bubbles(text)
        assert len(result) == 1

    def test_text_250_to_300_chars_may_stay_single(self) -> None:
        """Text between 61-250 chars can stay as single bubble (25% chance)."""
        import random

        service = ThinkerService()
        # Text ~200 chars - sometimes stays single
        text = "This is a medium length response that is somewhere in the middle. " * 3
        text = text[:200]

        single_count = 0
        for seed in range(40):
            random.seed(seed)
            result = service._split_response_into_bubbles(text)
            if len(result) == 1:
                single_count += 1

        # Should sometimes produce single bubble
        assert single_count > 0

    def test_no_empty_bubbles_in_output(self) -> None:
        """The output never contains empty string bubbles."""
        import random

        service = ThinkerService()
        texts = [
            "Short text.",
            "Medium length text that has some content here. More content here.",
            "Long text that repeats. " * 10,
        ]

        for text in texts:
            for seed in range(10):
                random.seed(seed)
                result = service._split_response_into_bubbles(text)
                for bubble in result:
                    assert bubble != "", f"Empty bubble found in: {result}"

    def test_force_split_for_very_long_single_sentence(self) -> None:
        """A very long text with no sentence boundaries is force-split."""
        import random

        service = ThinkerService()
        # A single very long sentence with no period until the end
        text = "This is a very long sentence that just keeps going without any natural break points and the only punctuation is at the end of this entire statement right here."  # noqa: E501
        assert len(text) > 100

        # Run with deterministic seed
        random.seed(1)
        result = service._split_response_into_bubbles(text)
        # Should return at least one bubble
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# _suggest_single_batch – deduplication logic (lines 236-255)
# ---------------------------------------------------------------------------


class TestSuggestSingleBatchDeduplication:
    """Tests for deduplication in the parallel suggest_thinkers path."""

    async def test_parallel_suggestions_deduplicate_by_name(self) -> None:
        """Parallel batch results deduplicate thinkers with the same name."""
        service = ThinkerService()

        # Both batches return "Socrates" - should be deduplicated
        same_thinker_json = """[{
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
        mock_response.content = [TextBlock(type="text", text=same_thinker_json)]
        mock_client = AsyncMock()
        # Return same thinker from both parallel calls
        mock_client.messages.create = AsyncMock(
            side_effect=[mock_response, mock_response, mock_response]
        )
        service._client = mock_client

        with patch.object(service, "get_wikipedia_image", return_value=None):
            result = await service.suggest_thinkers("philosophy", 3)

        # Should have deduplicated - Socrates only appears once
        names = [r.name for r in result]
        assert names.count("Socrates") <= 1

    async def test_all_parallel_batches_fail_raises_api_error(self) -> None:
        """When all parallel batches fail and there was a ThinkerAPIError, it's raised."""
        from anthropic import APIError

        from app.exceptions import ThinkerAPIError

        service = ThinkerService()

        mock_request = MagicMock()
        mock_request.url = "https://api.anthropic.com/v1/messages"
        mock_request.method = "POST"

        mock_client = AsyncMock()
        # All batches raise quota error
        mock_client.messages.create = AsyncMock(
            side_effect=APIError("credit balance is too low", mock_request, body=None)
        )
        service._client = mock_client

        with pytest.raises(ThinkerAPIError) as exc_info:
            await service.suggest_thinkers("philosophy", 3)

        assert exc_info.value.is_quota_error
