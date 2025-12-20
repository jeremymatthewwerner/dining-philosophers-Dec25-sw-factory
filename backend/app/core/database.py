"""Database configuration and session management."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.debug,
    future=True,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager to get a database session.

    Use this for background tasks or startup operations that don't
    use FastAPI's dependency injection.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def run_migrations() -> bool:
    """Run Alembic migrations synchronously.

    This is called from init_db() using run_sync to ensure migrations
    run in a sync context even when called from an async function.
    """
    backend_dir = Path(__file__).parent.parent.parent
    alembic_ini = backend_dir / "alembic.ini"

    if not alembic_ini.exists():
        logger.warning(f"alembic.ini not found at {alembic_ini}, skipping migrations")
        return False

    logger.info("Running database migrations...")
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    # Override the database URL to use sync driver for migrations
    alembic_cfg.set_main_option("sqlalchemy.url", settings.sync_database_url)

    command.upgrade(alembic_cfg, "head")
    logger.info("Database migrations complete")
    return True


async def init_db() -> None:
    """Initialize database by running Alembic migrations.

    This runs any pending migrations to ensure the database schema
    is up to date. For new databases, this will create all tables.
    For existing databases, this will apply any new migrations.
    """
    from app.models import Base

    # Try to run migrations
    backend_dir = Path(__file__).parent.parent.parent
    alembic_ini = backend_dir / "alembic.ini"

    if alembic_ini.exists():
        # Run migrations synchronously using sync database URL
        try:
            run_migrations()
            return
        except Exception as e:
            logger.warning(f"Migration failed: {e}, falling back to create_all")

    # Fall back to create_all for development/testing or if migrations fail
    logger.info("Using create_all for database initialization")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
