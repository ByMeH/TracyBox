---
name: test-and-debug
description: Use when reproducing TraceBox bugs, writing pytest tests, debugging exceptions, or verifying a change before reporting completion.
---

# Focused testing and debugging

1. Reproduce the failure or define the behavior being tested.
2. Identify the smallest relevant module and test surface.
3. Add or update a test for the behavior, especially for pure tools and repository logic.
4. Run the narrow test, inspect the full traceback, and fix the cause rather than suppressing the symptom.
5. Run the broader suite when shared behavior or a milestone is affected.

- Use `pytest` and `tmp_path` for temporary files and SQLite databases.
- Do not make tests depend on the user's real database, home directory, network, or external services.
- Prefer deterministic tests and real temporary SQLite databases over excessive mocks.
- Do not test private implementation details when observable behavior is sufficient.
- Report the exact commands run and distinguish passing tests from checks not performed.
