"""Memo-typed knowledge ops — investment memos."""

from typing import Any

from agentorg.tools.knowledge import list_knowledge, read_knowledge, search_knowledge, write_knowledge


def write_memo(name: str, title: str, content: str, metadata: dict[str, Any] | None = None) -> str:
    """Save an investment memo."""
    return write_knowledge(type="memo", name=name, title=title, content=content, metadata=metadata)


def read_memo(name: str) -> str:
    """Read an investment memo by name."""
    return read_knowledge(type="memo", name=name)


def list_memos(metadata_filter: dict[str, Any] | None = None) -> str:
    """List all memos, optionally filtered by metadata."""
    return list_knowledge(type="memo", metadata_filter=metadata_filter)


def search_memos(query: str) -> str:
    """Full-text + vector search across the memo archive."""
    return search_knowledge(query=query, types=["memo"])
