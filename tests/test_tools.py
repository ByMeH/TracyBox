import base64
import binascii
import hashlib
import os
from unittest import mock

import pytest

import tools


MD5_EMPTY = "d41d8cd98f00b204e9800998ecf8427e"
SHA1_EMPTY = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
SHA256_EMPTY = (
    "e3b0c44298fc1c149afbf4c8996fb924"
    "27ae41e4649b934ca495991b7852b855"
)


def test_hashes_of_empty_file(tmp_path):
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")

    hashes = tools.calculate_file_hashes(path)

    assert hashes == {
        "md5": MD5_EMPTY,
        "sha1": SHA1_EMPTY,
        "sha256": SHA256_EMPTY,
    }


def test_hashes_match_known_values(tmp_path):
    path = tmp_path / "abc.txt"
    path.write_bytes(b"abc")

    hashes = tools.calculate_file_hashes(path)

    assert hashes["md5"] == "900150983cd24fb0d6963f7d28e17f72"
    assert hashes["sha1"] == "a9993e364706816aba3e25717850c26c9cd0d89d"
    assert hashes["sha256"] == (
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )


def test_hashes_match_hashlib_for_large_file(tmp_path):
    data = bytes(range(256)) * (tools.CHUNK_SIZE // 256) + b"tail"
    assert len(data) > tools.CHUNK_SIZE
    path = tmp_path / "large.bin"
    path.write_bytes(data)

    hashes = tools.calculate_file_hashes(path)

    assert hashes["md5"] == hashlib.md5(data).hexdigest()
    assert hashes["sha1"] == hashlib.sha1(data).hexdigest()
    assert hashes["sha256"] == hashlib.sha256(data).hexdigest()


def test_hashing_does_not_modify_file(tmp_path):
    data = b"do not touch"
    path = tmp_path / "file.bin"
    path.write_bytes(data)

    tools.calculate_file_hashes(path)

    assert path.read_bytes() == data


def test_hashing_missing_file(tmp_path):
    with pytest.raises(OSError):
        tools.calculate_file_hashes(tmp_path / "missing.bin")


def test_hashing_directory_instead_of_file(tmp_path):
    with pytest.raises(OSError):
        tools.calculate_file_hashes(tmp_path)


def test_hashing_read_error(tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"data")
    with mock.patch("builtins.open") as fake_open:
        fake_open.return_value.__enter__.return_value.read.side_effect = OSError(
            "read failed"
        )
        with pytest.raises(OSError, match="read failed"):
            tools.calculate_file_hashes(path)


def test_hashes_match_hashlib_for_exactly_one_chunk(tmp_path):
    data = bytes(range(256)) * (tools.CHUNK_SIZE // 256)
    assert len(data) == tools.CHUNK_SIZE
    path = tmp_path / "one_chunk.bin"
    path.write_bytes(data)

    hashes = tools.calculate_file_hashes(path)

    assert hashes["md5"] == hashlib.md5(data).hexdigest()
    assert hashes["sha1"] == hashlib.sha1(data).hexdigest()
    assert hashes["sha256"] == hashlib.sha256(data).hexdigest()


def test_hashes_match_hashlib_for_exactly_two_chunks(tmp_path):
    data = bytes(range(256)) * (2 * tools.CHUNK_SIZE // 256)
    assert len(data) == 2 * tools.CHUNK_SIZE
    path = tmp_path / "two_chunks.bin"
    path.write_bytes(data)

    hashes = tools.calculate_file_hashes(path)

    assert hashes["md5"] == hashlib.md5(data).hexdigest()
    assert hashes["sha1"] == hashlib.sha1(data).hexdigest()
    assert hashes["sha256"] == hashlib.sha256(data).hexdigest()


def test_stable_hashes_unchanged_file(tmp_path):
    data = b"stable payload"
    path = tmp_path / "file.bin"
    path.write_bytes(data)

    hashes, file_size = tools.calculate_stable_file_hashes(path)

    assert file_size == len(data)
    assert hashes == {
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def test_stable_hashes_detect_size_change_during_reading(tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"data")

    def grow_and_hash(target):
        with open(target, "rb") as file:
            file.read()
        path.write_bytes(b"data plus tail")
        return {"md5": "0", "sha1": "0", "sha256": "0"}

    with mock.patch.object(tools, "calculate_file_hashes", grow_and_hash):
        with pytest.raises(tools.FileChangedDuringHashing):
            tools.calculate_stable_file_hashes(path)


def test_stable_hashes_detect_mtime_change_during_reading(tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"data")

    def touch_and_hash(target):
        with open(target, "rb") as file:
            file.read()
        os.utime(path, ns=(0, 1))
        return {"md5": "0", "sha1": "0", "sha256": "0"}

    with mock.patch.object(tools, "calculate_file_hashes", touch_and_hash):
        with pytest.raises(tools.FileChangedDuringHashing):
            tools.calculate_stable_file_hashes(path)


def test_stable_hashes_detect_replacement_during_reading(tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"payload")
    original = path.stat()
    replacement = tmp_path / "replacement.bin"
    replacement.write_bytes(b"payload")
    os.utime(replacement, ns=(original.st_atime_ns, original.st_mtime_ns))

    def replace_and_hash(target):
        with open(target, "rb") as file:
            file.read()
        replacement.replace(path)
        return {"md5": "0", "sha1": "0", "sha256": "0"}

    with mock.patch.object(tools, "calculate_file_hashes", replace_and_hash):
        with pytest.raises(tools.FileChangedDuringHashing):
            tools.calculate_stable_file_hashes(path)


def test_stable_hashes_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        tools.calculate_stable_file_hashes(tmp_path / "missing.bin")


def test_stable_hashes_access_error(tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"data")
    with mock.patch("builtins.open", side_effect=PermissionError("access denied")):
        with pytest.raises(PermissionError):
            tools.calculate_stable_file_hashes(path)


def test_base64_known_value():
    assert tools.encode_base64("Hello") == "SGVsbG8="
    assert tools.decode_base64("SGVsbG8=") == "Hello"


def test_base64_round_trip_with_cyrillic():
    text = "Привет, мир! ЁёЙй"
    assert tools.decode_base64(tools.encode_base64(text)) == text


def test_base64_round_trip_with_unicode_emoji():
    text = "flag{héllo_🌍}"
    assert tools.decode_base64(tools.encode_base64(text)) == text


def test_base64_encode_empty_string():
    assert tools.encode_base64("") == ""
    assert tools.decode_base64("") == ""


def test_base64_decode_invalid_characters():
    with pytest.raises(binascii.Error):
        tools.decode_base64("not base64!!")


def test_base64_decode_non_ascii_input():
    with pytest.raises(ValueError):
        tools.decode_base64("не base64!!")


def test_base64_decode_wrong_padding():
    with pytest.raises(binascii.Error):
        tools.decode_base64("SGVsbG8")


def test_base64_decode_with_newlines_and_spaces():
    assert tools.decode_base64("SGVs\nbG8=") == "Hello"
    assert tools.decode_base64("SGVsb G8=") == "Hello"
    assert tools.decode_base64("SGVsb\tG8=\r\n") == "Hello"


def test_base64_decode_rejects_non_whitespace_garbage():
    with pytest.raises(binascii.Error):
        tools.decode_base64("SGVs-bG8=")


def test_base64_decode_invalid_utf8():
    data = b"\xff\xfe"
    encoded = base64.b64encode(data).decode("ascii")
    with pytest.raises(UnicodeDecodeError):
        tools.decode_base64(encoded)


def test_hex_known_value():
    assert tools.encode_hex("ABC") == "414243"
    assert tools.decode_hex("414243") == "ABC"


def test_hex_round_trip_with_cyrillic():
    text = "Секретный флаг: CTF{hex}"
    assert tools.decode_hex(tools.encode_hex(text)) == text


def test_hex_encode_empty_string():
    assert tools.encode_hex("") == ""
    assert tools.decode_hex("") == ""


def test_hex_decode_invalid_characters():
    with pytest.raises(ValueError):
        tools.decode_hex("zz")


def test_hex_decode_odd_length():
    with pytest.raises(ValueError):
        tools.decode_hex("abc")


def test_hex_decode_invalid_utf8():
    with pytest.raises(UnicodeDecodeError):
        tools.decode_hex("fffe")


def test_url_encode_known_value():
    assert tools.encode_url("a b&c=d") == "a%20b%26c%3Dd"


def test_url_decode_known_value():
    assert tools.decode_url("%D0%BF%D1%80%D0%B8") == "при"


def test_url_round_trip_with_cyrillic_and_specials():
    text = "поиск?q=CTF челлендж/1&safe=no"
    assert tools.decode_url(tools.encode_url(text)) == text


def test_url_encode_empty_string():
    assert tools.encode_url("") == ""
    assert tools.decode_url("") == ""


def test_url_decode_invalid_utf8_sequence():
    with pytest.raises(UnicodeDecodeError):
        tools.decode_url("%ff%fe")
