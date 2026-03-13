Show project health status: tests, lint, git, containers.

Run these checks in parallel:

1. **Docker containers**: `docker compose -f docker/docker-compose.yml ps`
2. **Git status**: `git status --short` + `git log --oneline -5`
3. **Test suite**: `docker compose -f docker/docker-compose.yml exec bot python -m pytest --tb=no -q`
4. **Ruff lint**: `docker compose -f docker/docker-compose.yml exec bot ruff check . --statistics`

Present results as a dashboard:

```
📦 Containers:  bot ✓ running | mysql ✓ running
🔀 Git:         main | 3 uncommitted files
✅ Tests:       94 passed, 0 failed
🔍 Lint:        0 errors, 0 warnings
```

If any issues found, list them and offer to fix.
