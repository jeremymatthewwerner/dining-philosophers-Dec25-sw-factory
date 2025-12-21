# Railway deploy - builds from repo root context
FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files and README (required by pyproject.toml)
# Paths relative to repo root since that's the build context
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./

# Install dependencies (production only, skip editable project install)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code and alembic migrations
COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic

# Railway sets PORT env var, default to 8000 for local
ENV PORT=8000
EXPOSE $PORT

# Run using the venv's Python directly (since project isn't installed)
CMD .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
