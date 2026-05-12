"""FastAPI router exposing app config, state, documents, agent info, and workflow endpoints."""

import json
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from agno.agent import Agent
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, create_model
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from org.db import get_engine

router = APIRouter(prefix="/api", tags=["api"])

_CONFIG_PATH = Path(__file__).parent / "config.yaml"
_FULL_CONFIG: dict[str, Any] = yaml.safe_load(_CONFIG_PATH.read_text())
_UI: dict[str, Any] = _FULL_CONFIG.get("ui", {})
_CHARTER: dict[str, Any] = _FULL_CONFIG.get("charter", {})
_STATE_SCHEMA: dict[str, Any] = _FULL_CONFIG.get("state", {})
_DOCUMENTS_CFG: dict[str, Any] = _FULL_CONFIG.get("documents", {})
AGENT_NAMES: dict[str, str] = {k: v.get("name", k) for k, v in _UI.get("agent_configs", {}).items()}

TRUNCATE_AGNO_TABLES = [
    "team_knowledge_contents",
    "team_learnings_contents",
    "agno_sessions",
    "agno_memories",
    "agno_knowledge",
    "agno_learnings",
]


# ── Dynamic Pydantic model from state.parameters ─────────────────────────────
def _py_type(t: str) -> type:
    return {"int": int, "float": float, "string": str, "bool": bool, "object": dict, "array": list}.get(t, str)


def _build_state_model() -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for p in _CHARTER.get("parameters", []):
        py = _py_type(p["type"])
        fields[p["name"]] = (py, Field(default=p.get("default")))
    return create_model(_STATE_SCHEMA.get("model_name", "OrgConfig"), **fields)  # type: ignore[call-overload]


OrgConfig = _build_state_model()


# ── Config endpoint ──────────────────────────────────────────────────────────
@router.get("/config")
def ui_config() -> dict[str, Any]:
    """Return UI configuration loaded from config.yaml."""
    sidebar = _UI.get("sidebar", {})
    overview = _UI.get("overview", {})
    app_cfg = _UI.get("app", {})

    raw_agent_configs = _UI.get("agent_configs", {})
    agent_configs = {
        agent_id: {
            "model": cfg.get("model", ""),
            "role": cfg.get("description", ""),
            "tools": cfg.get("tools", []),
            "features": cfg.get("features", []),
        }
        for agent_id, cfg in raw_agent_configs.items()
    }

    return {
        "app_name": app_cfg.get("name", "Agent OS"),
        "app_icon": app_cfg.get("icon", "🤖"),
        "app_description": app_cfg.get("description", ""),
        "empty_state": _UI.get("empty_state", {}),
        "knowledge_empty": _UI.get("knowledge_empty", {}),
        "agent_groups": sidebar.get("agent_groups", []),
        "workflow_groups": sidebar.get("workflow_groups", []),
        "featured_agents": sidebar.get("featured_agents", []),
        "agent_icons": sidebar.get("agent_icons", {}),
        "overview": overview.get("widgets", []),
        "visualizations": overview.get("visualizations", []),
        "agent_configs": agent_configs,
        "document_types": _DOCUMENTS_CFG.get("types", []),
        "state_parameters": _CHARTER.get("parameters", []),
    }


# ── State endpoints (generic) ────────────────────────────────────────────────
@router.get("/state")
def get_state(user_id: str = Query(default="default")) -> dict[str, Any]:
    """Return the org state for a user."""
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT parameters, data FROM org_state WHERE user_id = :uid"),
            {"uid": user_id},
        ).first()
    if row is None:
        return {"configured": False, "parameters": {}, "data": {}}
    params = json.loads(row.parameters) if isinstance(row.parameters, str) else (row.parameters or {})
    data = json.loads(row.data) if isinstance(row.data, str) else (row.data or {})
    return {"configured": True, "parameters": params, "data": data}


@router.post("/setup")
def setup_state(body: OrgConfig, user_id: str = Query(default="default")) -> dict[str, Any]:  # type: ignore[valid-type]
    """First-run / post-reset setup: write the user's charter parameters and (re-)seed the
    policy document so it reflects the just-submitted values.
    """
    params = {**body.model_dump(), "inception_date": datetime.now(tz=UTC).date().isoformat()}
    with get_engine().begin() as conn:
        conn.execute(
            text("""
                INSERT INTO org_state (user_id, parameters, data)
                VALUES (:uid, :p, '{}')
                ON CONFLICT (user_id) DO UPDATE
                    SET parameters = excluded.parameters,
                        updated_at = CURRENT_TIMESTAMP
            """),
            {"uid": user_id, "p": json.dumps(params)},
        )
    from org.org import seed_policy_documents  # noqa: PLC0415

    seed_policy_documents(user_id)
    return {"status": "configured", "parameters": params}


@router.post("/reset")
def reset_state(user_id: str = Query(default="default")) -> dict[str, Any]:
    """Wipe documents, learnings, agent history, and the org_state row for this user.
    Frontend re-fetches /api/state afterwards and is sent through the setup flow again.
    """
    errors: list[str] = []

    try:
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM knowledge"))
            conn.execute(text("DELETE FROM org_state WHERE user_id = :uid"), {"uid": user_id})
        # Re-seed both platform reference docs and the policy charter, matching the
        # boot sequence in `app/main.py`.
        from org.org import seed_policy_documents  # noqa: PLC0415
        from org.org.platform_kb import seed_platform_kb  # noqa: PLC0415

        seed_platform_kb()
        seed_policy_documents(user_id)
    except SQLAlchemyError as e:
        errors.append(f"app_tables: {e}")

    try:
        from org.ai.agents.settings import team_knowledge, team_learnings  # noqa: PLC0415

        for kb in [team_knowledge, team_learnings]:
            if kb.vector_db:
                kb.vector_db.drop()
                kb.vector_db.create()
    except Exception as e:  # noqa: BLE001
        errors.append(f"vector_db: {e}")

    try:
        with get_engine().begin() as conn:
            for table in TRUNCATE_AGNO_TABLES:
                try:
                    conn.execute(text(f"DELETE FROM {table}"))
                except SQLAlchemyError as e:
                    errors.append(f"{table}: {e}")
    except SQLAlchemyError as e:
        errors.append(f"agno_tables: {e}")

    return {"status": "reset", "errors": errors}


# ── Documents endpoints ──────────────────────────────────────────────────────
@router.get("/documents")
def list_documents(type: str = Query(default=""), ticker: str = Query(default="")) -> list[dict[str, Any]]:  # noqa: A002
    """List documents (content-bearing knowledge rows). Excludes feed rows that back
    Overview widgets — those are infrastructure, not documents."""
    sql = "SELECT type, name, content, metadata, created_at FROM knowledge WHERE content IS NOT NULL"
    params: dict[str, Any] = {}
    if type:
        sql += " AND type = :t"
        params["t"] = type
    sql += " ORDER BY created_at DESC"
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
    except SQLAlchemyError:
        return []
    results = []
    for r in rows:
        md = json.loads(r.metadata) if isinstance(r.metadata, str) else (r.metadata or {})
        if ticker and md.get("ticker") != ticker.upper():
            continue
        created = r.created_at if isinstance(r.created_at, str) else (r.created_at.isoformat() if r.created_at else None)
        results.append({"type": r.type, "name": r.name, "content": r.content, "metadata": md, "created_at": created})
    return results


@router.get("/documents/search")
def search_docs(query: str = Query(..., min_length=1), types: list[str] = Query(default=[])) -> list[dict[str, Any]]:
    """Substring search across document content (case-insensitive)."""
    sql = (
        "SELECT type, name, content, metadata"
        " FROM knowledge"
        " WHERE LOWER(content || ' ' || name) LIKE LOWER(:q)"
    )
    params: dict[str, Any] = {"q": f"%{query}%"}
    if types:
        placeholders = ", ".join(f":t{i}" for i in range(len(types)))
        sql += f" AND type IN ({placeholders})"
        for i, t in enumerate(types):
            params[f"t{i}"] = t
    sql += " ORDER BY updated_at DESC LIMIT 15"
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    results = []
    for r in rows:
        md = json.loads(r.metadata) if isinstance(r.metadata, str) else (r.metadata or {})
        results.append({"type": r.type, "name": r.name, "content": r.content, "metadata": md})
    return results


@router.get("/document/{type}/{name}")
def get_document(type: str, name: str) -> dict[str, Any]:  # noqa: A002
    """Fetch a single document by type and name."""
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT content, metadata, created_at FROM knowledge WHERE type = :t AND name = :n"),
            {"t": type, "n": name},
        ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{type}/{name} not found")
    md = json.loads(row.metadata) if isinstance(row.metadata, str) else (row.metadata or {})
    created = row.created_at if isinstance(row.created_at, str) else row.created_at.isoformat()
    return {
        "type": type,
        "name": name,
        "content": row.content,
        "metadata": md,
        "created_at": created,
    }


# ── Backwards-compat aliases for the existing frontend ───────────────────────
@router.get("/knowledge")
def knowledge_list() -> list[dict[str, Any]]:
    """Unified list of all documents (consumed by Knowledge tab)."""
    return list_documents(type="", ticker="")


@router.get("/learnings")
def learnings_list() -> list[dict[str, Any]]:
    """Return accumulated agent learnings from agno's team_learnings_contents table."""
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, content, meta_data, created_at FROM team_learnings_contents"
                    " ORDER BY created_at DESC LIMIT 200",
                ),
            ).fetchall()
        return [
            {
                "id": r.id,
                "content": r.content,
                "meta_data": r.meta_data or {},
                "created_at": r.created_at if isinstance(r.created_at, str) else r.created_at.isoformat(),
            }
            for r in rows
        ]
    except SQLAlchemyError:
        return []


# ── Setup guide ──────────────────────────────────────────────────────────────
@router.get("/setup-guide")
def setup_guide() -> dict[str, Any]:
    """Return the master-agent-defined setup checklist (only the steps that were left pending after
    the user's interview). For env-var steps we auto-detect completion; CLI/manual steps stay
    'unverified' until the user (or the Platform Engineer) confirms them.
    """
    steps = _FULL_CONFIG.get("setup", {}).get("steps", [])
    enriched: list[dict[str, Any]] = []
    for s in steps:
        item = dict(s)
        if "vars" in s:
            missing = [v for v in s["vars"] if not os.getenv(v)]
            item["completed"] = len(missing) == 0
            item["missing_vars"] = missing
        else:
            item["completed"] = None  # CLI/manual — runtime can't tell
        enriched.append(item)
    blocked = sum(1 for s in enriched if s["completed"] is False)
    pending = sum(1 for s in enriched if s["completed"] is None)
    return {
        "steps": enriched,
        "blocked_count": blocked,
        "pending_count": pending,
        "total": len(enriched),
        "all_done": blocked == 0 and pending == 0 and len(enriched) > 0,
    }


# ── Agent info ───────────────────────────────────────────────────────────────
def _agent_map() -> dict[str, Any]:
    from org.ai.agents.factory import build_agents  # noqa: PLC0415

    return build_agents()


def _extract_tool_names(agent: Agent) -> list[str]:
    names: list[str] = []
    for t in getattr(agent, "tools", None) or []:
        if callable(t) and hasattr(t, "__name__") and not t.__name__.startswith("<"):
            names.append(t.__name__)
        elif hasattr(t, "name") and isinstance(t.name, str):
            names.append(t.name)
        elif hasattr(t, "functions"):
            names.extend(f.__name__ for f in t.functions if callable(f) and hasattr(f, "__name__"))
        else:
            names.append(type(t).__name__)
    return names


def _extract_capabilities(agent: Agent) -> dict[str, bool]:
    from agno.guardrails.prompt_injection import PromptInjectionGuardrail  # noqa: PLC0415

    return {
        "Knowledge Search":   bool(getattr(agent, "search_knowledge", False)),
        "Session History":    bool(getattr(agent, "add_history_to_context", False)),
        "Agentic Memory":     bool(getattr(agent, "enable_agentic_memory", False)),
        "Institutional Learning": getattr(agent, "learning", None) is not None,
        "Prompt Injection Guard": any(
            isinstance(h, PromptInjectionGuardrail) for h in (getattr(agent, "pre_hooks", None) or [])
        ),
    }


_AGENT_DEFS: dict[str, dict[str, Any]] = _FULL_CONFIG.get("agents", {})


@router.get("/agents/{agent_id}/info")
def get_agent_info(agent_id: str) -> dict[str, Any]:
    agent = _agent_map().get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    model_id = ""
    if getattr(agent, "model", None):
        model_id = getattr(agent.model, "id", type(agent.model).__name__)
    a = _AGENT_DEFS.get(agent_id, {})
    return {
        "agent_id": agent_id,
        "name": agent.name or agent_id,
        "model_id": model_id,
        "role": a.get("role", ""),
        "in_scope": a.get("in_scope", []),
        "out_of_scope": a.get("out_of_scope", []),
        "workflow": a.get("workflow", []),
        "output_format": a.get("output_format"),
        "count_rule": a.get("count_rule"),
        "save_rule": a.get("save_rule"),
        "tools": _extract_tool_names(agent),
        "capabilities": {k: v for k, v in _extract_capabilities(agent).items() if v},
    }


# ── Chat history (load latest session for an agent + user) ──────────────────
@router.get("/agents/{agent_id}/history")
def agent_history(agent_id: str, user_id: str = Query(default="default")) -> dict[str, Any]:
    """Return the most recent session's messages for this agent + user, plus its session_id."""
    with get_engine().connect() as conn:
        row = conn.execute(
            text(
                "SELECT session_id, runs FROM agno_sessions"
                " WHERE agent_id = :aid AND user_id = :uid"
                " ORDER BY updated_at DESC NULLS LAST, created_at DESC LIMIT 1",
            ),
            {"aid": agent_id, "uid": user_id},
        ).first()
    if row is None or not row.runs:
        return {"session_id": None, "messages": []}
    messages: list[dict[str, Any]] = []
    for run in row.runs:
        for m in run.get("messages") or []:
            role = m.get("role")
            content = m.get("content")
            if not content:
                continue
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})
    return {"session_id": row.session_id, "messages": messages}


# ── Agent reports (subset of documents with type='report') ───────────────────
@router.get("/agent-reports")
def agent_reports_list(agent_id: str = Query(default=""), ticker: str = Query(default="")) -> dict[str, Any]:
    sql = "SELECT id, name, metadata, created_at FROM knowledge WHERE type = 'report' ORDER BY created_at DESC"
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql)).fetchall()

    by_agent: dict[str, Any] = {}
    for r in rows:
        md = json.loads(r.metadata) if isinstance(r.metadata, str) else (r.metadata or {})
        if agent_id and md.get("agent_id") != agent_id:
            continue
        if ticker and md.get("ticker") != ticker.upper():
            continue
        aid = md.get("agent_id", "unknown")
        if aid not in by_agent:
            by_agent[aid] = {"agent_id": aid, "agent_name": AGENT_NAMES.get(aid, aid), "reports": []}
        created = r.created_at if isinstance(r.created_at, str) else r.created_at.isoformat()
        by_agent[aid]["reports"].append({"id": r.id, "title": r.name, "ticker": md.get("ticker", ""), "created_at": created})
    return {"agents": list(by_agent.values())}


@router.get("/agent-reports/{report_id}")
def agent_report_detail(report_id: int) -> dict[str, Any]:
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT name, content, metadata, created_at FROM knowledge WHERE id = :id AND type = 'report'"),
            {"id": report_id},
        ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    md = json.loads(row.metadata) if isinstance(row.metadata, str) else (row.metadata or {})
    return {
        "id": report_id,
        "agent_id": md.get("agent_id", ""),
        "agent_name": AGENT_NAMES.get(md.get("agent_id", ""), md.get("agent_id", "")),
        "title": row.name,
        "content": row.content,
        "ticker": md.get("ticker", ""),
        "created_at": row.created_at if isinstance(row.created_at, str) else row.created_at.isoformat(),
    }


# ── Workflow continuation (HITL) ─────────────────────────────────────────────
class WorkflowContinueRequest(BaseModel):
    workflow_id: str
    run_id: str
    session_id: str
    approved: bool
    user_input: str | None = None
    user_input_fields: dict[str, Any] | None = None


@router.post("/workflow/continue", response_model=None)
async def continue_workflow(
    body: WorkflowContinueRequest,
    background_tasks: BackgroundTasks,
) -> StreamingResponse | dict[str, str]:
    from agno.os.utils import format_sse_event, get_workflow_by_id  # noqa: PLC0415

    from org.ai.workflows.factory import build_workflows  # noqa: PLC0415

    workflow = get_workflow_by_id(
        workflow_id=body.workflow_id,
        workflows=build_workflows(),
        db=None,
        create_fresh=True,
    )
    if workflow is None:
        return {"error": f"Workflow '{body.workflow_id}' not found"}

    run_response = await workflow.aget_run_output(run_id=body.run_id, session_id=body.session_id)
    if run_response is None:
        return {"error": "Run not found"}

    for req in run_response.step_requirements or []:
        if req.confirmed is None:
            if body.approved:
                req.confirmed = True
                if req.requires_user_input and body.user_input_fields:
                    req.user_input = body.user_input_fields
                elif req.requires_user_input and body.user_input:
                    field_name = (req.user_input_schema or [{}])[0].get("name", "input")
                    req.user_input = {field_name: body.user_input}
            else:
                req.confirmed = False

    async def _stream() -> AsyncGenerator[str, None]:
        async for chunk in workflow.acontinue_run(run_response, stream=True, stream_events=True):
            yield format_sse_event(chunk)

    return StreamingResponse(_stream(), media_type="text/event-stream")


