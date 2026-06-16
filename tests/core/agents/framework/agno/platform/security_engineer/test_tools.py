"""Tests for the tools module."""

from pathlib import Path

import pytest

from agentorg.core.agents.framework.agno.platform.security_engineer import (
    list_required_env_vars,
    scan_secrets,
)


def test_scan_secrets_returns_clean_message_for_unsuspicious_code(tmp_path: Path):
    """A directory of innocuous Python returns the clean message — no false positives."""
    (tmp_path / 'app.py').write_text('def add(a, b):\n    return a + b\n')
    (tmp_path / 'config.py').write_text("VERSION = '1.0.0'\n")
    assert scan_secrets(str(tmp_path)) == 'No likely secrets found.'


def test_scan_secrets_flags_aws_access_key(tmp_path: Path):
    """An AWS access-key pattern is reported with file:line and the matching regex."""
    secret = 'AKIA' + 'A' * 16  # synthetic, matches the pattern
    (tmp_path / 'leak.py').write_text(f'AWS_ACCESS_KEY = {secret!r}\n')
    result = scan_secrets(str(tmp_path))
    assert result.startswith('Likely hardcoded secrets:')
    assert 'leak.py:1' in result


def test_scan_secrets_flags_github_token(tmp_path: Path):
    """A `ghp_*` GitHub PAT is detected by the dedicated pattern."""
    token = 'ghp_' + 'a' * 36
    (tmp_path / 'gh.py').write_text(f'GH_TOKEN = {token!r}\n')
    result = scan_secrets(str(tmp_path))
    assert 'Likely hardcoded secrets:' in result
    assert 'gh.py' in result


def test_scan_secrets_reports_missing_directory():
    """A nonexistent scan dir produces a clear no-directory message."""
    result = scan_secrets('/nonexistent/path/that/definitely/does/not/exist')
    assert result == 'No directory at /nonexistent/path/that/definitely/does/not/exist.'


def test_scan_secrets_recurses_into_subdirectories(tmp_path: Path):
    """Secrets in nested folders are found — `rglob` reaches every depth."""
    nested = tmp_path / 'deep' / 'inner'
    nested.mkdir(parents=True)
    token = 'ghp_' + 'b' * 36
    (nested / 'leak.py').write_text(f'TOKEN = {token!r}\n')
    result = scan_secrets(str(tmp_path))
    assert 'inner/leak.py' in result


def test_list_required_env_vars_returns_empty_message_when_none_declared():
    """No declared vars → no listing, just the empty-state message."""
    assert list_required_env_vars() == 'No required env vars declared.'
    assert list_required_env_vars([]) == 'No required env vars declared.'
    assert list_required_env_vars(None) == 'No required env vars declared.'


def test_list_required_env_vars_marks_each_var_set_or_missing(monkeypatch: pytest.MonkeyPatch):
    """Each declared var is annotated with `set` or `MISSING` based on the current environment."""
    monkeypatch.setenv('GOOGLE_API_KEY', 'sk-test')
    monkeypatch.delenv('SOME_UNSET_VAR', raising=False)
    result = list_required_env_vars(['GOOGLE_API_KEY', 'SOME_UNSET_VAR'])
    assert 'Required env vars:' in result
    assert '[set]' in result
    assert '[MISSING]' in result
    # The marker for each variable is on its line.
    assert 'GOOGLE_API_KEY' in result.split('[set]', 1)[0]
    assert 'SOME_UNSET_VAR' in result.split('[MISSING]', 1)[0]
