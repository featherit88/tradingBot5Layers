Run tests in Docker using `exec` on the running container.

Usage:
- `/test` — run ALL tests
- `/test risk` — run tests for the risk module
- `/test risk::TestTrailingStop` — run a specific test class
- `/test risk::TestTrailingStop::test_long_trail` — run a specific test method

Steps:
1. Ensure containers are running: `docker compose -f docker/docker-compose.yml up -d`
2. Build the pytest command:
   - No args: `python -m pytest -v`
   - Module name: `python -m pytest tests/test_<module>.py -v`
   - Class::method: `python -m pytest tests/test_<module>.py::<Class>::<method> -v`
3. Run: `docker compose -f docker/docker-compose.yml exec bot <command>`
4. Report results: passed/failed count, show failures with tracebacks
5. If failures found, offer to fix them
