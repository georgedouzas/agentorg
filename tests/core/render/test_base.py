"""Tests for base module."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from agentorg.core import render


@pytest.fixture
def write_spec_py(spec_dict_minimal: dict[str, Any]) -> Callable[..., Path]:
    """Factory: writes a minimal `spec.py` into a directory and returns its path."""

    def write(spec_dir: Path, **org_overrides: object) -> Path:
        spec_dict = {**spec_dict_minimal, 'org': {**spec_dict_minimal['org'], **org_overrides}}
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_py = spec_dir / 'spec.py'
        spec_py.write_text(f'from agentorg.core.spec import Spec\nspec = Spec.model_validate({spec_dict!r})\n')
        return spec_py

    return write


@pytest.mark.parametrize(
    ('template', 'must_contain'),
    [
        ('full', ['pyproject.toml', 'src/acme/spec.py', 'src/frontend/package.json']),
        ('frontend', ['package.json', 'vite.config.ts', 'src/App.tsx']),
        ('backend', ['pyproject.toml', 'src/acme/spec.py', 'src/acme/app/main.py', 'tests/test_routes.py']),
        ('ai', ['pyproject.toml', 'src/acme/spec.py', 'src/acme/sandbox.py', 'src/acme/ai/__init__.py']),
    ],
)
def test_each_shipped_template_renders(
    write_spec_py: Callable[..., Path],
    tmp_path: Path,
    template: str,
    must_contain: list[str],
) -> None:
    """Each shipped template renders against a minimal spec and produces its signature files."""
    spec_py = write_spec_py(tmp_path / 'spec')
    output = tmp_path / 'out'
    render(spec_py, output, template=template)
    for relpath in must_contain:
        assert (output / relpath).exists(), f'{template}: expected {relpath} to exist'


def test_spec_py_is_copied_into_rendered_package(write_spec_py: Callable[..., Path], tmp_path: Path) -> None:
    """The user's `spec.py` ends up at `<output>/src/<package>/spec.py` for runtime import."""
    spec_py = write_spec_py(tmp_path / 'spec')
    output = tmp_path / 'out'
    render(spec_py, output, template='full')
    copied = output / 'src' / 'acme' / 'spec.py'
    assert copied.exists()
    assert copied.read_text() == spec_py.read_text()
