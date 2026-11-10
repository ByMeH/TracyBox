import csv
import re
import sqlite3
from collections.abc import Sequence
from pathlib import Path

_CSV_HEADERS = ["Название", "Категория", "Сложность", "Статус", "Баллы", "Описание"]
_CSV_COLUMNS = ("title", "category", "difficulty", "status", "points", "description")

# Символы, запрещённые в именах файлов Windows: < > : " / \ | ? *
# и управляющие символы (0x00–0x1f). Linux запрещает только "/" и NUL.
_FORBIDDEN_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Служебные файлы SQLite рядом с базой: WAL, разделяемая память и журнал отката
_DATABASE_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def sanitize_filename(name: str) -> str:
    # Windows запрещает имена, заканчивающиеся точкой или пробелом
    return _FORBIDDEN_NAME_CHARS.sub("_", name).strip(" .")


def overwrites_database(path: Path | str, database_path: Path | str | None) -> bool:
    """Определяет, указывает ли путь сохранения на файл базы данных или её служебные файлы."""
    if database_path is None:
        return False
    try:
        target = Path(path).resolve()
        database = Path(database_path).resolve()
        # SQLite создаёт служебные файлы рядом с путём базы, переданным при подключении
        sidecars = [
            Path(f"{database_path}{suffix}").resolve() for suffix in _DATABASE_SIDECAR_SUFFIXES
        ]
    except (OSError, RuntimeError, ValueError):
        # безопасно сопоставить пути не удалось — надёжнее запретить экспорт
        return True
    for protected in (database, *sidecars):
        if target == protected:
            return True
        try:
            # файл может быть доступен под разными путями: ссылки, жёсткие ссылки, монтирование
            if target.samefile(protected):
                return True
        except FileNotFoundError:
            continue
        except OSError:
            return True
    return False


def export_challenges_csv(challenges: Sequence[sqlite3.Row], path: Path | str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(_CSV_HEADERS)
        for challenge in challenges:
            writer.writerow([str(challenge[column]) for column in _CSV_COLUMNS])


def export_competition_txt(
    competition: sqlite3.Row,
    entries: Sequence[tuple[sqlite3.Row, Sequence[sqlite3.Row], Sequence[sqlite3.Row]]],
    path: Path | str,
) -> None:
    lines = [
        "TraceBox — отчёт о соревновании",
        "",
        f"Соревнование: {competition['name']}",
    ]
    if competition["platform"]:
        lines.append(f"Организатор: {competition['platform']}")
    if competition["url"]:
        lines.append(f"Ссылка: {competition['url']}")
    if competition["start_date"]:
        lines.append(f"Дата начала: {competition['start_date']}")
    if competition["description"]:
        lines.extend(_indented("Описание:", competition["description"], " " * 4))
    lines.extend(["", f"Заданий: {len(entries)}", ""])
    if not entries:
        lines.append("В этом соревновании пока нет заданий.")

    for number, (challenge, notes, artifacts) in enumerate(entries, start=1):
        lines.append(f"{number}. {challenge['title']}")
        if challenge["category"]:
            lines.append(f"   Категория: {challenge['category']}")
        lines.append(f"   Сложность: {challenge['difficulty']}")
        lines.append(f"   Статус: {challenge['status']}")
        lines.append(f"   Баллы: {challenge['points']}")
        if challenge["description"]:
            lines.extend(_indented("   Описание:", challenge["description"], "       "))
        if notes:
            lines.append("   Заметки:")
            for note in notes:
                lines.append(f"     - {note['title']} (изменено {note['updated_at']}):")
                lines.extend(_indented("", note["content"], "         "))
        if artifacts:
            lines.append("   Файлы:")
            for artifact in artifacts:
                lines.append(
                    f"     - {artifact['file_name']} — {artifact['file_size']} байт,"
                    f" SHA-256: {artifact['sha256']}"
                )
        lines.append("")

    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def _indented(header: str, text: str, indent: str) -> list[str]:
    lines = [f"{indent}{line}" for line in text.splitlines()]
    return [header, *lines] if header else lines
