import csv
import sqlite3

import pytest

import reports
import repositories


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
