"""Shared test fixtures for all test files."""

import gc
from collections.abc import AsyncGenerator, Generator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base


# Disable tracemalloc to avoid circular import issues in pytest's unraisable hook
# This fixes "AttributeError: partially initialized module 'tracemalloc'" errors
@pytest.fixture(autouse=True)
def disable_tracemalloc_for_unraisable() -> None:
    """Disable tracemalloc to prevent circular import errors during test cleanup."""
    import tracemalloc

    if tracemalloc.is_tracing():
        tracemalloc.stop()


@pytest.fixture(autouse=True)
def cleanup_gc() -> Generator[None, None, None]:
    """Force garbage collection after each test to clean up dangling connections."""
    yield
    gc.collect()


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
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session
