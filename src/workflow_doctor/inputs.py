"""Bounded read-only local inputs. ZIP members are never extracted to disk."""
from __future__ import annotations

import os
from io import BytesIO
import stat
import zipfile
import zlib
from pathlib import Path, PurePosixPath

from .models import InputError, ScanLimits


def _regular_size(path: Path) -> int:
    try:
        info = path.lstat()
        if _is_link(info) or not stat.S_ISREG(info.st_mode):
            raise InputError("INPUT_UNSAFE_TYPE", "Input must be a regular file, not a link or special file", source=str(path))
        return info.st_size
    except OSError:
        raise InputError("INPUT_READ_ERROR", "Cannot access the input file", source=str(path)) from None


def _is_link(info) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def read_file(path: Path, byte_limit: int) -> bytes:
    if _regular_size(path) > byte_limit:
        raise InputError("INPUT_FILE_TOO_LARGE", "Input exceeds the available byte limit", source=str(path))
    try:
        with path.open("rb") as stream:
            raw = stream.read(byte_limit + 1)
        if len(raw) > byte_limit:
            raise InputError("INPUT_FILE_TOO_LARGE", "Input exceeds the available byte limit", source=str(path))
        return raw
    except OSError:
        raise InputError("INPUT_READ_ERROR", "Cannot read the input file", source=str(path)) from None


def collect_files(target: Path, recursive: bool, limits: ScanLimits) -> tuple[list[Path], list[dict]]:
    try:
        info = target.lstat()
        if _is_link(info):
            raise InputError("INPUT_UNSAFE_TYPE", "Input links and junctions are not followed")
        if stat.S_ISREG(info.st_mode):
            if target.suffix.lower() != ".json":
                raise InputError("INPUT_TYPE", "Input must be a JSON file, ZIP file or directory")
            files, skipped = [target], []
        elif stat.S_ISDIR(info.st_mode):
            files, skipped = [], []
            pending = [target]
            while pending:
                directory = pending.pop()
                with os.scandir(directory) as entries:
                    children = sorted(entries, key=lambda entry: entry.name)
                for entry in children:
                    path = Path(entry.path)
                    entry_info = entry.stat(follow_symlinks=False)
                    if _is_link(entry_info):
                        skipped.append({"file": str(path), "code": "INPUT_LINK_SKIPPED",
                                        "reason": "Links and junctions are not followed"})
                    elif stat.S_ISDIR(entry_info.st_mode):
                        if recursive:
                            pending.append(path)
                    elif stat.S_ISREG(entry_info.st_mode) and path.suffix.lower() == ".json":
                        files.append(path)
                        if len(files) > limits.max_files:
                            raise InputError("INPUT_FILE_COUNT", "JSON file count exceeds the limit")
                    elif path.suffix.lower() == ".json":
                        raise InputError("INPUT_UNSAFE_TYPE", "JSON input cannot be a special file", source=str(path))
            files.sort()
        else:
            raise InputError("INPUT_UNSAFE_TYPE", "Input must be a regular file or directory")
        total = 0
        for path in files:
            size = _regular_size(path)
            if size > limits.max_file_bytes:
                raise InputError("INPUT_FILE_TOO_LARGE", "JSON file exceeds the single-file byte limit", source=str(path))
            total += size
            if total > limits.max_total_bytes:
                raise InputError("INPUT_TOTAL_TOO_LARGE", "JSON batch exceeds the total byte limit")
        return files, skipped
    except OSError:
        raise InputError("INPUT_READ_ERROR", "Cannot access or enumerate the input") from None


def _member_key(info: zipfile.ZipInfo, location: str) -> str:
    # orig_filename retains NULs that ZipInfo.filename otherwise truncates.
    name = info.orig_filename.replace("\\", "/")
    parts = name.rstrip("/").split("/")
    if (not name or "\x00" in name or name.startswith("/")
            or any(part in ("", ".", "..") or ":" in part for part in parts)):
        raise InputError("ZIP_UNSAFE_PATH", "ZIP entry contains an unsafe path", location,
                         "Rebuild the ZIP with relative paths without parent traversal or drive prefixes.")
    mode = info.external_attr >> 16
    if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
        raise InputError("ZIP_UNSAFE_TYPE", "ZIP links and special files are not supported", location)
    return str(PurePosixPath(name)).casefold()


def read_zip(path: Path, limits: ScanLimits) -> tuple[list[tuple[str, bytes]], list[dict]]:
    """Preflight every entry, then read bounded JSON bytes and verify their CRCs.

    Non-JSON members count toward all metadata limits but are not decompressed.
    An unsafe or unreadable member rejects the entire archive, including results.
    """
    size = _regular_size(path)
    if size > limits.max_archive_bytes:
        raise InputError("ZIP_ARCHIVE_TOO_LARGE", "ZIP archive exceeds the compressed byte limit")
    try:
        with path.open("rb") as stream:
            return _read_zip_stream(stream, str(path), limits)
    except OSError:
        raise InputError("ZIP_INVALID", "ZIP cannot be read safely; it may be corrupt or truncated") from None


def read_zip_bytes(raw: bytes, source: str, limits: ScanLimits):
    """The same archive validator for bounded in-memory uploads; no extraction."""
    if len(raw) > limits.max_archive_bytes:
        raise InputError("ZIP_ARCHIVE_TOO_LARGE", "ZIP archive exceeds the compressed byte limit")
    return _read_zip_stream(BytesIO(raw), source, limits)


def _read_zip_stream(stream, source_label: str, limits: ScanLimits):
    location = "$"
    try:
        if stream.read(4) not in (b"PK\x03\x04", b"PK\x05\x06"):
            raise InputError("ZIP_INVALID", "Input does not have a supported ZIP signature")
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            if len(entries) > limits.max_files:
                raise InputError("ZIP_FILE_COUNT", "ZIP entry count exceeds the limit")
            seen, total = set(), 0
            for index, info in enumerate(entries):
                location = f"$.entries[{index}]"
                key = _member_key(info, location)
                if key in seen:
                    raise InputError("ZIP_DUPLICATE_PATH", "ZIP contains duplicate or case-colliding paths", location)
                seen.add(key)
                if info.flag_bits & 1:
                    raise InputError("ZIP_ENCRYPTED", "Encrypted ZIP entries are not supported", location)
                if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise InputError("ZIP_COMPRESSION", "ZIP compression method is not supported", location)
                if info.file_size > limits.max_file_bytes:
                    raise InputError("ZIP_FILE_TOO_LARGE", "ZIP entry exceeds the single-file byte limit", location)
                total += info.file_size
                if total > limits.max_total_bytes:
                    raise InputError("ZIP_TOTAL_TOO_LARGE", "ZIP exceeds the total decompressed byte limit", location)
            members, skipped = [], []
            actual_total = 0
            for index, info in enumerate(entries):
                location = f"$.entries[{index}]"
                source = f"{source_label}!entry[{index}]"
                if info.is_dir() or PurePosixPath(info.filename).suffix.lower() != ".json":
                    skipped.append({"file": source, "code": "ZIP_DIRECTORY" if info.is_dir() else "ZIP_NON_JSON",
                                    "reason": "Directory entry" if info.is_dir() else "Only JSON members are scanned"})
                    continue
                with archive.open(info, "r") as member:
                    raw = member.read(min(limits.max_file_bytes, limits.max_total_bytes - actual_total) + 1)
                actual_total += len(raw)
                if len(raw) > limits.max_file_bytes or actual_total > limits.max_total_bytes:
                    raise InputError("ZIP_SIZE_MISMATCH", "ZIP actual decompressed bytes exceed the limits", location)
                if len(raw) != info.file_size:
                    raise InputError("ZIP_SIZE_MISMATCH", "ZIP entry size does not match its metadata", location)
                members.append((source, raw))
            return members, skipped
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, RuntimeError,
            NotImplementedError, ValueError, zlib.error) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("ZIP_INVALID", "ZIP cannot be read safely; it may be corrupt or truncated", location,
                         "Rebuild the archive using ZIP Stored or Deflate without encryption.") from None
