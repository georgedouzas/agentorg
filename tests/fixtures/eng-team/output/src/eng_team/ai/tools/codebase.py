"""Codebase tools — read project files, run searches, inspect repository structure."""

from pathlib import Path


def read_file(path: str) -> str:
    """Return the contents of a project file relative to the repo root."""
    return Path(path).read_text()


def list_files(directory: str = ".") -> list[str]:
    """List files under a directory, recursively."""
    return [str(p) for p in Path(directory).rglob("*") if p.is_file()]
