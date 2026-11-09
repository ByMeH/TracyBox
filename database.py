import sqlite3
from pathlib import Path

from constants import DEFAULT_DIFFICULTY, DEFAULT_STATUS, DIFFICULTIES, STATUSES

_DIFFICULTY_VALUES = ", ".join(f"'{value}'" for value in DIFFICULTIES)
_STATUS_VALUES = ", ".join(f"'{value}'" for value in STATUSES)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS competitions (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (trim(name) <> ''),
    platform TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    start_date TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS challenges (
    id INTEGER PRIMARY KEY,
    competition_id INTEGER NOT NULL REFERENCES competitions (id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK (trim(title) <> ''),
    category TEXT NOT NULL DEFAULT '',
    difficulty TEXT NOT NULL DEFAULT '{DEFAULT_DIFFICULTY}' CHECK (difficulty IN ({_DIFFICULTY_VALUES})),
    status TEXT NOT NULL DEFAULT '{DEFAULT_STATUS}' CHECK (status IN ({_STATUS_VALUES})),
    points INTEGER NOT NULL DEFAULT 0 CHECK (points >= 0),
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    challenge_id INTEGER NOT NULL REFERENCES challenges (id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK (trim(title) <> ''),
    content TEXT NOT NULL CHECK (trim(content) <> ''),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY,
    challenge_id INTEGER NOT NULL REFERENCES challenges (id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER NOT NULL CHECK (file_size >= 0),
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_challenges_competition ON challenges (competition_id);
CREATE INDEX IF NOT EXISTS idx_challenges_status ON challenges (status);
CREATE INDEX IF NOT EXISTS idx_notes_challenge ON notes (challenge_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_challenge ON artifacts (challenge_id);
"""


def connect_database(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(_SCHEMA)
