#!/bin/bash
# Combined Docker check: syntax + ruff + tests on the ALREADY RUNNING container.
# Uses `docker compose exec` (instant) instead of `docker compose run` (slow startup).
# If container isn't running, starts it first with `docker compose up -d`.
# WARNS on all issues (exit 0) — keeps the edit so issues can be fixed in place.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only check Python files
if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
  exit 0
fi

if [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR" || exit 0

# Ensure bot container is running (no-op if already up)
if ! docker compose -f docker/docker-compose.yml ps --status running bot 2>/dev/null | grep -q bot; then
  docker compose -f docker/docker-compose.yml up -d bot 2>/dev/null
  sleep 2  # brief wait for container to be ready
fi

# Convert absolute path to relative for Docker
REL_PATH=$(realpath --relative-to="$CLAUDE_PROJECT_DIR" "$FILE_PATH" 2>/dev/null || echo "$FILE_PATH")

# Map to the relevant test file
TEST_FILE=""
if [[ "$FILE_PATH" =~ tests/test_.*\.py$ ]]; then
  # Editing a test file → run that test file itself
  TEST_FILE="$REL_PATH"
else
  # Editing source → map to its test file
  BASENAME=$(basename "$FILE_PATH")
  if [[ "$BASENAME" != "__init__.py" ]]; then
    MODULE=""
    if [[ "$FILE_PATH" =~ indicators/ ]]; then MODULE="indicators"
    elif [[ "$FILE_PATH" =~ filters/ ]]; then MODULE="filters"
    elif [[ "$FILE_PATH" =~ scoring/ ]]; then MODULE="scoring"
    elif [[ "$FILE_PATH" =~ strategies/ ]]; then MODULE="strategies"
    elif [[ "$FILE_PATH" =~ risk/ ]]; then MODULE="risk"
    elif [[ "$FILE_PATH" =~ config/ ]]; then MODULE="config"
    elif [[ "$FILE_PATH" =~ bot/ ]]; then MODULE="bot"
    elif [[ "$FILE_PATH" =~ backtest/ ]]; then MODULE="backtest"
    elif [[ "$FILE_PATH" =~ broker/ ]]; then MODULE="broker"
    fi
    if [ -n "$MODULE" ] && [ -f "tests/test_${MODULE}.py" ]; then
      TEST_FILE="tests/test_${MODULE}.py"
    fi
  fi
fi

# exec on running container (instant — no container startup)
RESULT=$(docker compose -f docker/docker-compose.yml exec -T bot \
  bash scripts/check.sh "$REL_PATH" "$TEST_FILE" 2>&1)

# Show output as warnings (always exit 0 to keep the edit)
if echo "$RESULT" | grep -q "issue(s)" && ! echo "$RESULT" | grep -q "0 issue(s)"; then
  echo "$RESULT" | grep -v "^$" >&2
fi

exit 0
