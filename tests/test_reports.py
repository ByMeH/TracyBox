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


@pytest.mark.parametrize(
    "name, expected",
    [
        ("CON", "_CON"),
        ("PRN", "_PRN"),
        ("AUX", "_AUX"),
        ("NUL", "_NUL"),
        ("COM1", "_COM1"),
        ("COM9", "_COM9"),
        ("LPT1", "_LPT1"),
        ("LPT9", "_LPT9"),
        ("con.txt", "_con.txt"),
        ("NUL.csv", "_NUL.csv"),
        ("COM1.backup.txt", "_COM1.backup.txt"),
        ("Lpt4.tar.gz", "_Lpt4.tar.gz"),
        ("кон", "кон"),
        ("_CON", "_CON"),
    ],
)
def test_sanitize_reserved_device_names(name, expected):
    assert reports.sanitize_filename(name) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("", "report"),
        ("   ", "report"),
        (" . . ", "report"),
        ("a<b>c:d\"e|f?g*h", "a_b_c_d_e_f_g_h"),
        ("a\x00b\tc\nd\x7f", "a_b_c_d_"),
        ("отчёт по CTF", "отчёт по CTF"),
        ("Отчёт. Итоговый", "Отчёт. Итоговый"),
        (".report", ".report"),
        ("конец .", "конец"),
    ],
)
def test_sanitize_filename_cases(name, expected):
    assert reports.sanitize_filename(name) == expected


def test_sanitize_limits_long_name():
    assert reports.sanitize_filename("а" * 400) == "а" * 255


def test_sanitize_limits_long_name_keeps_extension():
    result = reports.sanitize_filename("а" * 400 + ".csv")

    assert len(result) == 255
    assert result.endswith(".csv")


def test_sanitize_limits_long_extension():
    result = reports.sanitize_filename("report." + "b" * 400)

    assert len(result) == 255


@pytest.mark.parametrize(
    "name",
    [
        "CTF 2026",
        "a/b\\c",
        "CON",
        "con.txt",
        ".report",
        "report.csv",
        "   ",
        "",
        "а" * 400 + ".csv",
        "_COM1.backup.txt",
    ],
)
def test_sanitize_filename_is_idempotent(name):
    sanitized = reports.sanitize_filename(name)

    assert reports.sanitize_filename(sanitized) == sanitized


@pytest.mark.parametrize(
    "name, export_format, expected",
    [
        ("report", "csv", "report.csv"),
        ("report.", "csv", "report.csv"),
        ("report.txt", "csv", "report.csv"),
        ("report.csv", "txt", "report.txt"),
        ("report.csv", "csv", "report.csv"),
        (".report", "csv", ".report.csv"),
        ("report.tar.gz", "csv", "report.tar.csv"),
        ("REPORT.CSV", "csv", "REPORT.CSV"),
        ("REPORT.CSV", "txt", "REPORT.txt"),
        ("report.Csv", "csv", "report.Csv"),
        ("report.TXT", "txt", "report.TXT"),
    ],
)
def test_prepare_export_path_sets_extension(tmp_path, name, export_format, expected):
    assert reports.prepare_export_path(tmp_path / name, export_format) == tmp_path / expected


def test_prepare_export_path_keeps_parent_with_spaces(tmp_path):
    directory = tmp_path / "CTF Reports"

    assert reports.prepare_export_path(directory / "report", "csv") == directory / "report.csv"


def test_prepare_export_path_keeps_cyrillic_parent(tmp_path):
    directory = tmp_path / "Отчёты"

    assert reports.prepare_export_path(directory / "итог", "txt") == directory / "итог.txt"


def test_prepare_export_path_sanitizes_only_file_name(tmp_path):
    directory = tmp_path / "CTF Reports"
    path = reports.prepare_export_path(directory / "bad:name?.csv", "csv")

    assert path.parent == directory
    assert path.name == "bad_name_.csv"


def test_prepare_export_path_keeps_relative_directory():
    path = reports.prepare_export_path(Path("отчёты") / "report.csv", "txt")

    assert path == Path("отчёты") / "report.txt"


def test_prepared_path_landing_on_database_is_rejected(tmp_path):
    database_path = tmp_path / "data.csv"
    connection = connect_database(database_path)
    initialize_database(connection)
    try:
        final = reports.prepare_export_path(tmp_path / "data.csv-wal", "csv")

        assert final == database_path
        assert reports.overwrites_database(final, database_path)
    finally:
        connection.close()


def test_prepared_path_off_database_is_allowed(connection, tmp_path):
    database_path = get_database_path(connection)
    final = reports.prepare_export_path(tmp_path / "report.txt", "csv")

    assert final == tmp_path / "report.csv"
    assert not reports.overwrites_database(final, database_path)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("COM¹", "_COM¹"),
        ("COM²", "_COM²"),
        ("COM³", "_COM³"),
        ("LPT¹", "_LPT¹"),
        ("LPT²", "_LPT²"),
        ("LPT³", "_LPT³"),
        ("com¹.txt", "_com¹.txt"),
        ("LPT³.csv", "_LPT³.csv"),
        ("Com².backup.txt", "_Com².backup.txt"),
    ],
)
def test_sanitize_superscript_reserved_names(name, expected):
    assert reports.sanitize_filename(name) == expected


def test_prepare_export_path_limits_final_component_units(tmp_path):
    path = reports.prepare_export_path(tmp_path / ("a" * 255), "csv")

    assert path.name == "a" * 251 + ".csv"
    assert len(path.name.encode("utf-16-le")) // 2 == 255
    assert path.parent == tmp_path


def test_prepare_export_path_keeps_txt_extension_after_truncation(tmp_path):
    path = reports.prepare_export_path(tmp_path / ("отчёт" * 100 + ".txt"), "txt")

    assert path.name.endswith(".txt")
    assert len(path.name.encode("utf-16-le")) // 2 <= 255


def test_sanitize_limits_emoji_name_by_utf16_units():
    result = reports.sanitize_filename("😀" * 300)

    assert len(result) == 127
    assert len(result.encode("utf-16-le")) // 2 == 254


def test_sanitize_truncation_does_not_split_emoji():
    result = reports.sanitize_filename("а" * 250 + "😀" * 10)

    assert result == "а" * 250 + "😀" * 2
    assert len(result.encode("utf-16-le")) // 2 == 254


@pytest.mark.parametrize(
    "name, export_format",
    [
        ("report", "csv"),
        ("a" * 255, "csv"),
        ("отчёт" * 100 + ".txt", "txt"),
        ("😀" * 300, "csv"),
        ("а" * 250 + "😀" * 10, "txt"),
        ("com¹.tar.gz", "csv"),
    ],
)
def test_prepare_export_path_is_idempotent(tmp_path, name, export_format):
    prepared = reports.prepare_export_path(tmp_path / name, export_format)

    assert reports.prepare_export_path(prepared, export_format) == prepared


def test_sanitize_truncation_does_not_end_with_space():
    result = reports.sanitize_filename("a" * 254 + " b")

    assert not result.endswith(" ")
    assert result == "a" * 254


def test_sanitize_truncation_does_not_end_with_dot():
    result = reports.sanitize_filename("a" * 254 + "." + "b" * 300)

    assert not result.endswith(".")
    assert result == "a" * 254


def test_sanitize_dots_only_truncation_returns_fallback():
    result = reports.sanitize_filename("." * 255 + "a")

    assert result == "report"


@pytest.mark.parametrize(
    "name",
    [
        "a" * 254 + " b",
        "a" * 254 + "." + "b" * 300,
        "." * 255 + "a",
        "😀" * 300 + " ",
        "а" * 254 + ". ",
    ],
)
def test_sanitize_truncated_result_is_idempotent(name):
    sanitized = reports.sanitize_filename(name)

    assert reports.sanitize_filename(sanitized) == sanitized


@pytest.mark.parametrize(
    "name",
    [
        "a" * 254 + " b",
        "a" * 254 + "." + "b" * 300,
        "." * 255 + "a",
        "😀" * 300 + " ",
        "а" * 254 + ". ",
    ],
)
def test_sanitize_truncated_result_fits_utf16_limit(name):
    result = reports.sanitize_filename(name)

    assert len(result.encode("utf-16-le")) // 2 <= 255


def test_sanitize_degenerate_stem_returns_fallback():
    result = reports.sanitize_filename("." * 250 + ". " + ".csv")

    assert result == "report"


@pytest.mark.parametrize(
    "name, export_format, expected",
    [
        ("." * 250 + ". " + ".csv", "csv", "report.csv"),
        ("." * 250 + ". " + ".txt", "txt", "report.txt"),
    ],
)
def test_prepare_export_path_adds_extension_to_fallback_name(
    tmp_path, name, export_format, expected
):
    prepared = reports.prepare_export_path(tmp_path / name, export_format)

    assert prepared.name == expected


def test_sanitize_truncation_does_not_create_reserved_name():
    result = reports.sanitize_filename("CON" + "x" * 300 + "." + "y" * 251)

    assert result.split(".", 1)[0].upper() not in reports._RESERVED_DEVICE_NAMES
    assert result.startswith("_")


@pytest.mark.parametrize(
    "name",
    [
        "." * 250 + ". " + ".csv",
        "CON" + "x" * 300 + "." + "y" * 251,
    ],
)
def test_sanitize_edge_cases_remain_idempotent(name):
    sanitized = reports.sanitize_filename(name)

    assert reports.sanitize_filename(sanitized) == sanitized


@pytest.mark.parametrize(
    "name",
    [
        "." * 250 + ". " + ".csv",
        "CON" + "x" * 300 + "." + "y" * 251,
    ],
)
def test_sanitize_edge_cases_fit_utf16_limit(name):
    result = reports.sanitize_filename(name)

    assert len(result.encode("utf-16-le")) // 2 <= 255


@pytest.mark.parametrize(
    "name, export_format",
    [
        ("." * 250 + ". " + ".csv", "csv"),
        ("." * 250 + ". " + ".txt", "txt"),
        ("CON" + "x" * 300 + "." + "y" * 251, "csv"),
    ],
)
def test_prepare_export_path_edge_cases_keep_extension_and_idempotent(
    tmp_path, name, export_format
):
    prepared = reports.prepare_export_path(tmp_path / name, export_format)

    assert prepared.name.lower().endswith("." + export_format)
    assert reports.prepare_export_path(prepared, export_format) == prepared
