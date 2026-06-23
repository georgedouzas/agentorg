"""Live preview of the rendered org for the master UI."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import signal
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ...core.render import render as render_project
from .._state import get_state
from .._tools import finalize_spec

logger = logging.getLogger(__name__)

# Status the frontend polls to know whether the iframe should swap from the placeholder
# to the live URL, or stay on a "preview is starting" message.
PreviewStatus = Literal['idle', 'booting', 'ready', 'error']


@dataclass
class PreviewSnapshot:
    """Read-only view of `PreviewManager` state, returned to the frontend via /api/preview."""

    status: PreviewStatus
    api_url: str | None
    frontend_url: str | None
    slug: str | None
    detail: str | None
    started_at: float | None


def _pick_port() -> int:
    """Bind a socket to port 0 and return the OS-assigned port, then release the socket."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _have(executable: str) -> bool:
    """True when `executable` is on PATH (used for friendly diagnostics)."""
    return shutil.which(executable) is not None


def _probe_http(url: str, *, timeout: float = 0.6) -> bool:
    """True when `url` responds with ANY HTTP status (uvicorn's `/` returns 404 - that's fine).

    Used to gate `status='ready'`: we only flip after both subprocesses are actually
    serving HTTP, so the iframe never lands on a `connection refused` page.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout):  # noqa: S310 (localhost only)
            return True
    except urllib.error.HTTPError:
        return True  # any HTTP response - including 404 - means the port is bound
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


@dataclass
class PreviewManager:
    """Boots and supervises the rendered org as two subprocesses next to the master UI."""

    cache_root: Path = field(default_factory=lambda: Path.home() / '.agentorg' / 'preview')
    status: PreviewStatus = 'idle'
    detail: str | None = None
    api_port: int | None = None
    frontend_port: int | None = None
    work_dir: Path | None = None
    slug: str | None = None
    started_at: float | None = None
    api_proc: asyncio.subprocess.Process | None = None
    frontend_proc: asyncio.subprocess.Process | None = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _re_render_pending: bool = False
    _re_render_task: asyncio.Task[None] | None = None

    def snapshot(self) -> PreviewSnapshot:
        """Return the public-facing view of preview state used by /api/preview."""
        return PreviewSnapshot(
            status=self.status,
            api_url=f'http://127.0.0.1:{self.api_port}' if self.api_port else None,
            frontend_url=f'http://127.0.0.1:{self.frontend_port}' if self.frontend_port else None,
            slug=self.slug,
            detail=self.detail,
            started_at=self.started_at,
        )

    async def boot(self) -> None:
        """Render the current spec + spawn uvicorn + spawn Vite.

        Idempotent.         Called once at master-UI startup. If anything fails, `status` flips to 'error'         with
        the reason in `detail` so the frontend can show the failure mode instead of         an indefinite spinner.
        """

        async with self._lock:
            if self.status in {'booting', 'ready'}:
                return
            self.status = 'booting'
            self.detail = None
            self.started_at = time.time()
        try:
            await self._boot_locked()
            self.status = 'ready'
        except Exception as exc:
            logger.exception('preview boot failed')
            self.status = 'error'
            self.detail = f'{type(exc).__name__}: {exc}'

    async def _boot_locked(self) -> None:
        """Boot sequence: render -> uv sync -> npm install -> spawn uvicorn -> spawn Vite."""
        state = get_state()
        slug = state.spec.org.slug or 'preview'
        self.slug = slug
        self.work_dir = self.cache_root / slug
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # 1. Render current spec
        spec_path = self.work_dir / 'spec.py'
        await asyncio.to_thread(self._render_to_disk, spec_path)

        # 2a. Point the rendered pyproject.toml at our local `agentorg` checkout so `uv sync`
        #     can find the package (agentorg is not on PyPI). The block is idempotent - same
        #     content survives re-renders that overwrite pyproject.toml.
        await asyncio.to_thread(self._patch_pyproject_for_local_agentorg)

        # 2b. uv sync (Python deps for the rendered org)
        if not _have('uv'):
            msg = (
                "uv is not on PATH. Install uv (https://docs.astral.sh/uv/) so the "
                "preview can sync the rendered org's Python dependencies."
            )
            raise RuntimeError(msg)
        await self._run_sync(['uv', 'sync'], cwd=self.work_dir, label='uv sync')

        # 3. npm install (frontend deps)
        frontend_dir = self.work_dir / 'src' / 'frontend'
        if frontend_dir.exists():
            if not _have('npm'):
                msg = (
                    'npm is not on PATH. Install Node.js (https://nodejs.org/) so the '
                    'preview can install the rendered frontend dependencies.'
                )
                raise RuntimeError(msg)
            await self._run_sync(['npm', 'install', '--no-fund', '--no-audit'], cwd=frontend_dir, label='npm install')

        # 4. Spawn uvicorn --reload on the rendered API
        self.api_port = _pick_port()
        package = state.spec.org.package_name
        api_env = {
            **os.environ,
            'AGENTORG_PREVIEW_MODE': 'true',
        }
        api_log = self.work_dir / '.preview-api.log'
        # `start_new_session=True` makes the subprocess its own process-group leader, so
        # killing the group with `os.killpg(pgid, SIGTERM)` cleans up the `uv run` wrapper
        # AND the uvicorn child it spawns. Without this, uv exits but uvicorn keeps running
        # bound to its port - the next master-UI launch then can't claim the same port.
        self.api_proc = await asyncio.create_subprocess_exec(
            'uv',
            'run',
            'uvicorn',
            f'{package}.app.main:app',
            '--reload',
            '--host',
            '127.0.0.1',
            '--port',
            str(self.api_port),
            cwd=str(self.work_dir),
            env=api_env,
            stdout=api_log.open('wb'),
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        logger.info('preview: uvicorn started on :%d (pid=%s), log=%s', self.api_port, self.api_proc.pid, api_log)

        # 5. Spawn Vite dev server, pointing its API proxy at our uvicorn port.
        # `VITE_AGENTORG_PREVIEW_MODE` is baked into the served bundle and tells the
        # React app to skip the login + parameter-setup modal + setup-status block,
        # so the iframe lands straight on the dashboard from turn one.
        if frontend_dir.exists():
            self.frontend_port = _pick_port()
            vite_env = {
                **os.environ,
                'VITE_API_HOST': f'http://127.0.0.1:{self.api_port}',
                'VITE_AGENTORG_PREVIEW_MODE': 'true',
            }
            vite_log = self.work_dir / '.preview-vite.log'
            self.frontend_proc = await asyncio.create_subprocess_exec(
                'npm',
                'run',
                'dev',
                '--',
                '--host',
                '127.0.0.1',
                '--port',
                str(self.frontend_port),
                '--strictPort',
                cwd=str(frontend_dir),
                env=vite_env,
                stdout=vite_log.open('wb'),
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
            logger.info(
                'preview: vite started on :%d (pid=%s), log=%s',
                self.frontend_port,
                self.frontend_proc.pid,
                vite_log,
            )

        # 6. Wait until the frontend (and API) actually serve HTTP. If we flip to 'ready'
        #    before that, the iframe loads while the port is still unbound and Firefox /
        #    Chrome cache a "connection refused" page that doesn't auto-recover.
        await self._wait_for_http_ready()

    async def _wait_for_http_ready(self, *, timeout: float = 60.0, interval: float = 0.4) -> None:
        """Poll the spawned servers' HTTP ports until they respond (or `timeout` elapses)."""
        targets: list[tuple[str, int]] = []
        if self.frontend_port:
            targets.append(('vite', self.frontend_port))
        if self.api_port:
            targets.append(('uvicorn', self.api_port))
        if not targets:
            return
        deadline = time.monotonic() + timeout
        for label, port in targets:
            url = f'http://127.0.0.1:{port}/'
            while time.monotonic() < deadline:
                if not self._all_subprocesses_alive():
                    msg = f'preview subprocess died while waiting for {label}; see logs in {self.work_dir}'
                    raise RuntimeError(msg)
                if await asyncio.to_thread(_probe_http, url):
                    logger.info('preview: %s on :%d is serving HTTP', label, port)
                    break
                await asyncio.sleep(interval)
            else:
                msg = (
                    f'preview {label} on :{port} did not start serving within '
                    f'{timeout}s; see logs in {self.work_dir}'
                )
                raise RuntimeError(msg)

    def _all_subprocesses_alive(self) -> bool:
        """Return False if any spawned subprocess has already exited."""
        for proc in (self.api_proc, self.frontend_proc):
            if proc is not None and proc.returncode is not None:
                return False
        return True

    def _render_to_disk(self, spec_path: Path) -> None:
        """Write spec.py + materialise the project tree at `self.work_dir`."""
        assert self.work_dir is not None
        finalize_spec(spec_path)
        render_project(spec_path, self.work_dir)

    def _patch_pyproject_for_local_agentorg(self) -> None:
        """Append `[tool.uv.sources]` to the rendered pyproject so uv finds local agentorg.

        The rendered org's `pyproject.toml` declares `agentorg` as a dependency, but the
        package is not published. We point uv at this repo - the same trick the rendered-
        org test fixture uses. Idempotent: the block is only added if it's not there.
        """
        assert self.work_dir is not None
        pyproject = self.work_dir / 'pyproject.toml'
        if not pyproject.exists():
            return
        text = pyproject.read_text()
        if '[tool.uv.sources]' in text:
            return
        # Walk up from this module (src/agentorg/master/ui/_preview.py) to the repo root
        # that contains the `agentorg` package's own pyproject.
        agentorg_root = Path(__file__).resolve().parents[4]
        pyproject.write_text(
            text + f'\n[tool.uv.sources]\nagentorg = {{ path = "{agentorg_root}", editable = true }}\n',
        )

    async def _run_sync(self, cmd: list[str], *, cwd: Path, label: str) -> None:
        """Run a blocking subprocess (deps install) and surface failures to the caller."""
        logger.info('preview: %s in %s', label, cwd)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            tail = (err or out).decode(errors='replace').splitlines()[-30:]
            msg = f"'{label}' failed (exit {proc.returncode}):\n" + '\n'.join(tail)
            raise RuntimeError(msg)

    def schedule_rerender(self, *, debounce: float = 1.0) -> None:
        """Schedule a re-render after `debounce` seconds; coalesces multiple rapid calls.

        Called every chat turn. uvicorn's `--reload` watches the spec.py file and restarts the API process within a
        second; Vite HMRs any rendered frontend file that changed.
        """
        if self.status != 'ready':
            return  # nothing useful to re-render against yet
        self._re_render_pending = True
        if self._re_render_task is None or self._re_render_task.done():
            self._re_render_task = asyncio.create_task(self._debounced_rerender(debounce))

    async def _debounced_rerender(self, debounce: float) -> None:
        while self._re_render_pending:
            self._re_render_pending = False
            await asyncio.sleep(debounce)
        if self.work_dir is None:
            return
        spec_path = self.work_dir / 'spec.py'
        try:
            await asyncio.to_thread(self._render_to_disk, spec_path)
            logger.debug('preview: re-rendered spec.py at %s', spec_path)
        except Exception:
            logger.exception('preview: re-render failed')

    async def shutdown(self) -> None:
        """SIGTERM both subprocess groups on master-UI exit.

        Each subprocess is its own process-group leader (see `start_new_session=True`),
        so we kill the whole group - that catches the `uv run` / `npm run` wrapper AND
        the uvicorn / Vite child it spawned, preventing orphan ports across restarts.
        """
        for proc in (self.api_proc, self.frontend_proc):
            if proc is None or proc.returncode is not None:
                continue
            pgid = self._pgid(proc)
            try:
                if pgid is not None:
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5)
            except (TimeoutError, ProcessLookupError):
                with contextlib.suppress(ProcessLookupError):
                    if pgid is not None:
                        os.killpg(pgid, signal.SIGKILL)
                    else:
                        proc.kill()

    @staticmethod
    def _pgid(proc: asyncio.subprocess.Process) -> int | None:
        """Return the process-group id for `proc`, or None on platforms without process groups."""
        try:
            return os.getpgid(proc.pid)
        except (ProcessLookupError, OSError):
            return None
