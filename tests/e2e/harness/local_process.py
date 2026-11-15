"""Run the rendered node and frontend as local processes beside broker and control-plane containers."""

import os
import shutil
import subprocess  # nosec B404 - the harness drives docker, npm and the org's own processes
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import IO

import httpx

from .targets import Endpoints, Project, free_port, org_healthy, require_docker, wait_until

BROKER_IMAGE = 'rabbitmq:3.13-management'
CONTROL_PLANE_IMAGE = 'agentfield/control-plane:latest'
ALL_INTERFACES = '0.0.0.0'  # noqa: S104  # nosec B104 - the control-plane container calls the node back


def _run(*command: str, cwd: Path | None = None, check: bool = True) -> str:
    """Run a fixed harness command and return its output."""
    args = [shutil.which(command[0]) or command[0], *command[1:]]
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check)  # nosec B603
    return result.stdout.strip()


class LocalProcess:
    """The `local-process` target."""

    name = 'local-process'

    def __init__(self, run_id: str) -> None:
        """Prepare a target for the run `run_id` with its own log directory."""
        self.run_id = run_id
        self.logs = Path(tempfile.mkdtemp(prefix=f'agentorg-e2e-{run_id}-'))
        self.containers: dict[str, str] = {}
        self.processes: list[tuple[subprocess.Popen[bytes], IO[bytes]]] = []

    def _container(self, role: str, image: str, ports: str, *options: str) -> None:
        name = f'agentorg-e2e-{self.run_id}-{role}'
        self.containers[role] = name
        _run('docker', 'run', '-d', '--name', name, '-p', ports, *options, image)

    def _spawn(self, role: str, command: list[str], cwd: Path, env: Mapping[str, str]) -> None:
        log = (self.logs / f'{role}.log').open('wb')
        environ = {**os.environ, **env}
        process = subprocess.Popen(command, cwd=cwd, env=environ, stdout=log, stderr=subprocess.STDOUT)  # nosec B603
        self.processes.append((process, log))

    def _infrastructure(self) -> tuple[str, str]:
        broker_port, plane_port = free_port(), free_port()
        self._container('rabbitmq', BROKER_IMAGE, f'{broker_port}:5672')
        plane_env = ('-e', 'AGENTFIELD_HTTP_ADDR=0.0.0.0:8080', '-e', 'AGENTFIELD_STORAGE_MODE=local')
        host = ('--add-host', 'host.docker.internal:host-gateway')
        self._container('control-plane', CONTROL_PLANE_IMAGE, f'{plane_port}:8080', *plane_env, *host)
        # Exec'ing rabbitmq-diagnostics before the server has written its Erlang cookie stops it, so read its log.
        broker = self.containers['rabbitmq']
        wait_until(lambda: 'Server startup complete' in _run('docker', 'logs', broker, check=False), 'the broker')
        plane = f'http://127.0.0.1:{plane_port}'
        wait_until(lambda: not httpx.get(plane, timeout=2).is_server_error, 'the control plane')
        return f'amqp://guest:guest@127.0.0.1:{broker_port}/', plane

    def _frontend(self, project: Project, api: str) -> str:
        frontend = project.root / 'src' / 'frontend'
        _run('npm', 'ci', '--ignore-scripts', cwd=frontend)
        port = free_port()
        npm = shutil.which('npm') or 'npm'
        command = [npm, 'run', 'dev', '--', '--port', str(port), '--strictPort']
        self._spawn('frontend', command, frontend, {'VITE_API_HOST': api})
        url = f'http://127.0.0.1:{port}'
        wait_until(lambda: httpx.get(url, timeout=2).is_success, 'the frontend')
        return url

    def provision(self, project: Project, env: Mapping[str, str], *, ui: bool, chat: bool = False) -> Endpoints:
        """Start the broker, control plane, node and optionally the frontend, then wait for health."""
        if chat:
            msg = 'LibreChat runs only on the local-docker and cloud targets.'
            raise NotImplementedError(msg)
        require_docker()
        amqp, plane = self._infrastructure()
        port = free_port()
        api = f'http://127.0.0.1:{port}'
        node_env = {
            **env,
            'PYTHONPATH': str(project.root / 'src'),
            'AMQP_URL': amqp,
            'AGENTFIELD_SERVER': plane,
            'AGENT_CALLBACK_URL': f'http://host.docker.internal:{port}',
            'AGENTORG_DATA_DIR': str(self.logs / 'data'),
        }
        app = f'{project.package}.app.main:app'
        command = [sys.executable, '-m', 'uvicorn', app, '--host', ALL_INTERFACES, '--port', str(port)]
        self._spawn('node', command, project.root, node_env)
        wait_until(lambda: org_healthy(api), 'the node and its broker connection', timeout=180)
        return Endpoints(api, self._frontend(project, api) if ui else None)

    def collect_logs(self, into: Path) -> None:
        """Copy the process logs and each container's logs into `into`."""
        into.mkdir(parents=True, exist_ok=True)
        for log in self.logs.glob('*.log'):
            shutil.copy(log, into / log.name)
        for role, name in self.containers.items():
            (into / f'{role}.log').write_text(_run('docker', 'logs', name, check=False))

    def teardown(self) -> None:
        """Stop the processes and remove the containers."""
        for process, log in self.processes:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
            log.close()
        for name in self.containers.values():
            _run('docker', 'rm', '-f', '-v', name, check=False)
        shutil.rmtree(self.logs, ignore_errors=True)
