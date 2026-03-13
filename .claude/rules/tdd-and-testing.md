---
paths:
  - "**/*.py"
  - "tests/**/*.py"
---

# TDD & Testing Rules

## Batched TDD Cycle (mandatory for all code changes)
1. **UPDATE PROGRESS.md** — add planned work to "In Progress" (what + why)
2. **PLAN** — list functions needed, define inputs/outputs/edge cases
3. **WRITE ALL TESTS FIRST** — before any implementation
4. **WRITE ALL IMPLEMENTATIONS** — minimum code, no extras
5. **RUN TESTS** — `docker compose -f docker/docker-compose.yml exec bot python -m pytest tests/test_<module>.py -v`
6. **FIX & RE-RUN** — iterate until zero failures
7. **UPDATE DOCS** — move PROGRESS.md items to "Done", update README.md with final API

## Documentation timing
- **PROGRESS.md** → update BEFORE implementing (it's a task board — agents read it to know what to build)
- **README.md** → update AFTER tests pass (it documents the actual API, not speculative plans)

## Test Quality
- Assert behavior, not types (`assert result is True`, not `isinstance(result, bool)`)
- Test data must respect all thresholds (if reject is 3x, don't test with 5x)
- Realistic data shapes (flat for no-signal, trending/zigzag for signal)

## Coverage per function
- Happy path + edge cases (empty, zero, None, NaN)
- Boundary conditions (exactly at threshold)
- Both directions (long=1, short=-1)
- Time boundaries (before/after 14:00, inside/outside session)

## Agents follow TDD too
- Subagent reads PROGRESS.md first to understand what's planned and what exists
- Subagent reads README.md for current public API context
- Task descriptions must state: "Write tests first, then implement, then run and fix until green"
