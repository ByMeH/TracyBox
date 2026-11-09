---
name: cost-aware-work
description: Use when planning or implementing TraceBox tasks with an API/token budget. Keep context, tool calls, diffs, and model output small without sacrificing correctness.
---

# Cost-aware development

- Treat each request as one bounded task. State the intended files and acceptance check before editing.
- Read only the files directly involved and follow their imports/callers only as needed. Prefer targeted search and small excerpts over dumping the repository.
- Do not reprint full source files in chat. Summarize changes and show only the relevant snippet or diff when needed.
- Do not repeat project context already written in `AGENTS.md` or `docs/PROJECT_BRIEF.md`; refer to those files.
- Avoid speculative features, broad refactors, repeated planning, and generating multiple alternative implementations unless asked.
- Prefer standard-library functionality and the dependencies already in `requirements.txt`.
- Do not add a dependency, network service, paid API, or in-app AI feature without explicit approval.
- Run the narrowest useful test first. Run the full test suite at milestone boundaries or when shared code changed.
- If a command fails, inspect the relevant error and make one targeted correction; do not launch an unbounded trial-and-error loop.
- Keep final reports short: changed files, behavior added/fixed, commands actually run, test result, known limitation.
- Never claim a test, build, or Git operation succeeded unless its output confirms success.
