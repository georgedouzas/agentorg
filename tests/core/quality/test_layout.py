"""Tests for the layout module."""

from pathlib import Path

from agentorg.core.quality import find_layout_violations


def _write(root: Path, *paths: str, content: str = '"""Module."""\n') -> None:
    for path in paths:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def _project(root: Path, pyproject: str = '') -> Path:
    _write(root, 'src/pkg/__init__.py', 'tests/__init__.py')
    (root / 'pyproject.toml').write_text(pyproject)
    return root


def test_find_layout_violations_accepts_mirrored_private_module(tmp_path: Path) -> None:
    """A private module with its test at the mirrored path passes."""
    root = _project(tmp_path)
    _write(root, 'src/pkg/ops/_scheduler.py', 'tests/ops/test_scheduler.py')
    assert find_layout_violations(root) == []


def test_find_layout_violations_reports_missing_test(tmp_path: Path) -> None:
    """A module without a mirrored test file is reported with both paths."""
    root = _project(tmp_path)
    _write(root, 'src/pkg/ops/_bus.py')
    assert find_layout_violations(root) == ['src/pkg/ops/_bus.py has no test file tests/ops/test_bus.py']


def test_find_layout_violations_reports_orphan_test(tmp_path: Path) -> None:
    """A test file whose module was renamed is reported as an orphan."""
    root = _project(tmp_path)
    _write(root, 'src/pkg/_new_name.py', 'tests/test_new_name.py', 'tests/test_old_name.py')
    assert find_layout_violations(root) == ['tests/test_old_name.py has no source module in src/pkg']


def test_find_layout_violations_reports_public_private_twin(tmp_path: Path) -> None:
    """A public and a private module with the same name are ambiguous."""
    root = _project(tmp_path)
    _write(root, 'src/pkg/_scheduler.py', 'src/pkg/scheduler.py', 'tests/test_scheduler.py')
    assert find_layout_violations(root) == [
        'src/pkg/_scheduler.py and src/pkg/scheduler.py both map to tests/test_scheduler.py',
    ]


def test_find_layout_violations_honours_declared_exemption(tmp_path: Path) -> None:
    """A module listed under `exempt` needs no test file."""
    root = _project(tmp_path, '[tool.agentorg.test-layout]\nexempt = ["src/pkg/_config.py"]\n')
    _write(root, 'src/pkg/_config.py')
    assert find_layout_violations(root) == []


def test_find_layout_violations_reports_stale_exemption(tmp_path: Path) -> None:
    """An exempt entry naming a missing path is reported."""
    root = _project(tmp_path, '[tool.agentorg.test-layout]\nexempt = ["src/pkg/_gone.py"]\n')
    assert find_layout_violations(root) == ['exempt entry src/pkg/_gone.py does not exist']


def test_find_layout_violations_requires_test_for_init_with_logic(tmp_path: Path) -> None:
    """An `__init__.py` that defines a function needs `test_init.py`."""
    root = _project(tmp_path)
    _write(root, 'src/pkg/ops/__init__.py', content='"""Ops."""\n\n\ndef run() -> None:\n    """Run."""\n')
    assert find_layout_violations(root) == ['src/pkg/ops/__init__.py has no test file tests/ops/test_init.py']


def test_find_layout_violations_skips_reexport_only_init(tmp_path: Path) -> None:
    """An `__init__.py` holding only imports, `__all__` and type aliases needs no test."""
    root = _project(tmp_path)
    init = '"""Ops."""\n\nfrom typing import TypeAlias\n\nfrom ._a import a\n\nA: TypeAlias = int\n__all__ = ["a"]\n'
    _write(root, 'src/pkg/ops/__init__.py', content=init)
    _write(root, 'src/pkg/ops/_a.py', 'tests/ops/test_a.py')
    assert find_layout_violations(root) == []


def test_find_layout_violations_skips_template_and_unmirrored_dirs(tmp_path: Path) -> None:
    """Modules under non-identifier directories and tests under `e2e` or `fixtures` are skipped."""
    root = _project(tmp_path)
    _write(root, 'src/pkg/templates/{{ name }}/cli.py', 'tests/e2e/test_golden.py', 'tests/fixtures/test_data.py')
    assert find_layout_violations(root) == []


def test_find_layout_violations_uses_configured_roots(tmp_path: Path) -> None:
    """Configured roots map each source directory to its own tests directory."""
    roots = '[tool.agentorg.test-layout.roots]\n"src/pkg" = "tests"\n"scripts" = "tests/scripts"\n'
    root = _project(tmp_path, roots)
    _write(root, 'scripts/check.py', 'tests/scripts/test_check.py')
    assert find_layout_violations(root) == []
