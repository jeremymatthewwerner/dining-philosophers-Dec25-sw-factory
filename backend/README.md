# Dining Philosophers Backend

FastAPI backend for Dining Philosophers - real-time multi-party chat with AI-simulated thinkers.

## Development

```bash
# Install dependencies
uv sync --dev

# Run dev server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=app

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy .
```
