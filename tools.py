import base64
import hashlib
import re
from pathlib import Path
from urllib.parse import quote, unquote

CHUNK_SIZE = 1024 * 1024

# Base64 часто вставляют с переносами строк; удаляем только ASCII-пробельные символы
_BASE64_WHITESPACE = str.maketrans("", "", " \t\r\n")


def calculate_file_hashes(path: Path | str) -> dict[str, str]:
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    with open(path, "rb") as file:
        while chunk := file.read(CHUNK_SIZE):
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
    return {
        "md5": md5.hexdigest(),
        "sha1": sha1.hexdigest(),
        "sha256": sha256.hexdigest(),
    }


class FileChangedDuringHashing(OSError):
    """Файл изменился, пока вычислялись его хеши."""


def calculate_stable_file_hashes(path: Path | str) -> tuple[dict[str, str], int]:
    """Хеши и размер файла, который не изменился за время чтения."""
    stat_before = Path(path).stat()
    hashes = calculate_file_hashes(path)
    stat_after = Path(path).stat()
    before = (stat_before.st_size, stat_before.st_mtime_ns, stat_before.st_dev, stat_before.st_ino)
    after = (stat_after.st_size, stat_after.st_mtime_ns, stat_after.st_dev, stat_after.st_ino)
    if before != after:
        raise FileChangedDuringHashing(path)
    return hashes, stat_after.st_size


def encode_base64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def decode_base64(text: str) -> str:
    # validate=True запрещает символы вне алфавита Base64 и неверный padding
    data = base64.b64decode(text.translate(_BASE64_WHITESPACE), validate=True)
    return data.decode("utf-8")


def encode_hex(text: str) -> str:
    return text.encode("utf-8").hex()


def decode_hex(text: str) -> str:
    return bytes.fromhex(text).decode("utf-8")


def encode_url(text: str) -> str:
    return quote(text, safe="")


# unquote не считает ошибкой «%», за которым нет двух hex-цифр, поэтому такие
# места проверяем отдельно
_MALFORMED_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")


def decode_url(text: str) -> str:
    malformed = _MALFORMED_PERCENT.search(text)
    if malformed:
        raise ValueError(f"Некорректная percent-последовательность в позиции {malformed.start()}")
    # errors="strict" превращает битую UTF-8-последовательность в UnicodeDecodeError
    return unquote(text, errors="strict")
