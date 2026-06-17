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

    result = CliRunner().invoke(ui, ['--draft', str(tmp_path / 'draft.json'), '--no-open-browser'])
    assert result.exit_code == 0
    assert 'AgentOrg UI:' in result.output
    assert calls['serve'] == 1
