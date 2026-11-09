---
name: clean-python-code
description: Use when writing, editing, or refactoring Python in TraceBox. Keep code idiomatic, understandable to a student, and free of boilerplate or AI-looking comments.
---

# Clean Python for TraceBox

- Write code a student can explain line by line. Prefer the simplest correct implementation.
- Follow PEP 8, use descriptive names, and keep functions focused.
- Do not add comments that merely translate the next line into Russian or English.
- Do not add a docstring to every function. Document public behavior only when its purpose or contract is not clear from the name and signature.
- Avoid banner comments, fake section headers, excessive blank lines, generic TODOs, and verbose boilerplate.
- Do not introduce a class for a single stateless function. Do not introduce a helper used only once unless it materially clarifies the code.
- Avoid overengineering: no unnecessary factories, interfaces, abstract base classes, dependency-injection containers, event buses, or generic frameworks.
- Use constants for values that are genuinely shared or meaningful, not for every literal.
- Handle expected errors at the layer that can respond appropriately. Avoid blanket `except Exception` and silent failure.
- Do not hide complexity behind clever one-liners. Clear control flow is preferable.
- Do not inflate line count. Meaningful implementation, correctness, and maintainability matter more than LOC.
- Preserve existing conventions when they are reasonable; do not reformat unrelated files.
