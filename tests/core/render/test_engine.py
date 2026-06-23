"""Tests for engine module."""

from pathlib import Path
from typing import Any

import pytest

from agentorg.core.render import render_tree


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def walker_data() -> dict[str, Any]:
    """Minimal data dict the walker needs - just what tests reference inside Jinja."""
    return {'org': {'package_name': 'acme', 'visibility': 'private'}}


def test_verbatim_file_is_copied_unchanged(tmp_path: Path, walker_data: dict[str, Any]) -> None:
    """Files without a `.jinja` suffix go through `shutil.copy` verbatim."""
    template, output = tmp_path / 'template', tmp_path / 'output'
    _write(template / 'README.md', '# hello')
    render_tree(template, output, walker_data)
    assert (output / 'README.md').read_text() == '# hello'


def test_jinja_suffix_stripped_and_content_rendered(tmp_path: Path, walker_data: dict[str, Any]) -> None:
    """A `.jinja`-suffixed file is rendered through Jinja and the suffix is stripped."""
    template, output = tmp_path / 'template', tmp_path / 'output'
    _write(template / 'greeting.txt.jinja', 'Hi {{ org.package_name }}.')
    render_tree(template, output, walker_data)
    assert not (output / 'greeting.txt.jinja').exists()
    assert (output / 'greeting.txt').read_text() == 'Hi acme.'


def test_jinja_var_in_directory_name_is_substituted(tmp_path: Path, walker_data: dict[str, Any]) -> None:
    """A `{{ var }}` in a path segment resolves to the substituted value at render time."""
    template, output = tmp_path / 'template', tmp_path / 'output'
    _write(template / 'src' / '{{ org.package_name }}' / 'mod.py', 'pass')
    render_tree(template, output, walker_data)
    assert (output / 'src' / 'acme' / 'mod.py').read_text() == 'pass'
    assert not (output / 'src' / '{{ org.package_name }}').exists()


def test_conditional_file_skipped_when_condition_is_false(tmp_path: Path, walker_data: dict[str, Any]) -> None:
    """An empty rendered name produces no output file."""
    template, output = tmp_path / 'template', tmp_path / 'output'
    name = "{% if org.visibility == 'public' %}LICENSE{% endif %}.jinja"
    _write(template / name, 'MIT...')
    render_tree(template, output, walker_data)
    assert not (output / 'LICENSE').exists()
    assert not (output / '.jinja').exists()


def test_conditional_file_kept_when_condition_is_true(tmp_path: Path) -> None:
    """The same conditional, condition true, lands with the suffix stripped."""
    template, output = tmp_path / 'template', tmp_path / 'output'
    name = "{% if org.visibility == 'public' %}LICENSE{% endif %}.jinja"
    _write(template / name, 'MIT...')
    render_tree(template, output, {'org': {'visibility': 'public'}})
    assert (output / 'LICENSE').read_text() == 'MIT...'


def test_jinja_braces_in_verbatim_file_are_left_alone(tmp_path: Path, walker_data: dict[str, Any]) -> None:
    """Files without a `.jinja` suffix are copied byte-for-byte even with `{{` inside."""
    template, output = tmp_path / 'template', tmp_path / 'output'
    jsx = "const x = <div style={{color: 'red'}} />;"
    _write(template / 'App.tsx', jsx)
    render_tree(template, output, walker_data)
    assert (output / 'App.tsx').read_text() == jsx
