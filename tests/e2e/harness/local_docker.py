"""Run a rendered org with its own `compose.yaml`, adapted so parallel runs and the host's ports never collide."""

import os
import re
import secrets
import shutil
import subprocess  # nosec B404 - the harness drives docker compose and uv
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
import yaml

from .targets import Endpoints, Project, org_healthy, require_docker, wait_until

REPOSITORY = Path(__file__).parents[3]
COMPOSE_FILE = 'compose.e2e.yaml'
DOCKERFILE = 'Dockerfile.e2e'
WHEELS = '.e2e-wheels'
CONSTRAINTS = 'constraints.txt'
DOCKER_HOST = 'host.docker.internal'
LOCAL_URL = re.compile(r'^(https?://)(127\.0\.0\.1|localhost)([:/]|$)')
# Byte lengths of the LibreChat secrets each run generates, not the secrets themselves.
LIBRECHAT_SECRETS = {'LIBRECHAT_CREDS_IV': 16} | dict.fromkeys(
    ['MEILI_MASTER_KEY', 'LIBRECHAT_CREDS_KEY', 'LIBRECHAT_JWT_SECRET', 'LIBRECHAT_JWT_REFRESH_SECRET'],
    32,
)
CHAT_SERVICES = ('librechat', 'librechat-mongodb', 'librechat-meilisearch')


def _run(*command: str, cwd: Path | None = None, env: Mapping[str, str] | None = None, check: bool = True) -> str:
    """Run a fixed harness command and return its output, raising with its stderr when it fails."""
    args = [shutil.which(command[0]) or command[0], *command[1:]]
    environ = {**os.environ, **(env or {})}
    result = subprocess.run(args, cwd=cwd, env=environ, capture_output=True, text=True, check=False)  # nosec B603
    if check and result.returncode:
        msg = f'{" ".join(command[:3])} failed with code {result.returncode}:\n{result.stderr[-4000:]}'
        raise RuntimeError(msg)
    return result.stdout.strip()


def for_containers(value: str) -> str:
    """Rewrite a URL on the host's loopback so it is reachable from inside a container."""
    return LOCAL_URL.sub(rf'\g<1>{DOCKER_HOST}\g<3>', value)


def _environment(service: dict[str, Any]) -> dict[str, str]:
    environment = service.get('environment') or {}
    if isinstance(environment, dict):
        return {key: str(value) for key, value in environment.items()}
    return dict(item.partition('=')[::2] for item in environment)


def adapt_compose(compose: dict[str, Any], slug: str, env: Mapping[str, str], image: str) -> dict[str, Any]:
    """Return the rendered compose file adapted for an isolated e2e run.

    Fixed container names and host ports are dropped in favour of ephemeral loopback ports, the API service is built
    from the e2e Dockerfile and tagged `image`, its source bind mount is dropped so the built image is what runs, and
    `env` is added to its environment with loopback URLs rewritten for containers.

    Arguments:
        compose: The parsed rendered `compose.yaml`.
        slug: The org's slug, which names its services.
        env: Variables for the API service, such as the model API's URL.
        image: The tag of the API image this run builds.

    Returns:
        compose: The adapted compose file.
    """
    adapted = {key: value for key, value in compose.items() if key != 'name'}
    services: dict[str, dict[str, Any]] = {}
    for name, original in compose['services'].items():
        service = {key: value for key, value in original.items() if key != 'container_name'}
        if 'ports' in service:
            service['ports'] = [f'127.0.0.1::{str(port).rsplit(":", 1)[-1]}' for port in service['ports']]
        services[name] = service
    api = services[f'{slug}-api']
    api['build'] = {**api['build'], 'dockerfile': DOCKERFILE}
    api['image'] = image
    api.pop('volumes', None)
    api['command'] = [part for part in api['command'].split() if part != '--reload']
    api['environment'] = _environment(api) | {key: for_containers(value) for key, value in env.items()}
    adapted['services'] = services
    return adapted


def adapt_dockerfile(dockerfile: str) -> str:
    """Install the local agentorg wheel, pinned to the repository's lock, before the org's dependencies resolve.

    The pin keeps the image on the same Claude Code CLI as the host, so recordings replay on every target.
    """
    marker = 'RUN uv pip install --system -e'
    head, found, tail = dockerfile.partition(marker)
    if not found:
        msg = 'The rendered Dockerfile no longer installs the package with `uv pip install --system -e`.'
        raise ValueError(msg)
    local = (
        f'COPY {WHEELS}/ /tmp/wheels/\n'
        f'ENV UV_CONSTRAINT=/tmp/wheels/{CONSTRAINTS}\n'
        'RUN uv pip install --system /tmp/wheels/*.whl\n'
    )
    return f'{head}{local}{found}{tail}'


class LocalDocker:
    """The `local-docker` target."""

    name = 'local-docker'

    def __init__(self, run_id: str) -> None:
        """Prepare a target for the run `run_id` under its own compose project."""
        self.run_id = run_id
        self.project_name = f'agentorg-e2e-{run_id}'.lower()
        self.image = f'{self.project_name}-api:latest'
        self.root: Path | None = None
        self.compose_env: dict[str, str] = {}

    def _compose(self, *args: str, check: bool = True) -> str:
        if self.root is None:
            return ''
        command = ('docker', 'compose', '-p', self.project_name, '-f', str(self.root / COMPOSE_FILE), *args)
        return _run(*command, cwd=self.root, env=self.compose_env, check=check)

    def _url(self, service: str, port: int) -> str:
        address = self._compose('port', service, str(port))
        return f'http://127.0.0.1:{address.rsplit(":", 1)[-1]}'

    def _prepare(self, project: Project, env: Mapping[str, str]) -> None:
        if not (project.root / 'compose.yaml').exists():
            msg = f'{project.slug} has no compose.yaml; local-docker needs runtime.infra.packaging set to docker.'
            raise RuntimeError(msg)
        wheels = project.root / WHEELS
        shutil.rmtree(wheels, ignore_errors=True)
        _run('uv', 'build', '--wheel', '--out-dir', str(wheels), cwd=REPOSITORY)
        export = ('uv', 'export', '--frozen', '--no-hashes', '--no-dev', '--no-emit-project')
        _run(*export, '--output-file', str(wheels / CONSTRAINTS), cwd=REPOSITORY)
        dockerfile = (project.root / 'Dockerfile').read_text()
        (project.root / DOCKERFILE).write_text(adapt_dockerfile(dockerfile))
        compose = yaml.safe_load((project.root / 'compose.yaml').read_text())
        adapted = adapt_compose(compose, project.slug, env, self.image)
        (project.root / COMPOSE_FILE).write_text(yaml.safe_dump(adapted, sort_keys=False))
        self.compose_env = {name: secrets.token_hex(size) for name, size in LIBRECHAT_SECRETS.items()}
        self.compose_env |= {name: value for name, value in env.items() if name == 'CHAT_API_KEY'}

    def provision(self, project: Project, env: Mapping[str, str], *, ui: bool, chat: bool = False) -> Endpoints:
        """Build the API image, start the org's services and wait for the node, broker and control plane."""
        require_docker()
        self.root = project.root
        self._prepare(project, env)
        services = ['control-plane', 'rabbitmq', f'{project.slug}-db', f'{project.slug}-api']
        services += [f'{project.slug}-ui'] if ui else []
        services += list(CHAT_SERVICES) if chat else []
        self._compose('up', '-d', '--build', '--quiet-pull', *services)
        plane = self._url('control-plane', 8080)
        wait_until(lambda: not httpx.get(plane, timeout=2).is_server_error, 'the control plane')
        api = self._url(f'{project.slug}-api', 8000)
        wait_until(lambda: org_healthy(api), 'the node and its broker connection', timeout=240)
        endpoints = Endpoints(api)
        if ui:
            url = self._url(f'{project.slug}-ui', 5173)
            wait_until(lambda: httpx.get(url, timeout=2).is_success, 'the frontend', timeout=300)
            endpoints = Endpoints(api, ui=url)
        if chat:
            url = self._url('librechat', 3080)
            wait_until(lambda: httpx.get(f'{url}/health', timeout=2).is_success, 'LibreChat', timeout=300)
            endpoints = Endpoints(endpoints.api, ui=endpoints.ui, chat=url)
        return endpoints

    def collect_logs(self, into: Path) -> None:
        """Write each service's logs into `into`."""
        into.mkdir(parents=True, exist_ok=True)
        for service in self._compose('config', '--services', check=False).split():
            (into / f'{service}.log').write_text(self._compose('logs', '--no-color', service, check=False))

    def teardown(self) -> None:
        """Remove the run's containers, volumes, network and API image."""
        self._compose('down', '-v', '--remove-orphans', '--timeout', '10', check=False)
        _run('docker', 'image', 'rm', '-f', self.image, check=False)
        if self.root is not None:
            shutil.rmtree(self.root / WHEELS, ignore_errors=True)
