"""Research-typed knowledge ops — source-cited research documents."""

from typing import Any

from .knowledge import list_knowledge, read_knowledge, write_knowledge


def write_research_doc(name: str, title: str, content: str, metadata: dict[str, Any] | None = None) -> str:
    """Save a research document (sources-cited, drafted by the researcher)."""
    return write_knowledge(type="research", name=name, title=title, content=content, metadata=metadata)


def read_research_doc(name: str) -> str:
    """Read a research document by name."""
    return read_knowledge(type="research", name=name)


def list_research_docs(metadata_filter: dict[str, Any] | None = None) -> str:
    """List all research documents, optionally filtered by metadata."""
    return list_knowledge(type="research", metadata_filter=metadata_filter)
