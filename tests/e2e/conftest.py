"""Options, deployment and teardown guarantees for the e2e scenarios."""

import json
import os
import runpy
import secrets
import shutil
import sys
import threading
import time
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from agentorg.core.render import render
from agentorg.core.spec import Spec
from agentorg.master import write_spec

from .harness.client import OrgClient
from .harness.mock_anthropic import MockAnthropic, serve
from .harness.targets import MODEL_MODES, TARGETS, Endpoints, Project, Target, free_port, make_target, require_docker

CASSETTES = Path(__file__).parent / 'cassettes'
CHAT_KEY = 'e2e-chat-key'
ALL_INTERFACES = '0.0.0.0'  # noqa: S104  # nosec B104 - only on Linux, where containers reach the host's bridge
ARTIFACTS = Path('.e2e-artifacts')
FAILED = pytest.StashKey[bool]()


@dataclass
class Deployment:
    """A provisioned org and the client that drives it."""

    project: Project
    endpoints: Endpoints
    client: OrgClient


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the target, model mode and scenario options."""
    group = parser.getgroup('e2e')
    group.addoption('--target', default='local-process', help=f'One of {", ".join(TARGETS)}.')
    group.addoption('--model-mode', default='replay', help=f'One of {", ".join(MODEL_MODES)}.')
    group.addoption('--scenario', default=None, help='Run only this scenario, such as support-desk.')


def pytest_configure(config: pytest.Config) -> None:
    """Reject an unknown target or model mode before anything is provisioned."""
    config.addinivalue_line('markers', 'max_usd(amount): the live-mode budget of a scenario, 1.0 by default')
    target, mode = config.getoption('--target'), config.getoption('--model-mode')
    if target not in TARGETS:
        msg = f'Unknown --target {target!r}; choose one of {", ".join(TARGETS)}.'
        raise pytest.UsageError(msg)
    if mode not in MODEL_MODES:
        msg = f'Unknown --model-mode {mode!r}; choose one of {", ".join(MODEL_MODES)}.'
        raise pytest.UsageError(msg)
    if mode != 'replay' and not os.environ.get('ANTHROPIC_API_KEY'):
        msg = f'--model-mode {mode} calls the real API and needs ANTHROPIC_API_KEY.'
        raise pytest.UsageError(msg)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep only the requested scenario when `--scenario` is given."""
    scenario = config.getoption('--scenario')
    if scenario is None:
        return
    wanted = f'test_{scenario.replace("-", "_")}.py'
    kept = [item for item in items if item.path.name == wanted or item.path.parent.name == 'harness']
    config.hook.pytest_deselected(items=[item for item in items if item not in kept])
    items[:] = kept


def pytest_collection_finish(session: pytest.Session) -> None:
    """Fail before provisioning when local scenarios are collected without a Docker daemon."""
    scenarios = [item for item in session.items if item.path.parent.name == 'scenarios']
    if scenarios and session.config.getoption('--target') != 'cloud':
        try:
            require_docker()
        except RuntimeError as error:
            raise pytest.UsageError(str(error)) from error


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Generator[None, Any, Any]:
    """Remember whether any phase of a test failed, so teardown can save artifacts."""
    report = yield
    if report.failed:
        item.stash[FAILED] = True
    del call
    return report


@pytest.fixture(scope='session', autouse=True)
def fresh_cli_config(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Give the Claude Code CLI an empty config, as in a container.

    The developer's own settings and cached feature flags then never change what the agents send.
    """
    previous = os.environ.get('CLAUDE_CONFIG_DIR')
    os.environ['CLAUDE_CONFIG_DIR'] = str(tmp_path_factory.mktemp('claude-config'))
    yield
    if previous is None:
        os.environ.pop('CLAUDE_CONFIG_DIR', None)
    else:
        os.environ['CLAUDE_CONFIG_DIR'] = previous


@pytest.fixture(scope='session')
def run_id() -> str:
    """Return the id that names this run's artifacts and cloud resources."""
    return os.environ.get('E2E_RUN_ID') or f'{time.strftime("%Y%m%d%H%M%S")}-{secrets.token_hex(3)}'


@pytest.fixture(scope='module')
def model_api(request: pytest.FixtureRequest) -> Iterator[MockAnthropic]:
    """Serve the scenario's cassettes, or proxy to the real API in record and live modes."""
    scenario = request.path.stem.removeprefix('test_').replace('_', '-')
    mock = MockAnthropic(
        CASSETTES / scenario,
        mode=request.config.getoption('--model-mode'),
        api_key=os.environ.get('ANTHROPIC_API_KEY', ''),
    )
    # Docker Desktop forwards host.docker.internal to the host's loopback; Linux containers need a wider bind.
    containers = request.config.getoption('--target') == 'local-docker' and sys.platform == 'linux'
    with serve(mock, free_port(), ALL_INTERFACES if containers else '127.0.0.1'):
        yield mock


def _model_env(mock: MockAnthropic) -> dict[str, str]:
    return {
        'ANTHROPIC_BASE_URL': mock.url,
        'ANTHROPIC_API_KEY': 'e2e-mock',
        'CHAT_API_KEY': CHAT_KEY,
        'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
        'DISABLE_TELEMETRY': '1',
        'DISABLE_AUTOUPDATER': '1',
    }


def _save_artifacts(
    into: Path,
    project: Project | None,
    target: Target,
    client: OrgClient | None,
    mock: MockAnthropic,
) -> None:
    into.mkdir(parents=True, exist_ok=True)
    if project is not None:
        shutil.copytree(
            project.root,
            into / 'project',
            ignore=shutil.ignore_patterns('node_modules', '.venv'),
            dirs_exist_ok=True,
        )
    target.collect_logs(into / 'logs')
    if client is not None:
        try:
            runs = [client.run(run['id']) for run in client.runs(limit='1000')]
            (into / 'runs.json').write_text(json.dumps(runs, indent=2, default=str))
        except Exception as error:  # noqa: BLE001 - the node may be the thing that failed
            (into / 'runs.json').write_text(json.dumps({'error': str(error)}))
    (into / 'model-misses.txt').write_text('\n'.join(mock.misses))
    for digest, canonical in mock.missed.items():
        (into / 'model-misses').mkdir(exist_ok=True)
        (into / 'model-misses' / f'{digest}.json').write_text(json.dumps(json.loads(canonical), indent=2) + '\n')


def _watch_budget(client: OrgClient, max_usd: float, exceeded: list[float], stop: threading.Event) -> None:
    while not stop.wait(5):
        spent = client.spent()
        if spent > max_usd:
            exceeded.append(spent)
            client.transition('paused', f'e2e budget of ${max_usd} exceeded')
            return


@pytest.fixture
def deploy(
    request: pytest.FixtureRequest,
    run_id: str,
    model_api: MockAnthropic,
    tmp_path: Path,
) -> Iterator[Callable[..., Deployment]]:
    """Return a function that renders, provisions and health-checks a spec, with teardown guaranteed."""
    target = make_target(request.config.getoption('--target'), run_id)
    state: dict[str, Any] = {'project': None, 'client': None}
    stop, exceeded = threading.Event(), list[float]()
    marker = request.node.get_closest_marker('max_usd')
    max_usd = float(marker.args[0]) if marker else 1.0

    def _deploy(
        spec: Spec | Path,
        env: dict[str, str] | None = None,
        *,
        ui: bool = False,
        chat: bool = False,
    ) -> Deployment:
        spec_path = spec if isinstance(spec, Path) else tmp_path / 'spec.py'
        if isinstance(spec, Spec):
            write_spec(spec, spec_path)
        org = runpy.run_path(str(spec_path))['spec'].org
        root = tmp_path / org.slug
        render(spec_path, root)
        state['project'] = project = Project(root, org.package_name, org.slug)
        endpoints = target.provision(project, {**_model_env(model_api), **(env or {})}, ui=ui, chat=chat)
        state['client'] = client = OrgClient(endpoints.api, CHAT_KEY)
        if model_api.mode == 'live':
            threading.Thread(target=_watch_budget, args=(client, max_usd, exceeded, stop), daemon=True).start()
        return Deployment(project, endpoints, client)

    try:
        yield _deploy
    finally:
        stop.set()
        if request.node.stash.get(FAILED, False) or model_api.misses or exceeded:
            _save_artifacts(
                ARTIFACTS / run_id / request.node.name,
                state['project'],
                target,
                state['client'],
                model_api,
            )
        target.teardown()
    if exceeded:
        pytest.fail(f'budget: the scenario spent ${exceeded[0]:.2f}, over its max_usd of ${max_usd:.2f}.')
    if model_api.misses:
        pytest.fail('Missing recordings, re-run with --model-mode record:\n' + '\n'.join(model_api.misses))
