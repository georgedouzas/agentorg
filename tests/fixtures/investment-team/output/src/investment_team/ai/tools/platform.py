"""Platform reference knowledge ops — read-only platform docs (Clerk, GitHub, Railway, Vercel)."""

from typing import Any

from .knowledge import list_knowledge, read_knowledge, search_knowledge


def read_platform_doc(name: str) -> str:
    """Read a platform reference doc by name."""
    return read_knowledge(type="platform_reference", name=name)


def list_platform_docs(metadata_filter: dict[str, Any] | None = None) -> str:
    """List all platform reference docs."""
    return list_knowledge(type="platform_reference", metadata_filter=metadata_filter)


def search_platform_docs(query: str) -> str:
    """Full-text + vector search across platform docs."""
    return search_knowledge(query=query, types=["platform_reference"])
