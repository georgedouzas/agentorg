"""FastAPI router for the rendered org's agentorg-specific endpoints."""

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, create_model

from agentorg.core.knowledge import PREFIX as _KN_PREFIX, similarity_units
from agentorg.core.platform import PLATFORM_AGENT_GROUPS, PLATFORM_AGENT_ICONS, PLATFORM_AGENT_IDS
from agentorg.core.spec import Spec


class _Safe(dict):
    """`dict` that returns `{key}` for missing keys so charter bodies survive incomplete state."""

    def __missing__(self, key: str) -> str:
        return '{' + key + '}'


def _py_type(t: str) -> type:
    return {'int': int, 'float': float, 'string': str, 'bool': bool, 'object': dict, 'array': list}.get(t, str)


def _state_model(spec: Spec) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for p in spec.knowledge.charter.parameters:
        py = _py_type(p.type)
        fields[p.name] = (py, Field(default=p.default))
    return create_model('OrgConfig', **fields)  # type: ignore[call-overload]


def _document(unit: dict[str, Any]) -> dict[str, Any]:
    """Project a stored knowledge unit into the shape the frontend expects."""
    return {
        'type': unit.get('type'),
        'name': unit.get('name'),
        'title': unit.get('title'),
        'content': unit.get('content'),
        'metadata': unit.get('metadata') or {},
        'created_at': unit.get('updated_at'),
    }


def _agent_id(runnable: Any) -> str:
    """Best-effort id for a runnable (agno-style agents, teams, workflows)."""
    return str(getattr(runnable, 'id', None) or getattr(runnable, 'name', None) or getattr(runnable, '__name__', ''))


def _tool_names(tools: Any) -> list[str]:
    names: list[str] = []
    for t in tools or []:
        names.append(getattr(t, '__name__', None) or getattr(t, 'name', None) or repr(t))
    return names


def _model_name(model: Any) -> str:
    """Return a short model identifier — agno wraps strings into `Gemini(id='…')` objects."""
    if not model:
        return ''
    return str(getattr(model, 'id', None) or getattr(model, 'name', None) or model)


def _agent_summary(agent: Any) -> dict[str, Any]:
    """Project an agno-style agent into the shape the frontend's AgentPanel expects."""
    aid = _agent_id(agent)
    return {
        'id': aid,
        'name': getattr(agent, 'name', None) or aid,
        'role': getattr(agent, 'role', None) or '',
        'model': _model_name(getattr(agent, 'model', None)),
        'tools': _tool_names(getattr(agent, 'tools', None)),
        'instructions': getattr(agent, 'instructions', None) or '',
        'is_platform': aid in PLATFORM_AGENT_IDS,
    }


def build_router(app: Any, spec: Spec) -> APIRouter:  # noqa: C901
    """Build the FastAPI router with handlers closed over the AgentField node and spec."""
    router = APIRouter(prefix='/api/v1', tags=['api'])
    org_config = _state_model(spec)
    # AgentField exposes `app.memory` only inside reasoner executions; HTTP handlers run outside
    # any execution context, so capture the interface once at build time and reuse it.
    memory = app.memory
    knowledge = memory.global_scope

    async def _all_units() -> list[dict[str, Any]]:
        keys = [k for k in await knowledge.list_keys() if k.startswith(_KN_PREFIX)]
        units = [await knowledge.get(k) for k in keys]
        return [u for u in units if u is not None]

    # ── Config ──────────────────────────────────────────────────────────────
    @router.get('/config')
    def ui_config() -> dict[str, Any]:
        ui = spec.ui
        charter = spec.knowledge.charter
        defaults = {p.name: p.default for p in charter.parameters}
        sections = [
            {'id': s.id, 'title': s.title, 'body': s.body.format_map(_Safe(defaults))}
            for s in charter.sections
        ]
        return {
            'app_name': ui.app.name,
            'app_icon': ui.app.icon,
            'app_description': ui.app.description,
            'empty_state': ui.empty_state.model_dump(),
            'knowledge_empty': ui.knowledge_empty,
            'agent_groups': [g.model_dump() for g in ui.agent_groups],
            'workflow_groups': [g.model_dump() for g in ui.workflow_groups],
            'featured_agents': ui.featured_agents,
            'agent_icons': {**PLATFORM_AGENT_ICONS, **ui.agent_icons},
            'overview': [b.model_dump() for b in ui.overview],
            'agent_configs': {k: v.model_dump() for k, v in ui.agent_configs.items()},
            'charter': {'parameters': [p.model_dump() for p in charter.parameters], 'sections': sections},
            'types': [t.model_dump() for t in spec.knowledge.types],
            'platform_agent_groups': [{'label': g['label'], 'ids': list(g['ids'])} for g in PLATFORM_AGENT_GROUPS],
        }

    # ── State ───────────────────────────────────────────────────────────────
    @router.get('/state')
    async def get_state(user_id: str = Query(default='default')) -> dict[str, Any]:
        state = await memory.actor(user_id).get('org_state')
        if state is None:
            return {'configured': False, 'parameters': {}, 'data': {}}
        return {'configured': True, 'parameters': state.get('parameters', {}), 'data': state.get('data', {})}

    @router.post('/state')
    async def set_state(body: org_config, user_id: str = Query(default='default')) -> dict[str, Any]:  # type: ignore[valid-type]
        params = {**body.model_dump(), 'inception_date': datetime.now(tz=UTC).date().isoformat()}
        await memory.actor(user_id).set('org_state', {'parameters': params, 'data': {}})
        return {'status': 'configured', 'parameters': params}

    @router.post('/state/reset')
    async def reset_state(user_id: str = Query(default='default')) -> dict[str, Any]:
        for key in [k for k in await knowledge.list_keys() if k.startswith(_KN_PREFIX)]:
            await knowledge.delete(key)
        await memory.actor(user_id).delete('org_state')
        return {'status': 'reset', 'errors': []}

    # ── Setup checklist ─────────────────────────────────────────────────────
    @router.get('/setup')
    def setup_checklist() -> dict[str, Any]:
        import os  # noqa: PLC0415

        steps: list[dict[str, Any]] = []
        blocked = pending = 0
        for s in spec.runtime.setup:
            entry = s.model_dump()
            variables = entry.get('variables') or []
            if variables:
                missing = [v for v in variables if not os.getenv(v)]
                entry['completed'] = not missing
                entry['missing_vars'] = missing
                if missing:
                    blocked += 1
            else:
                entry['completed'] = None
                entry['missing_vars'] = []
                pending += 1
            steps.append(entry)
        total = len(steps)
        return {
            'steps': steps,
            'total': total,
            'blocked_count': blocked,
            'pending_count': pending,
            'all_done': total > 0 and blocked == 0 and pending == 0,
        }

    # ── Agents & workflows (introspection from the spec) ────────────────────
    @router.get('/agents')
    def list_agents() -> list[dict[str, Any]]:
        return [_agent_summary(a) for a in spec.ai.agents]

    @router.get('/agents/{agent_id}')
    def get_agent(agent_id: str) -> dict[str, Any]:
        for a in spec.ai.agents:
            if _agent_id(a) == agent_id:
                return _agent_summary(a)
        raise HTTPException(status_code=404, detail=f'agent {agent_id!r} not found')

    @router.get('/workflows')
    def list_workflows() -> list[dict[str, Any]]:
        return [{'id': _agent_id(w), 'name': getattr(w, 'name', None) or _agent_id(w)} for w in spec.ai.workflows]

    # ── Knowledge ───────────────────────────────────────────────────────────
    @router.get('/knowledge/search')
    async def kn_search(
        query: str = Query(..., min_length=1),
        types: list[str] = Query(default=[]),
        top_k: int = Query(default=15, ge=1, le=100),
    ) -> list[dict[str, Any]]:
        hits = await similarity_units(knowledge, getattr(app, 'embedder_model', None), query, list(types) or None, top_k)
        return [_document(u) for u in hits]

    @router.get('/knowledge/{type}/{name}')
    async def get_unit(type: str, name: str) -> dict[str, Any]:  # noqa: A002
        unit = await knowledge.get(f'{_KN_PREFIX}{type}:{name}')
        if unit is None:
            raise HTTPException(status_code=404, detail=f'{type}/{name} not found')
        return _document(unit)

    @router.get('/knowledge')
    async def list_knowledge(
        type: str = Query(default=''),  # noqa: A002
        agent_id: str = Query(default=''),
        limit: int = Query(default=0, ge=0),
    ) -> list[dict[str, Any]]:
        units = [
            u
            for u in await _all_units()
            if u.get('content') is not None
            and (not type or u.get('type') == type)
            and (not agent_id or (u.get('metadata') or {}).get('agent_id') == agent_id)
        ]
        units.sort(key=lambda u: u.get('updated_at', ''), reverse=True)
        if limit > 0:
            units = units[:limit]
        return [_document(u) for u in units]

    # ── Live knowledge events ───────────────────────────────────────────────
    # One in-process queue per WebSocket; AgentField's `on_change` fans events out to all of them.
    subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    async def _broadcast(event: Any) -> None:
        key = getattr(event, 'key', '') or ''
        msg = {
            'action': getattr(event, 'action', None),
            'key': key,
            'type': _type_of(key),
            'name': _name_of(key),
            'timestamp': getattr(event, 'timestamp', None),
        }
        for q in list(subscribers):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(msg)

    # `on_change` opens a websocket to the control plane, so it needs a running event loop —
    # register on FastAPI startup, not at import time.
    @app.on_event('startup')
    async def _wire_kn_events() -> None:
        knowledge.on_change('kn:*')(_broadcast)

    @router.websocket('/knowledge/events')
    async def kn_events(ws: WebSocket) -> None:
        await ws.accept()
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        subscribers.add(q)
        try:
            while True:
                msg = await q.get()
                await ws.send_json(msg)
        except WebSocketDisconnect:
            pass
        finally:
            subscribers.discard(q)

    return router


def _type_of(key: str) -> str | None:
    parts = key.split(':', 2)
    return parts[1] if len(parts) >= 3 and parts[0] == 'kn' else None  # noqa: PLR2004


def _name_of(key: str) -> str | None:
    parts = key.split(':', 2)
    return parts[2] if len(parts) >= 3 and parts[0] == 'kn' else None  # noqa: PLR2004


