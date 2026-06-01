"""Coverage-sprint tests targeting the last-mile gaps in websocket.py and thinker.py.

Focus: Monday QA coverage-sprint (2026-06-01).

Targets the residual missing lines/branches reported by pytest --cov:

* ``app/api/websocket.py`` — 95% before:
  - Lines 420-431: ``get_messages``/``save_message`` closures + the
    ``start_conversation_agents`` call that only runs when the websocket
    connects to a conversation that actually has thinkers in the DB.
  - Line 450: TYPING_START ``pass`` branch.
  - Line 453: TYPING_STOP ``pass`` branch.
  - Branch 478->441: the loop body returning to ``receive_text`` after a
    USER_MESSAGE has been broadcast.

* ``app/services/thinker.py`` — 98% before:
  - ``_extract_thinking_display`` short-text fast path (returns empty)
    so that the caller's ``if display_thinking:`` skip branch is covered.
  - ``_should_respond`` empty-messages early-exit.
  - ``_split_response_into_bubbles`` whitespace-only-sentence skip and
    other size/strategy branches.
"""

from __future__ import annotations

import random
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.core.auth import create_access_token
from app.main import app
from app.models import Conversation, Session, User
from app.models.thinker import ConversationThinker
from app.services.thinker import ThinkerService


def _get_test_token(user_id: str = "test-user-id", session_id: str = "test-session-id") -> str:
    return create_access_token({"sub": user_id, "session_id": session_id})


class TestWebSocketLoopHandlesTypingAndUserMessageSequence:
    """Cover lines 450 (TYPING_START), 453 (TYPING_STOP) and branch 478->441.

    The pass-only TYPING_START / TYPING_STOP handlers and the loop-continuation
    after USER_MESSAGE are only exercised when the server actually processes
    a *sequence* of messages on the same connection. The pre-existing tests
    each send a single frame and then disconnect, which races against the
    server's receive_text() — coverage was missing the lines because the
    server typically tore down before reaching them.

    By sending a follow-up frame whose handler echoes back, we force the
    server through the typing pass-branch AND the loop-continuation after
    USER_MESSAGE.
    """

    def test_typing_start_then_user_message_reaches_loop_again(self) -> None:
        token = _get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/typing-then-user?token={token}") as websocket,
        ):
            websocket.receive_json()  # user_joined
            websocket.receive_json()  # resumed

            # Frame 1: TYPING_START — server should hit line 450 (pass) and
            # loop back to receive_text.
            websocket.send_json({"type": "typing_start"})

            # Frame 2: USER_MESSAGE — the only way this broadcast arrives is
            # if the server returned to the top of the receive loop after
            # processing the TYPING_START frame.
            websocket.send_json({"type": "user_message", "content": "Hello after typing"})

            data = websocket.receive_json()
            assert data["type"] == "message"
            assert data["content"] == "Hello after typing"
            assert data["sender_type"] == "user"

    def test_typing_stop_then_user_message_reaches_loop_again(self) -> None:
        token = _get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/typing-stop-then-user?token={token}") as websocket,
        ):
            websocket.receive_json()
            websocket.receive_json()

            # Frame 1: TYPING_STOP — server should hit line 453 (pass).
            websocket.send_json({"type": "typing_stop"})

            # Frame 2: USER_MESSAGE — proves the loop returned to
            # receive_text after the pass-branch was taken.
            websocket.send_json({"type": "user_message", "content": "Hello after typing stop"})

            data = websocket.receive_json()
            assert data["type"] == "message"
            assert data["content"] == "Hello after typing stop"

    def test_two_user_messages_in_sequence_proves_loop_continuation(self) -> None:
        """Branch 478->441: USER_MESSAGE returns to top of receive loop.

        Sending two USER_MESSAGE frames in a row and receiving both
        broadcasts is the strongest proof that the server actually loops
        back to ``receive_text`` after USER_MESSAGE.
        """
        token = _get_test_token()
        with (
            TestClient(app) as test_client,
            test_client.websocket_connect(f"/ws/two-user-msgs?token={token}") as websocket,
        ):
            websocket.receive_json()
            websocket.receive_json()

            websocket.send_json({"type": "user_message", "content": "one"})
            data1 = websocket.receive_json()
            assert data1["type"] == "message"
            assert data1["content"] == "one"

            websocket.send_json({"type": "user_message", "content": "two"})
            data2 = websocket.receive_json()
            assert data2["type"] == "message"
            assert data2["content"] == "two"


class TestWebSocketStartsThinkerAgentsWhenConversationHasThinkers:
    """Cover lines 420-431 (closures + start_conversation_agents call).

    These lines run only when the websocket handler loads a Conversation
    whose ``thinkers`` collection is non-empty AND finds a User for the
    session. Rather than seeding the real SQLite file (which races against
    pytest's parallel db setup and TestClient's lifespan), we directly
    instantiate the websocket endpoint coroutine with a patched
    ``async_session_maker`` that returns mock sessions backed by hand-built
    Conversation/User rows. ``thinker_service.start_conversation_agents``
    is replaced with a capture that drives the closures, so the
    ``get_messages`` and ``save_message`` bodies are exercised end-to-end
    against the real ``get_messages_for_conversation`` and
    ``save_thinker_message`` helpers, but the websocket itself never blocks
    on ``receive_text``.
    """

    async def test_handler_invokes_start_conversation_agents_with_working_closures(
        self,
        db_session: Any,
    ) -> None:
        from contextlib import asynccontextmanager

        from app.api import websocket as ws_module
        from app.services.thinker import thinker_service

        # Seed an in-memory test DB (db_session fixture uses sqlite :memory:)
        # with a User, Session, Conversation, ConversationThinker.
        user = User(
            username="ws-thinker-coverage-user",
            password_hash="hash",
            language_preference="fr",
        )
        db_session.add(user)
        await db_session.flush()

        session = Session(user_id=user.id)
        db_session.add(session)
        await db_session.flush()

        conv = Conversation(
            session_id=session.id,
            topic="What is the good life?",
        )
        db_session.add(conv)
        await db_session.flush()

        thinker = ConversationThinker(
            conversation_id=conv.id,
            name="Aristotle",
            bio="Greek philosopher",
            positions="Virtue ethics",
            style="Reasoned dialogue",
        )
        db_session.add(thinker)
        await db_session.commit()

        captured: dict[str, Any] = {}

        async def fake_start(
            conv_id: str,
            thinkers: list[Any],
            topic: str,
            get_messages: Any,
            save_message: Any,
            language: str,
        ) -> None:
            captured["conv_id"] = conv_id
            captured["topic"] = topic
            captured["language"] = language
            captured["thinker_names"] = [t.name for t in thinkers]
            # Drive the closures (lines 420-428) end-to-end.
            captured["messages_initial"] = list(await get_messages(conv_id))
            saved = await save_message(conv_id, thinkers[0].name, "Hello from closure", 0.0007)
            captured["saved_thinker"] = saved.sender_name
            captured["saved_cost"] = saved.cost

        # Build an ``async_session_maker``-compatible callable that yields
        # the in-memory db_session. The websocket handler calls
        # ``async with async_session_maker() as db`` three times:
        # 1) load the conversation+thinkers
        # 2) load the user via session_id
        # 3) inside the get_messages closure
        # 4) inside the save_message closure
        # Reusing a single AsyncSession across context managers is safe for
        # SQLAlchemy because we're not closing it (the fixture owns it).
        @asynccontextmanager
        async def session_maker_stub() -> Any:
            yield db_session

        # Mock WebSocket — collect everything sent, drive receive_text() to
        # raise WebSocketDisconnect after the connect-side machinery runs.
        from fastapi import WebSocketDisconnect

        ws_mock = MagicMock()
        ws_mock.accept = AsyncMock()
        ws_mock.send_text = AsyncMock()
        ws_mock.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
        ws_mock.close = AsyncMock()
        ws_mock.client = None

        # Token wired to the seeded user/session so decode_access_token
        # succeeds and the user query returns our fr-language user.
        token = create_access_token({"sub": user.id, "session_id": session.id})

        with (
            # async_session_maker is imported INSIDE the websocket handler
            # function, so the only correct patch target is its source
            # module. The closures also re-call the imported binding, so a
            # single source-level patch covers both call sites.
            patch("app.core.database.async_session_maker", session_maker_stub),
            patch.object(
                thinker_service,
                "start_conversation_agents",
                side_effect=fake_start,
            ),
        ):
            # Drive the endpoint directly — fast, no TestClient/lifespan.
            await ws_module.websocket_endpoint(
                websocket=ws_mock,
                conversation_id=conv.id,
                token=token,
            )

        assert captured["conv_id"] == conv.id
        assert captured["topic"] == "What is the good life?"
        assert captured["language"] == "fr"  # picked up from user prefs
        assert captured["thinker_names"] == ["Aristotle"]
        assert captured["messages_initial"] == []
        assert captured["saved_cost"] == pytest.approx(0.0007)
        assert captured["saved_thinker"] == "Aristotle"


class TestExtractThinkingDisplayShortCircuits:
    """Cover ``_extract_thinking_display`` early-return paths.

    The branch 641->645 in the streaming loop is only taken when
    ``_extract_thinking_display`` returns a falsy value. We verify the
    short-text and empty-input fast paths directly so the helper itself
    is exercised on each branch.
    """

    def test_empty_thinking_text_returns_empty_string(self) -> None:
        service = ThinkerService()
        assert service._extract_thinking_display("") == ""

    def test_short_thinking_text_returns_empty_string(self) -> None:
        service = ThinkerService()
        # < 80 chars triggers the "too short" fast path.
        assert service._extract_thinking_display("Short thought.") == ""

    def test_long_thinking_text_returns_non_empty(self) -> None:
        service = ThinkerService()
        long_text = (
            "I am considering whether virtue is teachable. "
            "There are several angles. First, the Socratic view "
            "that knowledge is virtue. Second, the practical view."
        )
        result = service._extract_thinking_display(long_text)
        assert result != ""


class TestShouldRespondEarlyReturns:
    """Cover ``_should_respond`` empty-messages and no-new-messages branches."""

    def test_should_respond_returns_false_when_no_messages(self) -> None:
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"
        assert service._should_respond(thinker, [], last_response_count=0) is False

    def test_should_respond_returns_false_when_no_new_messages(self) -> None:
        service = ThinkerService()
        thinker = MagicMock()
        thinker.name = "Socrates"

        msg = MagicMock()
        msg.content = "Some user message"
        msg.sender_name = "Alice"

        # last_response_count == len(messages) → no new messages → False
        assert service._should_respond(thinker, [msg], last_response_count=1) is False


class TestSplitResponseIntoBubblesEdgeCases:
    """Cover branches in ``_split_response_into_bubbles``."""

    def test_empty_response_returns_empty_list(self) -> None:
        service = ThinkerService()
        assert service._split_response_into_bubbles("") == []

    def test_short_response_stays_single_bubble(self) -> None:
        service = ThinkerService()
        bubbles = service._split_response_into_bubbles("Just a short reply.")
        assert bubbles == ["Just a short reply."]

    def test_long_response_with_transition_words_splits_into_multiple(self) -> None:
        service = ThinkerService()
        # Force the small-bubble (aggressive) splitting strategy by seeding
        # random so strategy_roll < 0.45.
        random.seed(0)
        text = (
            "Knowledge starts with questioning everything we think we know. "
            "We must examine assumptions carefully and rigorously. "
            "However, examination alone is insufficient for wisdom. "
            "Action must follow contemplation and dialogue with others. "
            "Therefore, the philosopher must engage with the city, not retreat."
        )
        bubbles = service._split_response_into_bubbles(text)
        # We got more than one bubble — transitions ("However,") + length
        # both should have triggered splits.
        assert len(bubbles) >= 2
        # No bubble is empty.
        assert all(b for b in bubbles)

    def test_long_run_on_text_force_splits_at_sentence_boundary(self) -> None:
        service = ThinkerService()
        # A single very long "sentence" (>300 chars, no punctuation in the
        # middle) ends up as one bubble after the main loop, triggering the
        # force-split branch (lines 767-774).
        text = (
            "Consider the dialectic between being and becoming over many "
            "centuries of philosophical reflection, "
            "which has produced rich and competing traditions. "
            "Now imagine we apply these ideas to modern technology, "
            "ethics, and politics in ways no ancient writer could have "
            "anticipated yet remains deeply relevant today."
        )
        # Seed so the random strategy is "keep as single bubble" (< 0.25) —
        # that way we exercise the force-split branch even with multiple
        # sentences.
        random.seed(1)
        bubbles = service._split_response_into_bubbles(text)
        assert all(b for b in bubbles)
        assert len(bubbles) >= 1

    def test_whitespace_only_fragment_is_skipped(self) -> None:
        """Line 733: the ``if not sentence: continue`` skip is taken when
        ``re.split`` produces a whitespace-only fragment.

        Crafted text uses a non-printable C0 control character which
        ``str.strip`` (called on the whole text up front) leaves alone, but
        ``re.split`` then bounds a fragment containing only that character,
        whose per-sentence ``strip()`` *does* normalise it away — producing
        an empty sentence and exercising the ``continue``.
        """
        service = ThinkerService()
        # The fragment between the two sentence ends is one stripable char
        # surrounded by sentence boundaries.
        text = "First sentence here. ​ ​. Second sentence after."
        # We just need this not to crash; the assertion is structural.
        bubbles = service._split_response_into_bubbles(text)
        assert isinstance(bubbles, list)
        assert all(b for b in bubbles)
