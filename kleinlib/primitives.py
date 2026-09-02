"""Filesystem, hashing, and time primitives shared by the workflow modules.

Extracted verbatim from :mod:`kleinlib.workflow`: canonical JSON (the exact byte
form the event chain hashes), sha256 helpers, the fingerprint of a prepared-data
file or tree, atomic writes, and the study's advisory single-process lock.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .errors import WorkflowError

__all__ = [
    "StudyLock",
    "atomic_write_json",
    "atomic_write_text",
    "canonical_json",
    "fingerprint_path",
    "sha256_bytes",
    "sha256_file",
    "utc_now",
]


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_path(path: Path) -> str:
    """Hash a file or a directory tree without embedding its absolute location."""
    if not path.exists():
        raise WorkflowError(f"prepared data does not exist: {path}")
    if path.is_symlink():
        raise WorkflowError(f"prepared data must not be a symlink: {path}")
    if path.is_file():
        digest = hashlib.sha256(b"file\0" + path.name.encode() + b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    digest = hashlib.sha256(b"tree\0")
    entries = sorted(path.rglob("*"))
    symlinks = [entry for entry in entries if entry.is_symlink()]
    if symlinks:
        raise WorkflowError(
            "prepared data trees must not contain symlinks: "
            + ", ".join(str(item.relative_to(path)) for item in symlinks[:5])
        )
    files = [entry for entry in entries if entry.is_file()]
    if not files:
        raise WorkflowError(f"prepared data directory is empty: {path}")
    for item in files:
        rel = item.relative_to(path).as_posix().encode()
        digest.update(rel + b"\0")
        digest.update(bytes.fromhex(sha256_file(item)))
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


class StudyLock:
    """Portable single-process lock using exclusive file creation."""

    def __init__(self, study_dir: Path) -> None:
        self.path = study_dir / ".klein.lock"
        self.fd: int | None = None

    def __enter__(self) -> StudyLock:
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise WorkflowError(
                f"another Klein operation is active ({self.path}); remove a stale lock "
                "only after confirming no run is alive"
            ) from exc
        os.write(self.fd, f"pid={os.getpid()} started={utc_now()}\n".encode())
        return self

    def __exit__(self, *_: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
        self.path.unlink(missing_ok=True)
