"""Tests for base module."""

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from agentorg.core import render

FIXTURES_DIR = Path(__file__).parents[2] / 'fixtures'
FIXTURES = ['org']
CENTRAL_ENV = FIXTURES_DIR / '.env'
RENDERED_TESTS = (
    'tests/test_factories.py',
    'tests/test_routes.py',
    'tests/test_knowledge.py',
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _read_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, _, value = stripped.partition('=')
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


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


@pytest.mark.parametrize('fixture_id', FIXTURES)
def test_fixture_renders_byte_identical(fixture_id: str, tmp_path: Path) -> None:
    """Rendering the committed fixture matches the snapshot byte-for-byte."""
    out = tmp_path / 'render'
    render(FIXTURES_DIR / fixture_id / 'spec.py', out)

    fixture_out = FIXTURES_DIR / fixture_id / 'output'
    mismatches: list[str] = []
    missing: list[str] = []
    for src in out.rglob('*'):
        if not src.is_file():
            continue
        rel = src.relative_to(out).as_posix()
        target = fixture_out / rel
        if not target.exists():
            missing.append(rel)
            continue
        if src.read_bytes() != target.read_bytes():
            mismatches.append(rel)
    assert not missing, f'Rendered files missing from fixture {fixture_id!r}: {missing}'
    assert not mismatches, (
        f'Rendered files differ from fixture {fixture_id!r}: {mismatches}\n'
        f'The fixture is the hand-maintained expected output. If the renderer is wrong, '
        f'fix the template; if the new output is intended, edit the fixture by hand to match.'
    )


@pytest.fixture(scope='session')
def synced_org(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Render the org fixture into a tmp dir, point its agentorg dep at this repo, then uv sync."""
    work = tmp_path_factory.mktemp('rendered-org')
    render(FIXTURES_DIR / 'org' / 'spec.py', work)
    agentorg_root = Path(__file__).parents[3]
    pyproject = work / 'pyproject.toml'
    pyproject.write_text(
        pyproject.read_text() + f'\n[tool.uv.sources]\nagentorg = {{ path = "{agentorg_root}", editable = true }}\n',
    )
    result = subprocess.run(
        ['uv', 'sync', '--quiet'],  # noqa: S607
        cwd=str(work),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f'uv sync of rendered org failed: {result.stderr.strip()[:500]}')
    return work


@pytest.fixture(scope='session')
def env_with_secrets() -> dict[str, str]:
    """Process env merged with secrets from `tests/fixtures/.env`."""
    return {**os.environ, **_read_env_file(CENTRAL_ENV)}


def test_rendered_tests_pass(synced_org: Path, env_with_secrets: dict[str, str]) -> None:
    """The rendered org's pytest suite exits 0."""
    result = subprocess.run(  # noqa: S603
        ['uv', 'run', '--quiet', 'pytest', '-q', '--no-header', '--no-cov', *RENDERED_TESTS],  # noqa: S607
        cwd=str(synced_org),
        capture_output=True,
        text=True,
        env=env_with_secrets,
        check=False,
    )
    assert result.returncode == 0, f'rendered org tests failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}'
