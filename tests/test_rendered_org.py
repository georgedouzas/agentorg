"""End-to-end functional test — run the rendered `org` fixture's own pytest suite via uv.

Closes the loop between renderer and runtime: byte-identity says the rendered code matches the snapshot; this test
confirms the snapshot actually imports, factories build, instructions compose, routes respond, knowledge round-trips
against the local SQLite + Chroma store, and pytest exits 0 — i.e. the renderer produces *working* code, not just
consistent text.

Loads secrets from `tests/fixtures/.env` (the central .env we share across local fixtures) so `GOOGLE_API_KEY` is
available to the rendered app's embedder.

Slow on cold runs (`uv sync` pulls agno + fastapi + sqlalchemy + chromadb).
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / 'fixtures'
ORG_OUTPUT = FIXTURES_DIR / 'org' / 'output'
CENTRAL_ENV = FIXTURES_DIR / '.env'
RENDERED_TESTS = (
    'tests/test_factories.py',
    'tests/test_instructions.py',
    'tests/test_routes.py',
    'tests/test_knowledge.py',
)


def _uv_available() -> bool:
    return shutil.which('uv') is not None


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse a dotenv file into a plain dict.

    Strips quotes from values.
    """
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


@pytest.fixture(scope='session')
def synced_org() -> Path:
    """Sync the rendered org's deps once per session."""
    if not _uv_available():
        pytest.skip('uv not on PATH; cannot exercise the rendered org.')
    if not (ORG_OUTPUT / 'pyproject.toml').exists():
        pytest.skip(f'No rendered org snapshot at {ORG_OUTPUT}.')
    result = subprocess.run(
        ['uv', 'sync', '--quiet'],  # noqa: S607
        cwd=str(ORG_OUTPUT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f'uv sync of rendered org failed: {result.stderr.strip()[:500]}')
    return ORG_OUTPUT


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
