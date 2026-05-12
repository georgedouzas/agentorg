"""Report-typed knowledge ops — published analysis reports."""

from typing import Any

from .knowledge import list_knowledge, read_knowledge, write_knowledge


def write_agent_report(name: str, title: str, content: str, metadata: dict[str, Any] | None = None) -> str:
    """Save the analyst's final report as a `report` knowledge entry."""
    return write_knowledge(type="report", name=name, title=title, content=content, metadata=metadata)


def read_agent_report(name: str) -> str:
    """Read a previously-saved analyst report by name."""
    return read_knowledge(type="report", name=name)


def list_agent_reports(metadata_filter: dict[str, Any] | None = None) -> str:
    """List all analyst reports, optionally filtered by metadata."""
    return list_knowledge(type="report", metadata_filter=metadata_filter)
