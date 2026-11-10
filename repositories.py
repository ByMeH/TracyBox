import sqlite3

from constants import DEFAULT_DIFFICULTY, DEFAULT_STATUS, STATUSES


def get_competitions(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute("SELECT * FROM competitions ORDER BY id").fetchall()


def add_competition(
    connection: sqlite3.Connection,
    name: str,
    platform: str = "",
    url: str = "",
    start_date: str = "",
    description: str = "",
) -> int:
    with connection:
        cursor = connection.execute(
            "INSERT INTO competitions (name, platform, url, start_date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (name.strip(), platform, url, start_date, description),
        )
    return cursor.lastrowid


def update_competition(
    connection: sqlite3.Connection,
    competition_id: int,
    name: str,
    platform: str,
    url: str,
    start_date: str,
    description: str,
) -> bool:
    with connection:
        cursor = connection.execute(
            "UPDATE competitions SET name = ?, platform = ?, url = ?, start_date = ?, description = ?"
            " WHERE id = ?",
            (name.strip(), platform, url, start_date, description, competition_id),
        )
    return cursor.rowcount > 0


def delete_competition(connection: sqlite3.Connection, competition_id: int) -> bool:
    with connection:
        cursor = connection.execute("DELETE FROM competitions WHERE id = ?", (competition_id,))
    return cursor.rowcount > 0


def get_challenges(
    connection: sqlite3.Connection,
    competition_id: int | None = None,
    status: str | None = None,
) -> list[sqlite3.Row]:
    query = (
        "SELECT challenges.*, competitions.name AS competition_name"
        " FROM challenges JOIN competitions ON competitions.id = challenges.competition_id"
    )
    conditions = []
    parameters = []
    if competition_id is not None:
        conditions.append("challenges.competition_id = ?")
        parameters.append(competition_id)
    if status is not None:
        conditions.append("challenges.status = ?")
        parameters.append(status)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY challenges.id"
    return connection.execute(query, parameters).fetchall()


def get_challenge(connection: sqlite3.Connection, challenge_id: int) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT challenges.*, competitions.name AS competition_name"
        " FROM challenges JOIN competitions ON competitions.id = challenges.competition_id"
        " WHERE challenges.id = ?",
        (challenge_id,),
    ).fetchone()


def add_challenge(
    connection: sqlite3.Connection,
    competition_id: int,
    title: str,
    category: str = "",
    difficulty: str = DEFAULT_DIFFICULTY,
    status: str = DEFAULT_STATUS,
    points: int = 0,
    description: str = "",
) -> int:
    with connection:
        cursor = connection.execute(
            "INSERT INTO challenges (competition_id, title, category, difficulty, status, points, description)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (competition_id, title.strip(), category, difficulty, status, points, description),
        )
    return cursor.lastrowid


def update_challenge(
    connection: sqlite3.Connection,
    challenge_id: int,
    competition_id: int,
    title: str,
    category: str,
    difficulty: str,
    status: str,
    points: int,
    description: str,
) -> bool:
    with connection:
        cursor = connection.execute(
            "UPDATE challenges SET competition_id = ?, title = ?, category = ?, difficulty = ?,"
            " status = ?, points = ?, description = ?, updated_at = CURRENT_TIMESTAMP"
            " WHERE id = ?",
            (competition_id, title.strip(), category, difficulty, status, points, description, challenge_id),
        )
    return cursor.rowcount > 0


def delete_challenge(connection: sqlite3.Connection, challenge_id: int) -> bool:
    with connection:
        cursor = connection.execute("DELETE FROM challenges WHERE id = ?", (challenge_id,))
    return cursor.rowcount > 0


def get_notes(connection: sqlite3.Connection, challenge_id: int) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT * FROM notes WHERE challenge_id = ? ORDER BY id", (challenge_id,)
    ).fetchall()


def add_note(connection: sqlite3.Connection, challenge_id: int, title: str, content: str) -> int:
    with connection:
        cursor = connection.execute(
            "INSERT INTO notes (challenge_id, title, content) VALUES (?, ?, ?)",
            (challenge_id, title.strip(), content.strip()),
        )
    return cursor.lastrowid


def update_note(connection: sqlite3.Connection, note_id: int, title: str, content: str) -> bool:
    with connection:
        cursor = connection.execute(
            "UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title.strip(), content.strip(), note_id),
        )
    return cursor.rowcount > 0


def delete_note(connection: sqlite3.Connection, note_id: int) -> bool:
    with connection:
        cursor = connection.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return cursor.rowcount > 0


def get_artifacts(connection: sqlite3.Connection, challenge_id: int) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT * FROM artifacts WHERE challenge_id = ? ORDER BY id", (challenge_id,)
    ).fetchall()


def add_artifact(
    connection: sqlite3.Connection,
    challenge_id: int,
    path: str,
    file_name: str,
    file_size: int,
    sha256: str,
) -> int:
    with connection:
        cursor = connection.execute(
            "INSERT INTO artifacts (challenge_id, path, file_name, file_size, sha256)"
            " VALUES (?, ?, ?, ?, ?)",
            (challenge_id, path, file_name, file_size, sha256),
        )
    return cursor.lastrowid


def delete_artifact(connection: sqlite3.Connection, artifact_id: int) -> bool:
    with connection:
        cursor = connection.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
    return cursor.rowcount > 0


def get_dashboard_stats(connection: sqlite3.Connection) -> dict[str, object]:
    total_competitions = connection.execute("SELECT COUNT(*) FROM competitions").fetchone()[0]
    total_challenges = connection.execute("SELECT COUNT(*) FROM challenges").fetchone()[0]
    status_counts = dict.fromkeys(STATUSES, 0)
    other_challenges = 0
    for row in connection.execute("SELECT status, COUNT(*) FROM challenges GROUP BY status"):
        status = row["status"]
        if status in status_counts:
            status_counts[status] = row[1]
        else:
            other_challenges += row[1]
    solved_challenges = status_counts["Решено"]
    solved_percentage = round(solved_challenges * 100 / total_challenges) if total_challenges else 0
    return {
        "total_competitions": total_competitions,
        "total_challenges": total_challenges,
        "solved_challenges": solved_challenges,
        "solved_percentage": solved_percentage,
        "status_counts": status_counts,
        "other_challenges": other_challenges,
    }


def get_recent_challenges(connection: sqlite3.Connection, limit: int = 5) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT challenges.*, competitions.name AS competition_name"
        " FROM challenges JOIN competitions ON competitions.id = challenges.competition_id"
        " ORDER BY challenges.updated_at DESC, challenges.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
