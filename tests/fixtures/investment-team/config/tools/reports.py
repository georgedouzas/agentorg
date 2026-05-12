"""Report-typed knowledge ops — analysis artifacts an agent produces and stores."""

from typing import Any

from .knowledge import delete_knowledge, list_knowledge, read_knowledge, write_knowledge


def write_agent_report(name: str, title: str, content: str, metadata: dict[str, Any] | None = None) -> str:
    """Save the agent's final analysis as a `report` knowledge entry."""
    return write_knowledge(type="report", name=name, title=title, content=content, metadata=metadata)


def read_agent_report(name: str) -> str:
    """Read a previously-saved agent report by name."""
    return read_knowledge(type="report", name=name)


def list_agent_reports(metadata_filter: dict[str, Any] | None = None) -> str:
    """List all agent reports, optionally filtered by metadata."""
    return list_knowledge(type="report", metadata_filter=metadata_filter)


def list_my_reports(metadata_filter: dict[str, Any] | None = None) -> str:
    """List the current agent's own reports (alias of ``list_agent_reports``)."""
    return list_knowledge(type="report", metadata_filter=metadata_filter)


def delete_my_report(name: str) -> str:
    """Delete a previously-saved agent report by name."""
    return delete_knowledge(type="report", name=name)
