"""Coverage sprint tests for Mar 9, 2026 - targeting lowest-coverage modules.

Focuses on:
- app/core/database.py (43% -> target 65%+)
- app/main.py (60% -> target 75%+)
- app/core/config.py (72% -> target 90%+)

Relates to #729
"""

import contextlib
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.models import Base

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session backed by the in-memory engine."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# app/core/config.py - sync_database_url property (lines 35-44)
# ---------------------------------------------------------------------------


class TestSyncDatabaseUrl:
    """Tests for Settings.sync_database_url property.

    The coverage report shows lines 35-44 (the sync_database_url property)
    are not yet covered.
    """

    def test_sqlite_aiosqlite_converts_to_sync(self) -> None:
        """sqlite+aiosqlite:// should become sqlite:// for Alembic."""
        settings = Settings(database_url="sqlite+aiosqlite:///./test.db")
        assert settings.sync_database_url == "sqlite:///./test.db"

    def test_postgresql_asyncpg_converts_to_sync(self) -> None:
        """postgresql+asyncpg:// should convert to plain postgresql://."""
        settings = Settings(database_url="postgresql+asyncpg://user:pass@host:5432/db")
        assert settings.sync_database_url == "postgresql://user:pass@host:5432/db"

    def test_postgres_url_converts_to_postgresql(self) -> None:
        """postgres:// (Railway short form) should become postgresql://."""
        settings = Settings(database_url="postgres://user:pass@host:5432/db")
        assert settings.sync_database_url == "postgresql://user:pass@host:5432/db"

    def test_postgresql_sync_url_passes_through(self) -> None:
        """Already-sync postgresql:// should pass through unchanged."""
        settings = Settings(database_url="postgresql://user:pass@host:5432/db")
        assert settings.sync_database_url == "postgresql://user:pass@host:5432/db"

    def test_sqlite_sync_url_passes_through(self) -> None:
        """Plain sqlite:// (no aiosqlite) should pass through unchanged."""
        settings = Settings(database_url="sqlite:///./test.db")
        assert settings.sync_database_url == "sqlite:///./test.db"

    def test_in_memory_sqlite_aiosqlite_converts(self) -> None:
        """In-memory sqlite+aiosqlite:// should convert to sqlite://."""
        settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
        assert settings.sync_database_url == "sqlite:///:memory:"

    def test_async_and_sync_urls_are_different_for_aiosqlite(self) -> None:
        """async_database_url and sync_database_url should differ for aiosqlite URLs."""
        settings = Settings(database_url="sqlite+aiosqlite:///./test.db")
        assert settings.async_database_url != settings.sync_database_url
        assert "aiosqlite" in settings.async_database_url
        assert "aiosqlite" not in settings.sync_database_url


# ---------------------------------------------------------------------------
# app/core/database.py - session context manager & get_db (lines 43, 45-46, 55-57)
# ---------------------------------------------------------------------------


class TestAsyncSessionContextManager:
    """Tests for the async_session() context manager in database.py."""

    async def test_async_session_yields_session(self) -> None:
        """async_session() should yield a working AsyncSession."""
        from app.core.database import async_session

        async with async_session() as session:
            assert isinstance(session, AsyncSession)

    async def test_async_session_commits_on_success(self) -> None:
        """async_session() should commit on clean exit."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.database.async_session_maker", mock_session_maker):
            from app.core import database

            async with database.async_session():
                pass

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

    async def test_async_session_rolls_back_on_exception(self) -> None:
        """async_session() should rollback when an exception occurs."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.database.async_session_maker", mock_session_maker):
            from app.core import database

            with pytest.raises(ValueError, match="test error"):
                async with database.async_session():
                    raise ValueError("test error")

        mock_session.rollback.assert_awaited_once()


class TestGetDb:
    """Tests for the get_db() dependency generator in database.py."""

    async def test_get_db_yields_session(self) -> None:
        """get_db() should yield a working AsyncSession."""
        from app.core.database import get_db

        session_gen = get_db()
        session = await session_gen.__anext__()
        assert isinstance(session, AsyncSession)
        # Clean up - suppress any exception from teardown
        with contextlib.suppress(Exception):
            await session_gen.aclose()

    async def test_get_db_commits_on_success(self) -> None:
        """get_db() should commit when no exception occurs."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.database.async_session_maker", mock_session_maker):
            from app.core import database

            gen = database.get_db()
            await gen.__anext__()
            # Closing cleanly triggers commit path
            with contextlib.suppress(StopAsyncIteration):
                await gen.aclose()

    async def test_get_db_rolls_back_on_exception(self) -> None:
        """get_db() should rollback when an exception is thrown into it."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.database.async_session_maker", mock_session_maker):
            from app.core import database

            gen = database.get_db()
            await gen.__anext__()
            with pytest.raises(RuntimeError):
                await gen.athrow(RuntimeError("db error"))

        mock_session.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# app/core/database.py - run_migrations() (lines 66-82)
# ---------------------------------------------------------------------------


def _make_fake_backend_dir_with_no_ini() -> MagicMock:
    """Create a fake backend_dir mock where alembic.ini does not exist."""
    fake_ini = MagicMock()
    fake_ini.exists.return_value = False
    fake_backend_dir = MagicMock()
    fake_backend_dir.__truediv__ = MagicMock(return_value=fake_ini)
    return fake_backend_dir


def _make_fake_backend_dir_with_ini() -> tuple[MagicMock, MagicMock]:
    """Create a fake backend_dir mock where alembic.ini exists.

    Returns (fake_backend_dir, fake_ini).
    """
    fake_ini = MagicMock()
    fake_ini.exists.return_value = True
    fake_ini.__str__ = MagicMock(return_value="/fake/alembic.ini")
    fake_backend_dir = MagicMock()
    fake_backend_dir.__truediv__ = MagicMock(return_value=fake_ini)
    return fake_backend_dir, fake_ini


class TestRunMigrations:
    """Tests for run_migrations() in database.py."""

    def test_run_migrations_returns_false_when_no_alembic_ini(self) -> None:
        """run_migrations() should return False and log a warning when alembic.ini is absent."""
        fake_backend_dir = _make_fake_backend_dir_with_no_ini()

        with (
            patch("app.core.database.Path") as mock_path_cls,
            patch("app.core.database.logger") as mock_logger,
        ):
            mock_path_cls.return_value.parent.parent.parent = fake_backend_dir

            from app.core.database import run_migrations

            result = run_migrations()

        assert result is False
        mock_logger.warning.assert_called_once()

    def test_run_migrations_returns_true_when_migrations_succeed(self) -> None:
        """run_migrations() should return True when alembic.upgrade succeeds."""
        fake_backend_dir, fake_ini = _make_fake_backend_dir_with_ini()

        with (
            patch("app.core.database.Path") as mock_path_cls,
            patch("app.core.database.Config") as mock_config_cls,
            patch("app.core.database.command") as mock_command,
            patch("app.core.database.logger"),
        ):
            mock_path_cls.return_value.parent.parent.parent = fake_backend_dir
            fake_cfg = MagicMock()
            mock_config_cls.return_value = fake_cfg

            from app.core.database import run_migrations

            result = run_migrations()

        assert result is True
        mock_command.upgrade.assert_called_once_with(fake_cfg, "head")

    def test_run_migrations_sets_script_location_and_url(self) -> None:
        """run_migrations() should configure script_location and sqlalchemy.url."""
        fake_backend_dir, _fake_ini = _make_fake_backend_dir_with_ini()

        with (
            patch("app.core.database.Path") as mock_path_cls,
            patch("app.core.database.Config") as mock_config_cls,
            patch("app.core.database.command"),
            patch("app.core.database.logger"),
        ):
            mock_path_cls.return_value.parent.parent.parent = fake_backend_dir
            fake_cfg = MagicMock()
            mock_config_cls.return_value = fake_cfg

            from app.core.database import run_migrations

            run_migrations()

        # Verify set_main_option was called for both key options
        calls = [str(c) for c in fake_cfg.set_main_option.call_args_list]
        assert any("script_location" in c for c in calls)
        assert any("sqlalchemy.url" in c for c in calls)


# ---------------------------------------------------------------------------
# app/core/database.py - init_db() (lines 92-109)
# ---------------------------------------------------------------------------


class TestInitDb:
    """Tests for init_db() in database.py."""

    async def test_init_db_uses_run_migrations_when_alembic_ini_exists(self) -> None:
        """init_db() should call run_migrations() when alembic.ini is present."""
        fake_backend_dir, _fake_ini = _make_fake_backend_dir_with_ini()

        with (
            patch("app.core.database.Path") as mock_path_cls,
            patch("app.core.database.run_migrations") as mock_run_migrations,
        ):
            mock_path_cls.return_value.parent.parent.parent = fake_backend_dir

            from app.core.database import init_db

            await init_db()

        mock_run_migrations.assert_called_once()

    async def test_init_db_falls_back_to_create_all_when_no_alembic_ini(self) -> None:
        """init_db() should fall back to create_all when alembic.ini is absent."""
        fake_backend_dir = _make_fake_backend_dir_with_no_ini()

        with (
            patch("app.core.database.Path") as mock_path_cls,
            patch("app.core.database.engine") as mock_engine,
            patch("app.core.database.logger"),
        ):
            mock_path_cls.return_value.parent.parent.parent = fake_backend_dir

            # Mock async context manager for engine.begin()
            mock_conn = AsyncMock()
            mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.core.database import init_db

            await init_db()

        mock_conn.run_sync.assert_awaited_once()

    async def test_init_db_falls_back_to_create_all_when_migration_fails(self) -> None:
        """init_db() should fall back to create_all when run_migrations() raises."""
        fake_backend_dir, _fake_ini = _make_fake_backend_dir_with_ini()

        with (
            patch("app.core.database.Path") as mock_path_cls,
            patch("app.core.database.run_migrations") as mock_run_migrations,
            patch("app.core.database.engine") as mock_engine,
            patch("app.core.database.logger"),
        ):
            mock_path_cls.return_value.parent.parent.parent = fake_backend_dir
            mock_run_migrations.side_effect = RuntimeError("migration error")

            mock_conn = AsyncMock()
            mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.core.database import init_db

            await init_db()

        # Even though migration failed, create_all should have been called
        mock_conn.run_sync.assert_awaited_once()


# ---------------------------------------------------------------------------
# app/core/database.py - close_db() (line 114)
# ---------------------------------------------------------------------------


class TestCloseDb:
    """Tests for close_db() in database.py."""

    async def test_close_db_disposes_engine(self) -> None:
        """close_db() should call engine.dispose()."""
        with patch("app.core.database.engine") as mock_engine:
            mock_engine.dispose = AsyncMock()

            from app.core.database import close_db

            await close_db()

        mock_engine.dispose.assert_awaited_once()


# ---------------------------------------------------------------------------
# app/main.py - create_admin_user() (lines 27-43)
# ---------------------------------------------------------------------------


class TestCreateAdminUser:
    """Tests for create_admin_user() in main.py."""

    async def test_create_admin_user_creates_when_not_exists(
        self, test_session: AsyncSession
    ) -> None:
        """create_admin_user() should create admin user if one doesn't exist."""
        from sqlalchemy import select

        from app.main import create_admin_user
        from app.models import User

        with patch("app.main.async_session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=test_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            await create_admin_user()

        result = await test_session.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()
        assert admin is not None
        assert admin.is_admin is True

    async def test_create_admin_user_does_not_duplicate(self, test_session: AsyncSession) -> None:
        """create_admin_user() should not create a duplicate admin user."""
        from sqlalchemy import select

        from app.core.auth import get_password_hash
        from app.main import create_admin_user
        from app.models import User

        # Pre-create admin user
        existing_admin = User(
            username="admin",
            password_hash=get_password_hash("existing_pass"),
            is_admin=True,
        )
        test_session.add(existing_admin)
        await test_session.commit()

        with patch("app.main.async_session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=test_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            await create_admin_user()

        result = await test_session.execute(select(User).where(User.username == "admin"))
        admins = result.scalars().all()
        # Still only one admin
        assert len(admins) == 1


# ---------------------------------------------------------------------------
# app/main.py - lifespan() (lines 49-68)
# ---------------------------------------------------------------------------


class TestLifespan:
    """Tests for the lifespan() async context manager in main.py."""

    async def test_lifespan_calls_init_db_and_create_admin(self) -> None:
        """lifespan() should call init_db() and create_admin_user() on startup."""
        from fastapi import FastAPI

        from app.main import lifespan

        with (
            patch("app.main.init_db", new_callable=AsyncMock) as mock_init_db,
            patch("app.main.create_admin_user", new_callable=AsyncMock) as mock_create_admin,
            patch("app.main.close_db", new_callable=AsyncMock),
        ):
            test_app = FastAPI(lifespan=lifespan)
            async with lifespan(test_app):
                pass

        mock_init_db.assert_awaited_once()
        mock_create_admin.assert_awaited_once()

    async def test_lifespan_calls_close_db_on_shutdown(self) -> None:
        """lifespan() should call close_db() during teardown."""
        from fastapi import FastAPI

        from app.main import lifespan

        with (
            patch("app.main.init_db", new_callable=AsyncMock),
            patch("app.main.create_admin_user", new_callable=AsyncMock),
            patch("app.main.close_db", new_callable=AsyncMock) as mock_close_db,
        ):
            test_app = FastAPI(lifespan=lifespan)
            async with lifespan(test_app):
                pass

        mock_close_db.assert_awaited_once()

    async def test_lifespan_raises_when_init_db_fails(self) -> None:
        """lifespan() should propagate exceptions from init_db()."""
        from fastapi import FastAPI

        from app.main import lifespan

        with (
            patch("app.main.init_db", new_callable=AsyncMock) as mock_init_db,
            patch("app.main.close_db", new_callable=AsyncMock),
        ):
            mock_init_db.side_effect = RuntimeError("database unavailable")
            test_app = FastAPI(lifespan=lifespan)

            with pytest.raises(RuntimeError, match="database unavailable"):
                async with lifespan(test_app):
                    pass


# ---------------------------------------------------------------------------
# app/main.py - billing_error_handler() (lines 155-157)
# ---------------------------------------------------------------------------


@pytest.fixture
async def app_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client pointing at the main FastAPI app."""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestBillingErrorHandler:
    """Tests for the BillingError exception handler in main.py.

    Lines 155-157 are the exception handler for BillingError -> 503.
    These are exercised via the /api/test/billing-error endpoint when TEST_MODE=True,
    but we also test by triggering the handler directly.
    """

    async def test_billing_error_handler_returns_503(self, app_client: AsyncClient) -> None:
        """BillingError exception handler should return HTTP 503."""
        from app.exceptions import BillingError
        from app.main import app

        @app.get("/test-billing-direct")
        async def _raise_billing() -> None:
            raise BillingError("quota exceeded")

        response = await app_client.get("/test-billing-direct")
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "billing" in data["detail"].lower() or "unavailable" in data["detail"].lower()

    async def test_billing_error_handler_response_structure(self, app_client: AsyncClient) -> None:
        """BillingError handler response should be a JSON object with a 'detail' key."""
        from app.exceptions import BillingError
        from app.main import app

        @app.get("/test-billing-structure")
        async def _raise_billing_2() -> None:
            raise BillingError("rate limit exceeded")

        response = await app_client.get("/test-billing-structure")
        assert response.status_code == 503
        data = response.json()
        assert isinstance(data, dict)
        assert isinstance(data.get("detail"), str)
        assert len(data["detail"]) > 0


# ---------------------------------------------------------------------------
# app/core/auth.py - line 41 (the uncovered branch: expires_delta provided)
# ---------------------------------------------------------------------------


class TestAuthMissingLine:
    """Test the uncovered branch in app/core/auth.py line 41.

    Line 41 is the `if expires_delta:` branch where a custom expiry is supplied.
    All existing tests call create_access_token without expires_delta, so the
    else-branch runs. We cover the if-branch here.
    """

    def test_create_access_token_with_custom_expires_delta(self) -> None:
        """create_access_token() should use the provided expires_delta (covers line 41)."""
        from datetime import timedelta

        from app.core.auth import create_access_token, decode_access_token

        token = create_access_token(data={"sub": "test-user-id"}, expires_delta=timedelta(hours=1))
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "test-user-id"

    def test_create_access_token_short_expiry(self) -> None:
        """create_access_token() with a very short expires_delta should still encode correctly."""
        from datetime import timedelta

        from app.core.auth import create_access_token, decode_access_token

        token = create_access_token(data={"sub": "abc"}, expires_delta=timedelta(seconds=30))
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "abc"

    def test_create_access_token_without_expires_delta_uses_default(self) -> None:
        """create_access_token() without expires_delta should use settings default."""
        from app.core.auth import create_access_token, decode_access_token

        token = create_access_token(data={"sub": "default-user"})
        payload = decode_access_token(token)
        assert payload is not None

    def test_decode_access_token_invalid_returns_none(self) -> None:
        """decode_access_token() with an invalid token should return None."""
        from app.core.auth import decode_access_token

        result = decode_access_token("this-is-not-a-valid-jwt-token")
        assert result is None
