"""Deployment targets the e2e scenarios run against."""

import shutil
import socket
import subprocess  # nosec B404 - the harness drives docker and the org's own processes
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

TARGETS = ('local-process', 'local-docker', 'cloud')
MODEL_MODES = ('replay', 'record', 'live')


@dataclass(frozen=True)
class Project:
    """A rendered org on disk."""

    root: Path
    package: str
    slug: str


@dataclass(frozen=True)
class Endpoints:
    """Where a provisioned org answers."""

    api: str
    ui: str | None = None


class Target(Protocol):
    """Provisions a rendered org somewhere it can be exercised, and removes it again."""

    name: str

    def provision(self, project: Project, env: Mapping[str, str], *, ui: bool) -> Endpoints:
        """Start the org with `env` and return its endpoints once it is healthy."""
        ...

    def collect_logs(self, into: Path) -> None:
        """Copy the node, frontend and broker logs into `into`."""
        ...

    def teardown(self) -> None:
        """Remove everything `provision` created; safe to call after a partial provision."""
        ...


def require_docker() -> None:
    """Fail with a clear message when the Docker daemon is not reachable."""
    docker = shutil.which('docker')
    if docker is None or subprocess.run([docker, 'info'], capture_output=True, check=False).returncode:  # nosec B603
        msg = 'The e2e suite needs a running Docker daemon for the broker and the control plane.'
        raise RuntimeError(msg)


def free_port() -> int:
    """Return a TCP port that is free on localhost."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def wait_until(check: Callable[[], bool], what: str, timeout: float = 120) -> None:
    """Poll `check` until it returns true, failing after `timeout` seconds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except (httpx.HTTPError, OSError):
            pass
        time.sleep(0.5)
    msg = f'Timed out after {timeout:.0f}s waiting for {what}.'
    raise TimeoutError(msg)


def org_healthy(api: str) -> bool:
    """Return whether the org's node answers and its broker is connected."""
    reply = httpx.get(f'{api}/api/v1/health', timeout=5)
    return reply.is_success and reply.json().get('broker') == 'ok'


def make_target(name: str, run_id: str) -> Target:
    """Return the target called `name` for the run `run_id`."""
    from .local_process import LocalProcess  # noqa: PLC0415 - targets import this module

    targets: dict[str, Callable[[str], Target]] = {'local-process': LocalProcess}
    if name not in targets:
        msg = f'Target {name!r} is not implemented yet; available: {", ".join(targets)}.'
        raise NotImplementedError(msg)
    return targets[name](run_id)
