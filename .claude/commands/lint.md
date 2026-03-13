Run ruff linter on the codebase in Docker.

Usage:
- `/lint` — lint all Python files
- `/lint indicators` — lint only the indicators module
- `/lint indicators/core.py` — lint a specific file

Steps:
1. Ensure containers are running: `docker compose -f docker/docker-compose.yml up -d`
2. Build the ruff command:
   - No args: `ruff check .`
   - Module name: `ruff check <module>/`
   - File path: `ruff check <file>`
3. Run: `docker compose -f docker/docker-compose.yml exec bot <command>`
4. Report results
5. If errors found, offer to fix them (apply `ruff check --fix` or manual fixes)
