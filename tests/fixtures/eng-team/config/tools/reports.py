"""Engineering report tools — write and read engineering analysis artifacts (specs, ADRs, reviews)."""

from typing import Any

from .knowledge import list_knowledge, read_knowledge, write_knowledge


def write_report(name: str, content: str, metadata: dict[str, Any] | None = None) -> str:
    """Write an engineering report (spec, ADR, code review).

    Stored under type='report'.
    """
    return write_knowledge(type="report", name=name, content=content, metadata=metadata)


def read_report(name: str) -> str:
    """Read an engineering report by name."""
    return read_knowledge(type="report", name=name)


def list_reports() -> list[dict[str, Any]]:
    """List all engineering reports."""
    return list_knowledge(type="report")
