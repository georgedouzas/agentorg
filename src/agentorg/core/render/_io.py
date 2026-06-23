"""Idempotent file writes for the renderer."""

import shutil
from pathlib import Path


def _file_matches(path: Path, content: bytes) -> bool:
    """True if `path` already exists with byte-content equal to `content`."""
    try:
        return path.read_bytes() == content
    except (FileNotFoundError, OSError):
        return False


def _write_template(content: str, dest: Path) -> None:
    """Write `content` to `dest`; skip the write when the bytes match."""
    payload = content.encode('utf-8')
    if not _file_matches(dest, payload):
        dest.write_bytes(payload)


def _copy_static(source: Path, dest: Path) -> None:
    """Copy a file byte-for-byte; skip the write when the bytes match."""
    if not _file_matches(dest, source.read_bytes()):
        shutil.copy(source, dest)
