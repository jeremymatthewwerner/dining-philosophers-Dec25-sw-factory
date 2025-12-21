"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database - SQLite for local dev, PostgreSQL for production
    database_url: str = "sqlite+aiosqlite:///./thinkers_chat.db"

    @property
    def async_database_url(self) -> str:
        """Get database URL with async driver for SQLAlchemy."""
        url = self.database_url
        # Convert Railway's postgresql:// to postgresql+asyncpg://
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Convert postgres:// (also valid) to postgresql+asyncpg://
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Get database URL with sync driver for Alembic migrations."""
        url = self.database_url
        # Convert async URLs to sync equivalents
        if "asyncpg" in url:
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        if "aiosqlite" in url:
            return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        # Convert Railway's postgresql:// stays as is
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql://", 1)
        return url

    # Anthropic API
    anthropic_api_key: str = ""

    # Application settings
    debug: bool = False

    # CORS settings (comma-separated list of allowed origins)
    cors_origins: str = "http://localhost:3000"

    # Authentication
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Test mode (enables test endpoints)
    test_mode: bool = False


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


def is_test_mode() -> bool:
    """Check if test mode is enabled.

    Test mode enables special endpoints for integration testing.
    Should only be enabled in test environments.

    Returns:
        True if TEST_MODE environment variable is set to true/1/yes, False otherwise.
    """
    settings = get_settings()
    return settings.test_mode
