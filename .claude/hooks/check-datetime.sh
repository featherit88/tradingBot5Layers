#!/bin/bash
# Check for datetime.utcnow() usage — WARNS only (exit 0).
# Keeps the edit so the offending line can be fixed in place.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.command // empty')

# Only check Python files
if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
  exit 0
fi

if [ -f "$FILE_PATH" ]; then
  if grep -qn 'datetime\.utcnow()' "$FILE_PATH"; then
    LINE=$(grep -n 'datetime\.utcnow()' "$FILE_PATH" | head -1)
    echo "WARNING: datetime.utcnow() found at $LINE" >&2
    echo "Use datetime.now(timezone.utc) instead." >&2
    # exit 0 = warn only (keep the edit, fix in place)
    exit 0
  fi
fi

exit 0
