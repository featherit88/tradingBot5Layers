Create a new module following the project's modular architecture rules.

Argument: $ARGUMENTS (format: "module_name - one sentence purpose")

Steps:
1. Parse the module name and purpose from the argument
2. Verify the module name passes the one-sentence test
3. Create the folder structure:
   ```
   module_name/
   ├── __init__.py      # Public API exports
   ├── core.py          # Main logic (empty skeleton with docstring)
   ├── README.md        # Purpose + Public API + Dependencies
   └── PROGRESS.md      # Done / In Progress / Next sections
   ```
4. Create `tests/test_module_name.py` with a skeleton test class
5. Add the module to the "Current Modules" table in CLAUDE.md
6. Remind: follow TDD — write tests before implementing functions in core.py
