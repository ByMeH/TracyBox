import csv
import os
import sqlite3
from pathlib import Path

import pytest

import reports
import repositories
from database import connect_database, get_database_path, initialize_database


@pytest.fixture
def competition_id(connection):
    return repositories.add_competition(
        connection,
        "Тестовый CTF",
        platform="ctftime",
        url="https://ctftime.org",
        start_date="2026-11-01",
        description="Учебное соревнование",
    )


@pytest.fixture
def filled_competition(connection, competition_id):
    challenge_id = repositories.add_challenge(
        connection,
        competition_id,
        "Базовая задача",
        category="Криптография",
        status="Решено",
        points=200,
        description="Первая строка условия\nвторая строка условия",
    )
    repositories.add_note(connection, challenge_id, "Идея", "Попробовать XOR\nи перебор ключей")
    repositories.add_artifact(
        connection, challenge_id, "/tmp/flag.txt", "flag.txt", 128, "a" * 64
    )
    repositories.add_challenge(connection, competition_id, "Минимальная задача")
    return competition_id


def snapshot_database(connection: sqlite3.Connection) -> dict[str, list[tuple]]:
    return {
        table: connection.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
        for table in ("competitions", "challenges", "notes", "artifacts")
    }


def load_entries(connection: sqlite3.Connection, competition_id: int):
    entries = []
    for challenge in repositories.get_challenges(connection, competition_id=competition_id):
        notes = repositories.get_notes(connection, challenge["id"])
        artifacts = repositories.get_artifacts(connection, challenge["id"])
        entries.append((challenge, notes, artifacts))
    return entries


def test_csv_content_with_cyrillic(connection, filled_competition, tmp_path):
    challenges = repositories.get_challenges(connection, competition_id=filled_competition)
    destination = tmp_path / "report.csv"

    reports.export_challenges_csv(challenges, destination)

    raw = destination.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")

    with open(destination, encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file, delimiter=";"))
    assert rows[0] == ["Название", "Категория", "Сложность", "Статус", "Баллы", "Описание"]
    assert rows[1] == [
        "Базовая задача",
        "Криптография",
        "Средняя",
        "Решено",
        "200",
        "Первая строка условия\nвторая строка условия",
    ]
    assert rows[2] == ["Минимальная задача", "", "Средняя", "Новое", "0", ""]


def test_csv_escapes_delimiter_and_quotes(connection, competition_id, tmp_path):
    repositories.add_challenge(
        connection, competition_id, "Сложная; задача", category="OSINT 'x'"
    )
    challenges = repositories.get_challenges(connection, competition_id=competition_id)
    destination = tmp_path / "report.csv"

    reports.export_challenges_csv(challenges, destination)

    with open(destination, encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file, delimiter=";"))
    assert rows[1] == ["Сложная; задача", "OSINT 'x'", "Средняя", "Новое", "0", ""]


def test_csv_without_challenges(connection, competition_id, tmp_path):
    challenges = repositories.get_challenges(connection, competition_id=competition_id)
    destination = tmp_path / "report.csv"

    reports.export_challenges_csv(challenges, destination)

    with open(destination, encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file, delimiter=";"))
    assert len(rows) == 1
    assert rows[0][0] == "Название"


def test_txt_contains_competition_and_challenge_fields(connection, filled_competition, tmp_path):
    competition = repositories.get_competitions(connection)[0]
    destination = tmp_path / "report.txt"

    reports.export_competition_txt(competition, load_entries(connection, filled_competition), destination)

    text = destination.read_text(encoding="utf-8")
    assert not text.startswith("\ufeff")
    assert "Соревнование: Тестовый CTF" in text
    assert "Организатор: ctftime" in text
    assert "Ссылка: https://ctftime.org" in text
    assert "Дата начала: 2026-11-01" in text
    assert "Описание:" in text
    assert "Заданий: 2" in text
    assert "1. Базовая задача" in text
    assert "Категория: Криптография" in text
    assert "Сложность: Средняя" in text
    assert "Статус: Решено" in text
    assert "Баллы: 200" in text
    assert "       вторая строка условия" in text
    assert "     - Идея (изменено" in text
    assert "и перебор ключей" in text
    assert f"     - flag.txt — 128 байт, SHA-256: {'a' * 64}" in text
    assert "2. Минимальная задача" in text


def test_txt_without_challenges(connection, competition_id, tmp_path):
    competition = repositories.get_competitions(connection)[0]
    destination = tmp_path / "report.txt"

    reports.export_competition_txt(competition, [], destination)

    text = destination.read_text(encoding="utf-8")
    assert "Соревнование: Тестовый CTF" in text
    assert "Заданий: 0" in text
    assert "В этом соревновании пока нет заданий." in text


def test_txt_skips_empty_optional_fields(connection, tmp_path):
    repositories.add_competition(connection, "Только название")
    competition = repositories.get_competitions(connection)[0]
    repositories.add_challenge(connection, competition["id"], "Без категории")
    destination = tmp_path / "report.txt"

    reports.export_competition_txt(
        competition, load_entries(connection, competition["id"]), destination
    )

    text = destination.read_text(encoding="utf-8")
    assert "Организатор:" not in text
    assert "Ссылка:" not in text
    assert "Категория:" not in text
    assert "Заметки:" not in text
    assert "Файлы:" not in text


def test_export_to_unavailable_path_raises_oserror(connection, filled_competition, tmp_path):
    challenges = repositories.get_challenges(connection, competition_id=filled_competition)
    competition = repositories.get_competitions(connection)[0]

    with pytest.raises(OSError):
        reports.export_challenges_csv(challenges, tmp_path / "missing" / "report.csv")
    with pytest.raises(OSError):
        reports.export_competition_txt(
            competition, load_entries(connection, filled_competition), tmp_path / "missing" / "report.txt"
        )


@pytest.mark.parametrize("export_format", ["csv", "txt"])
def test_normal_destination_is_allowed(connection, tmp_path, export_format):
    destination = tmp_path / f"report.{export_format}"

    assert not reports.overwrites_database(destination, get_database_path(connection))


def test_save_report_over_database_is_rejected(connection, filled_competition):
    database_path = get_database_path(connection)
    before = database_path.read_bytes()

    assert reports.overwrites_database(database_path, database_path)

    assert database_path.read_bytes() == before


def test_equivalent_paths_to_database_are_rejected(tmp_path):
    directory = tmp_path / "data"
    directory.mkdir()
    database_path = directory / "tracebox.db"
    connection = connect_database(database_path)
    initialize_database(connection)
    connection.close()

    file_link = tmp_path / "tracebox-link.db"
    file_link.symlink_to(database_path)
    directory_link = tmp_path / "link"
    directory_link.symlink_to(directory)
    hardlink = tmp_path / "tracebox-hardlink.db"
    os.link(database_path, hardlink)

    destinations = [
        database_path,
        directory / "." / "tracebox.db",
        directory / "sub" / ".." / "tracebox.db",
        Path(f"{directory}//tracebox.db"),
        Path(os.path.relpath(database_path)),
        file_link,
        directory_link / "tracebox.db",
        hardlink,
    ]

    for destination in destinations:
        assert reports.overwrites_database(destination, database_path), destination


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_absent_sidecar_destination_is_rejected(connection, suffix):
    database_path = get_database_path(connection)

    assert reports.overwrites_database(Path(f"{database_path}{suffix}"), database_path)


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_existing_sidecar_destination_is_rejected(connection, suffix):
    database_path = get_database_path(connection)
    sidecar = Path(f"{database_path}{suffix}")
    sidecar.write_bytes(b"journal data")
    before = sidecar.read_bytes()

    assert reports.overwrites_database(sidecar, database_path)
    assert sidecar.read_bytes() == before


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_sidecar_equivalent_paths_are_rejected(connection, tmp_path, suffix):
    database_path = get_database_path(connection)
    sidecar = Path(f"{database_path}{suffix}")
    sidecar.write_bytes(b"journal data")
    file_link = tmp_path / f"sidecar-link{suffix}"
    file_link.symlink_to(sidecar)
    hardlink = tmp_path / f"sidecar-hardlink{suffix}"
    os.link(sidecar, hardlink)

    destinations = [
        sidecar,
        database_path.parent / "sub" / ".." / sidecar.name,
        file_link,
        hardlink,
    ]

    for destination in destinations:
        assert reports.overwrites_database(destination, database_path), destination


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_neighbouring_files_are_allowed(connection, suffix):
    database_path = get_database_path(connection)

    assert not reports.overwrites_database(Path(f"{database_path}{suffix}-backup"), database_path)
    assert not reports.overwrites_database(Path(f"{database_path}{suffix}copy"), database_path)


def test_different_files_are_allowed(connection, tmp_path):
    database_path = get_database_path(connection)

    assert not reports.overwrites_database(tmp_path / "report.csv", database_path)
    assert not reports.overwrites_database(tmp_path / "missing" / "report.txt", database_path)


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root игнорирует права доступа к файлам",
)
def test_rejection_check_does_not_open_database_for_writing(connection, filled_competition):
    database_path = get_database_path(connection)
    database_path.chmod(0o444)
    try:
        assert reports.overwrites_database(database_path, database_path)
    finally:
        database_path.chmod(0o644)


def test_unnormalizable_path_is_rejected(connection):
    database_path = get_database_path(connection)

    assert reports.overwrites_database("report\0.csv", database_path)


def test_undeterminable_equivalence_is_rejected(connection, tmp_path, monkeypatch):
    database_path = get_database_path(connection)

    def denied(self, other):
        raise PermissionError("невозможно определить")

    monkeypatch.setattr(Path, "samefile", denied)

    assert reports.overwrites_database(tmp_path / "report.csv", database_path)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("CTF 2026", "CTF 2026"),
        ("a/b\\c", "a_b_c"),
        ('< > : " | ? *', "_ _ _ _ _ _ _"),
        ("конец.", "конец"),
        ("  пробелы  ", "пробелы"),
    ],
)
def test_sanitize_filename(name, expected):
    assert reports.sanitize_filename(name) == expected


@pytest.mark.parametrize("export_format", ["csv", "txt"])
def test_export_does_not_modify_database(connection, filled_competition, tmp_path, export_format):
    before = snapshot_database(connection)
    destination = tmp_path / f"report.{export_format}"

    if export_format == "csv":
        challenges = repositories.get_challenges(connection, competition_id=filled_competition)
        reports.export_challenges_csv(challenges, destination)
    else:
        competition = repositories.get_competitions(connection)[0]
        reports.export_competition_txt(
            competition, load_entries(connection, filled_competition), destination
        )

    assert snapshot_database(connection) == before


def test_csv_accepts_string_path(connection, competition_id, tmp_path):
    challenges = repositories.get_challenges(connection, competition_id=competition_id)
    destination = tmp_path / "report.csv"

    reports.export_challenges_csv(challenges, str(destination))

    assert destination.exists()
