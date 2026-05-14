"""FastAPI router for agentorg-specific endpoints — app config, state, knowledge, documents, reports.

`build_router(spec)` returns a router closed over the spec. Agent invocation, discovery, history, and workflow
continuation are *not* here — those are AgentField's job (reasoners auto-expose at `/reasoners/{name}`, the control
plane serves discovery / DAG / execution history, and HITL is `app.pause`).
"""

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, create_model
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from agentorg.core.spec import Spec
from agentorg.core.tools._engine import get_engine


def _py_type(t: str) -> type:
    return {'int': int, 'float': float, 'string': str, 'bool': bool, 'object': dict, 'array': list}.get(t, str)


def _state_model(spec: Spec) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for p in spec.knowledge.charter.parameters:
        py = _py_type(p.type)
        fields[p.name] = (py, Field(default=p.default))
    return create_model('OrgConfig', **fields)  # type: ignore[call-overload]


def _decode_json(maybe: Any) -> Any:
    if isinstance(maybe, str):
        return json.loads(maybe) if maybe else {}
    return maybe or {}


def build_router(spec: Spec) -> APIRouter:  # noqa: C901, PLR0915
    """Build the FastAPI router with handlers closed over the spec."""
    router = APIRouter(prefix='/api', tags=['api'])
    org_config = _state_model(spec)

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
    def get_state(user_id: str = Query(default='default')) -> dict[str, Any]:
        with get_engine().connect() as conn:
            row = conn.execute(
                text('SELECT parameters, data FROM org_state WHERE user_id = :uid'),
                {'uid': user_id},
            ).first()
        if row is None:
            return {'configured': False, 'parameters': {}, 'data': {}}
        return {
            'configured': True,
            'parameters': _decode_json(row.parameters),
            'data': _decode_json(row.data),
        }

    @router.post('/setup')
    def setup_state(body: org_config, user_id: str = Query(default='default')) -> dict[str, Any]:  # type: ignore[valid-type]
        params = {**body.model_dump(), 'inception_date': datetime.now(tz=UTC).date().isoformat()}
        with get_engine().begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO org_state (user_id, parameters, data)
                    VALUES (:uid, :p, '{}')
                    ON CONFLICT (user_id) DO UPDATE
                        SET parameters = excluded.parameters,
                            updated_at = CURRENT_TIMESTAMP
                """),
                {'uid': user_id, 'p': json.dumps(params)},
            )
        return {'status': 'configured', 'parameters': params}

    @router.post('/reset')
    def reset_state(user_id: str = Query(default='default')) -> dict[str, Any]:
        errors: list[str] = []
        try:
            with get_engine().begin() as conn:
                conn.execute(text('DELETE FROM knowledge'))
                conn.execute(text('DELETE FROM org_state WHERE user_id = :uid'), {'uid': user_id})
        except SQLAlchemyError as e:
            errors.append(f'app_tables: {e}')
        return {'status': 'reset', 'errors': errors}

    # ── Setup guide ─────────────────────────────────────────────────────────
    @router.get('/setup-guide')
    def setup_guide() -> dict[str, Any]:
        return {'steps': [s.model_dump() for s in spec.runtime.setup]}

    # ── Documents / knowledge ───────────────────────────────────────────────
    @router.get('/documents')
    def list_documents(type: str = Query(default='')) -> list[dict[str, Any]]:  # noqa: A002
        sql = 'SELECT type, name, content, metadata, created_at FROM knowledge WHERE content IS NOT NULL'
        params: dict[str, Any] = {}
        if type:
            sql += ' AND type = :t'
            params['t'] = type
        sql += ' ORDER BY created_at DESC'
        try:
            with get_engine().connect() as conn:
                rows = conn.execute(text(sql), params).fetchall()
        except SQLAlchemyError:
            return []
        return [
            {
                'type': r.type, 'name': r.name, 'content': r.content,
                'metadata': _decode_json(r.metadata),
                'created_at': r.created_at if isinstance(r.created_at, str)
                              else (r.created_at.isoformat() if r.created_at else None),
            }
            for r in rows
        ]

    @router.get('/documents/search')
    def search_docs(query: str = Query(..., min_length=1), types: list[str] = Query(default=[])) -> list[dict[str, Any]]:
        sql = (
            'SELECT type, name, content, metadata'
            ' FROM knowledge WHERE LOWER(content || \' \' || name) LIKE LOWER(:q)'
        )
        params: dict[str, Any] = {'q': f'%{query}%'}
        if types:
            placeholders = ', '.join(f':t{i}' for i in range(len(types)))
            sql += f' AND type IN ({placeholders})'
            for i, t in enumerate(types):
                params[f't{i}'] = t
        sql += ' ORDER BY updated_at DESC LIMIT 15'
        with get_engine().connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        return [
            {'type': r.type, 'name': r.name, 'content': r.content, 'metadata': _decode_json(r.metadata)}
            for r in rows
        ]

    @router.get('/document/{type}/{name}')
    def get_document(type: str, name: str) -> dict[str, Any]:  # noqa: A002
        with get_engine().connect() as conn:
            row = conn.execute(
                text('SELECT content, metadata, created_at FROM knowledge WHERE type = :t AND name = :n'),
                {'t': type, 'n': name},
            ).first()
        if row is None:
            raise HTTPException(status_code=404, detail=f'{type}/{name} not found')
        return {
            'type': type, 'name': name, 'content': row.content,
            'metadata': _decode_json(row.metadata),
            'created_at': row.created_at if isinstance(row.created_at, str) else row.created_at.isoformat(),
        }

    @router.get('/knowledge')
    def knowledge_list() -> list[dict[str, Any]]:
        return list_documents(type='')

    @router.get('/learnings')
    def learnings_list() -> list[dict[str, Any]]:
        try:
            with get_engine().connect() as conn:
                rows = conn.execute(
                    text(
                        'SELECT id, content, meta_data, created_at FROM team_learnings_contents'
                        ' ORDER BY created_at DESC',
                    ),
                ).fetchall()
        except SQLAlchemyError:
            return []
        return [
            {
                'id': r.id, 'content': r.content,
                'meta_data': _decode_json(r.meta_data),
                'created_at': r.created_at if isinstance(r.created_at, str) else r.created_at.isoformat(),
            }
            for r in rows
        ]

    # ── Agent reports ───────────────────────────────────────────────────────
    @router.get('/agent-reports')
    def agent_reports_list(agent_id: str = Query(default='')) -> dict[str, Any]:
        sql = "SELECT id, name, metadata, created_at FROM knowledge WHERE type = 'report' ORDER BY created_at DESC"
        with get_engine().connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
        by_agent: dict[str, Any] = {}
        for r in rows:
            md = _decode_json(r.metadata)
            if agent_id and md.get('agent_id') != agent_id:
                continue
            aid = md.get('agent_id', 'unknown')
            by_agent.setdefault(aid, {'agent_id': aid, 'agent_name': aid, 'reports': []})
            created = r.created_at if isinstance(r.created_at, str) else r.created_at.isoformat()
            by_agent[aid]['reports'].append({'id': r.id, 'title': r.name, 'created_at': created})
        return {'agents': list(by_agent.values())}

    @router.get('/agent-reports/{report_id}')
    def agent_report_detail(report_id: int) -> dict[str, Any]:
        with get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT name, content, metadata, created_at FROM knowledge WHERE id = :id AND type = 'report'"),
                {'id': report_id},
            ).first()
        if row is None:
            raise HTTPException(status_code=404, detail=f'Report {report_id} not found')
        md = _decode_json(row.metadata)
        return {
            'id': report_id,
            'agent_id': md.get('agent_id', ''),
            'agent_name': md.get('agent_id', ''),
            'title': row.name,
            'content': row.content,
            'created_at': row.created_at if isinstance(row.created_at, str) else row.created_at.isoformat(),
        }

    return router
