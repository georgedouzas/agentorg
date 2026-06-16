"""Tests for the tools module."""

import socket
from contextlib import closing

import pytest

from agentorg.core.agents.framework.agno.platform.platform_engineer import (
    check_health,
    list_env_vars,
    read_infra,
)


def test_read_infra_defaults_to_local_when_env_unset(monkeypatch: pytest.MonkeyPatch):
    """With no `AGENTORG_INFRA` set, the mode is `local` and data falls back to the default dir."""
    monkeypatch.delenv('AGENTORG_INFRA', raising=False)
    monkeypatch.delenv('AGENTORG_DATA_DIR', raising=False)
    assert read_infra() == 'infra=local\ndata=.agentorg-data'


def test_read_infra_reflects_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """`AGENTORG_INFRA` and `AGENTORG_DATA_DIR` override the defaults when in local mode."""
    monkeypatch.setenv('AGENTORG_INFRA', 'local')
    monkeypatch.setenv('AGENTORG_DATA_DIR', str(tmp_path))
    assert read_infra() == f'infra=local\ndata={tmp_path}'


def test_read_infra_marks_postgres_when_mode_is_docker(monkeypatch: pytest.MonkeyPatch):
    """In non-`local` modes, data reports as `postgres` regardless of the data-dir env var."""
    monkeypatch.setenv('AGENTORG_INFRA', 'docker')
    monkeypatch.setenv('AGENTORG_DATA_DIR', '/ignored')
    assert read_infra() == 'infra=docker\ndata=postgres'


def test_list_env_vars_reports_only_org_relevant_keys(monkeypatch: pytest.MonkeyPatch):
    """Only `AGENTORG_*`, `DB_*`, `GOOGLE_*`, and `EXA_*` env vars are surfaced; others are ignored."""
    monkeypatch.setenv('AGENTORG_TEST_VAR', '1')
    monkeypatch.setenv('GOOGLE_API_KEY', 'sk-test')
    monkeypatch.setenv('UNRELATED_LIBRARY_VAR', 'ignored')
    result = list_env_vars()
    assert 'AGENTORG_TEST_VAR=<set>' in result
    assert 'GOOGLE_API_KEY=<set>' in result
    assert 'UNRELATED_LIBRARY_VAR' not in result


def test_list_env_vars_returns_just_the_header_when_no_relevant_vars(monkeypatch: pytest.MonkeyPatch):
    """When no org-relevant vars are set, the output is just the section header."""
    for var in list(__import__('os').environ):
        if var.startswith(('AGENTORG_', 'DB_', 'GOOGLE_', 'EXA_')):
            monkeypatch.delenv(var, raising=False)
    assert list_env_vars() == 'Env vars:'


def test_check_health_returns_ok_for_a_listening_socket():
    """A live local socket returns the `OK` line with host:port."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as server:
        server.bind(('127.0.0.1', 0))  # OS-assigned port
        server.listen(1)
        port = server.getsockname()[1]
        result = check_health(host='127.0.0.1', port=port)
        assert result == f'OK: 127.0.0.1:{port} reachable.'


def test_check_health_returns_fail_when_nothing_is_listening():
    """An unbound port returns the `FAIL` line including the OSError."""
    # Port 1 is reserved and unlikely to have anything listening.
    result = check_health(host='127.0.0.1', port=1, timeout=0.1)
    assert result.startswith('FAIL: 127.0.0.1:1 unreachable ')
