"""Thinker service for LLM-powered thinker interactions."""

import asyncio
import contextlib
import logging
import random
import re
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING

import httpx
from anthropic import APIError, AsyncAnthropic
from anthropic.types import TextBlock, ThinkingBlock

from app.api.websocket import SpendLimitExceeded, WSMessage, WSMessageType, manager
from app.core.config import get_settings
from app.exceptions import BillingError, ThinkerAPIError
from app.schemas import ThinkerProfile, ThinkerSuggestion

if TYPE_CHECKING:
    from app.models import ConversationThinker, Message

# Cost per token (approximate for Claude Sonnet 4)
INPUT_COST_PER_TOKEN = 0.000003  # $3 per million input tokens
OUTPUT_COST_PER_TOKEN = 0.000015  # $15 per million output tokens
# Extended thinking uses same rate as output tokens
THINKING_COST_PER_TOKEN = 0.000015  # $15 per million thinking tokens


class ThinkerService:
    """Service for thinker suggestions, validation, and conversation simulation."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: AsyncAnthropic | None = None
        self._active_tasks: dict[str, dict[str, asyncio.Task[None]]] = {}
        self._paused_conversations: set[str] = set()

    @property
    def client(self) -> AsyncAnthropic | None:
        """Get the Anthropic client, creating it if needed."""
        if self._client is None and self.settings.anthropic_api_key:
            self._client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
        return self._client

    async def get_wikipedia_image(self, name: str) -> str | None:
        """Fetch the Wikipedia image URL for a person.

        Uses the Wikipedia API to get the main image from the person's page.
        Returns None if no image found.
        """
        try:
            # Wikipedia requires a User-Agent header
            headers = {
                "User-Agent": "ThinkersChatApp/1.0 (https://github.com/example/thinkers-chat; contact@example.com)"
            }
            async with httpx.AsyncClient(headers=headers) as client:
                # First, search for the Wikipedia page title
                search_url = "https://en.wikipedia.org/w/api.php"
                search_params: dict[str, str | int] = {
                    "action": "query",
                    "list": "search",
                    "srsearch": name,
                    "format": "json",
                    "srlimit": 1,
                }
                response = await client.get(search_url, params=search_params, timeout=5.0)
                data = response.json()

                if not data.get("query", {}).get("search"):
                    return None

                page_title = data["query"]["search"][0]["title"]

                # Get the page images
                image_params: dict[str, str | int] = {
                    "action": "query",
                    "titles": page_title,
                    "prop": "pageimages",
                    "format": "json",
                    "pithumbsize": 200,  # Request 200px thumbnail
                }
                response = await client.get(search_url, params=image_params, timeout=5.0)
                data = response.json()

                pages = data.get("query", {}).get("pages", {})
                for page in pages.values():
                    if "thumbnail" in page:
                        thumbnail_url: str = page["thumbnail"]["source"]
                        return thumbnail_url

                return None
        except Exception:
            return None

    async def suggest_thinkers(
        self, topic: str, count: int = 3, exclude: list[str] | None = None
    ) -> list[ThinkerSuggestion]:
        """Suggest diverse thinkers for a given topic.

        Uses Claude to suggest thinkers who would have interesting,
        diverse perspectives on the topic. Makes parallel API calls for speed.

        Args:
            topic: The topic to suggest thinkers for
            count: Number of suggestions to return (1-5)
            exclude: List of thinker names to exclude from suggestions
        """
        if not self.client:
            return []

        exclude = exclude or []

        # For counts > 2, make parallel calls for faster response
        if count > 2:
            # Split into parallel tasks asking for 1-2 thinkers each
            tasks = []
            remaining = count
            task_num = 0
            perspectives = [
                "scientific or analytical",
                "philosophical or ethical",
                "artistic or creative",
                "political or social",
                "religious or spiritual",
            ]
            while remaining > 0:
                batch_size = min(2, remaining)
                perspective_hint = perspectives[task_num % len(perspectives)]
                tasks.append(
                    self._suggest_single_batch(topic, batch_size, perspective_hint, exclude)
                )
                remaining -= batch_size
                task_num += 1

            # Run all tasks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for API errors first - if any task hit quota, propagate error
            api_error: ThinkerAPIError | None = None
            for result in results:
                if isinstance(result, ThinkerAPIError):
                    api_error = result
                    break

            # Combine results, filtering out errors
            all_suggestions: list[ThinkerSuggestion] = []
            seen_names: set[str] = set()
            for i, result in enumerate(results):
                if isinstance(result, list):
                    logging.info(f"Task {i} returned {len(result)} suggestions")
                    for suggestion in result:
                        # Deduplicate by name
                        if suggestion.name.lower() not in seen_names:
                            seen_names.add(suggestion.name.lower())
                            all_suggestions.append(suggestion)
                elif isinstance(result, Exception):
                    logging.warning(f"Parallel suggestion task {i} failed: {result}")

            # If we got no suggestions and there was an API error, raise it
            if not all_suggestions and api_error:
                raise api_error

            return all_suggestions[:count]

        # For small counts, single call is fine
        return await self._suggest_single_batch(topic, count, None, exclude)

    async def _suggest_single_batch(
        self,
        topic: str,
        count: int,
        perspective_hint: str | None = None,
        exclude: list[str] | None = None,
    ) -> list[ThinkerSuggestion]:
        """Make a single API call to get thinker suggestions."""
        if not self.client:
            return []

        perspective_text = ""
        if perspective_hint:
            perspective_text = f"\nFocus on thinkers with a {perspective_hint} perspective."

        exclude_text = ""
        if exclude:
            exclude_names = ", ".join(exclude)
            exclude_text = f"\n\nIMPORTANT: Do NOT suggest any of these people (they have already been suggested): {exclude_names}"

        prompt = f"""Suggest {count} historical or contemporary thinkers who would have interesting and diverse perspectives on this topic: "{topic}"{perspective_text}{exclude_text}

For each thinker, provide:
1. Their full name
2. A brief reason why they would be interesting for this discussion (1-2 sentences)
3. A profile including:
   - Bio: A 2-3 sentence biographical summary
   - Positions: Their known positions and beliefs relevant to the topic (2-3 sentences)
   - Style: How they communicate - their rhetorical style, tone, and manner (1-2 sentences)

Aim for diversity: include people from different eras, backgrounds, and viewpoints.
People who might disagree with each other make for more interesting discussions.

Format your response as JSON with this structure:
[
  {{
    "name": "Full Name",
    "reason": "Why they're interesting for this topic",
    "profile": {{
      "name": "Full Name",
      "bio": "Biographical summary",
      "positions": "Their positions and beliefs",
      "style": "Communication style"
    }}
  }}
]

Return ONLY the JSON array, no other text."""

        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse the response
            import json

            first_block = response.content[0]
            if not isinstance(first_block, TextBlock):
                import logging

                logging.warning(f"Claude returned non-text block: {type(first_block)}")
                return []
            raw_content = first_block.text
            content = raw_content.strip()
            if not content:
                import logging

                logging.warning("Claude returned empty response")
                return []
            # Strip markdown code fences if present
            if content.startswith("```"):
                # Remove opening fence (```json or ```)
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                import logging

                logging.warning(
                    f"Failed to parse JSON: {e}. Raw: {repr(raw_content[:300])} | After strip: {repr(content[:300])}"
                )
                return []

            # Build suggestions with image URLs (fetched in parallel)
            suggestions = []
            image_tasks = [self.get_wikipedia_image(item["name"]) for item in data]
            images = await asyncio.gather(*image_tasks, return_exceptions=True)

            for item, image in zip(data, images, strict=False):
                image_url = image if isinstance(image, str) else None
                profile = ThinkerProfile(
                    **item["profile"],
                    image_url=image_url,
                )
                suggestions.append(
                    ThinkerSuggestion(
                        name=item["name"],
                        reason=item["reason"],
                        profile=profile,
                    )
                )
            return suggestions
        except APIError as e:
            logging.warning(f"Anthropic API error: {e}")
            # Check for quota/billing errors
            error_msg = str(e)
            is_quota = "credit balance" in error_msg.lower() or "billing" in error_msg.lower()
            if is_quota:
                raise ThinkerAPIError(
                    "API credit limit reached. Please check your Anthropic billing.",
                    is_quota_error=True,
                ) from e
            raise ThinkerAPIError(f"AI service error: {error_msg}") from e
        except Exception as e:
            logging.warning(f"Failed to get thinker suggestions: {e}")
            return []

    async def validate_thinker(self, name: str) -> tuple[bool, ThinkerProfile | None]:
        """Validate that a name refers to a real historical/contemporary figure.

        Returns (is_valid, profile) where profile is populated if valid.
        """
        if not self.client:
            return False, None

        prompt = f"""Is "{name}" a real historical or contemporary figure who is notable enough to be discussed?

If YES, respond with a JSON object:
{{
  "valid": true,
  "profile": {{
    "name": "Their correct full name",
    "bio": "A 2-3 sentence biographical summary",
    "positions": "Their known positions and beliefs (2-3 sentences)",
    "style": "How they communicate - their rhetorical style, tone, manner (1-2 sentences)"
  }}
}}

If NO (fictional, unknown, or too obscure), respond with:
{{
  "valid": false,
  "reason": "Brief explanation why"
}}

Return ONLY the JSON, no other text."""

        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            import json

            first_block = response.content[0]
            if not isinstance(first_block, TextBlock):
                return False, None
            content = first_block.text
            data = json.loads(content)

            if data.get("valid"):
                # Fetch Wikipedia image for the validated thinker
                profile_data = data["profile"]
                image_url = await self.get_wikipedia_image(profile_data["name"])
                return True, ThinkerProfile(**profile_data, image_url=image_url)
            return False, None
        except APIError as e:
            logging.warning(f"Anthropic API error in validate_thinker: {e}")
            error_msg = str(e)
            is_quota = "credit balance" in error_msg.lower() or "billing" in error_msg.lower()
            if is_quota:
                raise ThinkerAPIError(
                    "API credit limit reached. Please check your Anthropic billing.",
                    is_quota_error=True,
                ) from e
            raise ThinkerAPIError(f"AI service error: {error_msg}") from e
        except Exception as e:
            logging.warning(f"Failed to validate thinker: {e}")
            return False, None

    def _choose_response_style(
        self,
        thinker: "ConversationThinker",
        messages: Sequence["Message"],
    ) -> tuple[str, int]:
        """Choose a response style based on conversation context.

        Returns (style_instruction, max_tokens).
        Uses high variance for natural messaging feel - short quips to longer thoughts.
        """
        # Analyze recent messages to decide style
        recent_messages = messages[-5:] if messages else []

        # Check if this thinker just spoke (might want a follow-up)
        just_spoke = recent_messages and recent_messages[-1].sender_name == thinker.name

        # Check if addressed directly
        was_addressed = any(thinker.name.lower() in m.content.lower() for m in recent_messages[-2:])

        # Random selection with HIGH variance for natural feel
        roll = random.random()

        if just_spoke and roll < 0.4:
            # Follow-up thought - very brief
            return (
                "Respond with a VERY brief follow-up (just a few words to one short sentence, like 'Exactly.' or 'Though I wonder...' or 'Hmm, fair point.')",
                50,
            )
        elif was_addressed:
            # When addressed, still vary response length significantly
            if roll < 0.15:
                return ("Respond with just 2-5 words - a quick acknowledgment or reaction", 30)
            elif roll < 0.35:
                return ("Give a brief, direct response (1 short sentence, around 10-15 words)", 60)
            elif roll < 0.55:
                return ("Give a medium response (1-2 sentences)", 120)
            elif roll < 0.80:
                return ("Give a substantive response (2-3 sentences)", 200)
            else:
                return (
                    "Give a fuller response exploring the idea (3-5 sentences)",
                    350,
                )
        else:
            # Not addressed - even MORE variety, skewing shorter
            if roll < 0.20:
                # Very quick reaction - like real texting
                return (
                    "Give a very brief reaction (2-6 words only, like 'Absolutely.' or 'I'm not so sure.' or 'Ha! Yes.')",
                    30,
                )
            elif roll < 0.40:
                # Quick thought
                return (
                    "Give a brief reaction (1 short sentence, around 8-12 words)",
                    60,
                )
            elif roll < 0.60:
                # Medium response
                return ("Give a medium response (1-2 sentences)", 120)
            elif roll < 0.80:
                return ("Give a substantive response (2-3 sentences)", 200)
            else:
                return ("Give a more developed response (3-4 sentences)", 300)

    async def generate_response_with_streaming_thinking(
        self,
        conversation_id: str,
        thinker: "ConversationThinker",
        messages: Sequence["Message"],
        topic: str,
    ) -> tuple[str, float]:
        """Generate a response using streaming extended thinking.

        Streams thinking tokens via WebSocket as they're generated,
        then returns the final response text and cost.
        """
        if not self.client:
            return "", 0.0

        # Choose response style based on context
        style_instruction, max_tokens = self._choose_response_style(thinker, messages)

        # Build conversation context
        def get_sender_label(msg: "Message") -> str:
            sender = msg.sender_type
            is_user = (hasattr(sender, "value") and sender.value == "user") or sender == "user"
            # Use the actual sender name from the message (display_name or username)
            return (msg.sender_name or "User") if is_user else (msg.sender_name or "Unknown")

        conversation_history = "\n".join(
            f"{get_sender_label(m)}: {m.content}"
            for m in messages[-20:]  # Last 20 messages for context
        )

        prompt = f"""You ARE {thinker.name}, participating in a group discussion.

WHO YOU ARE:
{thinker.bio}
Your known positions: {thinker.positions}
Your communication style: {thinker.style}

DISCUSSION TOPIC: {topic}

CONVERSATION SO FAR:
{conversation_history}

IMPORTANT - STAY IN FIRST PERSON:
Think and respond in FIRST PERSON as yourself ({thinker.name}). Your inner thoughts should be "I believe...", "I want to mention...", "Let me consider..." - NOT third person reasoning like "{thinker.name} would say...".

Guidelines for your response:
- Stay in character based on your known views and communication style
- Use modern English regardless of your era
- If discussing something that didn't exist in your time, acknowledge it (e.g., "In my era we didn't have X, but...")
- Engage with what others have said - agree, disagree, build on ideas
- Don't be preachy or lecture-like
- Show personality through your response style

RESPONSE STYLE: {style_instruction}

Respond with ONLY what you would say as {thinker.name}, nothing else."""

        try:
            # Use streaming with extended thinking
            response_text = ""
            thinking_text = ""
            input_tokens = 0
            output_tokens = 0

            # Get speed multiplier for this conversation (higher = slower)
            speed_mult = manager.get_speed_multiplier(conversation_id)

            # Track when we last sent a thinking update (throttle for readability)
            last_thinking_update = 0.0
            # Base interval is 2s, multiplied by speed setting for slower display
            # At 6x (Contemplative), this gives 12s between updates
            thinking_update_interval = 2.0 * speed_mult

            paused_during_stream = False
            async with self.client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens + 2000,  # Extra for thinking budget
                thinking={
                    "type": "enabled",
                    "budget_tokens": 2000,  # Budget for thinking
                },
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for event in stream:
                    # Check if paused - stop streaming updates if so
                    if self.is_paused(conversation_id):
                        if not paused_during_stream:
                            await manager.send_thinker_stopped_typing(conversation_id, thinker.name)
                            paused_during_stream = True
                        # Continue consuming stream but don't send updates
                        # We still need to get the response for potential later use
                        continue

                    # Handle different event types
                    if event.type == "content_block_start":
                        pass  # Block started
                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if hasattr(delta, "thinking") and delta.thinking:
                            # Accumulate thinking text
                            thinking_text += delta.thinking
                            # Throttle updates to avoid overwhelming WebSocket
                            current_time = asyncio.get_event_loop().time()
                            if current_time - last_thinking_update >= thinking_update_interval:
                                # Extract last sentence or meaningful chunk for display
                                display_thinking = self._extract_thinking_display(thinking_text)
                                if display_thinking:
                                    await manager.send_thinker_thinking(
                                        conversation_id, thinker.name, display_thinking
                                    )
                                last_thinking_update = current_time
                        elif hasattr(delta, "text") and delta.text:
                            # Accumulate response text
                            response_text += delta.text
                    elif event.type == "message_delta" and hasattr(event, "usage") and event.usage:
                        # Final usage info
                        output_tokens = event.usage.output_tokens

                # Get final message for input token count
                final_message = await stream.get_final_message()
                input_tokens = final_message.usage.input_tokens
                output_tokens = final_message.usage.output_tokens

                # Calculate cost (thinking tokens counted as output)
                # Count thinking tokens from the thinking block
                thinking_tokens = 0
                for block in final_message.content:
                    if isinstance(block, ThinkingBlock):
                        # Approximate thinking tokens from text length
                        thinking_tokens = len(block.thinking) // 4  # Rough estimate

                cost = (
                    input_tokens * INPUT_COST_PER_TOKEN
                    + output_tokens * OUTPUT_COST_PER_TOKEN
                    + thinking_tokens * THINKING_COST_PER_TOKEN
                )

            return response_text.strip(), cost

        except APIError as e:
            # Check for billing/quota errors first
            error_msg = str(e)
            is_billing = "credit balance" in error_msg.lower() or "billing" in error_msg.lower()
            if is_billing:
                logging.error(f"Anthropic billing error in streaming thinking: {e}")
                raise BillingError(
                    "API credit limit reached. Please check your Anthropic billing."
                ) from e
            # Log API-specific errors with more detail
            logging.error(f"Anthropic API error in streaming thinking: {e}")
            raise ThinkerAPIError(f"AI service error: {e}") from e
        except Exception as e:
            logging.error(f"Unexpected error in streaming thinking response: {e}", exc_info=True)
            raise ThinkerAPIError(f"Failed to generate response: {e}") from e

    def _split_response_into_bubbles(self, response_text: str) -> list[str]:
        """Split a response into multiple chat bubbles for natural conversation flow.

        Uses variable splitting strategy for natural message size variety:
        - Sometimes keeps longer responses as single bubbles
        - Sometimes splits aggressively into many small bubbles
        - Target bubble sizes vary randomly
        """
        if not response_text:
            return []

        text = response_text.strip()

        # Very short responses always stay as single bubble
        if len(text) < 60:
            return [text]

        # Random splitting strategy for variety
        strategy_roll = random.random()

        # 25% chance: Keep as single bubble even if longer (up to ~250 chars)
        if strategy_roll < 0.25 and len(text) < 250:
            return [text]

        # 20% chance: Aggressive splitting (small bubbles ~80-120 chars)
        # 35% chance: Normal splitting (~120-180 chars)
        # 20% chance: Relaxed splitting (~180-250 chars)
        if strategy_roll < 0.45:
            target_size = random.randint(80, 120)  # Small bubbles
        elif strategy_roll < 0.80:
            target_size = random.randint(120, 180)  # Normal bubbles
        else:
            target_size = random.randint(180, 250)  # Larger bubbles

        bubbles: list[str] = []
        current_bubble = ""

        # Split on sentence endings, keeping the punctuation
        sentences = re.split(r"(?<=[.!?])\s+", text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check for thought transitions that should start a new bubble
            transition_words = [
                "But ",
                "However,",
                "Although ",
                "On the other hand,",
                "That said,",
                "Nevertheless,",
                "Yet ",
                "Still,",
                "Though ",
                "Conversely,",
            ]
            starts_with_transition = any(sentence.startswith(tw) for tw in transition_words)

            # Split if current bubble would exceed target or starts with transition
            if current_bubble and (
                len(current_bubble) + len(sentence) > target_size or starts_with_transition
            ):
                bubbles.append(current_bubble.strip())
                current_bubble = sentence
            else:
                if current_bubble:
                    current_bubble += " " + sentence
                else:
                    current_bubble = sentence

        # Don't forget the last bubble
        if current_bubble:
            bubbles.append(current_bubble.strip())

        # If we ended up with just one bubble but text is very long, force split
        if len(bubbles) == 1 and len(text) > 300:
            # Force a split at roughly the middle sentence boundary
            mid = len(text) // 2
            # Find the nearest sentence end after mid
            for i in range(mid, len(text)):
                if text[i] in ".!?" and i + 1 < len(text) and text[i + 1] == " ":
                    bubbles = [text[: i + 1].strip(), text[i + 2 :].strip()]
                    break

        return [b for b in bubbles if b]  # Filter out empty strings

    def _extract_thinking_display(self, thinking_text: str) -> str:
        """Extract a displayable portion of the thinking text.

        Transforms raw LLM thinking into thinker's internal monologue style.
        Returns the last complete thought, rephrased as if the thinker is talking to themselves.
        Returns empty string if text is too short (< 80 chars) to show meaningful preview.
        """
        if not thinking_text:
            return ""

        # Clean up the text
        text = thinking_text.strip()

        # Don't display if too short - wait for more content
        # This avoids showing truncated snippets like "Har..."
        if len(text) < 80:
            return ""

        # Get the last ~200 characters for display (increased for better context)
        if len(text) > 200:
            text = text[-200:]
            # Try to start at a sentence boundary
            for punct in [". ", "! ", "? ", "\n"]:
                idx = text.find(punct)
                if idx != -1 and idx < 80:
                    text = text[idx + len(punct) :]
                    break

        # Clean up any incomplete words at the start
        if text and not text[0].isupper() and " " in text:
            text = text[text.find(" ") + 1 :]

        # Also ensure we don't end mid-word - truncate at last word boundary
        # but keep at least 40 chars to be meaningful
        if len(text) > 60 and not text[-1].isspace() and " " in text[-30:]:
            # Find last space and truncate there if text doesn't end properly
            last_space = text.rfind(" ", len(text) - 30)
            if last_space > 40:
                text = text[:last_space]

        # Transform to sound like internal monologue rather than LLM reasoning
        # Remove obvious LLM-style phrases
        replacements = [
            ("I should ", "Perhaps I should "),
            ("I need to ", "Hmm, I need to "),
            ("I think ", ""),
            ("I'll ", "I shall "),
            ("The user ", "They "),
            ("the user ", "they "),
            ("I am going to ", "I shall "),
            ("Let me ", "Let me see... "),
            ("I can ", "I might "),
            ("I will ", "I shall "),
        ]
        for old, new in replacements:
            text = text.replace(old, new)

        # Add contemplative starters for variety
        starters = [
            "Hmm... ",
            "Now then... ",
            "Interesting... ",
            "Let me consider... ",
            "*pondering* ",
            "",  # Sometimes no prefix
            "",
        ]
        # Use a simple hash of the text to pick a consistent starter
        starter_idx = hash(text[:20] if len(text) > 20 else text) % len(starters)
        prefix = starters[starter_idx]

        # Only add prefix if the text doesn't already start with something similar
        if not text.lower().startswith(("hmm", "let me", "now", "interesting", "*")):
            text = prefix + text

        # Add ellipsis if truncated
        if text and not text.endswith((".", "!", "?", "...")):
            text = text.rstrip() + "..."

        return text

    async def generate_response(
        self,
        thinker: "ConversationThinker",
        messages: Sequence["Message"],
        topic: str,
    ) -> tuple[str, float]:
        """Generate a response from a thinker (non-streaming fallback).

        Returns (response_text, cost).
        """
        if not self.client:
            return "", 0.0

        # Choose response style based on context
        style_instruction, max_tokens = self._choose_response_style(thinker, messages)

        # Build conversation context
        def get_sender_label(msg: "Message") -> str:
            sender = msg.sender_type
            is_user = (hasattr(sender, "value") and sender.value == "user") or sender == "user"
            # Use the actual sender name from the message (display_name or username)
            return (msg.sender_name or "User") if is_user else (msg.sender_name or "Unknown")

        conversation_history = "\n".join(
            f"{get_sender_label(m)}: {m.content}"
            for m in messages[-20:]  # Last 20 messages for context
        )

        prompt = f"""You ARE {thinker.name}, participating in a group discussion.

WHO YOU ARE:
{thinker.bio}
Your known positions: {thinker.positions}
Your communication style: {thinker.style}

DISCUSSION TOPIC: {topic}

CONVERSATION SO FAR:
{conversation_history}

IMPORTANT - STAY IN FIRST PERSON:
Think and respond in FIRST PERSON as yourself ({thinker.name}). Your inner thoughts should be "I believe...", "I want to mention...", "Let me consider..." - NOT third person reasoning like "{thinker.name} would say...".

Guidelines for your response:
- Stay in character based on your known views and communication style
- Use modern English regardless of your era
- If discussing something that didn't exist in your time, acknowledge it (e.g., "In my era we didn't have X, but...")
- Engage with what others have said - agree, disagree, build on ideas
- Don't be preachy or lecture-like
- Show personality through your response style

RESPONSE STYLE: {style_instruction}

Respond with ONLY what you would say as {thinker.name}, nothing else."""

        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )

            # Calculate cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = input_tokens * INPUT_COST_PER_TOKEN + output_tokens * OUTPUT_COST_PER_TOKEN

            first_block = response.content[0]
            if not isinstance(first_block, TextBlock):
                return "", 0.0
            return first_block.text, cost
        except APIError as e:
            logging.error(f"Anthropic API error in generate_response: {e}")
            raise ThinkerAPIError(f"AI service error: {e}") from e
        except Exception as e:
            logging.error(f"Error in generate_response: {e}", exc_info=True)
            raise ThinkerAPIError(f"Failed to generate response: {e}") from e

    async def start_conversation_agents(
        self,
        conversation_id: str,
        thinkers: list["ConversationThinker"],
        topic: str,
        get_messages: Callable[[str], Awaitable[Sequence["Message"]]],
        save_message: Callable[[str, str, str, float], Awaitable["Message"]],
    ) -> None:
        """Start thinker agents for a conversation.

        Each thinker runs as an independent async task that:
        - Monitors the conversation
        - Decides when to respond
        - Generates and sends responses
        """
        if conversation_id in self._active_tasks:
            # Stop existing tasks first
            await self.stop_conversation_agents(conversation_id)

        self._active_tasks[conversation_id] = {}

        for thinker in thinkers:
            task = asyncio.create_task(
                self._run_thinker_agent(
                    conversation_id,
                    thinker,
                    topic,
                    get_messages,
                    save_message,
                )
            )
            self._active_tasks[conversation_id][thinker.id] = task

    async def stop_conversation_agents(self, conversation_id: str) -> None:
        """Stop all thinker agents for a conversation."""
        if conversation_id in self._active_tasks:
            for task in self._active_tasks[conversation_id].values():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            del self._active_tasks[conversation_id]
        # Note: We intentionally do NOT clean up paused state here.
        # Pause state should persist across reconnections so users
        # see the conversation is still paused when they return.

    def pause_conversation(self, conversation_id: str) -> None:
        """Pause all thinker agents for a conversation."""
        self._paused_conversations.add(conversation_id)

    def resume_conversation(self, conversation_id: str) -> None:
        """Resume all thinker agents for a conversation."""
        self._paused_conversations.discard(conversation_id)

    def is_paused(self, conversation_id: str) -> bool:
        """Check if a conversation is paused."""
        return conversation_id in self._paused_conversations

    async def _run_thinker_agent(
        self,
        conversation_id: str,
        thinker: "ConversationThinker",
        topic: str,
        get_messages: Callable[[str], Awaitable[Sequence["Message"]]],
        save_message: Callable[[str, str, str, float], Awaitable["Message"]],
    ) -> None:
        """Run a single thinker agent.

        The agent monitors the conversation and responds when appropriate.
        It pauses when no users are connected and resumes when they return.
        Uses variable timing for more natural conversation flow.
        """
        last_response_count = 0
        consecutive_silence = 0  # Track how long since last response
        last_message_time = 0.0  # Track when this thinker last sent a message

        while True:
            try:
                # Check if conversation is active (users connected)
                if not manager.is_conversation_active(conversation_id):
                    # Wait for users to reconnect
                    await asyncio.sleep(1)
                    continue

                # Check if conversation is paused
                if self.is_paused(conversation_id):
                    # Wait while paused
                    await asyncio.sleep(0.5)
                    continue

                # Get speed multiplier (higher = slower)
                # Use non-linear scaling: speed_mult^1.5 makes higher speeds much slower
                # At 1x: 1.0, at 2x: 2.8, at 4x: 8.0, at 6x: 14.7
                raw_speed = manager.get_speed_multiplier(conversation_id)
                speed_mult = raw_speed**1.5

                # Enforce minimum time between messages from this thinker
                # At 6x (Contemplative), minimum ~150s between messages from same thinker
                # This ensures truly slow, contemplative pacing
                min_interval = 10.0 * speed_mult  # 10s base, ~147s at 6x
                current_time = asyncio.get_event_loop().time()
                if last_message_time > 0:
                    elapsed = current_time - last_message_time
                    if elapsed < min_interval:
                        await asyncio.sleep(min_interval - elapsed)
                        continue

                # Get current messages
                messages = await get_messages(conversation_id)

                # Decide whether to respond
                should_respond = self._should_respond(
                    thinker, messages, last_response_count, consecutive_silence
                )

                if should_respond:
                    consecutive_silence = 0

                    # Check if we should prompt the user instead of normal response
                    should_prompt = self._should_prompt_user(messages, speed_mult)
                    user_name = (
                        self._get_user_name_from_messages(messages) if should_prompt else None
                    )

                    # Show typing indicator
                    await manager.send_thinker_typing(conversation_id, thinker.name)

                    # Initial "reading" delay - longer at slower speeds
                    # At 6x: 3-9 seconds of reading before starting to type
                    await asyncio.sleep(random.uniform(0.5, 1.5) * speed_mult)

                    # Check pause state before generating (prevents spend during pause)
                    if self.is_paused(conversation_id):
                        await manager.send_thinker_stopped_typing(conversation_id, thinker.name)
                        continue

                    # Generate response - either a user prompt or normal response
                    if should_prompt and user_name:
                        # Generate a message that invites the user to participate
                        response_text, cost = await self.generate_user_prompt(
                            thinker, messages, topic, user_name
                        )
                    else:
                        # Generate normal response with streaming thinking
                        # This streams thinking tokens via WebSocket as they're generated
                        response_text, cost = await self.generate_response_with_streaming_thinking(
                            conversation_id, thinker, messages, topic
                        )

                    # Check pause state again before saving (in case paused during generation)
                    if self.is_paused(conversation_id):
                        await manager.send_thinker_stopped_typing(conversation_id, thinker.name)
                        continue

                    if response_text:
                        # Split response into multiple chat bubbles for natural flow
                        bubbles = self._split_response_into_bubbles(response_text)

                        # Distribute cost across bubbles
                        cost_per_bubble = cost / len(bubbles) if bubbles else 0

                        # Send each bubble with typing delay between them
                        for i, bubble_text in enumerate(bubbles):
                            # Check pause state IMMEDIATELY before each send
                            if self.is_paused(conversation_id):
                                await manager.send_thinker_stopped_typing(
                                    conversation_id, thinker.name
                                )
                                break

                            # Save and broadcast the bubble
                            message = await save_message(
                                conversation_id,
                                thinker.name,
                                bubble_text,
                                cost_per_bubble,
                            )

                            # Final pause check right before sending to UI
                            if self.is_paused(conversation_id):
                                await manager.send_thinker_stopped_typing(
                                    conversation_id, thinker.name
                                )
                                break

                            # Stop typing indicator before sending message
                            await manager.send_thinker_stopped_typing(conversation_id, thinker.name)
                            await manager.send_thinker_message(
                                conversation_id,
                                thinker.name,
                                bubble_text,
                                message.id,
                                cost_per_bubble,
                            )

                            # If there are more bubbles, show typing and wait
                            if i < len(bubbles) - 1:
                                await asyncio.sleep(random.uniform(1.0, 2.5) * speed_mult)
                                # Show typing for next bubble
                                await manager.send_thinker_typing(conversation_id, thinker.name)
                                # Brief typing delay
                                await asyncio.sleep(random.uniform(1.0, 3.0) * speed_mult)

                        last_response_count = len(messages) + len(bubbles)
                        last_message_time = asyncio.get_event_loop().time()
                    else:
                        await manager.send_thinker_stopped_typing(conversation_id, thinker.name)
                else:
                    consecutive_silence += 1

                # Variable wait before checking again
                # Base times are longer to ensure proper pacing
                # At 6x (Contemplative): active = 30-60s, quiet = 60-120s between checks
                if consecutive_silence > 3:
                    wait_time = random.uniform(10.0, 20.0) * speed_mult  # Quiet conversation
                else:
                    wait_time = random.uniform(5.0, 10.0) * speed_mult  # Active conversation
                await asyncio.sleep(wait_time)

            except asyncio.CancelledError:
                break
            except SpendLimitExceeded as e:
                # User hit spend limit - pause and notify
                logging.info(f"Spend limit exceeded for conversation {conversation_id}: {e}")
                self.pause_conversation(conversation_id)
                await manager.send_thinker_stopped_typing(conversation_id, thinker.name)
                await manager.broadcast_to_conversation(
                    conversation_id,
                    WSMessage(
                        type=WSMessageType.ERROR,
                        conversation_id=conversation_id,
                        content=f"Spend limit reached (${e.current_spend:.2f}/${e.spend_limit:.2f}). Contact admin to increase your limit.",
                    ),
                )
                await manager.broadcast_to_conversation(
                    conversation_id,
                    WSMessage(
                        type=WSMessageType.PAUSED,
                        conversation_id=conversation_id,
                    ),
                )
                break  # Stop this thinker agent
            except BillingError as e:
                # Billing/quota error - notify user with clear message
                logging.error(f"Billing error for {thinker.name}: {e}")
                await manager.send_thinker_stopped_typing(conversation_id, thinker.name)
                await manager.broadcast_to_conversation(
                    conversation_id,
                    WSMessage(
                        type=WSMessageType.ERROR,
                        conversation_id=conversation_id,
                        content=f"API billing error: {e.message}. Please contact support.",
                    ),
                )
                # Pause conversation to prevent further spending
                self.pause_conversation(conversation_id)
                await manager.broadcast_to_conversation(
                    conversation_id,
                    WSMessage(
                        type=WSMessageType.PAUSED,
                        conversation_id=conversation_id,
                    ),
                )
                break  # Stop this thinker agent
            except ThinkerAPIError as e:
                # API error - notify user and retry after delay
                logging.error(f"Thinker API error for {thinker.name}: {e}")
                await manager.send_thinker_stopped_typing(conversation_id, thinker.name)
                await manager.broadcast_to_conversation(
                    conversation_id,
                    WSMessage(
                        type=WSMessageType.ERROR,
                        conversation_id=conversation_id,
                        content=f"{thinker.name} encountered an error: {e}. Retrying...",
                    ),
                )
                await asyncio.sleep(10)  # Wait longer before retry
            except Exception as e:
                # Unexpected error - log with traceback and notify user
                logging.error(
                    f"Unexpected error in thinker agent {thinker.name}: {e}", exc_info=True
                )
                await manager.send_thinker_stopped_typing(conversation_id, thinker.name)
                await manager.broadcast_to_conversation(
                    conversation_id,
                    WSMessage(
                        type=WSMessageType.ERROR,
                        conversation_id=conversation_id,
                        content=f"{thinker.name} encountered an unexpected error. Retrying...",
                    ),
                )
                await asyncio.sleep(5)

    def _get_user_name_from_messages(self, messages: Sequence["Message"]) -> str | None:
        """Extract the user's display name from message history."""
        for msg in reversed(messages):
            sender = msg.sender_type
            is_user = (hasattr(sender, "value") and sender.value == "user") or sender == "user"
            if is_user and msg.sender_name:
                return msg.sender_name
        return None

    def _count_messages_since_user(self, messages: Sequence["Message"]) -> int:
        """Count how many thinker messages have occurred since the user last spoke."""
        count = 0
        for msg in reversed(messages):
            sender = msg.sender_type
            is_user = (hasattr(sender, "value") and sender.value == "user") or sender == "user"
            if is_user:
                break
            count += 1
        return count

    def _should_prompt_user(
        self,
        messages: Sequence["Message"],
        speed_mult: float,
    ) -> bool:
        """Determine if we should prompt the user to participate.

        Returns True if:
        - User hasn't spoken in many messages (threshold scales with speed)
        - There are enough messages for context
        - Random chance (don't always prompt)
        """
        if len(messages) < 5:
            return False

        messages_since_user = self._count_messages_since_user(messages)

        # Threshold: prompt after ~8 thinker messages at 1x, ~5 at 6x (more contemplative = more inclusive)
        threshold = max(4, int(8 / (speed_mult**0.3)))

        if messages_since_user < threshold:
            return False

        # Don't prompt too often - low probability even when threshold met
        # Higher speed = more likely to prompt (slower pace, more natural to invite)
        prompt_probability = 0.15 * (speed_mult**0.3)
        return bool(random.random() < prompt_probability)

    async def generate_user_prompt(
        self,
        thinker: "ConversationThinker",
        messages: Sequence["Message"],
        topic: str,
        user_name: str,
    ) -> tuple[str, float]:
        """Generate a message that prompts the user to participate.

        Creates a natural invitation for the user to share their thoughts.
        """
        if not self.client:
            return "", 0.0

        # Build recent conversation context
        def get_sender_label(msg: "Message") -> str:
            sender = msg.sender_type
            is_user = (hasattr(sender, "value") and sender.value == "user") or sender == "user"
            return user_name if is_user else (msg.sender_name or "Unknown")

        conversation_history = "\n".join(
            f"{get_sender_label(m)}: {m.content}" for m in messages[-15:]
        )

        prompt = f"""You ARE {thinker.name}, participating in a group discussion.

WHO YOU ARE:
{thinker.bio}
Your known positions: {thinker.positions}
Your communication style: {thinker.style}

DISCUSSION TOPIC: {topic}

RECENT CONVERSATION:
{conversation_history}

The user {user_name} hasn't spoken in a while. Generate a SHORT, natural message that:
1. Stays in character as yourself ({thinker.name})
2. Invites {user_name} to share their perspective
3. References something specific from the recent discussion
4. Feels warm and curious, not demanding

Examples of good prompts (adapt to your style):
- "{user_name}, I'm curious what you make of all this."
- "We've been going back and forth, but {user_name}, where do you stand?"
- "{user_name}, you've been quiet - any thoughts on what [other thinker] said about X?"

Keep it to ONE short sentence (under 20 words). Be genuine, not formulaic.

Respond with ONLY what you would say, nothing else."""

        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=60,
                messages=[{"role": "user", "content": prompt}],
            )

            # Calculate cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = input_tokens * INPUT_COST_PER_TOKEN + output_tokens * OUTPUT_COST_PER_TOKEN

            first_block = response.content[0]
            if not isinstance(first_block, TextBlock):
                return "", 0.0
            return first_block.text.strip(), cost
        except Exception as e:
            logging.warning(f"Failed to generate user prompt: {e}")
            return "", 0.0

    def _should_respond(
        self,
        thinker: "ConversationThinker",
        messages: Sequence["Message"],
        last_response_count: int,
        consecutive_silence: int = 0,
    ) -> bool:
        """Decide if a thinker should respond to the current conversation state.

        Uses heuristics to create natural conversation flow:
        - Respond after new messages arrive
        - Don't respond too frequently
        - Higher chance to respond when addressed or when topic is relevant
        - May stay silent for multiple turns (more realistic)
        """
        if not messages:
            return False

        # New messages since last response
        new_message_count = len(messages) - last_response_count
        if new_message_count <= 0:
            return False

        # Check if the thinker was addressed
        last_messages = messages[-3:]
        was_addressed = any(thinker.name.lower() in m.content.lower() for m in last_messages)

        # Base probability increases with new messages
        base_probability = min(0.25 + (new_message_count * 0.12), 0.7)

        # Higher probability if addressed
        if was_addressed:
            base_probability = min(base_probability + 0.5, 0.95)

        # Increase probability if been silent for a while (should eventually respond)
        if consecutive_silence > 2:
            base_probability = min(base_probability + (consecutive_silence * 0.1), 0.9)

        # Don't respond to your own message immediately (but allow follow-ups handled elsewhere)
        if messages and messages[-1].sender_name == thinker.name:
            base_probability = 0.05  # Very low - follow-ups handled separately

        # Sometimes stay completely silent for variety (unless addressed)
        if not was_addressed and random.random() < 0.15:
            return False

        return random.random() < base_probability


# Global service instance
thinker_service = ThinkerService()
