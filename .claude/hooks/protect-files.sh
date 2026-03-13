#!/bin/bash
# Guard edits to sensitive files
# BLOCKS: .env (credentials) and .git/ (repository internals)
# WARNS: docker-compose, Dockerfile, init.sql (infra — may need legitimate edits)

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# HARD BLOCK — never edit these automatically
if [[ "$FILE_PATH" =~ /\.env$ ]] || \
   [[ "$FILE_PATH" =~ /\.env\. ]] || \
   [[ "$FILE_PATH" =~ \.git/ ]]; then
  echo "BLOCKED: $FILE_PATH contains credentials or git internals." >&2
  echo "This file must be edited manually by the user." >&2
  exit 2
fi

# SOFT WARN — infrastructure files that sometimes need legitimate edits
if [[ "$FILE_PATH" =~ docker-compose ]] || \
   [[ "$FILE_PATH" =~ Dockerfile$ ]] || \
   [[ "$FILE_PATH" =~ init\.sql$ ]] || \
   [[ "$FILE_PATH" =~ \.env\.example$ ]]; then
  echo "WARNING: Editing infrastructure file $FILE_PATH — make sure this was requested." >&2
  # exit 0 = allow but warn
fi

exit 0
