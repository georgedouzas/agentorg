"""Policy-typed knowledge ops — committee policies and rules."""

from typing import Any

from agentorg.tools.knowledge import list_knowledge, read_knowledge, search_knowledge, write_knowledge


def write_policy(name: str, title: str, content: str, metadata: dict[str, Any] | None = None) -> str:
    """Save a policy document."""
    return write_knowledge(type="policy", name=name, title=title, content=content, metadata=metadata)


def read_policy(name: str) -> str:
    """Read a policy by name."""
    return read_knowledge(type="policy", name=name)


def list_policies(metadata_filter: dict[str, Any] | None = None) -> str:
    """List all policies, optionally filtered by metadata."""
    return list_knowledge(type="policy", metadata_filter=metadata_filter)


def search_policies(query: str) -> str:
    """Full-text + vector search across policies."""
    return search_knowledge(query=query, types=["policy"])
