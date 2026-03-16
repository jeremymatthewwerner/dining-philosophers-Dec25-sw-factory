"""Coverage sprint tests - Mar 16, 2026 (Monday QA).

Targeting the lowest-coverage modules:
- app/core/database.py (43%)
- app/main.py (60%)
- app/api/websocket.py (66%)
- app/core/config.py (72%)

Relates to #753
"""

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import (
    ConnectionManager,
    ConversationRoom,
    SpendLimitExceeded,
    WSMessage,
    WSMessageType,
    get_messages_for_conversation,
    save_thinker_message,
)
from app.core.config import Settings

# =============================================================================
# app/core/config.py - sync_database_url property (lines 35-44, currently 72%)
# =============================================================================


class TestSyncDatabaseUrl:
    """Tests for the sync_database_url property."""

    def test_sqlite_aiosqlite_converts_to_sync(self) -> None:
        """sqlite+aiosqlite:// should be converted to sqlite:// for Alembic."""
        settings = Settings(database_url="sqlite+aiosqlite:///./test.db")
        assert settings.sync_database_url == "sqlite:///./test.db"

    def test_postgresql_asyncpg_converts_to_sync(self) -> None:
        """postgresql+asyncpg:// should be converted to postgresql:// for Alembic."""
        settings = Settings(database_url="postgresql+asyncpg://user:pass@host:5432/db")
        assert settings.sync_database_url == "postgresql://user:pass@host:5432/db"

    def test_postgres_shorthand_converts_to_postgresql(self) -> None:
        """postgres:// (Railway short form) should be converted to postgresql:// for Alembic."""
        settings = Settings(database_url="postgres://user:pass@host:5432/db")
        assert settings.sync_database_url == "postgresql://user:pass@host:5432/db"

    def test_plain_postgresql_url_unchanged(self) -> None:
        """postgresql:// (no asyncpg) should pass through unchanged."""
        settings = Settings(database_url="postgresql://user:pass@host:5432/db")
        assert settings.sync_database_url == "postgresql://user:pass@host:5432/db"

    def test_memory_sqlite_converts_to_sync(self) -> None:
        """In-memory SQLite aiosqlite URL converts correctly."""
        settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
        assert settings.sync_database_url == "sqlite:///:memory:"

    def test_default_database_url_has_correct_sync_form(self) -> None:
        """Default SQLite URL (sqlite+aiosqlite) converts to sync form."""
        settings = Settings()
        sync_url = settings.sync_database_url
        assert "aiosqlite" not in sync_url
        assert sync_url.startswith("sqlite://")


# =============================================================================
# app/core/database.py - async_session, get_db, init_db, close_db (43%)
# =============================================================================


class TestAsyncSessionContextManager:
    """Tests for the async_session context manager in database.py."""

    async def test_async_session_yields_session(self) -> None:
        """async_session context manager should yield a usable AsyncSession."""
        from app.core.database import async_session

        async with async_session() as db:
            assert db is not None
            assert isinstance(db, AsyncSession)

    async def test_async_session_commits_on_success(self) -> None:
        """async_session should commit on successful exit."""
        from app.core.database import async_session

        # If commit is called without error, session should complete cleanly
        async with async_session() as db:
            result = await db.execute(text("SELECT 1"))
            assert result is not None

    async def test_async_session_rolls_back_on_exception(self) -> None:
        """async_session should rollback on exception and re-raise."""
        from app.core.database import async_session

        with pytest.raises(ValueError, match="test error"):
            async with async_session() as db:
                assert db is not None
                raise ValueError("test error")


class TestGetDb:
    """Tests for the get_db dependency generator."""

    async def test_get_db_yields_session(self) -> None:
        """get_db should yield an AsyncSession instance."""
        import contextlib

        from app.core.database import get_db

        gen = get_db()
        try:
            db = await gen.__anext__()
            assert db is not None
            assert isinstance(db, AsyncSession)
        finally:
            with contextlib.suppress(Exception):
                await gen.aclose()


class TestRunMigrations:
    """Tests for the run_migrations function."""

    def test_run_migrations_returns_false_when_no_alembic_ini(self, tmp_path: Path) -> None:
        """run_migrations should return False when alembic.ini is not found."""
        from app.core.database import run_migrations

        # Mock the backend_dir so it points to tmp_path which has no alembic.ini
        fake_ini = tmp_path / "alembic.ini"
        assert not fake_ini.exists()

        with patch("app.core.database.Path") as mock_path_cls:
            # __file__ in database.py resolves to a Path; we need parent.parent.parent = tmp_path
            mock_file_path = MagicMock()
            mock_file_path.parent.parent.parent = tmp_path
            mock_path_cls.return_value = mock_file_path

            result = run_migrations()
            assert result is False

    def test_run_migrations_succeeds_with_valid_alembic_ini(self) -> None:
        """run_migrations should call alembic command.upgrade when alembic.ini exists."""
        from app.core.database import run_migrations

        with patch("app.core.database.command.upgrade") as mock_upgrade:
            # The real alembic.ini exists in the repo
            result = run_migrations()
            assert result is True
            mock_upgrade.assert_called_once()


class TestInitDb:
    """Tests for the init_db function."""

    async def test_init_db_uses_migrations_when_alembic_ini_exists(self) -> None:
        """init_db should call run_migrations when alembic.ini exists."""
        from app.core.database import init_db

        with patch("app.core.database.run_migrations") as mock_run:
            mock_run.return_value = True
            await init_db()
            mock_run.assert_called_once()

    async def test_init_db_falls_back_to_create_all_when_migrations_fail(self) -> None:
        """init_db should fall back to create_all if run_migrations raises."""
        from app.core.database import init_db

        with (
            patch("app.core.database.run_migrations", side_effect=Exception("migration failed")),
            patch("app.core.database.engine") as mock_engine,
        ):
            mock_conn = AsyncMock()
            mock_conn.run_sync = AsyncMock()
            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_engine.begin.return_value = mock_ctx

            await init_db()
            # Should have called create_all via run_sync
            mock_conn.run_sync.assert_called_once()


class TestCloseDb:
    """Tests for the close_db function."""

    async def test_close_db_disposes_engine(self) -> None:
        """close_db should call engine.dispose()."""
        from app.core.database import close_db

        with patch("app.core.database.engine") as mock_engine:
            mock_engine.dispose = AsyncMock()
            await close_db()
            mock_engine.dispose.assert_called_once()


# =============================================================================
# app/main.py - create_admin_user and lifespan (60%)
# =============================================================================


class TestCreateAdminUser:
    """Tests for the create_admin_user function in main.py."""

    async def test_creates_admin_user_when_not_exists(self) -> None:
        """create_admin_user should create the admin user if not present."""
        from app.main import create_admin_user

        # Mock the async_session to control the DB interaction
        mock_db = AsyncMock(spec=AsyncSession)
        # Simulate no admin user found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_db)
        mock_context.__aexit__ = AsyncMock(return_value=False)

        with patch("app.main.async_session", return_value=mock_context):
            await create_admin_user()

        # Should have called db.add with the new admin user
        mock_db.add.assert_called_once()

    async def test_skips_creation_when_admin_already_exists(self) -> None:
        """create_admin_user should not create admin if one already exists."""
        from app.main import create_admin_user
        from app.models import User

        mock_db = AsyncMock(spec=AsyncSession)
        existing_admin = User(username="admin", password_hash="hash", is_admin=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_admin
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_db)
        mock_context.__aexit__ = AsyncMock(return_value=False)

        with patch("app.main.async_session", return_value=mock_context):
            await create_admin_user()

        # Should NOT have called db.add since admin already exists
        mock_db.add.assert_not_called()


class TestHealthReadyDbError:
    """Tests for the /health/ready endpoint database error path."""

    async def test_health_ready_returns_503_on_db_error(self) -> None:
        """health_ready should return 503 when database check fails."""

        from httpx import ASGITransport, AsyncClient

        from app.core.database import get_db
        from app.main import app

        async def broken_db() -> AsyncGenerator[AsyncSession, None]:
            mock_db = AsyncMock(spec=AsyncSession)
            mock_db.execute = AsyncMock(side_effect=Exception("DB connection failed"))
            yield mock_db

        app.dependency_overrides[get_db] = broken_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "degraded"
            assert "database" in data["checks"]
            assert "error" in data["checks"]["database"]
        finally:
            app.dependency_overrides.clear()

    async def test_health_ready_returns_200_on_db_success(self) -> None:
        """health_ready should return 200 when database check succeeds."""

        from httpx import ASGITransport, AsyncClient

        from app.core.database import get_db
        from app.main import app

        async def working_db() -> AsyncGenerator[AsyncSession, None]:
            mock_db = AsyncMock(spec=AsyncSession)
            mock_db.execute = AsyncMock(return_value=MagicMock())
            yield mock_db

        app.dependency_overrides[get_db] = working_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert data["checks"]["database"] == "ok"
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# app/api/websocket.py - ConnectionManager methods (66%)
# =============================================================================


class TestConversationRoom:
    """Tests for the ConversationRoom dataclass."""

    async def test_add_connection_sets_active(self) -> None:
        """Adding a connection should mark room as active."""
        room = ConversationRoom(conversation_id="conv-1")
        assert room.is_active is False

        mock_ws = AsyncMock()
        room.add_connection(mock_ws)
        assert room.is_active is True
        assert mock_ws in room.connections

    def test_remove_connection_deactivates_when_empty(self) -> None:
        """Removing last connection should deactivate room."""
        room = ConversationRoom(conversation_id="conv-1")
        mock_ws = MagicMock()
        room.connections.add(mock_ws)
        room.is_active = True

        room.remove_connection(mock_ws)
        assert room.is_active is False
        assert mock_ws not in room.connections

    def test_remove_nonexistent_connection_is_safe(self) -> None:
        """Removing a connection that isn't in room should not raise."""
        room = ConversationRoom(conversation_id="conv-1")
        mock_ws = MagicMock()
        room.remove_connection(mock_ws)  # should not raise

    async def test_broadcast_skips_failed_connections(self) -> None:
        """Broadcast should remove connections that fail to send."""
        room = ConversationRoom(conversation_id="conv-1")

        good_ws = AsyncMock()
        bad_ws = AsyncMock()
        bad_ws.send_text = AsyncMock(side_effect=Exception("connection dropped"))

        room.connections.add(good_ws)
        room.connections.add(bad_ws)
        room.is_active = True

        message = WSMessage(type=WSMessageType.MESSAGE, content="hello")
        await room.broadcast(message)

        # Bad connection should be removed
        assert bad_ws not in room.connections
        # Good connection should still be there
        assert good_ws in room.connections

    async def test_broadcast_deactivates_when_all_connections_fail(self) -> None:
        """Broadcast with all connections failing should deactivate room."""
        room = ConversationRoom(conversation_id="conv-1")

        bad_ws = AsyncMock()
        bad_ws.send_text = AsyncMock(side_effect=Exception("dropped"))
        room.connections.add(bad_ws)
        room.is_active = True

        message = WSMessage(type=WSMessageType.MESSAGE, content="hello")
        await room.broadcast(message)

        assert room.is_active is False


class TestConnectionManagerMethods:
    """Tests for ConnectionManager methods beyond basic initialization."""

    async def test_connect_creates_room_if_not_exists(self) -> None:
        """connect() should create a new room if none exists for the conversation."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()

        await manager.connect(mock_ws, "new-conv-id")

        assert "new-conv-id" in manager.rooms
        assert manager.is_conversation_active("new-conv-id")
        mock_ws.accept.assert_called_once()

    async def test_disconnect_removes_connection(self) -> None:
        """disconnect() should remove connection from room."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()

        await manager.connect(mock_ws, "conv-disconnect")
        assert manager.is_conversation_active("conv-disconnect")

        await manager.disconnect(mock_ws, "conv-disconnect")
        assert not manager.is_conversation_active("conv-disconnect")

    async def test_disconnect_nonexistent_conversation_is_safe(self) -> None:
        """disconnect() on a nonexistent conversation ID should not raise."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.disconnect(mock_ws, "does-not-exist")  # should not raise

    def test_get_speed_multiplier_returns_default_for_unknown(self) -> None:
        """get_speed_multiplier returns 1.0 for unknown conversations."""
        manager = ConnectionManager()
        assert manager.get_speed_multiplier("unknown-conv") == 1.0

    def test_get_speed_multiplier_returns_room_value(self) -> None:
        """get_speed_multiplier returns the room's multiplier."""
        manager = ConnectionManager()
        manager.rooms["conv-speed"] = ConversationRoom(
            conversation_id="conv-speed", speed_multiplier=2.5
        )
        assert manager.get_speed_multiplier("conv-speed") == 2.5

    async def test_set_speed_multiplier_clamps_to_minimum(self) -> None:
        """set_speed_multiplier should clamp values below 0.5 to 0.5."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-clamp-min")
        # Clear the accept/join messages
        mock_ws.reset_mock()

        await manager.set_speed_multiplier("conv-clamp-min", 0.1)
        assert manager.rooms["conv-clamp-min"].speed_multiplier == 0.5

    async def test_set_speed_multiplier_clamps_to_maximum(self) -> None:
        """set_speed_multiplier should clamp values above 6.0 to 6.0."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-clamp-max")
        mock_ws.reset_mock()

        await manager.set_speed_multiplier("conv-clamp-max", 100.0)
        assert manager.rooms["conv-clamp-max"].speed_multiplier == 6.0

    async def test_set_speed_multiplier_broadcasts_speed_changed(self) -> None:
        """set_speed_multiplier should broadcast SPEED_CHANGED to all clients."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-speed-broadcast")
        mock_ws.reset_mock()

        await manager.set_speed_multiplier("conv-speed-broadcast", 2.0)

        # Should have sent a SPEED_CHANGED message
        mock_ws.send_text.assert_called_once()
        import json

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "speed_changed"
        assert data["speed_multiplier"] == 2.0

    async def test_set_speed_multiplier_noop_for_unknown_conversation(self) -> None:
        """set_speed_multiplier should not raise for unknown conversation."""
        manager = ConnectionManager()
        # Should not raise even if conversation room doesn't exist
        await manager.set_speed_multiplier("nonexistent-conv", 1.5)

    async def test_send_thinker_message_broadcasts_correctly(self) -> None:
        """send_thinker_message should broadcast a MESSAGE type to connected clients."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-thinker-msg")
        mock_ws.reset_mock()

        await manager.send_thinker_message(
            conversation_id="conv-thinker-msg",
            thinker_name="Socrates",
            content="What is the good life?",
            message_id="msg-001",
            cost=0.01,
        )

        mock_ws.send_text.assert_called_once()
        import json

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "message"
        assert data["sender_name"] == "Socrates"
        assert data["content"] == "What is the good life?"
        assert data["cost"] == 0.01
        assert data["sender_type"] == "thinker"

    async def test_send_thinker_typing_adds_to_typing_set(self) -> None:
        """send_thinker_typing should add thinker to typing_thinkers set."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-typing")
        mock_ws.reset_mock()

        await manager.send_thinker_typing("conv-typing", "Aristotle")

        assert "Aristotle" in manager.rooms["conv-typing"].typing_thinkers

    async def test_send_thinker_stopped_typing_removes_from_set(self) -> None:
        """send_thinker_stopped_typing should remove thinker from typing_thinkers."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-stopped-typing")
        manager.rooms["conv-stopped-typing"].typing_thinkers.add("Plato")
        mock_ws.reset_mock()

        await manager.send_thinker_stopped_typing("conv-stopped-typing", "Plato")

        assert "Plato" not in manager.rooms["conv-stopped-typing"].typing_thinkers

    async def test_send_thinker_thinking_broadcasts_content(self) -> None:
        """send_thinker_thinking should broadcast THINKER_THINKING with content."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-thinking")
        mock_ws.reset_mock()

        await manager.send_thinker_thinking("conv-thinking", "Kant", "About ethics...")

        import json

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "thinker_thinking"
        assert data["sender_name"] == "Kant"
        assert data["content"] == "About ethics..."

    async def test_send_research_started_broadcasts_event(self) -> None:
        """send_research_started should broadcast RESEARCH_STARTED with thinker_name."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-research")
        mock_ws.reset_mock()

        await manager.send_research_started("conv-research", "Nietzsche")

        import json

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "research_started"
        assert data["thinker_name"] == "Nietzsche"

    async def test_send_research_complete_broadcasts_event(self) -> None:
        """send_research_complete should broadcast RESEARCH_COMPLETE."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-research-done")
        mock_ws.reset_mock()

        await manager.send_research_complete("conv-research-done", "Hegel")

        import json

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "research_complete"
        assert data["thinker_name"] == "Hegel"

    async def test_send_research_failed_broadcasts_with_error(self) -> None:
        """send_research_failed should broadcast RESEARCH_FAILED with error content."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-research-fail")
        mock_ws.reset_mock()

        await manager.send_research_failed("conv-research-fail", "Wittgenstein", "timeout")

        import json

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "research_failed"
        assert data["thinker_name"] == "Wittgenstein"
        assert data["content"] == "timeout"

    async def test_send_cache_hit_broadcasts_event(self) -> None:
        """send_cache_hit should broadcast CACHE_HIT with thinker_name."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        await manager.connect(mock_ws, "conv-cache")
        mock_ws.reset_mock()

        await manager.send_cache_hit("conv-cache", "Descartes")

        import json

        data = json.loads(mock_ws.send_text.call_args[0][0])
        assert data["type"] == "cache_hit"
        assert data["thinker_name"] == "Descartes"


class TestWebSocketAuthentication:
    """Tests for WebSocket authentication handling."""

    def test_websocket_rejects_missing_token(self) -> None:
        """WebSocket should close with 4001 when no token is provided."""
        from starlette.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect

        from app.main import app

        with (
            TestClient(app) as client,
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect("/ws/test-conv-no-token"),
        ):
            pass

    def test_websocket_rejects_invalid_token(self) -> None:
        """WebSocket should close with 4001 when token is invalid."""
        from starlette.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect

        from app.main import app

        with (
            TestClient(app) as client,
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect("/ws/test-conv-bad-token?token=not-a-real-token"),
        ):
            pass


class TestSpendLimitExceeded:
    """Tests for the SpendLimitExceeded exception."""

    def test_spend_limit_exceeded_message(self) -> None:
        """SpendLimitExceeded should produce readable message."""
        exc = SpendLimitExceeded(current_spend=5.50, spend_limit=5.00)
        assert "5.50" in str(exc)
        assert "5.00" in str(exc)
        assert exc.current_spend == 5.50
        assert exc.spend_limit == 5.00

    async def test_save_thinker_message_raises_when_spend_limit_exceeded(
        self, db_session: AsyncSession
    ) -> None:
        """save_thinker_message should raise SpendLimitExceeded if limit is hit."""
        from app.models import User
        from tests.conftest import create_test_user_session_conversation

        user, session, conversation = await create_test_user_session_conversation(db_session)

        # Set user at or above their spend limit
        from sqlalchemy import select

        result = await db_session.execute(select(User).where(User.id == user.id))
        db_user = result.scalar_one()
        db_user.spend_limit = 1.00
        db_user.total_spend = 1.00  # exactly at limit
        await db_session.commit()

        with pytest.raises(SpendLimitExceeded):
            await save_thinker_message(
                conversation_id=conversation.id,
                thinker_name="Socrates",
                content="Should not save",
                cost=0.01,
                db=db_session,
            )


class TestGetMessagesForConversation:
    """Tests for the get_messages_for_conversation helper."""

    async def test_get_messages_returns_empty_list_for_new_conversation(
        self, db_session: AsyncSession
    ) -> None:
        """Should return empty list when no messages exist."""
        messages = await get_messages_for_conversation("nonexistent-conv-id", db_session)
        assert list(messages) == []

    async def test_get_messages_returns_messages_in_order(self, db_session: AsyncSession) -> None:
        """Should return messages ordered by created_at."""
        from app.models import Message
        from app.models.message import SenderType
        from tests.conftest import create_test_user_session_conversation

        _, _, conversation = await create_test_user_session_conversation(db_session)

        # Create two messages
        msg1 = Message(
            conversation_id=conversation.id,
            sender_type=SenderType.THINKER,
            sender_name="Socrates",
            content="First message",
            cost=0.01,
        )
        msg2 = Message(
            conversation_id=conversation.id,
            sender_type=SenderType.THINKER,
            sender_name="Plato",
            content="Second message",
            cost=0.02,
        )
        db_session.add(msg1)
        db_session.add(msg2)
        await db_session.commit()

        messages = await get_messages_for_conversation(conversation.id, db_session)
        message_list = list(messages)
        assert len(message_list) == 2
        assert message_list[0].content == "First message"
        assert message_list[1].content == "Second message"


class TestWebSocketSetSpeed:
    """Tests for the set_speed message type via WebSocket."""

    def test_set_speed_message_updates_multiplier(self) -> None:
        """Sending SET_SPEED message should update conversation speed."""

        from starlette.testclient import TestClient

        from app.core.auth import create_access_token
        from app.main import app

        token = create_access_token({"sub": "user-speed-test", "session_id": "session-speed"})

        with (
            TestClient(app) as client,
            client.websocket_connect(f"/ws/conv-set-speed-test?token={token}") as ws,
        ):
            ws.receive_json()  # user_joined
            ws.receive_json()  # resumed

            ws.send_json({"type": "set_speed", "speed_multiplier": 2.5})

            # Should receive speed_changed broadcast
            data = ws.receive_json()
            assert data["type"] == "speed_changed"
            assert data["speed_multiplier"] == 2.5
