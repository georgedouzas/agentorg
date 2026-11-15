"""FastAPI app exposing the master interview agent over HTTP for a browser client."""

import asyncio
import io
import logging
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ...core.operations import build_chat_router
from ...core.render import jinja_context
from ...core.render import render as render_project
from .._agent import agent_for_current_stage
from .._persistence import save_draft
from .._seed import PLACEHOLDER_VALUES
from .._stages import stage_summary
from .._state import State, get_state
from .._tools import finalize_spec
from ._chat import MasterChat
from ._preview import PreviewManager

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / '_static'
INDEX_HTML = STATIC_DIR / 'index.html'

CHAT_RETRY_ATTEMPTS = 3
CHAT_RETRY_BASE_DELAY = 1.0


class RenderRequest(BaseModel):
    """Body of a `POST /api/render` request - currently empty, kept for future options."""


def _is_placeholder_value(value: Any) -> bool:  # noqa: ANN401
    """True when `value` is one of the seed-state placeholders the user has not filled in yet."""
    return isinstance(value, str) and value in PLACEHOLDER_VALUES


def _readiness(state: State) -> dict[str, Any]:
    """Return whether the working spec is complete enough to render, plus blockers if not.

    Distinct from the stage-machine's per-stage threshold - this gates external render
    actions (e.g. the /api/render zip download endpoint).
    """
    blockers: list[str] = []
    org = state.spec.org
    if not org.name or _is_placeholder_value(org.name):
        blockers.append('Organization needs a real name.')
    if not org.slug or _is_placeholder_value(org.slug):
        blockers.append('Organization needs a slug.')
    if not org.package_name or _is_placeholder_value(org.package_name):
        blockers.append('Organization needs a Python package name.')
    default = org.slug if org.slug and not _is_placeholder_value(org.slug) else ''
    return {
        'ready': not blockers,
        'blockers': blockers,
        'org_slug': default,
    }


def _agent_factory_default() -> Any:  # noqa: ANN401 - a StageAgent, or a test double with `arun`
    """Return the agent for the current stage.

    Called once per chat turn so a stage transition (after `advance_to_next_stage`) is
    picked up immediately - the next user message hits the new stage's narrowly-scoped
    agent. Override in tests via `build_app(agent_factory=...)`.
    """
    return agent_for_current_stage()


def _spec_snapshot() -> dict[str, Any]:
    """Build the JSON payload `GET /api/spec` returns: spec + custom tools/skills + readiness + stage."""
    state = get_state()
    return {
        'spec': jinja_context(state.spec),
        'structure_error': state.structure_error,
        'custom_tools': [{'name': t.name, 'source': t.source} for t in state.custom_tools],
        'custom_skills': [{'name': s.name, 'skill_md': s.skill_md} for s in state.custom_skills],
        'readiness': _readiness(state),
        'stage_summary': stage_summary(state),
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
    markers = (
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
    msg = str(exc).lower()
    return any(marker in msg for marker in markers)


async def _arun_with_retry(agent: Any, message: str) -> Any:  # noqa: ANN401
    """Run `agent.arun(message)` with exponential backoff on transient upstream errors.

    Non-transient exceptions propagate immediately. Transient ones are retried up to `CHAT_RETRY_ATTEMPTS` total times
    with `CHAT_RETRY_BASE_DELAY * 2**attempt` second pauses; the last failure is re-raised so the caller can surface it.
    """
    last_exc: BaseException | None = None
    for attempt in range(CHAT_RETRY_ATTEMPTS):
        try:
            return await agent.arun(message)
        except Exception as exc:
            last_exc = exc
            if not _is_transient(exc) or attempt == CHAT_RETRY_ATTEMPTS - 1:
                raise
            delay = CHAT_RETRY_BASE_DELAY * (2**attempt)
            logger.warning(
                'chat: transient upstream error (attempt %d/%d), retrying in %.1fs: %s',
                attempt + 1,
                CHAT_RETRY_ATTEMPTS,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None  # the loop above always returns or raises - this satisfies the type-checker
    raise last_exc


def build_app(  # noqa: C901  (route-registry function; complexity grows with route count)
    *,
    agent_factory: Callable[[], Any] = _agent_factory_default,
    draft_path: Path | None = None,
    autosave: bool = True,
    preview: PreviewManager | None = None,
    chat_api_key: str | None = None,
    chat_url: str = 'http://localhost:3080',
) -> FastAPI:
    """Build a FastAPI app wrapping the master agent.

    Arguments:
        agent_factory: Callable returning the stage agent. Overridden in tests to inject a
            mock without making real model calls.
        draft_path: Where `save_draft` writes after each turn. Defaults to none = no autosave.
        autosave: When True and `draft_path` is set, snapshots the working spec to disk after
            every turn so resume / inspection works.
        preview: Optional preview-manager singleton. When supplied, the server boots it on
            startup, schedules a re-render after each spec-mutating chat turn, and exposes
            its state via `GET /api/preview`. Tests pass `None` to skip subprocess spawn.
        chat_api_key: The key LibreChat sends; when set, the interview is served at `/v1` as the `agentorg` model.
        chat_url: The LibreChat address the page links to.

    Returns:
        app: The configured FastAPI app.
    """
    app = FastAPI(title='agentorg master UI', docs_url=None, redoc_url=None)

    boot_task_holder: dict[str, asyncio.Task[None]] = {}
    if preview is not None:

        @app.on_event('startup')
        async def _boot_preview() -> None:
            # Fire-and-forget: the master UI starts serving immediately; the canvas shows
            # a 'Preview is loading...' placeholder until /api/preview reports ready.
            boot_task_holder['task'] = asyncio.create_task(preview.boot())

        @app.on_event('shutdown')
        async def _shutdown_preview() -> None:
            await preview.shutdown()

    def _agent() -> Any:  # noqa: ANN401
        # Call the factory each turn so stage transitions (advance_to_next_stage flips
        # `state.stage`) immediately pick up the new stage's agent. The previous single-
        # agent design cached the FIRST stage's agent forever, freezing tool scope.
        return agent_factory()

    async def _after_turn() -> None:
        if autosave and draft_path is not None:
            save_draft(draft_path)
        # The spec almost certainly changed, so re-render the preview; uvicorn --reload and Vite pick it up.
        if preview is not None:
            preview.schedule_rerender()

    def _preview_status() -> dict[str, Any]:
        if preview is None:
            return {'status': 'disabled', 'detail': 'Preview is not enabled for this app.'}
        snap = preview.snapshot()
        return {'status': snap.status, 'detail': snap.detail, 'slug': snap.slug, 'frontend_url': snap.frontend_url}

    if chat_api_key:
        chat = MasterChat(lambda message: _arun_with_retry(_agent(), message), _after_turn, _preview_status)
        app.include_router(build_chat_router(chat, api_key=chat_api_key, owner='agentorg'))

    @app.get('/', response_class=HTMLResponse)
    async def index() -> str:
        return INDEX_HTML.read_text()

    @app.get('/api/spec')
    async def get_spec() -> dict[str, Any]:
        return _spec_snapshot()

    @app.get('/api/preview')
    async def get_preview() -> dict[str, Any]:
        if preview is None:
            return {
                'status': 'disabled',
                'api_url': None,
                'frontend_url': None,
                'slug': None,
                'detail': 'Preview is not enabled for this app.',
                'started_at': None,
            }
        snap = preview.snapshot()
        return {
            'status': snap.status,
            'api_url': snap.api_url,
            'frontend_url': snap.frontend_url,
            'slug': snap.slug,
            'detail': snap.detail,
            'started_at': snap.started_at,
        }

    @app.get('/api/chat-app')
    async def get_chat_app() -> dict[str, str]:
        return {'url': chat_url}

    async def _render_zip() -> Response:
        state = get_state()
        if state.stage not in {'build', 'refine', 'handoff'}:
            raise HTTPException(
                status_code=409,
                detail={
                    'blockers': [
                        (
                            f"The project download is available from Stage 3 onward; "
                            f"you're currently in Stage '{state.stage}'."
                        ),
                    ],
                },
            )
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

    @app.get('/api/render')
    async def get_render() -> Response:
        # Plain anchor clicks (`<a href="/api/render">`) issue GET and trigger the download
        # because Content-Disposition: attachment is set on the response.
        return await _render_zip()

    @app.post('/api/render')
    async def post_render(_req: RenderRequest | None = None) -> Response:
        # POST kept for back-compat with the older create-org-dialog flow.
        return await _render_zip()

    app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
    return app


def serve(
    *,
    host: str = '127.0.0.1',
    port: int = 8765,
    draft_path: Path | None = None,
    preview_enabled: bool = True,
    chat_api_key: str | None = None,
    chat_url: str = 'http://localhost:3080',
) -> None:
    """Run the UI server with uvicorn until interrupted.

    Arguments:
        host: Bind address.
        port: Bind port; the preview node listens on the next port.
        draft_path: Where the autosave hook writes the in-progress draft.
        preview_enabled: Whether to boot the live preview subprocesses on startup.
        chat_api_key: The key LibreChat sends to the master and the preview.
        chat_url: The LibreChat address the page links to.
    """
    import uvicorn  # noqa: PLC0415  (defer import - uvicorn is heavy)

    preview = PreviewManager(fixed_api_port=port + 1, chat_api_key=chat_api_key) if preview_enabled else None
    app = build_app(draft_path=draft_path, preview=preview, chat_api_key=chat_api_key, chat_url=chat_url)
    uvicorn.run(app, host=host, port=port, log_level='warning')


__all__: list[str] = [
    'RenderRequest',
    'build_app',
    'serve',
]
