#!/bin/bash
set -e

echo "================================"
echo "Running Backend Tests"
echo "================================"
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest --cov=app --cov-fail-under=80
cd ..

echo ""
echo "================================"
echo "Running Frontend Tests"
echo "================================"
cd frontend
npm run lint
npm run format:check
npm run typecheck
npm run test:coverage
cd ..

echo ""
echo "================================"
echo "All tests passed!"
echo "================================"
