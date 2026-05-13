"""Tests for `agentorg.core.render`.

Three layers, from fastest/most-focused to slowest/most-realistic:

1. Path-rendering units — synthetic template trees in `tmp_path` exercising the renderer's
   handling of `.jinja` suffixes, conditional path segments, variable substitution, and
   the spec-file copy step.

2. Fixture byte-identity — render `tests/fixtures/<id>/spec.py` and assert every produced
   file matches the committed `output/` snapshot byte-for-byte.

3. Rendered-org functional — sync the rendered org's deps via `uv` and run *its* pytest
   suite. Secrets come from `tests/fixtures/.env`.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agentorg.core import render

FIXTURES_DIR = Path(__file__).parent.parent / 'fixtures'
FIXTURES = ['org']
ORG_OUTPUT = FIXTURES_DIR / 'org' / 'output'
CENTRAL_ENV = FIXTURES_DIR / '.env'
RENDERED_TESTS = (
    'tests/test_factories.py',
    'tests/test_instructions.py',
    'tests/test_routes.py',
    'tests/test_knowledge.py',
)


def _write(path: Path, content: str = '') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _spec_py(spec_dir: Path, **org_overrides: object) -> None:
    """Write a minimal `spec.py` with `package_name=acme` plus any org overrides."""
    overrides_kwargs = ', '.join(f'{k}={v!r}' for k, v in org_overrides.items())
    extra = (', ' + overrides_kwargs) if overrides_kwargs else ''
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / 'spec.py').write_text(
        'from agentorg.core.schema import Spec, Org\n'
        f'spec = Spec(org=Org(name="Acme", slug="acme", package_name="acme"{extra}))\n',
    )


def _uv_available() -> bool:
    return shutil.which('uv') is not None


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


# ── 1. Path-rendering unit tests ─────────────────────────────────────────────


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Provide three empty dirs: (template, spec, output) all under tmp_path."""
    template = tmp_path / 'template'
    spec_dir = tmp_path / 'spec'
    output = tmp_path / 'output'
    template.mkdir()
    spec_dir.mkdir()
    return template, spec_dir, output


def test_verbatim_file_is_copied_unchanged(workspace: tuple[Path, Path, Path]) -> None:
    """Files without a `.jinja` suffix go through `shutil.copy` verbatim."""
    template, spec_dir, output = workspace
    _write(template / 'README.md', '# hello')
    _spec_py(spec_dir)
    render(spec_dir, output, template_dir=template)
    assert (output / 'README.md').read_text() == '# hello'


def test_jinja_suffix_stripped_and_content_rendered(workspace: tuple[Path, Path, Path]) -> None:
    """A `.jinja`-suffixed file is rendered through Jinja and the suffix is stripped on output."""
    template, spec_dir, output = workspace
    _write(template / 'greeting.txt.jinja', 'Hi {{ org.package_name }}.')
    _spec_py(spec_dir)
    render(spec_dir, output, template_dir=template)
    assert not (output / 'greeting.txt.jinja').exists()
    assert (output / 'greeting.txt').read_text() == 'Hi acme.'


def test_jinja_var_in_directory_name_is_substituted(workspace: tuple[Path, Path, Path]) -> None:
    """`{{ var }}` in a path segment resolves to the substituted value at render time."""
    template, spec_dir, output = workspace
    _write(template / 'src' / '{{ org.package_name }}' / 'mod.py', 'pass')
    _spec_py(spec_dir)
    render(spec_dir, output, template_dir=template)
    assert (output / 'src' / 'acme' / 'mod.py').read_text() == 'pass'
    assert not (output / 'src' / '{{ org.package_name }}').exists()


def test_conditional_file_skipped_when_condition_is_false(workspace: tuple[Path, Path, Path]) -> None:
    """`{% if false %}LICENSE{% endif %}.jinja` renders to `.jinja` → empty stem → skipped."""
    template, spec_dir, output = workspace
    name = "{% if org.visibility == 'public' %}LICENSE{% endif %}.jinja"
    _write(template / name, 'MIT...')
    _spec_py(spec_dir, visibility='private')
    render(spec_dir, output, template_dir=template)
    assert not (output / 'LICENSE').exists()
    assert not (output / '.jinja').exists()


def test_conditional_file_kept_when_condition_is_true(workspace: tuple[Path, Path, Path]) -> None:
    """Same conditional, condition true: file lands with the `.jinja` suffix stripped."""
    template, spec_dir, output = workspace
    name = "{% if org.visibility == 'public' %}LICENSE{% endif %}.jinja"
    _write(template / name, 'MIT...')
    _spec_py(spec_dir, visibility='public')
    render(spec_dir, output, template_dir=template)
    assert (output / 'LICENSE').read_text() == 'MIT...'


def test_jinja_braces_in_verbatim_file_are_left_alone(workspace: tuple[Path, Path, Path]) -> None:
    """Files without `.jinja` suffix are copied byte-for-byte, even when they contain ``{{ }}``."""
    template, spec_dir, output = workspace
    jsx = "const x = <div style={{color: 'red'}} />;"
    _write(template / 'App.tsx', jsx)
    _spec_py(spec_dir)
    render(spec_dir, output, template_dir=template)
    assert (output / 'App.tsx').read_text() == jsx


def test_spec_py_is_copied_into_rendered_package(workspace: tuple[Path, Path, Path]) -> None:
    """`spec.py` is copied to `<output>/src/<package>/spec.py` for the runtime to import at boot."""
    template, spec_dir, output = workspace
    _write(template / 'src' / '{{ org.package_name }}' / '__init__.py', '"""acme"""')
    _spec_py(spec_dir)
    render(spec_dir, output, template_dir=template)
    copied = output / 'src' / 'acme' / 'spec.py'
    assert copied.exists()
    assert 'Spec(org=Org' in copied.read_text()


# ── 2. Fixture byte-identity ─────────────────────────────────────────────────


@pytest.mark.parametrize('fixture_id', FIXTURES)
def test_fixture_renders_byte_identical(fixture_id: str, tmp_path: Path) -> None:
    """Render the fixture and assert every produced file matches the committed snapshot."""
    out = tmp_path / 'render'
    render(FIXTURES_DIR / fixture_id, out)

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


# ── 3. Rendered-org functional test ──────────────────────────────────────────


@pytest.fixture(scope='session')
def synced_org(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Render the org into a tmp dir, point its `agentorg` dep at this repo, then `uv sync`."""
    if not _uv_available():
        pytest.skip('uv not on PATH; cannot exercise the rendered org.')
    work = tmp_path_factory.mktemp('rendered-org')
    render(FIXTURES_DIR / 'org', work)
    agentorg_root = Path(__file__).parents[2]
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
    """Merge process env with secrets from `tests/fixtures/.env`."""
    return {**os.environ, **_read_env_file(CENTRAL_ENV)}


def test_rendered_tests_pass(synced_org: Path, env_with_secrets: dict[str, str]) -> None:
    """Run the rendered org's full pytest suite. Exit code 0 = renderer is healthy end-to-end."""
    result = subprocess.run(  # noqa: S603
        ['uv', 'run', '--quiet', 'pytest', '-q', '--no-header', '--no-cov', *RENDERED_TESTS],  # noqa: S607
        cwd=str(synced_org),
        capture_output=True,
        text=True,
        env=env_with_secrets,
        check=False,
    )
    assert result.returncode == 0, f'rendered org tests failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}'
