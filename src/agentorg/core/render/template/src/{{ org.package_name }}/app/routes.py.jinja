"""FastAPI router exposing app config, state, documents, agents, reports, and workflows.

`build_router(spec, agents, workflows)` returns a router whose handlers are closed over
the already-built spec + agents + workflows — no re-reading of configuration per request.
"""

import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from agno.agent import Agent as AgnoAgent
from agno.workflow import Workflow as AgnoWorkflow
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, create_model
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from agentorg.core.schema import Spec
from agentorg.core.tools._engine import get_engine


def _py_type(t: str) -> type:
    return {'int': int, 'float': float, 'string': str, 'bool': bool, 'object': dict, 'array': list}.get(t, str)


def _state_model(spec: Spec) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for p in spec.generated.charter.parameters:
        py = _py_type(p.type)
        fields[p.name] = (py, Field(default=p.default))
    return create_model(spec.generated.state.model_name, **fields)  # type: ignore[call-overload]


def _decode_json(maybe: Any) -> Any:
    if isinstance(maybe, str):
        return json.loads(maybe) if maybe else {}
    return maybe or {}


def build_router(  # noqa: C901, PLR0915
    spec: Spec,
    agents: dict[str, AgnoAgent],
    workflows: list[AgnoWorkflow],
) -> APIRouter:
    """Build the FastAPI router with handlers closed over the spec + agents + workflows."""
    router = APIRouter(prefix='/api', tags=['api'])
    agent_names = {a.id: a.name for a in spec.generated.agents}
    org_config = _state_model(spec)

    # ── Config ──────────────────────────────────────────────────────────────
    @router.get('/config')
    def ui_config() -> dict[str, Any]:
        ui = spec.generated.ui
        return {
            'app_name': ui.app.name if ui else spec.org.name,
            'app_icon': ui.app.icon if ui else '🤖',
            'app_description': ui.app.description if ui else spec.org.description,
            'empty_state': ui.empty_state.model_dump() if ui else {},
            'knowledge_empty': ui.knowledge_empty.model_dump() if ui else {},
            'agent_groups': [g.model_dump() for g in spec.generated.agent_groups],
            'workflow_groups': [g.model_dump() for g in spec.generated.workflow_groups],
            'featured_agents': ui.featured_agents if ui else [],
            'agent_icons': ui.agent_icons if ui else {},
            'agent_configs': {k: v.model_dump() for k, v in (ui.agent_configs if ui else {}).items()},
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
        return {'steps': [s.model_dump() for s in spec.setup.steps]}

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

    # ── Agents ──────────────────────────────────────────────────────────────
    @router.get('/agents/{agent_id}/info')
    def get_agent_info(agent_id: str) -> dict[str, Any]:
        agent = agents.get(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        agent_spec = next((a for a in spec.generated.agents if a.id == agent_id), None)
        return {
            'agent_id': agent_id,
            'name': agent.name or agent_id,
            'model_id': getattr(agent.model, 'id', '') if getattr(agent, 'model', None) else '',
            'role': agent_spec.role if agent_spec else '',
            'in_scope': agent_spec.in_scope if agent_spec else [],
            'out_of_scope': [s.model_dump() for s in (agent_spec.out_of_scope if agent_spec else [])],
            'workflow': agent_spec.workflow if agent_spec else [],
            'tools': [getattr(t, '__name__', type(t).__name__) for t in (agent_spec.tools if agent_spec else [])],
        }

    @router.get('/agents/{agent_id}/history')
    def agent_history(agent_id: str, user_id: str = Query(default='default')) -> dict[str, Any]:
        try:
            with get_engine().connect() as conn:
                row = conn.execute(
                    text(
                        'SELECT session_id, runs FROM agno_sessions'
                        ' WHERE agent_id = :aid AND user_id = :uid'
                        ' ORDER BY updated_at DESC, created_at DESC LIMIT 1',
                    ),
                    {'aid': agent_id, 'uid': user_id},
                ).first()
        except SQLAlchemyError:
            return {'session_id': None, 'messages': []}
        if row is None or not row.runs:
            return {'session_id': None, 'messages': []}
        runs = _decode_json(row.runs) if isinstance(row.runs, str) else (row.runs or [])
        messages: list[dict[str, Any]] = []
        for run in runs:
            for m in run.get('messages') or []:
                role = m.get('role')
                content = m.get('content')
                if not content:
                    continue
                if role in ('user', 'assistant'):
                    messages.append({'role': role, 'content': content})
        return {'session_id': row.session_id, 'messages': messages}

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
            by_agent.setdefault(aid, {'agent_id': aid, 'agent_name': agent_names.get(aid, aid), 'reports': []})
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
            'agent_name': agent_names.get(md.get('agent_id', ''), md.get('agent_id', '')),
            'title': row.name,
            'content': row.content,
            'created_at': row.created_at if isinstance(row.created_at, str) else row.created_at.isoformat(),
        }

    # ── Workflows ───────────────────────────────────────────────────────────
    class WorkflowContinueRequest(BaseModel):
        workflow_id: str
        run_id: str
        session_id: str
        approved: bool
        user_input: str | None = None
        user_input_fields: dict[str, Any] | None = None

    @router.post('/workflow/continue', response_model=None)
    async def continue_workflow(
        body: WorkflowContinueRequest,
        background_tasks: BackgroundTasks,
    ) -> StreamingResponse | dict[str, str]:
        from agno.os.utils import format_sse_event, get_workflow_by_id  # noqa: PLC0415

        workflow = get_workflow_by_id(
            workflow_id=body.workflow_id,
            workflows=workflows,
            db=None,
            create_fresh=True,
        )
        if workflow is None:
            return {'error': f"Workflow '{body.workflow_id}' not found"}

        run_response = await workflow.aget_run_output(run_id=body.run_id, session_id=body.session_id)
        if run_response is None:
            return {'error': 'Run not found'}

        for req in run_response.step_requirements or []:
            if req.confirmed is None:
                if body.approved:
                    req.confirmed = True
                    if req.requires_user_input and body.user_input_fields:
                        req.user_input = body.user_input_fields
                    elif req.requires_user_input and body.user_input:
                        field_name = (req.user_input_schema or [{}])[0].get('name', 'input')
                        req.user_input = {field_name: body.user_input}
                else:
                    req.confirmed = False

        async def _stream() -> AsyncGenerator[str, None]:
            async for chunk in workflow.acontinue_run(run_response, stream=True, stream_events=True):
                yield format_sse_event(chunk)

        return StreamingResponse(_stream(), media_type='text/event-stream')

    return router
