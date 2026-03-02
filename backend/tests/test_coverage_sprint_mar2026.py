"""Coverage Sprint - March 2026 (Monday Focus).

Target files:
  - app/core/database.py (43%) → aim 85%+
  - app/main.py (60%)         → aim 85%+
  - app/core/config.py (72%)  → aim 100%

Tests cover: async_session commit/rollback, get_db rollback, run_migrations
(found / not-found), init_db (success / no-ini / migration-failure), close_db,
create_admin_user (create / skip), health_ready DB-failure path,
and sync_database_url property branches.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# app/core/database.py — async_session
# ---------------------------------------------------------------------------


class TestDatabaseAsyncSession:
    """Tests for the async_session context manager in database.py."""

    async def test_async_session_commits_on_success(self) -> None:
        """async_session commits the transaction when no exception is raised."""
        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_maker = MagicMock(return_value=mock_cm)

        # Import the context-manager function with an alias to avoid collision
        # with the conftest `async_session` fixture.
        from app.core.database import async_session as db_async_session

        with patch("app.core.database.async_session_maker", mock_maker):
            async with db_async_session() as session:
                assert session is mock_session
            mock_session.commit.assert_called_once()
            mock_session.rollback.assert_not_called()

    async def test_async_session_rollbacks_on_exception(self) -> None:
        """async_session rolls back and re-raises when an exception occurs."""
        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_maker = MagicMock(return_value=mock_cm)

        from app.core.database import async_session as db_async_session

        with (
            patch("app.core.database.async_session_maker", mock_maker),
            pytest.raises(ValueError, match="boom"),
        ):
            async with db_async_session() as _session:
                raise ValueError("boom")

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# app/core/database.py — get_db
# ---------------------------------------------------------------------------


class TestGetDb:
    """Tests for the get_db async-generator dependency."""

    async def test_get_db_rollback_on_exception(self) -> None:
        """get_db rolls back when an exception is thrown into the generator."""
        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_maker = MagicMock(return_value=mock_cm)

        from app.core.database import get_db

        with patch("app.core.database.async_session_maker", mock_maker):
            gen = get_db()
            await gen.__anext__()  # advance to the yield
            with pytest.raises(RuntimeError):
                await gen.athrow(RuntimeError("db error"))

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()

    async def test_get_db_commits_on_success(self) -> None:
        """get_db commits when the caller exits normally."""
        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_maker = MagicMock(return_value=mock_cm)

        from app.core.database import get_db

        with patch("app.core.database.async_session_maker", mock_maker):
            gen = get_db()
            session = await gen.__anext__()
            assert session is mock_session
            # Exhaust the generator (normal exit)
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()


# ---------------------------------------------------------------------------
# app/core/database.py — run_migrations
# ---------------------------------------------------------------------------


class TestRunMigrations:
    """Tests for the synchronous run_migrations helper."""

    def test_returns_false_when_alembic_ini_missing(self) -> None:
        """run_migrations returns False when alembic.ini is not found."""
        with patch.object(Path, "exists", return_value=False):
            from app.core.database import run_migrations

            result = run_migrations()

        assert result is False

    def test_returns_true_when_migrations_succeed(self) -> None:
        """run_migrations returns True and calls alembic upgrade on success."""
        with (
            patch("app.core.database.command.upgrade") as mock_upgrade,
            patch.object(Path, "exists", return_value=True),
        ):
            from app.core.database import run_migrations

            result = run_migrations()

        assert result is True
        mock_upgrade.assert_called_once()

    def test_upgrades_to_head_revision(self) -> None:
        """run_migrations always upgrades to the 'head' revision."""
        with (
            patch("app.core.database.command.upgrade") as mock_upgrade,
            patch.object(Path, "exists", return_value=True),
        ):
            from app.core.database import run_migrations

            run_migrations()

        _cfg, revision = mock_upgrade.call_args[0]
        assert revision == "head"


# ---------------------------------------------------------------------------
# app/core/database.py — init_db
# ---------------------------------------------------------------------------


class TestInitDb:
    """Tests for the async init_db startup function."""

    async def test_runs_migrations_when_ini_exists(self) -> None:
        """init_db calls run_migrations when alembic.ini is present."""
        with (
            patch("app.core.database.run_migrations") as mock_run,
            patch.object(Path, "exists", return_value=True),
        ):
            mock_run.return_value = True
            from app.core.database import init_db

            await init_db()

        mock_run.assert_called_once()

    async def test_falls_back_to_create_all_when_no_ini(self) -> None:
        """init_db falls back to create_all when alembic.ini is absent."""
        mock_conn = AsyncMock()
        mock_engine_cm = MagicMock()
        mock_engine_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.object(Path, "exists", return_value=False),
            patch("app.core.database.engine") as mock_engine,
        ):
            mock_engine.begin.return_value = mock_engine_cm
            from app.core.database import init_db

            await init_db()

        mock_conn.run_sync.assert_called_once()

    async def test_falls_back_to_create_all_when_migrations_fail(self) -> None:
        """init_db uses create_all when run_migrations raises an exception."""
        mock_conn = AsyncMock()
        mock_engine_cm = MagicMock()
        mock_engine_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "app.core.database.run_migrations",
                side_effect=Exception("migration failed"),
            ),
            patch.object(Path, "exists", return_value=True),
            patch("app.core.database.engine") as mock_engine,
        ):
            mock_engine.begin.return_value = mock_engine_cm
            from app.core.database import init_db

            await init_db()

        mock_conn.run_sync.assert_called_once()


# ---------------------------------------------------------------------------
# app/core/database.py — close_db
# ---------------------------------------------------------------------------


class TestCloseDb:
    """Tests for the close_db shutdown function."""

    async def test_close_db_disposes_engine(self) -> None:
        """close_db calls engine.dispose() to release all connections."""
        with patch("app.core.database.engine") as mock_engine:
            mock_engine.dispose = AsyncMock()
            from app.core.database import close_db

            await close_db()

        mock_engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# app/main.py — create_admin_user
# ---------------------------------------------------------------------------


class TestCreateAdminUser:
    """Tests for create_admin_user in main.py."""

    async def test_creates_admin_when_not_exists(
        self,
        db_session: object,
    ) -> None:
        """create_admin_user inserts an admin User when none exists."""
        from sqlalchemy import select

        from app.models import User

        @asynccontextmanager  # type: ignore[misc]
        async def _mock_session() -> object:
            yield db_session

        with patch("app.main.async_session", _mock_session):
            from app.main import create_admin_user

            await create_admin_user()

        result = await db_session.execute(  # type: ignore[union-attr]
            select(User).where(User.username == "admin")
        )
        admin = result.scalar_one_or_none()
        assert admin is not None
        assert admin.is_admin is True

    async def test_skips_creation_when_admin_exists(
        self,
        db_session: object,
    ) -> None:
        """create_admin_user does not create a duplicate admin user."""
        from sqlalchemy import func, select

        from app.core.auth import get_password_hash
        from app.models import User

        # Pre-populate an admin user
        existing_admin = User(
            username="admin",
            password_hash=get_password_hash("admin"),
            is_admin=True,
        )
        db_session.add(existing_admin)  # type: ignore[union-attr]
        await db_session.commit()  # type: ignore[union-attr]

        @asynccontextmanager  # type: ignore[misc]
        async def _mock_session() -> object:
            yield db_session

        with patch("app.main.async_session", _mock_session):
            from app.main import create_admin_user

            await create_admin_user()

        result = await db_session.execute(  # type: ignore[union-attr]
            select(func.count()).where(User.username == "admin")  # type: ignore[arg-type]
        )
        count = result.scalar()
        assert count == 1


# ---------------------------------------------------------------------------
# app/main.py — health_ready error path
# ---------------------------------------------------------------------------


class TestHealthReadyDbFailure:
    """Tests for the degraded path in /health/ready."""

    async def test_returns_503_when_db_execute_fails(
        self,
        client: AsyncClient,
    ) -> None:
        """health_ready returns HTTP 503 when the database check raises."""
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.core.database import get_db
        from app.main import app

        async def _failing_db() -> object:
            mock_sess = AsyncMock(spec=AsyncSession)
            mock_sess.execute.side_effect = Exception("connection refused")
            yield mock_sess

        # Temporarily override the DB dependency with a failing one
        app.dependency_overrides[get_db] = _failing_db
        try:
            response = await client.get("/health/ready")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert "database" in body["checks"]
        assert body["checks"]["database"].startswith("error:")


# ---------------------------------------------------------------------------
# app/main.py — lifespan (startup + shutdown)
# ---------------------------------------------------------------------------


class TestLifespan:
    """Tests for the FastAPI lifespan context-manager in main.py."""

    async def test_lifespan_calls_init_and_close_db(self) -> None:
        """lifespan calls init_db on startup and close_db on shutdown."""
        from app.main import app, lifespan

        with (
            patch("app.main.init_db", new_callable=AsyncMock) as mock_init,
            patch("app.main.create_admin_user", new_callable=AsyncMock) as mock_create,
            patch("app.main.close_db", new_callable=AsyncMock) as mock_close,
        ):
            async with lifespan(app):
                pass

        mock_init.assert_called_once()
        mock_create.assert_called_once()
        mock_close.assert_called_once()

    async def test_lifespan_propagates_startup_exception(self) -> None:
        """lifespan re-raises if init_db fails so the process can fail fast."""
        from app.main import app, lifespan

        with (
            patch(
                "app.main.init_db",
                new_callable=AsyncMock,
                side_effect=RuntimeError("db down"),
            ),
            pytest.raises(RuntimeError, match="db down"),
        ):
            async with lifespan(app):
                pass  # pragma: no cover — startup should raise before yield


# ---------------------------------------------------------------------------
# app/core/config.py — sync_database_url branches
# ---------------------------------------------------------------------------


class TestSyncDatabaseUrl:
    """Tests for the sync_database_url property in config.py."""

    def test_asyncpg_url_converted_to_sync(self) -> None:
        """postgresql+asyncpg:// is converted to postgresql:// for Alembic."""
        from app.core.config import Settings

        s = Settings(database_url="postgresql+asyncpg://user:pass@host:5432/db")
        assert s.sync_database_url == "postgresql://user:pass@host:5432/db"

    def test_aiosqlite_url_converted_to_sync(self) -> None:
        """sqlite+aiosqlite:// is converted to sqlite:// for Alembic."""
        from app.core.config import Settings

        s = Settings(database_url="sqlite+aiosqlite:///./test.db")
        assert s.sync_database_url == "sqlite:///./test.db"

    def test_postgres_url_converted_to_postgresql(self) -> None:
        """postgres:// (Railway shorthand) becomes postgresql:// for Alembic."""
        from app.core.config import Settings

        s = Settings(database_url="postgres://user:pass@host:5432/db")
        assert s.sync_database_url == "postgresql://user:pass@host:5432/db"

    def test_plain_postgresql_url_unchanged(self) -> None:
        """A URL already using postgresql:// passes through unchanged."""
        from app.core.config import Settings

        s = Settings(database_url="postgresql://user:pass@host:5432/db")
        assert s.sync_database_url == "postgresql://user:pass@host:5432/db"

    def test_other_url_passthrough(self) -> None:
        """Unrecognised URL schemes are returned as-is."""
        from app.core.config import Settings

        s = Settings(database_url="mysql+aiomysql://user:pass@host:3306/db")
        assert s.sync_database_url == "mysql+aiomysql://user:pass@host:3306/db"
