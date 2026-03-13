Add a new feature following the Batched TDD workflow.

Argument: $ARGUMENTS (describe the feature to add)

Mandatory steps — do NOT skip any:

### Step 1: UPDATE PROGRESS.md (BEFORE implementing)
- Read the module's PROGRESS.md to understand current state
- Add the planned work to "In Progress" section with a clear description
- This gives agents and future sessions context about what's being built

### Step 2: PLAN
- Identify which module(s) this feature belongs to
- List all functions/methods needed
- For each function, define: purpose (one sentence), inputs, outputs, edge cases
- Present the plan to the user for approval before proceeding

### Step 3: WRITE ALL TESTS FIRST
- Add test classes/methods to the appropriate `tests/test_<module>.py`
- Cover for each function:
  - Happy path
  - Edge cases (empty input, zero, None, NaN)
  - Boundary conditions (at threshold values)
  - Both directions if applicable (long/short)
- Run tests to confirm they FAIL (Red phase):
  `docker compose -f docker/docker-compose.yml exec bot python -m pytest tests/test_<module>.py -v`

### Step 4: WRITE ALL IMPLEMENTATIONS
- Implement in the appropriate `core.py` file(s)
- Export new public API in `__init__.py`
- Follow all coding rules (datetime, DataFrame safety, state ownership, etc.)

### Step 5: RUN & ITERATE
- Run tests: `docker compose -f docker/docker-compose.yml exec bot python -m pytest tests/test_<module>.py -v`
- Fix any failures
- Re-run until ALL tests pass (zero failures)
- Run full test suite to check for regressions:
  `docker compose -f docker/docker-compose.yml exec bot python -m pytest -v`

### Step 6: UPDATE DOCS (AFTER tests pass)
- PROGRESS.md: move items from "In Progress" to "Done"
- README.md: update Public API section with the final function signatures
- These now reflect the ACTUAL implementation, not speculative plans
