import csv
import re
import sqlite3
from collections.abc import Sequence
from pathlib import Path

_CSV_HEADERS = ["Название", "Категория", "Сложность", "Статус", "Баллы", "Описание"]
_CSV_COLUMNS = ("title", "category", "difficulty", "status", "points", "description")

# Символы, запрещённые в именах файлов Windows: < > : " / \ | ? *
# и управляющие символы (0x00–0x1f, 0x7f). Linux запрещает только "/" и NUL.
_FORBIDDEN_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')

# Имена устройств Windows резервируются независимо от регистра и расширения;
# у COM и LPT зарезервированы и формы с надстрочными цифрами: COM¹–COM³, LPT¹–LPT³
_RESERVED_DEVICE_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL", "COM¹", "COM²", "COM³", "LPT¹", "LPT²", "LPT³"]
    + [f"COM{number}" for number in range(1, 10)]
    + [f"LPT{number}" for number in range(1, 10)]
)

# Максимальная длина компонента пути Windows в UTF-16 code units
_MAX_FILENAME_LENGTH = 255
_FALLBACK_NAME = "report"

# Служебные файлы SQLite рядом с базой: WAL, разделяемая память и журнал отката
_DATABASE_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def _char_units(character: str) -> int:
    # символы вне базовой многоязычной плоскости (эмодзи) занимают две UTF-16 code units
    return 2 if ord(character) > 0xFFFF else 1


def _utf16_units(text: str) -> int:
    return sum(_char_units(character) for character in text)


def _truncate_to_units(text: str, max_units: int) -> str:
    units = 0
    for index, character in enumerate(text):
        size = _char_units(character)
        if units + size > max_units:
            return text[:index]
        units += size
    return text


def _limit_length(name: str) -> str:
    if _utf16_units(name) <= _MAX_FILENAME_LENGTH:
        return name
    stem, dot, extension = name.rpartition(".")
    # укорачиваем имя, сохраняя расширение целиком
    if dot and stem and _utf16_units(extension) < _MAX_FILENAME_LENGTH - 2:
        keep = _MAX_FILENAME_LENGTH - _utf16_units(extension) - 1
        truncated_stem = _truncate_to_units(stem, keep)
        # если от имени перед расширением остались только точки и пробелы,
        # сохранять расширение бессмысленно — надёжнее вернуть запасное имя
        if truncated_stem.strip(" ."):
            return truncated_stem + "." + extension
        return _FALLBACK_NAME
    truncated = _truncate_to_units(name, _MAX_FILENAME_LENGTH).rstrip(" .")
    return truncated or _FALLBACK_NAME


def sanitize_filename(name: str) -> str:
    # Windows запрещает имена, заканчивающиеся точкой или пробелом;
    # начальная точка допустима (скрытые имена вида .report), поэтому убираем её только справа
    cleaned = _FORBIDDEN_NAME_CHARS.sub("_", name).strip(" ").rstrip(" .")
    if not cleaned:
        return _FALLBACK_NAME
    if cleaned.split(".", 1)[0].upper() in _RESERVED_DEVICE_NAMES:
        cleaned = "_" + cleaned
    limited = _limit_length(cleaned)
    # усечение может открыть зарезервированное имя в начале: CONxxx… сжимается до CON
    if limited.split(".", 1)[0].upper() in _RESERVED_DEVICE_NAMES:
        limited = _limit_length("_" + limited)
    return limited


def prepare_export_path(path: Path | str, export_format: str) -> Path:
    """Исправляет путь экспорта: санитизирует только имя файла, подгоняет расширение
    под формат и ограничивает длину итогового имени."""
    path = Path(path)
    name = sanitize_filename(path.name)
    stem, dot, extension = name.rpartition(".")
    if not dot or not stem:
        name = f"{name}.{export_format}"
    elif extension.lower() != export_format.lower():
        name = f"{stem}.{export_format}"
    limited = _limit_length(name)
    # усечение вырожденного имени возвращает запасное имя без расширения —
    # добавляем выбранный формат заново
    if limited == _FALLBACK_NAME:
        limited = f"{_FALLBACK_NAME}.{export_format}"
    return path.with_name(limited)


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
        except (OSError, ValueError):
            # сравнение невозможно (например, NUL в пути) — надёжнее запретить экспорт
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
