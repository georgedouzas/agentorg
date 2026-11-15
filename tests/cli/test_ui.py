"""Tests for the ui module."""

import pytest
from click.testing import CliRunner

from agentorg.cli import _ui as ui_module
from agentorg.cli import ui


def test_ui_help_documents_the_command():
    """`agentorg ui --help` exits 0 and mentions the master UI."""
    result = CliRunner().invoke(ui, ['--help'])
    assert result.exit_code == 0
    assert 'UI' in result.output or 'browser' in result.output.lower()


def test_ui_does_not_block_the_test_runner_when_serve_is_mocked(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """With `serve` and `webbrowser.open` mocked, invoking the command returns immediately."""
    calls = {'serve': 0, 'open': 0}
    monkeypatch.setattr(ui_module, 'serve', lambda **_kw: calls.__setitem__('serve', calls['serve'] + 1))
    monkeypatch.setattr('webbrowser.open', lambda *_a, **_k: calls.__setitem__('open', calls['open'] + 1))

    result = CliRunner().invoke(ui, ['--draft', str(tmp_path / 'draft.json'), '--no-open-browser', '--no-chat'])
    assert result.exit_code == 0
    assert 'AgentOrg UI:' in result.output
    assert calls['serve'] == 1


def test_ui_requires_docker_for_the_chat(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Without a Docker daemon the command stops before starting anything."""
    monkeypatch.setattr(ui_module, 'docker_available', lambda: False)
    monkeypatch.setattr(ui_module, 'serve', lambda **_kw: pytest.fail('serve must not start'))
    result = CliRunner().invoke(ui, ['--draft', str(tmp_path / 'draft.json'), '--no-open-browser'])
    assert result.exit_code != 0
    assert 'Docker is required' in result.output


def test_ui_starts_and_stops_librechat_around_the_server(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """The stack is prepared and started, the server gets its chat key, and the stack stops on exit."""
    events: list[str] = []
    served: dict[str, object] = {}
    monkeypatch.setattr(ui_module, 'docker_available', lambda: True)
    monkeypatch.setattr(ui_module.LibreChatStack, 'up', lambda _self: events.append('up'))
    monkeypatch.setattr(ui_module.LibreChatStack, 'down', lambda _self: events.append('down'))

    def serve(**kwargs: object) -> None:
        served.update(kwargs)
        events.append('serve')

    monkeypatch.setattr(ui_module, 'serve', serve)
    home = tmp_path / 'librechat'
    args = [
        '--draft',
        str(tmp_path / 'draft.json'),
        '--no-open-browser',
        '--port',
        '9000',
        '--librechat-dir',
        str(home),
    ]
    result = CliRunner().invoke(ui, args)
    assert result.exit_code == 0, result.output
    assert events == ['up', 'serve', 'down']
    assert served['chat_api_key'] == ui_module.LibreChatStack(home).chat_api_key
    assert served['chat_url'] == 'http://localhost:3080'
    assert 'host.docker.internal:9001/v1' in (home / 'librechat.yaml').read_text()
