"""FastAPI app exposing the master interview agent over HTTP for a browser client.

The server holds a single agent instance for the process lifetime. `/api/chat` accepts the
user's message and returns the master's reply plus the tool calls it made; `/api/spec`
returns a JSON snapshot of the working spec (org + agents + teams + workflows + knowledge +
parameters, plus any custom tools/skills) so the browser can render a live view that updates
after every turn. `/api/render` writes spec.py + materialises the full project tree.
"""

import asyncio
import io
import logging
import tempfile
import zipfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agentorg.core.render import render as render_project

from .._agent import build_master_agent
from .._persistence import save_draft
from .._seed import PLACEHOLDER_VALUES
from .._state import State, get_state, reset_state
from .._tools import finalize_spec

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / '_static'
INDEX_HTML = STATIC_DIR / 'index.html'

# Substrings (case-insensitive) that mark an upstream-model exception as transient and worth retrying.
_TRANSIENT_MARKERS: tuple[str, ...] = (
    '429',
    '502',
    '503',
    '504',
    'service unavailable',
    'overloaded',
    'rate limit',
    'too many requests',
    'temporarily unavailable',
)
_CHAT_RETRY_ATTEMPTS = 3
_CHAT_RETRY_BASE_DELAY = 1.0


class ChatRequest(BaseModel):
    """Body of a `POST /api/chat` request - just the user's message text."""

    message: str


class ChatResponse(BaseModel):
    """Result of a `POST /api/chat` call - the master's reply text and the tool calls it made."""

    response: str
    tool_calls: list[str]


class RenderRequest(BaseModel):
    """Body of a `POST /api/render` request - currently empty, kept for future options."""


def _is_placeholder_value(value: Any) -> bool:  # noqa: ANN401
    """True when `value` is one of the seed-state placeholders the user has not filled in yet."""
    return isinstance(value, str) and value in PLACEHOLDER_VALUES


STAGES: tuple[str, ...] = ('discover', 'propose', 'build', 'audit', 'review')


def _detect_stage(state: State) -> str:
    """Return the furthest interview stage the state has progressed to.

    Pure heuristic over the spec - the master agent does not have to cooperate:
      - discover: org.name still placeholder or org.description still placeholder
      - propose:  org identity is real, but `ai.agents` is empty
      - build:    agents exist, but at least one is missing name/role/(tools|skills)
      - audit:    all agents are fully defined, but no env vars / setup steps declared
      - review:   env vars / setup steps populated (the operator-facing material)
    """
    spec = state.spec
    org = spec.org
    if (not org.name or _is_placeholder_value(org.name)
            or not org.description or _is_placeholder_value(org.description)):
        return 'discover'
    if not spec.ai.agents:
        return 'propose'
    for agent in spec.ai.agents:
        if (not agent.name or _is_placeholder_value(agent.name)
                or not agent.role or _is_placeholder_value(agent.role)
                or (not agent.tools and not agent.skills)):
            return 'build'
    runtime = spec.runtime
    if not runtime.env_vars.required and not runtime.env_vars.optional and not runtime.setup:
        return 'audit'
    return 'review'


def _readiness(state: State) -> dict[str, Any]:
    """Return whether the working spec is complete enough to render, plus blockers if not."""
    blockers: list[str] = []
    org = state.spec.org
    if not org.name or _is_placeholder_value(org.name):
        blockers.append('Organization needs a real name.')
    if not org.slug or _is_placeholder_value(org.slug):
        blockers.append('Organization needs a slug.')
    if not org.package_name or _is_placeholder_value(org.package_name):
        blockers.append('Organization needs a Python package name.')
    if not state.spec.ai.agents:
        blockers.append('Add at least one agent.')
    for agent in state.spec.ai.agents:
        if not agent.name or _is_placeholder_value(agent.name):
            blockers.append(f"Agent '{agent.agent_id}' needs a name.")
        if not agent.role or _is_placeholder_value(agent.role):
            blockers.append(f"Agent '{agent.agent_id}' needs a role.")
    default = org.slug if org.slug and not _is_placeholder_value(org.slug) else ''
    return {
        'ready': not blockers,
        'blockers': blockers,
        'org_slug': default,
        'stage': _detect_stage(state),
    }


def _agent_factory_default() -> Any:  # noqa: ANN401 (returns an agno.Agent; avoid leaking the type)
    """Build the default master agent. Override in tests via `build_app(agent_factory=...)`."""
    return build_master_agent()


def _extract_tool_calls(run_output: Any) -> list[str]:  # noqa: ANN401 (RunOutput shape is loose)
    """Pull a flat list of tool-call names out of an agno `RunOutput`."""
    tool_calls = getattr(run_output, 'tool_calls', None) or []
    names: list[str] = []
    for call in tool_calls:
        name = (
            getattr(call, 'tool_name', None)
            or getattr(call, 'name', None)
            or (call.get('tool_name') if isinstance(call, dict) else None)
            or (call.get('name') if isinstance(call, dict) else None)
        )
        if name:
            names.append(str(name))
    return names


def _spec_snapshot() -> dict[str, Any]:
    """Build the JSON payload `GET /api/spec` returns - spec + custom tools/skills + readiness."""
    state = get_state()
    return {
        'spec': state.spec.model_dump(mode='json'),
        'custom_tools': [{'name': t.name, 'source': t.source} for t in state.custom_tools],
        'custom_skills': [{'name': s.name, 'skill_md': s.skill_md} for s in state.custom_skills],
        'readiness': _readiness(state),
    }


def _materialise_to_zip(slug: str) -> bytes:
    """Render the current spec into a fresh temp dir, then zip it and return the bytes.

    Caller-agnostic: works whether the server runs on the user's laptop or in the cloud.
    The temp directory is removed when this function returns; the user receives the zip
    via the HTTP response and decides where to extract.
    """
    with tempfile.TemporaryDirectory(prefix='agentorg-render-') as tmp_str:
        output_dir = Path(tmp_str) / slug
        output_dir.mkdir(parents=True, exist_ok=True)
        spec_path = output_dir / 'spec.py'
        finalize_spec(spec_path)
        render_project(spec_path, output_dir)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            for entry in sorted(output_dir.rglob('*')):
                if entry.is_file():
                    zf.write(entry, arcname=Path(slug) / entry.relative_to(output_dir))
        return buffer.getvalue()


def _is_transient(exc: BaseException) -> bool:
    """True when `exc` carries a marker that suggests retrying might succeed (5xx, 429, overload)."""
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


async def _arun_with_retry(agent: Any, message: str) -> Any:  # noqa: ANN401
    """Run `agent.arun(message)` with exponential backoff on transient upstream errors.

    Non-transient exceptions propagate immediately. Transient ones are retried up to
    `_CHAT_RETRY_ATTEMPTS` total times with `_CHAT_RETRY_BASE_DELAY * 2**attempt` second pauses;
    the last failure is re-raised so the caller can surface it.
    """
    last_exc: BaseException | None = None
    for attempt in range(_CHAT_RETRY_ATTEMPTS):
        try:
            return await agent.arun(message)
        except Exception as exc:
            last_exc = exc
            if not _is_transient(exc) or attempt == _CHAT_RETRY_ATTEMPTS - 1:
                raise
            delay = _CHAT_RETRY_BASE_DELAY * (2**attempt)
            logger.warning('chat: transient upstream error (attempt %d/%d), retrying in %.1fs: %s',
                           attempt + 1, _CHAT_RETRY_ATTEMPTS, delay, exc)
            await asyncio.sleep(delay)
    assert last_exc is not None  # the loop above always returns or raises - this satisfies the type-checker
    raise last_exc


def build_app(  # noqa: C901  (route-registry function; complexity grows with route count)
    *,
    agent_factory: Callable[[], Any] = _agent_factory_default,
    draft_path: Path | None = None,
    autosave: bool = True,
) -> FastAPI:
    """Build a FastAPI app wrapping the master agent.

    Arguments:
        agent_factory: Callable returning an `agno.Agent`. Overridden in tests to inject a
            mock without making real model calls.
        draft_path: Where `save_draft` writes after each turn. Defaults to none = no autosave.
        autosave: When True and `draft_path` is set, snapshots the working spec to disk after
            every turn so resume / inspection works.

    Returns:
        app: The configured FastAPI app.
    """
    app = FastAPI(title='agentorg master UI', docs_url=None, redoc_url=None)
    agent_holder: dict[str, Any] = {}

    def _agent() -> Any:  # noqa: ANN401
        if 'agent' not in agent_holder:
            agent_holder['agent'] = agent_factory()
        return agent_holder['agent']

    async def _post_chat_hook() -> None:
        if autosave and draft_path is not None:
            save_draft(draft_path)

    @app.get('/', response_class=HTMLResponse)
    async def index() -> str:
        return INDEX_HTML.read_text()

    @app.get('/api/spec')
    async def get_spec() -> dict[str, Any]:
        return _spec_snapshot()

    @app.post('/api/chat', response_model=ChatResponse)
    async def post_chat(req: ChatRequest) -> ChatResponse:
        try:
            run_output = await _arun_with_retry(_agent(), req.message)
        except Exception as exc:
            if _is_transient(exc):
                logger.warning('chat: upstream still unavailable after retries: %s', exc)
                raise HTTPException(
                    status_code=503,
                    detail='Upstream model is temporarily unavailable. Please retry your message.',
                ) from exc
            logger.exception('chat: agent.arun raised')
            raise HTTPException(status_code=500, detail=f'Chat failed: {exc}') from exc
        content = getattr(run_output, 'content', None) or ''
        tool_calls = _extract_tool_calls(run_output)
        await _post_chat_hook()
        return ChatResponse(response=str(content), tool_calls=tool_calls)

    @app.post('/api/reset')
    async def post_reset() -> dict[str, str]:
        reset_state()
        agent_holder.pop('agent', None)
        return {'status': 'reset'}

    @app.post('/api/render')
    async def post_render(_req: RenderRequest | None = None) -> Response:
        state = get_state()
        readiness = _readiness(state)
        if not readiness['ready']:
            raise HTTPException(status_code=409, detail={'blockers': readiness['blockers']})
        slug = state.spec.org.slug
        try:
            payload = await asyncio.to_thread(_materialise_to_zip, slug)
        except Exception as exc:
            logger.exception('render: materialise_to_zip raised')
            raise HTTPException(status_code=500, detail=f'Render failed: {exc}') from exc
        return Response(
            content=payload,
            media_type='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename="{slug}.zip"',
                'X-AgentOrg-Slug': slug,
            },
        )

    app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
    return app


def serve(*, host: str = '127.0.0.1', port: int = 8765, draft_path: Path | None = None) -> None:
    """Run the UI server with uvicorn. Blocks until interrupted.

    Arguments:
        host: Bind address.
        port: Bind port.
        draft_path: Where the autosave hook writes the in-progress draft.
    """
    import uvicorn  # noqa: PLC0415  (defer import - uvicorn is heavy)

    app = build_app(draft_path=draft_path)
    uvicorn.run(app, host=host, port=port, log_level='warning')


__all__: list[str] = [
    'ChatRequest',
    'ChatResponse',
    'RenderRequest',
    'build_app',
    'serve',
]

# typing helper for ruff/mypy peace
_HookT = Callable[[], Awaitable[None]]
