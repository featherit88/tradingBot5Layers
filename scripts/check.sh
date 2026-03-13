#!/bin/bash
# All-in-one check script. Runs INSIDE Docker container.
# Usage: check.sh <file_path> [test_file]

FILE="$1"
TEST_FILE="$2"

ERRORS=0

# 1. Syntax check
echo "=== SYNTAX ==="
if python -m py_compile "$FILE" 2>&1; then
  echo "OK"
else
  ERRORS=$((ERRORS + 1))
fi

# 2. Ruff lint
echo "=== RUFF ==="
if ruff check "$FILE" 2>&1; then
  echo "OK"
else
  ERRORS=$((ERRORS + 1))
fi

# 3. Tests (if test file provided and exists)
if [ -n "$TEST_FILE" ] && [ -f "$TEST_FILE" ]; then
  echo "=== TESTS ==="
  python -m pytest "$TEST_FILE" -v --tb=short 2>&1
  if [ $? -ne 0 ]; then
    ERRORS=$((ERRORS + 1))
  fi
fi

echo "=== DONE: $ERRORS issue(s) ==="
exit $ERRORS
