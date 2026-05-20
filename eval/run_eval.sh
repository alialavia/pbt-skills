#!/usr/bin/env bash
# Run each of the four test suites separately and emit a machine-readable
# summary. Each suite is run against the same SUT (eval/src) which contains
# two deliberate bugs: shipping > vs >= at the $50.00 boundary, and the
# self-transfer money-creation bug in Bank.transfer.
#
# Pass counts: tests that passed (i.e. did not detect a bug or are testing
# unrelated behavior).
# Fail counts: tests that detected a bug (or for the eb suite, tests that
# would pass if the bugs did not exist).
#
# The summary is written to eval/results/summary.json.

set -uo pipefail

EVAL_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$EVAL_DIR/results"
mkdir -p "$RESULTS_DIR"

# Suites in the comparison. The eb suite is a baseline-context entry,
# not part of the three-way comparison.
SUITES=(eb no_skill trailofbits this_repo)

summary_json="$RESULTS_DIR/summary.json"
echo "[" >"$summary_json"

first=1
overall_status=0
for suite in "${SUITES[@]}"; do
    log_file="$RESULTS_DIR/${suite}.log"
    echo "=== $suite ==="
    # Run pytest at the suite directory. --tb=no keeps the log compact for
    # downstream parsing; -v makes per-test pass/fail visible.
    # We do not fail-fast: we want to see which specific tests fail in each
    # suite so the writeup can name them.
    # Override pyproject's -q so per-test PASSED/FAILED lines are visible.
    pytest "$EVAL_DIR/tests/$suite" \
        --rootdir="$EVAL_DIR" \
        -p no:cacheprovider \
        -o addopts="" \
        --tb=no -v \
        >"$log_file" 2>&1
    rc=$?

    # Count from per-test lines (e.g. "tests/.../test_x PASSED").
    passed=$(grep -cE ' PASSED' "$log_file" || true)
    failed=$(grep -cE ' FAILED' "$log_file" || true)
    errors=$(grep -cE ' ERROR' "$log_file" || true)

    # The short summary section prints "FAILED <test_id> - <reason>".
    # Match it specifically (rather than the per-test "<id> FAILED" line)
    # so we get just the test ids.
    failed_tests=$(grep -E '^FAILED ' "$log_file" | awk '{print $2}' | sort -u | paste -sd, -)

    echo "  passed=$passed failed=$failed errors=$errors rc=$rc"
    [[ -n "$failed_tests" ]] && echo "  failed_tests=$failed_tests"

    [[ $first -eq 0 ]] && echo "," >>"$summary_json"
    first=0
    cat >>"$summary_json" <<JSON
  {
    "suite": "$suite",
    "rc": $rc,
    "passed": $passed,
    "failed": $failed,
    "errors": $errors,
    "failed_tests": "$failed_tests",
    "log": "results/${suite}.log"
  }
JSON

    # We expect some failures (the SUT has bugs), so rc != 0 is normal.
    # Only treat collection errors as overall failure.
    if [[ $errors -gt 0 ]]; then
        overall_status=1
    fi
done

echo "]" >>"$summary_json"
echo
echo "Summary written to $summary_json"
exit $overall_status
