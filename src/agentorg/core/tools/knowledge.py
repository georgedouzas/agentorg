"""Knowledge CRUD tools backed by AgentField memory.

A knowledge unit is anything an agent produces — text artifacts (research, memo, report) or structured data. Units live
in the node's **global-scope** memory under `kn:{type}:{name}` keys. These are agent *tools*: they run inside a reasoner
execution, so they resolve the running node via `Agent.get_current()`.
"""

import json
from datetime import UTC, datetime
from typing import Any

from agentfield import Agent

_PREFIX = 'kn:'


def _key(type_: str, name: str) -> str:
    return f'{_PREFIX}{type_}:{name}'


def _scope() -> Any:
    """Global-scope memory client of the running node (knowledge tools run inside a reasoner)."""
    node = Agent.get_current()
    if node is None:
        msg = 'Knowledge tools must run inside a reasoner execution.'
        raise RuntimeError(msg)
    return node.memory.global_scope


async def write_knowledge(
    type: str,  # noqa: A002
    name: str,
    content: str | None = None,
    title: str | None = None,
    data: dict[str, Any] | list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Write or update a knowledge unit.

    Returns confirmation.
    """
    await _scope().set(
        _key(type, name),
        {
            'type': type,
            'name': name,
            'title': title,
            'content': content,
            'data': data,
            'metadata': metadata or {},
            'updated_at': datetime.now(tz=UTC).isoformat(),
        },
    )
    return f"Saved {type} '{name}' to knowledge."


async def read_knowledge(type: str, name: str) -> str:  # noqa: A002
    """Read a knowledge unit by type and name.

    Returns content (markdown) or stringified data.
    """
    unit = await _scope().get(_key(type, name))
    if unit is None:
        return f"No {type} knowledge found for '{name}'."
    if unit.get('content'):
        return str(unit['content'])
    if unit.get('data') is not None:
        return json.dumps(unit['data'], indent=2)
    return ''


async def _all_units(scope: Any) -> list[dict[str, Any]]:
    keys = [k for k in await scope.list_keys() if k.startswith(_PREFIX)]
    units = [await scope.get(k) for k in keys]
    return [u for u in units if u is not None]


def _matches_metadata(unit: dict[str, Any], metadata_filter: dict[str, Any]) -> bool:
    md = unit.get('metadata') or {}
    return all(md.get(k) == v for k, v in metadata_filter.items())


async def list_knowledge(type: str = '', metadata_filter: dict[str, Any] | None = None) -> str:  # noqa: A002
    """List knowledge units, optionally filtered by type and/or metadata (subset match)."""
    scope = _scope()
    units = [
        u
        for u in await _all_units(scope)
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


async def search_knowledge(query: str, types: list[str] | None = None) -> str:
    """Substring search across knowledge content (case-insensitive)."""
    scope = _scope()
    needle = query.lower()
    hits: list[dict[str, Any]] = []
    for unit in await _all_units(scope):
        if types and unit.get('type') not in types:
            continue
        content = unit.get('content') or ''
        if needle in content.lower():
            hits.append(unit)
    if not hits:
        return f"No knowledge units matching '{query}'."
    hits.sort(key=lambda u: u.get('updated_at', ''), reverse=True)
    return '\n\n'.join(f'**{u.get("type")}/{u.get("name")}**\n{(u.get("content") or "")[:400]}…' for u in hits[:10])


async def delete_knowledge(type: str, name: str) -> str:  # noqa: A002
    """Delete a knowledge unit."""
    scope = _scope()
    key = _key(type, name)
    if await scope.get(key) is None:
        return f"No {type} knowledge found for '{name}'."
    await scope.delete(key)
    return f"Deleted {type} '{name}'."
