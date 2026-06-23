"""Tests for base module."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from agentorg.core import render


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Three empty dirs under tmp_path: (template, spec, output)."""
    template = tmp_path / 'template'
    spec_dir = tmp_path / 'spec'
    output = tmp_path / 'output'
    template.mkdir()
    spec_dir.mkdir()
    return template, spec_dir, output


@pytest.fixture
def write_spec_py(spec_dict_minimal: dict[str, Any]) -> Callable[..., None]:
    """Factory that writes a minimal `spec.py` into a directory, with optional org overrides."""

    def write(spec_dir: Path, **org_overrides: object) -> None:
        spec_dict = {**spec_dict_minimal, 'org': {**spec_dict_minimal['org'], **org_overrides}}
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / 'spec.py').write_text(
            f'from agentorg.core.spec import Spec\nspec = Spec.model_validate({spec_dict!r})\n',
        )

    return write


def test_verbatim_file_is_copied_unchanged(
    workspace: tuple[Path, Path, Path],
    write_spec_py: Callable[..., None],
) -> None:
    """Files without a `.jinja` suffix go through `shutil.copy` verbatim."""
    template, spec_dir, output = workspace
    _write(template / 'README.md', '# hello')
    write_spec_py(spec_dir)
    render(spec_dir / 'spec.py', output, template_dir=template)
    assert (output / 'README.md').read_text() == '# hello'


def test_jinja_suffix_stripped_and_content_rendered(
    workspace: tuple[Path, Path, Path],
    write_spec_py: Callable[..., None],
) -> None:
    """A `.jinja`-suffixed file is rendered through Jinja and the suffix is stripped."""
    template, spec_dir, output = workspace
    _write(template / 'greeting.txt.jinja', 'Hi {{ org.package_name }}.')
    write_spec_py(spec_dir)
    render(spec_dir / 'spec.py', output, template_dir=template)
    assert not (output / 'greeting.txt.jinja').exists()
    assert (output / 'greeting.txt').read_text() == 'Hi acme.'


def test_jinja_var_in_directory_name_is_substituted(
    workspace: tuple[Path, Path, Path],
    write_spec_py: Callable[..., None],
) -> None:
    """A `{{ var }}` in a path segment resolves to the substituted value at render time."""
    template, spec_dir, output = workspace
    _write(template / 'src' / '{{ org.package_name }}' / 'mod.py', 'pass')
    write_spec_py(spec_dir)
    render(spec_dir / 'spec.py', output, template_dir=template)
    assert (output / 'src' / 'acme' / 'mod.py').read_text() == 'pass'
    assert not (output / 'src' / '{{ org.package_name }}').exists()


def test_conditional_file_skipped_when_condition_is_false(
    workspace: tuple[Path, Path, Path],
    write_spec_py: Callable[..., None],
) -> None:
    """An empty rendered name produces no output file."""
    template, spec_dir, output = workspace
    name = "{% if org.visibility == 'public' %}LICENSE{% endif %}.jinja"
    _write(template / name, 'MIT...')
    write_spec_py(spec_dir, visibility='private')
    render(spec_dir / 'spec.py', output, template_dir=template)
    assert not (output / 'LICENSE').exists()
    assert not (output / '.jinja').exists()


def test_conditional_file_kept_when_condition_is_true(
    workspace: tuple[Path, Path, Path],
    write_spec_py: Callable[..., None],
) -> None:
    """The same conditional, condition true, lands with the suffix stripped."""
    template, spec_dir, output = workspace
    name = "{% if org.visibility == 'public' %}LICENSE{% endif %}.jinja"
    _write(template / name, 'MIT...')
    write_spec_py(spec_dir, visibility='public')
    render(spec_dir / 'spec.py', output, template_dir=template)
    assert (output / 'LICENSE').read_text() == 'MIT...'


def test_jinja_braces_in_verbatim_file_are_left_alone(
    workspace: tuple[Path, Path, Path],
    write_spec_py: Callable[..., None],
) -> None:
    """Files without a `.jinja` suffix are copied byte-for-byte even with `{{` inside."""
    template, spec_dir, output = workspace
    jsx = "const x = <div style={{color: 'red'}} />;"
    _write(template / 'App.tsx', jsx)
    write_spec_py(spec_dir)
    render(spec_dir / 'spec.py', output, template_dir=template)
    assert (output / 'App.tsx').read_text() == jsx


def test_spec_py_is_copied_into_rendered_package(
    workspace: tuple[Path, Path, Path],
    write_spec_py: Callable[..., None],
) -> None:
    """`spec.py` is copied to `<output>/src/<package>/spec.py`."""
    template, spec_dir, output = workspace
    _write(template / 'src' / '{{ org.package_name }}' / '__init__.py', '"""acme"""')
    write_spec_py(spec_dir)
    render(spec_dir / 'spec.py', output, template_dir=template)
    copied = output / 'src' / 'acme' / 'spec.py'
    assert copied.exists()
    assert copied.read_text() == (spec_dir / 'spec.py').read_text()


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
    write_spec_py: Callable[..., None],
    tmp_path: Path,
    template: str,
    must_contain: list[str],
) -> None:
    """Each shipped template renders against a minimal spec and produces its signature files."""
    spec_dir = tmp_path / 'spec'
    output = tmp_path / 'out'
    write_spec_py(spec_dir)
    render(spec_dir / 'spec.py', output, template=template)
    for relpath in must_contain:
        assert (output / relpath).exists(), f'{template}: expected {relpath} to exist'
