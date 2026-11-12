"""Check that the test tree mirrors the source tree."""

import ast
import tomllib
from collections.abc import Iterator
from pathlib import Path

UNMIRRORED_TEST_DIRS = frozenset({'e2e', 'fixtures'})


def _is_importable(rel: Path) -> bool:
    """Return whether every directory and the module name of `rel` are valid Python identifiers."""
    return all(part.isidentifier() for part in (*rel.parent.parts, rel.stem))


def _is_declaration(node: ast.stmt) -> bool:
    """Return whether `node` is an import, an `__all__` assignment or a type alias."""
    if isinstance(node, ast.Import | ast.ImportFrom):
        return True
    if isinstance(node, ast.Assign):
        return [getattr(target, 'id', None) for target in node.targets] == ['__all__']
    if isinstance(node, ast.AnnAssign):
        is_all = getattr(node.target, 'id', None) == '__all__'
        return is_all or getattr(node.annotation, 'id', None) == 'TypeAlias'
    return False


def _is_reexport_only(path: Path) -> bool:
    """Return whether an `__init__.py` holds only a docstring and declarations."""
    body = ast.parse(path.read_text()).body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return all(_is_declaration(node) for node in body)


def _test_path(rel: Path) -> Path:
    """Return the mirrored test file path of a module path relative to its source root."""
    name = 'init' if rel.name == '__init__.py' else rel.stem.strip('_')
    return rel.parent / f'test_{name}.py'


def _iter_modules(source_root: Path) -> Iterator[Path]:
    """Yield the importable modules under `source_root`, relative to it."""
    for path in sorted(source_root.rglob('*.py')):
        rel = path.relative_to(source_root)
        if _is_importable(rel):
            yield rel


def _iter_tests(tests_root: Path, nested_roots: list[Path]) -> Iterator[Path]:
    """Yield the mirrored test files under `tests_root`, relative to it."""
    for path in sorted(tests_root.rglob('test_*.py')):
        rel = path.relative_to(tests_root)
        if rel.parts[0] in UNMIRRORED_TEST_DIRS or not _is_importable(rel):
            continue
        if any(path.is_relative_to(nested) for nested in nested_roots):
            continue
        yield rel


def _load_config(project_root: Path) -> tuple[dict[str, str], list[str]]:
    """Return the source-to-tests roots and the exempt paths of a project."""
    pyproject = project_root / 'pyproject.toml'
    data = tomllib.loads(pyproject.read_text()) if pyproject.exists() else {}
    config = data.get('tool', {}).get('agentorg', {}).get('test-layout', {})
    packages = sorted((project_root / 'src').glob('*/__init__.py'))
    roots = config.get('roots') or {
        package.parent.relative_to(project_root).as_posix(): 'tests' for package in packages
    }
    return roots, config.get('exempt', [])


def _is_exempt(path: str, exempt: list[str]) -> bool:
    """Return whether `path` is an exempt entry or lies under one."""
    return any(path == entry or path.startswith(f'{entry.rstrip("/")}/') for entry in exempt)


def _check_root(project_root: Path, source: str, tests: str, nested_roots: list[Path], exempt: list[str]) -> list[str]:
    """Return the layout violations of one source root and its tests root."""
    source_root, tests_root = project_root / source, project_root / tests
    violations: list[str] = []
    claimed: dict[Path, Path] = {}
    for module in _iter_modules(source_root):
        test = _test_path(module)
        module_path = f'{source}/{module.as_posix()}'
        if test in claimed:
            violations.append(
                f'{source}/{claimed[test].as_posix()} and {module_path} both map to {tests}/{test.as_posix()}',
            )
            continue
        claimed[test] = module
        required = module.name != '__init__.py' or not _is_reexport_only(source_root / module)
        if required and not _is_exempt(module_path, exempt) and not (tests_root / test).exists():
            violations.append(f'{module_path} has no test file {tests}/{test.as_posix()}')
    if tests_root.exists():
        orphans = [test for test in _iter_tests(tests_root, nested_roots) if test not in claimed]
        violations.extend(f'{tests}/{test.as_posix()} has no source module in {source}' for test in orphans)
    return violations


def find_layout_violations(project_root: Path) -> list[str]:
    """Find every place where a project's test tree does not mirror its source tree.

    The roots map each source directory to its tests directory and default to `src/<package>` → `tests`. They and the
    exempt paths are read from `[tool.agentorg.test-layout]` in the project's `pyproject.toml`.

    Arguments:
        project_root: The directory holding the project's `pyproject.toml`.

    Returns:
        violations: One message per missing test file, orphan test file, ambiguous module pair or stale exemption.
    """
    roots, exempt = _load_config(project_root)
    violations = [f'exempt entry {entry} does not exist' for entry in exempt if not (project_root / entry).exists()]
    tests_dirs = [project_root / tests for tests in roots.values()]
    for source, tests in roots.items():
        tests_root = project_root / tests
        nested = [other for other in tests_dirs if other != tests_root and other.is_relative_to(tests_root)]
        violations.extend(_check_root(project_root, source, tests, nested, exempt))
    return violations
