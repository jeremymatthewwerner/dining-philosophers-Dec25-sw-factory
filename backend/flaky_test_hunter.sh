#!/bin/bash
# Flaky Test Hunter - Runs tests 5 times to identify flaky tests
# QA Agent - Tuesday Focus: Flaky Test Hunt

set -e

RUNS=5
RESULTS_FILE="/tmp/flaky_test_results.txt"

echo "🔍 Flaky Test Hunt - Running tests $RUNS times..." > $RESULTS_FILE
echo "Started at: $(date)" >> $RESULTS_FILE
echo "" >> $RESULTS_FILE

cd "$(dirname "$0")"

for i in $(seq 1 $RUNS); do
    echo "================================================" >> $RESULTS_FILE
    echo "Run $i of $RUNS ($(date))" >> $RESULTS_FILE
    echo "================================================" >> $RESULTS_FILE

    # Run tests without coverage for speed, capture exit code
    if uv run pytest -v --tb=short 2>&1 | tee -a $RESULTS_FILE; then
        echo "✅ Run $i: PASSED" >> $RESULTS_FILE
    else
        echo "❌ Run $i: FAILED" >> $RESULTS_FILE
    fi
    echo "" >> $RESULTS_FILE
done

echo "" >> $RESULTS_FILE
echo "================================================" >> $RESULTS_FILE
echo "Analysis Complete at: $(date)" >> $RESULTS_FILE
echo "================================================" >> $RESULTS_FILE

# Analyze results
echo "" >> $RESULTS_FILE
echo "📊 Summary:" >> $RESULTS_FILE
grep -E "(✅|❌) Run" $RESULTS_FILE || true

echo ""
echo "Results written to: $RESULTS_FILE"
cat $RESULTS_FILE
