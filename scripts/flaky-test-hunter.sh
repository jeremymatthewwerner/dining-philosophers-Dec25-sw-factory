#!/bin/bash
# Flaky Test Hunter - Run tests 5x and detect failures
# Usage: ./scripts/flaky-test-hunter.sh [backend|frontend|both]

set -e

TARGET="${1:-both}"
RUNS=5
BACKEND_RESULTS="/tmp/backend_flaky_results.txt"
FRONTEND_RESULTS="/tmp/frontend_flaky_results.txt"

echo "🔍 Flaky Test Hunter - Running tests ${RUNS}x"
echo "Target: $TARGET"
echo ""

run_backend_tests() {
    echo "=== Backend Tests ==="
    > "$BACKEND_RESULTS"

    for i in $(seq 1 $RUNS); do
        echo "Run $i/$RUNS..."
        cd backend
        if uv run pytest -x --tb=short 2>&1 | tee -a "$BACKEND_RESULTS"; then
            echo "✅ Run $i: PASSED" | tee -a "$BACKEND_RESULTS"
        else
            echo "❌ Run $i: FAILED" | tee -a "$BACKEND_RESULTS"
        fi
        cd ..
        echo "" | tee -a "$BACKEND_RESULTS"
    done

    echo ""
    echo "=== Backend Summary ==="
    grep -E "(✅|❌)" "$BACKEND_RESULTS" || echo "No summary found"
}

run_frontend_tests() {
    echo "=== Frontend Tests ==="
    > "$FRONTEND_RESULTS"

    for i in $(seq 1 $RUNS); do
        echo "Run $i/$RUNS..."
        cd frontend
        if npm test -- --bail 2>&1 | tee -a "$FRONTEND_RESULTS"; then
            echo "✅ Run $i: PASSED" | tee -a "$FRONTEND_RESULTS"
        else
            echo "❌ Run $i: FAILED" | tee -a "$FRONTEND_RESULTS"
        fi
        cd ..
        echo "" | tee -a "$FRONTEND_RESULTS"
    done

    echo ""
    echo "=== Frontend Summary ==="
    grep -E "(✅|❌)" "$FRONTEND_RESULTS" || echo "No summary found"
}

if [ "$TARGET" = "backend" ] || [ "$TARGET" = "both" ]; then
    run_backend_tests
fi

if [ "$TARGET" = "frontend" ] || [ "$TARGET" = "both" ]; then
    run_frontend_tests
fi

echo ""
echo "📊 Flaky Test Hunt Complete!"
echo "Backend results: $BACKEND_RESULTS"
echo "Frontend results: $FRONTEND_RESULTS"
