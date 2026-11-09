---
name: sqlite-data-layer
description: Use when designing TraceBox tables, writing sqlite3 queries, implementing repositories or CRUD, handling transactions and database tests.
---

# SQLite data layer

- Use Python's built-in `sqlite3`; do not add an ORM.
- Enable `PRAGMA foreign_keys = ON` on every connection.
- Use parameterized SQL (`?`) for every value. Never interpolate user input into SQL.
- Keep schema creation/initialization separate from UI code.
- Define primary keys, foreign keys, `NOT NULL`, `UNIQUE`, defaults, and deletion behavior deliberately.
- Use transactions for related writes. Let failures roll back instead of leaving partial records.
- Return predictable values from repository methods and keep SQL details out of widgets.
- Use `sqlite3.Row` when named column access improves clarity.
- Avoid global connections and hidden connection state. Keep connection ownership explicit and simple for this single-process desktop app.
- Store file metadata and paths, not file contents. Do not modify evidence files.
- Add tests for CRUD, relationships, invalid references, and deletion behavior using a temporary database.
- Do not invent migrations or a generic repository framework before schema changes actually require them.
