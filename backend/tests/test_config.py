"""Tests for configuration settings."""

from unittest.mock import patch

from app.core.config import Settings, is_test_mode


class TestAsyncDatabaseUrl:
    """Tests for async_database_url property."""

    def test_sqlite_url_unchanged(self) -> None:
        """SQLite URLs should pass through unchanged."""
        settings = Settings(database_url="sqlite+aiosqlite:///./test.db")
        assert settings.async_database_url == "sqlite+aiosqlite:///./test.db"

    def test_postgresql_url_converted(self) -> None:
        """postgresql:// should be converted to postgresql+asyncpg://."""
        settings = Settings(database_url="postgresql://user:pass@host:5432/db")
        assert settings.async_database_url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_postgres_url_converted(self) -> None:
        """postgres:// (Railway format) should be converted to postgresql+asyncpg://."""
        settings = Settings(database_url="postgres://user:pass@host:5432/db")
        assert settings.async_database_url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_already_async_url_unchanged(self) -> None:
        """URLs already using asyncpg should pass through unchanged."""
        settings = Settings(database_url="postgresql+asyncpg://user:pass@host:5432/db")
        assert settings.async_database_url == "postgresql+asyncpg://user:pass@host:5432/db"


class TestAnthropicModel:
    """Tests for the centralized Anthropic model id (issue #973)."""

    def test_default_model_is_a_current_non_dated_id(self) -> None:
        """Default model must be a current alias, not a retired dated snapshot.

        The dated snapshot ``claude-sonnet-4-20250514`` was retired and started
        returning 404 from the Anthropic API, breaking all suggestion/validation
        paths. Guard against re-introducing a hardcoded dead snapshot.
        """
        settings = Settings()
        assert settings.anthropic_model == "claude-sonnet-4-6"
        # Never the retired snapshot that 404s.
        assert settings.anthropic_model != "claude-sonnet-4-20250514"

    def test_model_is_overridable_via_env(self) -> None:
        """The model id should be configurable via environment override."""
        settings = Settings(anthropic_model="claude-opus-4-8")
        assert settings.anthropic_model == "claude-opus-4-8"


class TestTestMode:
    """Tests for test mode configuration."""

    def test_is_test_mode_returns_false_by_default(self) -> None:
        """Test mode should be disabled by default."""
        with patch("app.core.config.get_settings") as mock_get_settings:
            mock_settings = Settings(test_mode=False)
            mock_get_settings.return_value = mock_settings
            assert is_test_mode() is False

    def test_is_test_mode_returns_true_when_enabled(self) -> None:
        """Test mode should return True when TEST_MODE is enabled."""
        with patch("app.core.config.get_settings") as mock_get_settings:
            mock_settings = Settings(test_mode=True)
            mock_get_settings.return_value = mock_settings
            assert is_test_mode() is True
