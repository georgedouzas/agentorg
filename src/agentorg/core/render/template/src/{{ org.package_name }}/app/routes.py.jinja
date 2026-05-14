"""FastAPI router for agentorg-specific endpoints — app config, state, knowledge, documents, reports.

`build_router(app, spec)` returns a router closed over the AgentField node + spec. Knowledge and per-user state live
in the node's memory: knowledge units in **global scope** under `kn:{type}:{name}` keys, state in **actor scope**
under `org_state`. Agent invocation, discovery, history, and workflow continuation are not here — those are
AgentField's surface (`/reasoners/{name}`, the control plane, `app.pause`).
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, create_model

from agentorg.core.spec import Spec

_KN_PREFIX = 'kn:'


def _py_type(t: str) -> type:
    return {'int': int, 'float': float, 'string': str, 'bool': bool, 'object': dict, 'array': list}.get(t, str)


def _state_model(spec: Spec) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for p in spec.knowledge.charter.parameters:
        py = _py_type(p.type)
        fields[p.name] = (py, Field(default=p.default))
    return create_model('OrgConfig', **fields)  # type: ignore[call-overload]


def _document(unit: dict[str, Any]) -> dict[str, Any]:
    """Project a stored knowledge unit into the document shape the frontend expects."""
    return {
        'type': unit.get('type'),
        'name': unit.get('name'),
        'content': unit.get('content'),
        'metadata': unit.get('metadata') or {},
        'created_at': unit.get('updated_at'),
    }


def build_router(app: Any, spec: Spec) -> APIRouter:  # noqa: C901, PLR0915
    """Build the FastAPI router with handlers closed over the AgentField node + spec."""
    router = APIRouter(prefix='/api', tags=['api'])
    org_config = _state_model(spec)
    knowledge = app.memory.global_scope

    async def _all_units() -> list[dict[str, Any]]:
        keys = [k for k in await knowledge.list_keys() if k.startswith(_KN_PREFIX)]
        units = [await knowledge.get(k) for k in keys]
        return [u for u in units if u is not None]

    # ── Config ──────────────────────────────────────────────────────────────
    @router.get('/config')
    def ui_config() -> dict[str, Any]:
        ui = spec.ui
        return {
            'app_name': ui.app.name,
            'app_icon': ui.app.icon,
            'app_description': ui.app.description,
            'empty_state': ui.empty_state.model_dump(),
            'knowledge_empty': ui.knowledge_empty.model_dump(),
            'agent_groups': [g.model_dump() for g in ui.agent_groups],
            'workflow_groups': [g.model_dump() for g in ui.workflow_groups],
            'featured_agents': ui.featured_agents,
            'agent_icons': ui.agent_icons,
            'agent_configs': {k: v.model_dump() for k, v in ui.agent_configs.items()},
        }

    # ── State / setup / reset ───────────────────────────────────────────────
    @router.get('/state')
    async def get_state(user_id: str = Query(default='default')) -> dict[str, Any]:
        state = await app.memory.actor(user_id).get('org_state')
        if state is None:
            return {'configured': False, 'parameters': {}, 'data': {}}
        return {'configured': True, 'parameters': state.get('parameters', {}), 'data': state.get('data', {})}

    @router.post('/setup')
    async def setup_state(body: org_config, user_id: str = Query(default='default')) -> dict[str, Any]:  # type: ignore[valid-type]
        params = {**body.model_dump(), 'inception_date': datetime.now(tz=UTC).date().isoformat()}
        await app.memory.actor(user_id).set('org_state', {'parameters': params, 'data': {}})
        return {'status': 'configured', 'parameters': params}

    @router.post('/reset')
    async def reset_state(user_id: str = Query(default='default')) -> dict[str, Any]:
        for key in [k for k in await knowledge.list_keys() if k.startswith(_KN_PREFIX)]:
            await knowledge.delete(key)
        await app.memory.actor(user_id).delete('org_state')
        return {'status': 'reset', 'errors': []}

    # ── Setup guide ─────────────────────────────────────────────────────────
    @router.get('/setup-guide')
    def setup_guide() -> dict[str, Any]:
        return {'steps': [s.model_dump() for s in spec.runtime.setup]}

    # ── Documents / knowledge ───────────────────────────────────────────────
    @router.get('/documents')
    async def list_documents(type: str = Query(default='')) -> list[dict[str, Any]]:  # noqa: A002
        units = [u for u in await _all_units() if u.get('content') and (not type or u.get('type') == type)]
        units.sort(key=lambda u: u.get('updated_at', ''), reverse=True)
        return [_document(u) for u in units]

    @router.get('/documents/search')
    async def search_docs(
        query: str = Query(..., min_length=1),
        types: list[str] = Query(default=[]),
    ) -> list[dict[str, Any]]:
        needle = query.lower()
        hits = [
            u
            for u in await _all_units()
            if (not types or u.get('type') in types)
            and needle in f'{u.get("content") or ""} {u.get("name") or ""}'.lower()
        ]
        hits.sort(key=lambda u: u.get('updated_at', ''), reverse=True)
        return [_document(u) for u in hits[:15]]

    @router.get('/document/{type}/{name}')
    async def get_document(type: str, name: str) -> dict[str, Any]:  # noqa: A002
        unit = await knowledge.get(f'{_KN_PREFIX}{type}:{name}')
        if unit is None:
            raise HTTPException(status_code=404, detail=f'{type}/{name} not found')
        return _document(unit)

    @router.get('/knowledge')
    async def knowledge_list() -> list[dict[str, Any]]:
        return await list_documents(type='')

    @router.get('/learnings')
    def learnings_list() -> list[dict[str, Any]]:
        return []

    # ── Agent reports ───────────────────────────────────────────────────────
    @router.get('/agent-reports')
    async def agent_reports_list(agent_id: str = Query(default='')) -> dict[str, Any]:
        by_agent: dict[str, Any] = {}
        reports = [u for u in await _all_units() if u.get('type') == 'report']
        reports.sort(key=lambda u: u.get('updated_at', ''), reverse=True)
        for unit in reports:
            aid = (unit.get('metadata') or {}).get('agent_id', 'unknown')
            if agent_id and aid != agent_id:
                continue
            by_agent.setdefault(aid, {'agent_id': aid, 'agent_name': aid, 'reports': []})
            by_agent[aid]['reports'].append(
                {'name': unit.get('name'), 'title': unit.get('title') or unit.get('name'),
                 'created_at': unit.get('updated_at')},
            )
        return {'agents': list(by_agent.values())}

    @router.get('/agent-reports/{name}')
    async def agent_report_detail(name: str) -> dict[str, Any]:
        unit = await knowledge.get(f'{_KN_PREFIX}report:{name}')
        if unit is None:
            raise HTTPException(status_code=404, detail=f'Report {name!r} not found')
        md = unit.get('metadata') or {}
        return {
            'name': name,
            'agent_id': md.get('agent_id', ''),
            'agent_name': md.get('agent_id', ''),
            'title': unit.get('title') or name,
            'content': unit.get('content'),
            'created_at': unit.get('updated_at'),
        }

    return router
