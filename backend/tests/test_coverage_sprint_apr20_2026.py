"""Coverage sprint tests for Apr 20, 2026.

Targets:
- app/main.py: lifespan startup (create_admin_user when admin missing and when it exists)
- app/main.py: lifespan error handling
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.auth import get_password_hash
from app.models import Base, User


@pytest.fixture
async def main_engine() -> AsyncEngine:
    """In-memory SQLite engine for main.py tests."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def main_db_session(main_engine: AsyncEngine) -> AsyncSession:
    """Database session for main.py tests."""
    session_factory = async_sessionmaker(
        main_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


class TestCreateAdminUser:
    """Tests for the create_admin_user function."""

    async def test_creates_admin_user_when_not_exists(self, main_engine: AsyncEngine) -> None:
        """Admin user is created when it doesn't already exist."""
        from contextlib import asynccontextmanager

        from sqlalchemy import select

        from app.main import create_admin_user

        session_factory = async_sessionmaker(
            main_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        @asynccontextmanager
        async def _fake_async_session():
            async with session_factory() as session:
                yield session

        with patch("app.main.async_session", _fake_async_session):
            # Verify no admin user exists initially
            async with _fake_async_session() as session:
                result = await session.execute(select(User).where(User.username == "admin"))
                assert result.scalar_one_or_none() is None

            await create_admin_user()

            # Verify admin user was created
            async with _fake_async_session() as session:
                result = await session.execute(select(User).where(User.username == "admin"))
                admin = result.scalar_one_or_none()
                assert admin is not None
                assert admin.is_admin is True

    async def test_skips_admin_user_creation_when_already_exists(
        self, main_engine: AsyncEngine
    ) -> None:
        """Admin user is not duplicated if it already exists."""
        from sqlalchemy import select

        from app.main import create_admin_user

        session_factory = async_sessionmaker(
            main_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Pre-create the admin user
        async with session_factory() as session:
            existing_admin = User(
                username="admin",
                password_hash=get_password_hash("admin"),
                is_admin=True,
            )
            session.add(existing_admin)
            await session.commit()

        call_count = 0

        def mock_session_factory():
            class MockCtx:
                async def __aenter__(self_inner):  # noqa: N805
                    nonlocal call_count
                    call_count += 1
                    self_inner._session = session_factory()
                    return await self_inner._session.__aenter__()

                async def __aexit__(self_inner, *args):  # noqa: N805
                    return await self_inner._session.__aexit__(*args)

            return MockCtx()

        with patch("app.main.async_session", side_effect=mock_session_factory):
            await create_admin_user()

        # Verify only one admin user exists (not duplicated)
        async with session_factory() as session:
            from sqlalchemy import func

            result = await session.execute(select(func.count()).where(User.username == "admin"))
            count = result.scalar()
            assert count == 1


class TestLifespan:
    """Tests for the lifespan async context manager."""

    async def test_lifespan_calls_init_db_and_create_admin(self) -> None:
        """Lifespan startup calls init_db() and create_admin_user()."""
        from app.main import app, lifespan

        mock_init_db = AsyncMock()
        mock_create_admin = AsyncMock()
        mock_close_db = AsyncMock()

        with (
            patch("app.main.init_db", mock_init_db),
            patch("app.main.create_admin_user", mock_create_admin),
            patch("app.main.close_db", mock_close_db),
        ):
            async with lifespan(app):
                mock_init_db.assert_called_once()
                mock_create_admin.assert_called_once()

            mock_close_db.assert_called_once()

    async def test_lifespan_closes_db_on_shutdown(self) -> None:
        """Lifespan shutdown calls close_db()."""
        from app.main import app, lifespan

        mock_close_db = AsyncMock()

        with (
            patch("app.main.init_db", AsyncMock()),
            patch("app.main.create_admin_user", AsyncMock()),
            patch("app.main.close_db", mock_close_db),
        ):
            async with lifespan(app):
                pass

        mock_close_db.assert_called_once()

    async def test_lifespan_raises_on_startup_failure(self) -> None:
        """Lifespan re-raises exception if startup fails."""
        from app.main import app, lifespan

        with (
            patch("app.main.init_db", AsyncMock(side_effect=RuntimeError("DB failed"))),
            patch("app.main.close_db", AsyncMock()),pytest.raises(RuntimeError, match="DB failed")
        ):
            async with lifespan(app):
                pass  # Should not reach here
