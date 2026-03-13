---
paths:
  - "**/*"
---

# Docker-Only Python Execution Rule

**NEVER run Python, pytest, ruff, or any Python tool directly on the Windows host.**
**ALL Python commands MUST run inside the Docker bot container.**

## Start containers once per session
```bash
docker compose -f docker/docker-compose.yml up -d
```
This starts both bot + MySQL. They stay running until you stop them.

## Run commands on the running container (instant, no startup overhead)
```bash
# Use `exec` — runs on already-running container
docker compose -f docker/docker-compose.yml exec bot <command>
```

## Examples
```bash
# Tests
docker compose -f docker/docker-compose.yml exec bot python -m pytest -v
docker compose -f docker/docker-compose.yml exec bot python -m pytest tests/test_indicators.py -v
docker compose -f docker/docker-compose.yml exec bot python -m pytest tests/test_risk.py::TestTrailingStop -v

# Linting
docker compose -f docker/docker-compose.yml exec bot ruff check .

# Run bot / backtest
docker compose -f docker/docker-compose.yml exec bot python main.py
docker compose -f docker/docker-compose.yml exec bot python run_backtest.py

# Stop containers when done
docker compose -f docker/docker-compose.yml down
```

## Why `exec` not `run`
- `run --rm` creates a NEW container each time (~5-10s startup overhead)
- `exec` runs on the EXISTING container (instant, <1s)
- Source code is volume-mounted, so edits are visible immediately

## This applies to ALL agents
Subagents must also use `exec`. No exceptions.

## What CAN run on Windows host
- `git` commands
- `docker` and `docker compose` commands
- File editing (Read, Write, Edit, Glob, Grep tools)
- Shell utilities (ls, cat, etc.)
