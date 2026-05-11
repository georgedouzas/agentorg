"""Research-typed knowledge ops — company/sector profiles."""

from typing import Any

from agentorg.tools.knowledge import list_knowledge, read_knowledge, write_knowledge


def write_research_doc(name: str, title: str, content: str, metadata: dict[str, Any] | None = None) -> str:
    """Save a research document (company profile, sector analysis, etc.)."""
    return write_knowledge(type="research", name=name, title=title, content=content, metadata=metadata)


def read_research_doc(name: str) -> str:
    """Read a research document by name."""
    return read_knowledge(type="research", name=name)


def list_research_docs(metadata_filter: dict[str, Any] | None = None) -> str:
    """List all research documents, optionally filtered by metadata."""
    return list_knowledge(type="research", metadata_filter=metadata_filter)
