"""Agent-callable knowledge tools plus the storage primitives they share with the rendered org's routes."""

import contextlib
from datetime import UTC, datetime
from typing import Any

import litellm
from agentfield import Agent
from agentfield.memory import ScopedMemoryClient

from ._tags import tags

PREFIX = 'kn:'
LITELLM_PROVIDER_ALIASES = {'google': 'gemini'}


def _key(type_: str, name: str) -> str:
    """Compose the memory key for a knowledge unit.

    Arguments:
        type_: The knowledge type.
        name: The unit name within the type.

    Returns:
        key: The composed `kn:<type>:<name>` memory key.
    """
    return f'{PREFIX}{type_}:{name}'


async def _embed(text: str, model: str | None) -> list[float] | None:
    """Compute an embedding for `text` using `model`.

    Arguments:
        text: The text to embed.
        model: A `provider:name` pair, or None to disable embedding.

    Returns:
        vector: The embedding, or None when no model is configured.
    """
    if not model:
        return None
    provider, _, leaf = model.partition(':')
    full = f'{LITELLM_PROVIDER_ALIASES.get(provider, provider)}/{leaf}' if provider and leaf else model
    resp = await litellm.aembedding(model=full, input=text)
    return list(resp.data[0]['embedding'])


async def _list_units(scope: ScopedMemoryClient) -> list[dict[str, Any]]:
    """Hydrate every knowledge unit stored under the `kn:` prefix.

    Arguments:
        scope: The AgentField memory scope to read from.

    Returns:
        units: The stored knowledge units.
    """
    keys = [k for k in await scope.list_keys() if k.startswith(PREFIX)]
    units = [await scope.get(k) for k in keys]
    return [u for u in units if u is not None]


async def similarity_units(
    scope: ScopedMemoryClient,
    embedder: str | None,
    query: str,
    types: list[str] | None,
    top_k: int,
) -> list[dict[str, Any]]:
    """Rank knowledge units by embedding similarity, falling back to substring when no embedder.

    Arguments:
        scope: The AgentField memory scope to search.
        embedder: The `provider:name` embedder model, or None.
        query: The query text.
        types: Restrict to these knowledge types, or None for all.
        top_k: Maximum number of hits to return.

    Returns:
        units: The top-ranked knowledge units.
    """
    vec = await _embed(query, embedder)
    if vec is not None:
        filters = {'type': {'$in': types}} if types else None
        hits = await scope.similarity_search(vec, top_k=top_k, filters=filters)
        units = [await scope.get(h.get('key') or h.get('id')) for h in hits if (h.get('key') or h.get('id'))]
        return [u for u in units if u is not None]
    needle = query.lower()
    matches = [
        u
        for u in await _list_units(scope)
        if (not types or u.get('type') in types) and needle in (u.get('content') or '').lower()
    ]
    matches.sort(key=lambda u: u.get('updated_at', ''), reverse=True)
    return matches[:top_k]


def _node() -> Agent:
    node = Agent.get_current()
    if node is None:
        msg = 'Knowledge tools must run inside a reasoner execution.'
        raise RuntimeError(msg)
    return node


def _scope() -> ScopedMemoryClient:
    return _node().memory.global_scope


def _embedder() -> str | None:
    return getattr(_node(), 'embedder_model', None)


def _matches_metadata(unit: dict[str, Any], metadata_filter: dict[str, Any]) -> bool:
    md = unit.get('metadata') or {}
    return all(md.get(k) == v for k, v in metadata_filter.items())


@tags('knowledge')
async def write_knowledge(
    type: str,  # noqa: A002
    name: str,
    content: str,
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Write or update a knowledge unit.

    Arguments:
        type: The knowledge type.
        name: The unique unit name within the type.
        content: Markdown body for the unit.
        title: Display title.
        metadata: Free-form metadata.

    Returns:
        message: Confirmation that the unit was saved.
    """
    scope = _scope()
    md = dict(metadata or {})
    await scope.set(
        _key(type, name),
        {
            'type': type,
            'name': name,
            'title': title,
            'content': content,
            'metadata': md,
            'updated_at': datetime.now(tz=UTC).isoformat(),
        },
    )
    vec = await _embed(f'{title or name}\n\n{content}', _embedder())
    if vec is not None:
        await scope.set_vector(_key(type, name), vec, metadata={'type': type, 'name': name, **md})
    return f"Saved {type} '{name}' to knowledge."


@tags('knowledge')
async def read_knowledge(type: str, name: str) -> str:  # noqa: A002
    """Read a knowledge unit by type and name.

    Arguments:
        type: The knowledge type.
        name: The unit name.

    Returns:
        content: The unit's content, or a not-found message.
    """
    unit = await _scope().get(_key(type, name))
    if unit is None:
        return f"No {type} knowledge found for '{name}'."
    return str(unit['content'])


@tags('knowledge')
async def list_knowledge(knowledge_type: str = '', metadata_filter: dict[str, Any] | None = None) -> str:
    """List knowledge units, optionally filtered by type and metadata.

    Arguments:
        knowledge_type: Restrict to this knowledge type, or empty for all.
        metadata_filter: Subset match against unit metadata, or None.

    Returns:
        listing: A formatted listing of matching units.
    """
    scope = _scope()
    units = [
        u
        for u in await _list_units(scope)
        if (not knowledge_type or u.get('type') == knowledge_type)
        and (not metadata_filter or _matches_metadata(u, metadata_filter))
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
        title_part = f' — {unit["title"]}' if unit.get('title') else ''
        meta = f' {unit["metadata"]}' if unit.get('metadata') else ''
        lines.append(f'  - {unit.get("name")}{title_part}{meta}  (updated {unit.get("updated_at", "?")})')
    return '\n'.join(lines)


@tags('knowledge')
async def search_knowledge(query: str, types: list[str] | None = None, top_k: int = 10) -> str:
    """Search knowledge units ranked by embedding similarity.

    Arguments:
        query: The query text.
        types: Restrict to these knowledge types, or None for all.
        top_k: Maximum number of hits.

    Returns:
        results: Formatted top-matching units.
    """
    hits = await similarity_units(_scope(), _embedder(), query, types, top_k)
    if not hits:
        return f"No knowledge units matching '{query}'."
    return '\n\n'.join(f'**{u.get("type")}/{u.get("name")}**\n{(u.get("content") or "")[:400]}…' for u in hits)


@tags('knowledge')
async def delete_knowledge(type: str, name: str) -> str:  # noqa: A002
    """Delete a knowledge unit and its embedding.

    Arguments:
        type: The knowledge type.
        name: The unit name.

    Returns:
        message: Confirmation of deletion, or a not-found message.
    """
    scope = _scope()
    k = _key(type, name)
    if await scope.get(k) is None:
        return f"No {type} knowledge found for '{name}'."
    await scope.delete(k)
    with contextlib.suppress(Exception):
        await scope.delete_vector(k)
    return f"Deleted {type} '{name}'."
