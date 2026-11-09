import sqlite3

import pytest

import repositories
from constants import DEFAULT_DIFFICULTY, DEFAULT_STATUS, STATUSES
from database import connect_database, initialize_database

SHA256 = "a" * 64


def test_foreign_keys_enabled(connection):
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_initialize_creates_tables_and_indexes(connection):
    names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    assert {"competitions", "challenges", "notes", "artifacts"} <= names
    assert {
        "idx_challenges_competition",
        "idx_challenges_status",
        "idx_notes_challenge",
        "idx_artifacts_challenge",
    } <= names


def test_initialize_is_idempotent(connection):
    initialize_database(connection)


def test_data_persists_between_connections(tmp_path):
    db_path = tmp_path / "tracebox.db"
    first = connect_database(db_path)
    initialize_database(first)
    repositories.add_competition(first, "Persist")
    first.close()

    second = connect_database(db_path)
    initialize_database(second)
    assert [row["name"] for row in repositories.get_competitions(second)] == ["Persist"]
    second.close()


def test_competition_crud(connection):
    competition_id = repositories.add_competition(
        connection,
        "TestCTF",
        platform="ctftime",
        url="https://ctftime.org",
        start_date="2026-11-01",
        description="Учебный CTF",
    )
    stored = connection.execute(
        "SELECT * FROM competitions WHERE id = ?", (competition_id,)
    ).fetchone()
    assert stored["name"] == "TestCTF"
    assert stored["platform"] == "ctftime"
    assert stored["url"] == "https://ctftime.org"
    assert stored["start_date"] == "2026-11-01"
    assert stored["description"] == "Учебный CTF"
    assert stored["created_at"] != ""

    repositories.update_competition(
        connection, competition_id, "Renamed", platform="platform", url="", start_date="", description=""
    )
    updated = connection.execute(
        "SELECT * FROM competitions WHERE id = ?", (competition_id,)
    ).fetchone()
    assert updated["name"] == "Renamed"
    assert updated["platform"] == "platform"
    assert updated["url"] == ""

    repositories.delete_competition(connection, competition_id)
    assert repositories.get_competitions(connection) == []


def test_blank_name_rejected(connection):
    with pytest.raises(sqlite3.IntegrityError):
        repositories.add_competition(connection, "   ")
    competition_id = repositories.add_competition(connection, "TestCTF")
    with pytest.raises(sqlite3.IntegrityError):
        repositories.update_competition(
            connection, competition_id, "\t", platform="", url="", start_date="", description=""
        )


def test_titles_are_stripped(connection):
    competition_id = repositories.add_competition(connection, "  TestCTF  ")
    challenge_id = repositories.add_challenge(connection, competition_id, "  Base64  ")
    repositories.add_note(connection, challenge_id, "  Идея  ", "  Текст  ")
    assert repositories.get_competitions(connection)[0]["name"] == "TestCTF"
    assert repositories.get_challenge(connection, challenge_id)["title"] == "Base64"
    assert repositories.get_notes(connection, challenge_id)[0]["content"] == "Текст"


def test_challenge_defaults(connection):
    competition_id = repositories.add_competition(connection, "TestCTF")
    challenge_id = repositories.add_challenge(connection, competition_id, "Base64")
    challenge = repositories.get_challenge(connection, challenge_id)
    assert challenge["difficulty"] == DEFAULT_DIFFICULTY
    assert challenge["status"] == DEFAULT_STATUS
    assert challenge["category"] == ""
    assert challenge["points"] == 0
    assert challenge["description"] == ""


def test_challenge_requires_existing_competition(connection):
    with pytest.raises(sqlite3.IntegrityError):
        repositories.add_challenge(connection, 999, "Orphan")


def test_challenge_rejects_invalid_values(connection):
    competition_id = repositories.add_competition(connection, "TestCTF")
    with pytest.raises(sqlite3.IntegrityError):
        repositories.add_challenge(connection, competition_id, "Challenge", points=-1)
    with pytest.raises(sqlite3.IntegrityError):
        repositories.add_challenge(connection, competition_id, "Challenge", difficulty="Невозможная")
    with pytest.raises(sqlite3.IntegrityError):
        repositories.add_challenge(connection, competition_id, "Challenge", status="Отменено")


def test_get_challenges_filters(connection):
    first = repositories.add_competition(connection, "First")
    second = repositories.add_competition(connection, "Second")
    solved_id = repositories.add_challenge(connection, first, "Solved", status="Решено")
    repositories.add_challenge(connection, second, "Fresh")

    assert len(repositories.get_challenges(connection)) == 2
    assert [row["id"] for row in repositories.get_challenges(connection, competition_id=first)] == [solved_id]
    assert [row["title"] for row in repositories.get_challenges(connection, status="Новое")] == ["Fresh"]
    assert repositories.get_challenges(connection, competition_id=first, status="Новое") == []


def test_update_challenge_sets_updated_at(connection):
    competition_id = repositories.add_competition(connection, "TestCTF")
    challenge_id = repositories.add_challenge(connection, competition_id, "Old")
    connection.execute(
        "UPDATE challenges SET created_at = '2000-01-01 00:00:00',"
        " updated_at = '2000-01-01 00:00:00' WHERE id = ?",
        (challenge_id,),
    )
    connection.commit()

    repositories.update_challenge(
        connection,
        challenge_id,
        competition_id,
        "New",
        category="",
        difficulty=DEFAULT_DIFFICULTY,
        status="Решено",
        points=100,
        description="",
    )
    challenge = repositories.get_challenge(connection, challenge_id)
    assert challenge["title"] == "New"
    assert challenge["status"] == "Решено"
    assert challenge["points"] == 100
    assert challenge["updated_at"] > challenge["created_at"]


def test_delete_competition_cascades(connection):
    competition_id = repositories.add_competition(connection, "TestCTF")
    challenge_id = repositories.add_challenge(connection, competition_id, "Challenge")
    repositories.add_note(connection, challenge_id, "Note", "Content")
    repositories.add_artifact(connection, challenge_id, "/tmp/flag.txt", "flag.txt", 128, SHA256)

    repositories.delete_competition(connection, competition_id)

    assert repositories.get_challenges(connection) == []
    assert connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_delete_challenge_cascades(connection):
    competition_id = repositories.add_competition(connection, "TestCTF")
    removed = repositories.add_challenge(connection, competition_id, "Removed")
    kept = repositories.add_challenge(connection, competition_id, "Kept")
    repositories.add_note(connection, removed, "Note", "Content")
    repositories.add_artifact(connection, removed, "/tmp/flag.txt", "flag.txt", 128, SHA256)

    repositories.delete_challenge(connection, removed)

    assert repositories.get_notes(connection, removed) == []
    assert repositories.get_artifacts(connection, removed) == []
    assert repositories.get_challenge(connection, kept)["title"] == "Kept"


def test_note_crud(connection):
    competition_id = repositories.add_competition(connection, "TestCTF")
    challenge_id = repositories.add_challenge(connection, competition_id, "Challenge")
    note_id = repositories.add_note(connection, challenge_id, "Идея", "Попробовать rot13")

    connection.execute(
        "UPDATE notes SET created_at = '2000-01-01 00:00:00',"
        " updated_at = '2000-01-01 00:00:00' WHERE id = ?",
        (note_id,),
    )
    connection.commit()

    repositories.update_note(connection, note_id, "Идея 2", "Попробовать xor")
    notes = repositories.get_notes(connection, challenge_id)
    assert len(notes) == 1
    assert notes[0]["title"] == "Идея 2"
    assert notes[0]["updated_at"] > notes[0]["created_at"]

    repositories.delete_note(connection, note_id)
    assert repositories.get_notes(connection, challenge_id) == []


def test_artifact_constraints(connection):
    competition_id = repositories.add_competition(connection, "TestCTF")
    challenge_id = repositories.add_challenge(connection, competition_id, "Challenge")
    artifact_id = repositories.add_artifact(connection, challenge_id, "/tmp/flag.txt", "flag.txt", 128, SHA256)
    assert repositories.get_artifacts(connection, challenge_id)[0]["id"] == artifact_id

    with pytest.raises(sqlite3.IntegrityError):
        repositories.add_artifact(connection, challenge_id, "/tmp/x.txt", "x.txt", 1, "short")
    with pytest.raises(sqlite3.IntegrityError):
        repositories.add_artifact(connection, challenge_id, "/tmp/x.txt", "x.txt", -1, SHA256)

    repositories.delete_artifact(connection, artifact_id)
    assert repositories.get_artifacts(connection, challenge_id) == []


def test_dashboard_stats_empty_database(connection):
    stats = repositories.get_dashboard_stats(connection)
    assert stats["total_competitions"] == 0
    assert stats["total_challenges"] == 0
    assert stats["solved_challenges"] == 0
    assert stats["solved_percentage"] == 0
    assert stats["status_counts"] == dict.fromkeys(STATUSES, 0)


def test_dashboard_stats(connection):
    competition_id = repositories.add_competition(connection, "TestCTF")
    repositories.add_challenge(connection, competition_id, "One", status="Решено")
    repositories.add_challenge(connection, competition_id, "Two", status="Решено")
    repositories.add_challenge(connection, competition_id, "Three")

    stats = repositories.get_dashboard_stats(connection)
    assert stats["total_competitions"] == 1
    assert stats["total_challenges"] == 3
    assert stats["solved_challenges"] == 2
    assert stats["solved_percentage"] == 67
    assert stats["status_counts"]["Решено"] == 2
    assert stats["status_counts"]["Новое"] == 1


def test_recent_challenges(connection):
    competition_id = repositories.add_competition(connection, "TestCTF")
    old = repositories.add_challenge(connection, competition_id, "Old")
    new = repositories.add_challenge(connection, competition_id, "New")
    connection.execute(
        "UPDATE challenges SET updated_at = '2000-01-01 00:00:00' WHERE id = ?", (old,)
    )
    connection.commit()

    recent = repositories.get_recent_challenges(connection, limit=1)
    assert [row["id"] for row in recent] == [new]
    assert recent[0]["competition_name"] == "TestCTF"


def test_update_and_delete_return_true(connection):
    competition_id = repositories.add_competition(connection, "TestCTF", platform="ctftime")
    assert repositories.update_competition(
        connection, competition_id, "TestCTF", platform="ctftime", url="", start_date="", description=""
    )
    challenge_id = repositories.add_challenge(connection, competition_id, "Challenge")
    assert repositories.update_challenge(
        connection,
        challenge_id,
        competition_id,
        "Challenge",
        category="",
        difficulty=DEFAULT_DIFFICULTY,
        status="Решено",
        points=0,
        description="",
    )
    note_id = repositories.add_note(connection, challenge_id, "Note", "Content")
    assert repositories.update_note(connection, note_id, "Note 2", "Content 2")
    artifact_id = repositories.add_artifact(connection, challenge_id, "/tmp/flag.txt", "flag.txt", 1, SHA256)

    assert repositories.delete_artifact(connection, artifact_id)
    assert repositories.delete_note(connection, note_id)
    assert repositories.delete_challenge(connection, challenge_id)
    assert repositories.delete_competition(connection, competition_id)


def test_missing_id_returns_false(connection):
    assert not repositories.update_competition(
        connection, 9999, "Name", platform="", url="", start_date="", description=""
    )
    assert not repositories.delete_competition(connection, 9999)
    assert not repositories.update_challenge(
        connection,
        9999,
        1,
        "Title",
        category="",
        difficulty=DEFAULT_DIFFICULTY,
        status="Новое",
        points=0,
        description="",
    )
    assert not repositories.delete_challenge(connection, 9999)
    assert not repositories.update_note(connection, 9999, "Title", "Content")
    assert not repositories.delete_note(connection, 9999)
    assert not repositories.delete_artifact(connection, 9999)


def test_update_requires_all_fields(connection):
    with pytest.raises(TypeError):
        repositories.update_competition(connection, 1, "Name", platform="p")
    with pytest.raises(TypeError):
        repositories.update_challenge(
            connection, 1, 1, "Title", category="", difficulty=DEFAULT_DIFFICULTY, status="Новое", points=0
        )


def test_empty_string_clears_fields(connection):
    competition_id = repositories.add_competition(
        connection,
        "TestCTF",
        platform="ctftime",
        url="https://ctftime.org",
        start_date="2026-11-01",
        description="Описание",
    )
    assert repositories.update_competition(
        connection, competition_id, "TestCTF", platform="", url="", start_date="", description="Описание"
    )
    competition = connection.execute(
        "SELECT * FROM competitions WHERE id = ?", (competition_id,)
    ).fetchone()
    assert competition["platform"] == ""
    assert competition["url"] == ""
    assert competition["start_date"] == ""
    assert competition["description"] == "Описание"

    challenge_id = repositories.add_challenge(
        connection, competition_id, "Challenge", category="Web", description="Текст задания"
    )
    assert repositories.update_challenge(
        connection,
        challenge_id,
        competition_id,
        "Challenge",
        category="",
        difficulty=DEFAULT_DIFFICULTY,
        status="Новое",
        points=0,
        description="Текст задания",
    )
    challenge = repositories.get_challenge(connection, challenge_id)
    assert challenge["category"] == ""
    assert challenge["description"] == "Текст задания"
