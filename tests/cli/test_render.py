"""Tests for the render module."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from agentorg.cli import render


def test_render_dispatches_to_core_with_explicit_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """`agentorg render <spec> --output <out>` calls `core.render(spec, output)`."""
    spec = tmp_path / 'spec.py'
    spec.write_text('')
    out = tmp_path / 'rendered'
    calls: list[tuple[Path, Path]] = []
    monkeypatch.setattr('agentorg.cli._render._render', lambda s, o: calls.append((s, o)))

    result = CliRunner().invoke(render, [str(spec), '--output', str(out)])

    assert result.exit_code == 0
    assert f'Rendered into {out}' in result.output
    assert calls == [(spec, out)]


def test_render_defaults_to_cwd_spec_py(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Without a positional arg, `render` uses `./spec.py` from the current working directory."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'spec.py').write_text('')
    calls: list[tuple[Path, Path]] = []
    monkeypatch.setattr('agentorg.cli._render._render', lambda s, o: calls.append((s, o)))

    result = CliRunner().invoke(render, [])

    assert result.exit_code == 0
    assert calls[0][0] == tmp_path / 'spec.py'


def test_render_default_output_is_relative_output_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """`--output` defaults to `./output` when omitted."""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / 'spec.py'
    spec.write_text('')
    calls: list[tuple[Path, Path]] = []
    monkeypatch.setattr('agentorg.cli._render._render', lambda s, o: calls.append((s, o)))

    result = CliRunner().invoke(render, [str(spec)])

    assert result.exit_code == 0
    assert calls[0][1] == Path('output')


def test_render_raises_click_exception_when_default_spec_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Running `render` with no args and no `./spec.py` shows a friendly error, not a stack trace."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('agentorg.cli._render._render', lambda s, o: None)

    result = CliRunner().invoke(render, [])

    assert result.exit_code != 0
    assert 'No spec at' in result.output
    assert str(tmp_path / 'spec.py') in result.output


def test_render_rejects_nonexistent_explicit_spec_path(tmp_path: Path):
    """An explicit spec_path that doesn't exist is rejected by click's path validation up front."""
    result = CliRunner().invoke(render, [str(tmp_path / 'does-not-exist.py')])
    assert result.exit_code != 0
    # click's "Invalid value" message goes to stderr — in CliRunner that's mixed into .output.
    assert 'does not exist' in result.output.lower() or 'Invalid value' in result.output


def test_render_rejects_a_directory_as_spec_path(tmp_path: Path):
    """`spec_path` must be a file — passing a directory is rejected by click's `file_okay=True, dir_okay=False`."""
    sub = tmp_path / 'a-directory'
    sub.mkdir()
    result = CliRunner().invoke(render, [str(sub)])
    assert result.exit_code != 0
