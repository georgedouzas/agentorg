"""FastAPI router for the rendered org's agentorg-specific endpoints."""

import asyncio
import contextlib
import json
import os
from datetime import UTC, datetime
from typing import Any

from agentfield import Agent as _AfAgent
from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, create_model
from sse_starlette.sse import EventSourceResponse

from agentorg.core.agents.tools import PREFIX as _KN_PREFIX, similarity_units
from agentorg.core.agents.framework.agno.platform import PLATFORM_AGENT_GROUPS, PLATFORM_AGENT_ICONS, PLATFORM_AGENT_IDS, PLATFORM_AGENTS
from agentorg.core.spec import Spec


class _Safe(dict):
    """`dict` that returns `{key}` for missing keys so principle bodies survive incomplete state."""

    def __missing__(self, key: str) -> str:
        return '{' + key + '}'


def _py_type(t: str) -> type:
    return {'int': int, 'float': float, 'string': str, 'bool': bool, 'object': dict, 'array': list}.get(t, str)


def _parameters_model(spec: Spec) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for p in spec.parameters:
        py = _py_type(p.type)
        fields[p.name] = (py, Field(default=p.default))
    return create_model('OrgParameters', **fields)


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
    org_parameters = _parameters_model(spec)
    # AgentField exposes `app.memory` only inside reasoner executions; HTTP handlers run outside
    # any execution context, so capture the interface once at build time and reuse it.
    memory = app.memory
    knowledge = memory.global_scope

    # Index every spec runnable by id so the streaming endpoint can look it up cheaply.
    runnables: dict[str, Any] = {}
    for runnable in (*PLATFORM_AGENTS, *spec.ai.agents, *spec.ai.teams, *spec.ai.workflows):
        runnables[_agent_id(runnable)] = runnable

    async def _all_units() -> list[dict[str, Any]]:
        # In preview mode the control plane is absent, so `list_keys` raises a memory
        # connection error. Treat that as "no knowledge yet" and return an empty list
        # so the Knowledge tab shows its empty state instead of a 500.
        try:
            keys = [k for k in await knowledge.list_keys() if k.startswith(_KN_PREFIX)]
        except Exception:
            return []
        units = []
        for k in keys:
            try:
                u = await knowledge.get(k)
            except Exception:
                continue
            if u is not None:
                units.append(u)
        return units

    # Seed placeholder strings the master agent has not yet replaced. The dashboard
    # uses this to detect "not configured yet" and render a getting-started state
    # instead of showing seed text as if it were the user's real content.
    _PLACEHOLDER_TEXTS = {
        'Not set yet', 'Untitled org', 'untitled-org', 'untitled_org', 'you@example.com',
        '🛠', 'You', 'A new agent organisation in progress.',
        'Nothing here yet', 'Your org is taking shape — keep chatting with AgentOrg.',
        '✨', 'No knowledge entries yet.',
        'TODO', 'My Org', 'my-org', 'my_org', 'author@example.com', 'robot',
    }

    # ── Config ──────────────────────────────────────────────────────────────
    @router.get('/config')
    def ui_config() -> dict[str, Any]:
        ui = spec.ui
        principles = spec.knowledge.principles
        defaults = {p.name: p.default for p in spec.parameters}
        sections = [
            {'id': s.id, 'title': s.title, 'body': s.body.format_map(_Safe(defaults))}
            for s in principles.sections
        ]
        return {
            'app_name': ui.app.name,
            'app_icon': ui.app.icon,
            'app_description': ui.app.description,
            'name_is_placeholder': ui.app.name in _PLACEHOLDER_TEXTS,
            'description_is_placeholder': ui.app.description in _PLACEHOLDER_TEXTS,
            'empty_state': ui.empty_state.model_dump(),
            'knowledge_empty': ui.knowledge_empty,
            'agent_groups': [g.model_dump() for g in ui.agent_groups],
            'workflow_groups': [g.model_dump() for g in ui.workflow_groups],
            'featured_agents': ui.featured_agents,
            'agent_icons': {**PLATFORM_AGENT_ICONS, **ui.agent_icons},
            'overview': [b.model_dump() for b in ui.overview],
            'agent_configs': {k: v.model_dump() for k, v in ui.agent_configs.items()},
            'parameters': [p.model_dump() for p in spec.parameters],
            'principles': {'sections': sections},
            # Synthesize a 'principle' knowledge type when there ARE sections, so the
            # React Knowledge view can bucket them like any other knowledge entries.
            # The frontend filter hides this bucket unless the principles_owner agent
            # is the active author filter.
            'types': (
                [t.model_dump() for t in spec.knowledge.types]
                + ([{'id': 'principle', 'label': 'Principles', 'metadata_fields': []}] if sections else [])
            ),
            'platform_agent_groups': [{'label': g['label'], 'ids': list(g['ids'])} for g in PLATFORM_AGENT_GROUPS],
            # Platform agent metadata for the Knowledge tab's author filter, etc.
            # Always present in the dropdown regardless of whether they've written units.
            'platform_agents': [
                {'id': _agent_id(a), 'name': getattr(a, 'name', None) or _agent_id(a)}
                for a in PLATFORM_AGENTS
            ],
            # Principles owner - clickable badge in the Knowledge tab opens chat with this agent.
            'principles_owner': 'knowledge-engineer',
        }

    # ── Org instance parameters ─────────────────────────────────────────────
    @router.get('/parameters')
    async def get_parameters() -> dict[str, Any]:
        # In preview mode the control plane is absent; treat that as 'no parameters set'.
        try:
            state = await knowledge.get('org_parameters')
        except Exception:
            return {'parameters': {}}
        return {'parameters': state.get('parameters', {}) if state else {}}

    @router.post('/parameters')
    async def set_parameters(body: org_parameters) -> dict[str, Any]:  # type: ignore[valid-type]
        params = {**body.model_dump(), 'inception_date': datetime.now(tz=UTC).date().isoformat()}
        await knowledge.set('org_parameters', {'parameters': params})
        return {'status': 'configured', 'parameters': params}

    @router.post('/parameters/reset')
    async def reset_parameters() -> dict[str, Any]:
        for key in [k for k in await knowledge.list_keys() if k.startswith(_KN_PREFIX)]:
            await knowledge.delete(key)
        await knowledge.delete('org_parameters')
        return {'status': 'reset', 'errors': []}

    # ── Setup checklist ─────────────────────────────────────────────────────
    @router.get('/setup')
    def setup_checklist() -> dict[str, Any]:
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
        return [_agent_summary(a) for a in (*PLATFORM_AGENTS, *spec.ai.agents)]

    @router.get('/agents/{agent_id}')
    def get_agent(agent_id: str) -> dict[str, Any]:
        for a in (*PLATFORM_AGENTS, *spec.ai.agents):
            if _agent_id(a) == agent_id:
                return _agent_summary(a)
        raise HTTPException(status_code=404, detail=f'agent {agent_id!r} not found')

    @router.get('/workflows')
    def list_workflows() -> list[dict[str, Any]]:
        return [{'id': _agent_id(w), 'name': getattr(w, 'name', None) or _agent_id(w)} for w in spec.ai.workflows]

    # ── Streaming chat (SSE over agno's stream_events) ──────────────────────
    @router.post('/reasoners/{name}/stream')
    async def stream_reasoner(name: str, request: Request, user_id: str = Query(default='default')) -> EventSourceResponse:
        runnable = runnables.get(name)
        if runnable is None:
            raise HTTPException(status_code=404, detail=f'reasoner {name!r} not found')
        body = await request.json()
        message = body.get('message', '')
        session_id = body.get('session_id')
        actor_id = body.get('user_id', user_id)

        async def event_gen() -> Any:
            # Bind `Agent.get_current()` to our node so any tool the agno agent invokes
            # (write_knowledge, read_knowledge, …) resolves the right memory scope. We patch
            # the classmethod itself (not the contextvar) because agno may iterate the stream
            # in a task whose context doesn't see the contextvar update.
            original_get_current = _AfAgent.get_current
            _AfAgent.get_current = staticmethod(lambda: app)
            try:
                arun = getattr(runnable, 'arun', None)
                if arun is None:
                    yield {'event': 'RunCompleted', 'data': json.dumps({'content': str(runnable)})}
                    return
                stream = arun(message, stream=True, stream_events=True, session_id=session_id, user_id=actor_id)
                async for ev in stream:
                    kind = getattr(ev, 'event', type(ev).__name__)
                    payload: dict[str, Any] = {'event': kind, 'content': getattr(ev, 'content', None) or ''}
                    if kind in ('ToolCallStarted', 'ToolCallCompleted', 'ToolCallError'):
                        tool = getattr(ev, 'tool', None)
                        tool_name = (
                            getattr(tool, 'tool_name', None)
                            or getattr(tool, 'name', None)
                            or (tool.__class__.__name__ if tool else None)
                        )
                        payload['tool_name'] = tool_name
                    yield {'event': kind, 'data': json.dumps(payload)}
            except Exception as exc:  # noqa: BLE001 — surface to the client
                yield {'event': 'RunError', 'data': json.dumps({'error': str(exc)})}
            finally:
                _AfAgent.get_current = original_get_current

        return EventSourceResponse(event_gen())

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

    # ── Activity summary ────────────────────────────────────────────────────
    # One-sentence pulse across ALL agents, fed to the always-visible bottom strip in
    # the dashboard. Computed from recent knowledge units (each unit's metadata carries
    # `agent_id` and `agent_name`, set by the runtime when a reasoner writes knowledge).
    @router.get('/activity/summary')
    async def activity_summary() -> dict[str, Any]:
        units = [u for u in await _all_units() if u.get('content') is not None]
        units.sort(key=lambda u: u.get('updated_at', ''), reverse=True)
        if not units:
            return {'summary': 'No agent activity yet.', 'level': 'idle',
                    'count_recent': 0, 'latest_at': None}
        latest = units[0]
        meta = latest.get('metadata') or {}
        agent_name = meta.get('agent_name') or meta.get('agent_id') or 'An agent'
        title = latest.get('title') or latest.get('name') or 'an item'
        latest_at = latest.get('updated_at') or latest.get('created_at')
        # Count activity in the last hour for the level + headline alternation.
        try:
            now = datetime.now(tz=UTC)
            recent = [
                u for u in units
                if datetime.fromisoformat(u['updated_at'].replace('Z', '+00:00')) >= now.replace(minute=now.minute, second=0, microsecond=0)
            ]
        except Exception:
            recent = units[:5]
        count_recent = len(recent)
        if count_recent >= 6:
            level = 'busy'
            summary = f'{count_recent} actions in the last hour - {agent_name} most recent.'
        elif count_recent >= 2:
            level = 'active'
            summary = f'{agent_name} just updated "{title}" (+{count_recent - 1} more recent).'
        else:
            level = 'active'
            summary = f'{agent_name} just updated "{title}".'
        return {'summary': summary, 'level': level, 'count_recent': count_recent, 'latest_at': latest_at}

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


_KN_KEY_PARTS = 3


def _type_of(key: str) -> str | None:
    parts = key.split(':', 2)
    return parts[1] if len(parts) >= _KN_KEY_PARTS and parts[0] == 'kn' else None


def _name_of(key: str) -> str | None:
    parts = key.split(':', 2)
    return parts[2] if len(parts) >= _KN_KEY_PARTS and parts[0] == 'kn' else None


