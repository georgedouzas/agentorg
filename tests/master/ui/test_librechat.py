"""Tests for the librechat module."""

import subprocess  # nosec B404 - only builds CompletedProcess fakes
from pathlib import Path

import pytest
import yaml

from agentorg.master.ui import COMPOSE, LIBRECHAT_IMAGE, LibreChatStack, docker_available, librechat_config


def _done(code: int = 0, stderr: str = '') -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, '', stderr)


def test_config_offers_the_interview_and_the_preview() -> None:
    """The master endpoint serves agentorg; the preview endpoint lists the node's agents."""
    config = librechat_config(8765, 8766)
    master, preview = config['endpoints']['custom']
    assert (master['name'], master['models']) == ('AgentOrg', {'default': ['agentorg'], 'fetch': False})
    assert master['baseURL'] == 'http://host.docker.internal:8765/v1'
    assert (preview['baseURL'], preview['models']['fetch']) == ('http://host.docker.internal:8766/v1', True)
    assert preview['headers']['X-Agentorg-User-Email'] == '{{LIBRECHAT_USER_EMAIL}}'
    assert config['interface']['agents'] is False
    assert config['interface']['mcpServers'] == {'use': False, 'create': False}


def test_prepare_writes_files_and_keeps_secrets(tmp_path: Path) -> None:
    """Preparing twice writes the stack files and keeps the first secrets."""
    stack = LibreChatStack(tmp_path)
    stack.prepare(8765, 8766)
    key = stack.chat_api_key
    stack.prepare(9000, 9001)
    env = (tmp_path / '.env').read_text()
    assert stack.chat_api_key == key
    assert len(key) == 64
    assert f'LIBRECHAT_IMAGE={LIBRECHAT_IMAGE}' in env
    assert (tmp_path / '.env').stat().st_mode & 0o777 == 0o600
    assert 'host.docker.internal:9001' in (tmp_path / 'librechat.yaml').read_text()
    assert (tmp_path / 'compose.yaml').read_text() == COMPOSE.read_text()


def test_compose_runs_librechat_mongodb_and_meilisearch() -> None:
    """The shipped compose file runs the three services from the pinned image variable."""
    services = yaml.safe_load(COMPOSE.read_text())['services']
    assert set(services) == {'librechat', 'mongodb', 'meilisearch'}
    assert services['librechat']['image'] == '${LIBRECHAT_IMAGE}'
    assert 'ENDPOINTS=custom' in services['librechat']['environment']


def test_up_and_down_run_compose(tmp_path: Path) -> None:
    """Up and down run docker compose on the stack's file; a failure raises with its stderr."""
    calls: list[list[str]] = []

    def record(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return _done()

    stack = LibreChatStack(tmp_path)
    stack.up(run=record)
    stack.down(run=record)
    assert [call[4:] for call in calls] == [['up', '-d'], ['down']]
    assert calls[0][:4] == ['docker', 'compose', '-f', str(tmp_path / 'compose.yaml')]
    with pytest.raises(RuntimeError, match='port is taken'):
        stack.up(run=lambda _args: _done(1, 'port is taken'))


def test_docker_available_checks_the_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Docker counts as available only when the binary exists and `docker info` succeeds."""
    monkeypatch.setattr('shutil.which', lambda _name: '/usr/bin/docker')
    assert docker_available(lambda _args: _done()) is True
    assert docker_available(lambda _args: _done(1)) is False
    monkeypatch.setattr('shutil.which', lambda _name: None)
    assert docker_available(lambda _args: _done()) is False


def test_pinned_image_matches_rendered_orgs() -> None:
    """The master and rendered orgs use the same LibreChat image."""
    template = Path(__file__).parents[3] / 'src/agentorg/core/render/templates/full'
    compose = next(template.glob('*compose.yaml*.jinja')).read_text()
    assert f'image: {LIBRECHAT_IMAGE}' in compose
