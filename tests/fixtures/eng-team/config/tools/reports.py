"""Engineering report tools — write and read engineering analysis artifacts (specs, ADRs, reviews)."""

from typing import Any

from .documents import (
    list_documents,
    read_document,
    write_document,
)


def write_report(name: str, content: str, metadata: dict[str, Any] | None = None) -> str:
    """Write an engineering report (spec, ADR, code review).

    Stored under type='report'.
    """
    return write_document(type="report", name=name, content=content, metadata=metadata)


def read_report(name: str) -> str:
    """Read an engineering report by name."""
    return read_document(type="report", name=name)


def list_reports() -> list[dict[str, Any]]:
    """List all engineering reports."""
    return list_documents(type="report")
