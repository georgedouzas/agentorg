"""Agent-callable wrappers over the knowledge scope ops, resolving the running AgentField node."""

import json
from datetime import UTC, datetime
from typing import Any

from agentfield import Agent

from agentorg.core.knowledge._base import embed, key, list_units, similarity_units


def _node() -> Any:
    node = Agent.get_current()
    if node is None:
        msg = 'Knowledge tools must run inside a reasoner execution.'
        raise RuntimeError(msg)
    return node


def _scope() -> Any:
    return _node().memory.global_scope


def _embedder() -> str | None:
    return getattr(_node(), 'embedder_model', None)


async def write_knowledge(
    type: str,  # noqa: A002
    name: str,
    content: str | None = None,
    title: str | None = None,
    data: dict[str, Any] | list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Write or update a knowledge unit.

    Persists the unit and (when content is present) stores an embedding alongside it so
    `search_knowledge` can rank by semantic similarity.
    """
    scope = _scope()
    md = metadata or {}
    await scope.set(
        key(type, name),
        {
            'type': type,
            'name': name,
            'title': title,
            'content': content,
            'data': data,
            'metadata': md,
            'updated_at': datetime.now(tz=UTC).isoformat(),
        },
    )
    if content:
        vec = await embed(f'{title or name}\n\n{content}', _embedder())
        if vec is not None:
            await scope.set_vector(key(type, name), vec, metadata={'type': type, 'name': name, **md})
    return f"Saved {type} '{name}' to knowledge."


async def read_knowledge(type: str, name: str) -> str:  # noqa: A002
    """Read a knowledge unit by type and name; returns content (markdown) or stringified data."""
    unit = await _scope().get(key(type, name))
    if unit is None:
        return f"No {type} knowledge found for '{name}'."
    if unit.get('content'):
        return str(unit['content'])
    if unit.get('data') is not None:
        return json.dumps(unit['data'], indent=2)
    return ''


def _matches_metadata(unit: dict[str, Any], metadata_filter: dict[str, Any]) -> bool:
    md = unit.get('metadata') or {}
    return all(md.get(k) == v for k, v in metadata_filter.items())


async def list_knowledge(type: str = '', metadata_filter: dict[str, Any] | None = None) -> str:  # noqa: A002
    """List knowledge units, optionally filtered by type and/or metadata (subset match)."""
    scope = _scope()
    units = [
        u
        for u in await list_units(scope)
        if (not type or u.get('type') == type) and (not metadata_filter or _matches_metadata(u, metadata_filter))
    ]
    if not units:
        return 'No knowledge units found.'
    units.sort(key=lambda u: (u.get('type', ''), u.get('name', '')))
    lines: list[str] = []
    current = None
    for unit in units:
        if unit.get('type') != current:
            current = unit.get('type')
            lines.append(f'{str(current).title()}:')
        title = unit.get('title') or unit.get('name')
        meta = f' {unit["metadata"]}' if unit.get('metadata') else ''
        lines.append(f'  - {unit.get("name")} — {title}{meta}  (updated {unit.get("updated_at", "?")})')
    return '\n'.join(lines)


async def search_knowledge(query: str, types: list[str] | None = None, top_k: int = 10) -> str:
    """Search knowledge units ranked by embedding similarity (substring fallback)."""
    hits = await similarity_units(_scope(), _embedder(), query, types, top_k)
    if not hits:
        return f"No knowledge units matching '{query}'."
    return '\n\n'.join(f'**{u.get("type")}/{u.get("name")}**\n{(u.get("content") or "")[:400]}…' for u in hits)


async def delete_knowledge(type: str, name: str) -> str:  # noqa: A002
    """Delete a knowledge unit and its embedding (if present)."""
    scope = _scope()
    k = key(type, name)
    if await scope.get(k) is None:
        return f"No {type} knowledge found for '{name}'."
    await scope.delete(k)
    try:
        await scope.delete_vector(k)
    except Exception:  # noqa: BLE001 — vector may not exist if no embedder was configured at write time
        pass
    return f"Deleted {type} '{name}'."
