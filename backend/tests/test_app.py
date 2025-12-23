"""Tests for app module."""

import app


def test_version_constant_exists() -> None:
    """Test that VERSION constant exists and has correct value."""
    assert hasattr(app, "VERSION")
    assert app.VERSION == "0.1.0"


def test_version_constant_type() -> None:
    """Test that VERSION is a string."""
    assert isinstance(app.VERSION, str)


def test_version_and_dunder_version_match() -> None:
    """Test that VERSION matches __version__."""
    assert app.__version__ == app.VERSION
