"""Unit tests for `agentorg.core.render`'s path-rendering behaviour.

Each test builds a small synthetic template tree + spec on disk, runs `render()` against it with `template_dir`
injected, and asserts what landed (or didn't) in the output. Keeps fast, focused, and independent of the shipped
template.
"""

import json
from pathlib import Path

import pytest

from agentorg.core import render


def _write(path: Path, content: str = '') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Provide three empty dirs: (template, config, output) all under tmp_path."""
    template = tmp_path / 'template'
    config = tmp_path / 'config'
    output = tmp_path / 'output'
    template.mkdir()
    config.mkdir()
    return template, config, output


def _spec(config: Path, **overrides: object) -> None:
    """Write a minimal agentorg.json with `org.package_name=acme` plus any overrides."""
    data = {'org': {'package_name': 'acme', 'visibility': 'private', **overrides}}
    (config / 'agentorg.json').write_text(json.dumps(data))


def test_verbatim_file_is_copied_unchanged(workspace: tuple[Path, Path, Path]) -> None:
    """Files without a `.jinja` suffix go through `shutil.copy` verbatim."""
    template, config, output = workspace
    _write(template / 'README.md', '# hello')
    _spec(config)
    render(config, output, template_dir=template)
    assert (output / 'README.md').read_text() == '# hello'


def test_jinja_suffix_stripped_and_content_rendered(workspace: tuple[Path, Path, Path]) -> None:
    """A `.jinja`-suffixed file is rendered through Jinja and the suffix is stripped on output."""
    template, config, output = workspace
    _write(template / 'greeting.txt.jinja', 'Hi {{ org.package_name }}.')
    _spec(config)
    render(config, output, template_dir=template)
    assert not (output / 'greeting.txt.jinja').exists()
    assert (output / 'greeting.txt').read_text() == 'Hi acme.'


def test_jinja_var_in_directory_name_is_substituted(workspace: tuple[Path, Path, Path]) -> None:
    """`{{ var }}` in a path segment resolves to the substituted value at render time."""
    template, config, output = workspace
    _write(template / 'src' / '{{ org.package_name }}' / 'mod.py', 'pass')
    _spec(config)
    render(config, output, template_dir=template)
    assert (output / 'src' / 'acme' / 'mod.py').read_text() == 'pass'
    assert not (output / 'src' / '{{ org.package_name }}').exists()


def test_conditional_file_skipped_when_condition_is_false(workspace: tuple[Path, Path, Path]) -> None:
    """`{% if false %}LICENSE{% endif %}.jinja` renders to `.jinja` → empty stem → skipped."""
    template, config, output = workspace
    name = "{% if org.visibility == 'public' %}LICENSE{% endif %}.jinja"
    _write(template / name, 'MIT...')
    _spec(config, visibility='private')
    render(config, output, template_dir=template)
    assert not (output / 'LICENSE').exists()
    assert not (output / '.jinja').exists()


def test_conditional_file_kept_when_condition_is_true(workspace: tuple[Path, Path, Path]) -> None:
    """Same conditional, condition true: file lands with the `.jinja` suffix stripped."""
    template, config, output = workspace
    name = "{% if org.visibility == 'public' %}LICENSE{% endif %}.jinja"
    _write(template / name, 'MIT...')
    _spec(config, visibility='public')
    render(config, output, template_dir=template)
    assert (output / 'LICENSE').read_text() == 'MIT...'


def test_conditional_at_end_of_nested_path_skipped(workspace: tuple[Path, Path, Path]) -> None:
    """Source filename has no `.jinja` — when false, path collapses to `docs/`, skipped."""
    template, config, output = workspace
    name = "{% if org.visibility == 'public' %}code_of_conduct.md{% endif %}"
    _write(template / 'docs' / name, 'be nice')
    _spec(config, visibility='private')
    render(config, output, template_dir=template)
    assert not (output / 'docs').exists() or not list((output / 'docs').iterdir())


def test_conditional_in_filename_with_jinja_extension_only_skipped(workspace: tuple[Path, Path, Path]) -> None:
    """`dir/{% if false %}X{% endif %}.jinja` → renders to `dir/.jinja` → strip to `dir/` → skip."""
    template, config, output = workspace
    name = "{% if org.visibility == 'public' %}feed.yaml{% endif %}.jinja"
    _write(template / '.github' / name, 'content')
    _spec(config, visibility='private')
    render(config, output, template_dir=template)
    assert not (output / '.github').exists() or not list((output / '.github').iterdir())


def test_jinja_braces_in_verbatim_file_are_left_alone(workspace: tuple[Path, Path, Path]) -> None:
    """Files without `.jinja` suffix are copied byte-for-byte, even when they contain ``{{ }}``."""
    template, config, output = workspace
    jsx = "const x = <div style={{color: 'red'}} />;"
    _write(template / 'App.tsx', jsx)
    _spec(config)
    render(config, output, template_dir=template)
    assert (output / 'App.tsx').read_text() == jsx


def test_config_tools_dir_is_merged_into_rendered_package(workspace: tuple[Path, Path, Path]) -> None:
    """`config/tools/*.py` files land in `<output>/src/<pkg>/ai/tools/` alongside template-side tools."""
    template, config, output = workspace
    _write(template / 'src' / '{{ org.package_name }}' / 'ai' / 'tools' / 'knowledge.py', '# from template')
    _write(config / 'tools' / 'reports.py', '# from spec')
    _spec(config)
    render(config, output, template_dir=template)
    pkg_tools = output / 'src' / 'acme' / 'ai' / 'tools'
    assert (pkg_tools / 'knowledge.py').read_text() == '# from template'
    assert (pkg_tools / 'reports.py').read_text() == '# from spec'
