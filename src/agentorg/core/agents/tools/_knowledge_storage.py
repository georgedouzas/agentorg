"""Storage primitives over an AgentField memory scope for the org's knowledge corpus."""

from typing import Any

import litellm

PREFIX = 'kn:'

# Bridges agno-style provider names (e.g. `google`) to litellm's provider keys (`gemini`).
_LITELLM_PROVIDER_ALIASES = {'google': 'gemini'}


def key(type_: str, name: str) -> str:
    """Compose the memory key for a knowledge unit.

    Arguments:
        type_: The knowledge type.
        name: The unit name within the type.

    Returns:
        key: The composed `kn:<type>:<name>` memory key.
    """
    return f'{PREFIX}{type_}:{name}'


async def embed(text: str, model: str | None) -> list[float] | None:
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
    if provider and leaf:
        full = f'{_LITELLM_PROVIDER_ALIASES.get(provider, provider)}/{leaf}'
    else:
        full = model
    resp = await litellm.aembedding(model=full, input=text)
    return list(resp.data[0]['embedding'])


async def list_units(scope: Any) -> list[dict[str, Any]]:
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
    scope: Any,
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
    vec = await embed(query, embedder)
    if vec is not None:
        filters = {'type': {'$in': types}} if types else None
        hits = await scope.similarity_search(vec, top_k=top_k, filters=filters)
        units = [await scope.get(h.get('key') or h.get('id')) for h in hits if (h.get('key') or h.get('id'))]
        return [u for u in units if u is not None]
    needle = query.lower()
    matches = [
        u
        for u in await list_units(scope)
        if (not types or u.get('type') in types) and needle in (u.get('content') or '').lower()
    ]
    matches.sort(key=lambda u: u.get('updated_at', ''), reverse=True)
    return matches[:top_k]
