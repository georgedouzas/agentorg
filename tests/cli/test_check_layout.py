"""Tests for the check_layout module."""

from pathlib import Path

from click.testing import CliRunner

from agentorg.cli import check_layout


def _write(root: Path, *paths: str) -> None:
    for path in paths:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('"""Module."""\n')


def test_check_layout_passes_on_mirrored_project(tmp_path: Path) -> None:
    """A mirrored project exits 0 and reports OK."""
    _write(tmp_path, 'src/pkg/__init__.py', 'src/pkg/_a.py', 'tests/test_a.py')
    result = CliRunner().invoke(check_layout, [str(tmp_path)])
    assert result.exit_code == 0
    assert 'Test layout OK' in result.output


def test_check_layout_fails_listing_violations(tmp_path: Path) -> None:
    """A missing test file exits non-zero and names the paths."""
    _write(tmp_path, 'src/pkg/__init__.py', 'src/pkg/_a.py')
    result = CliRunner().invoke(check_layout, [str(tmp_path)])
    assert result.exit_code == 1
    assert 'src/pkg/_a.py has no test file tests/test_a.py' in result.output
    assert '1 test layout violation(s)' in result.output
