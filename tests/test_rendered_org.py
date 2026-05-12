"""End-to-end functional test — run the rendered `org` fixture's own pytest suite via uv.

Closes the loop between renderer and runtime: byte-identity says the rendered code matches
the snapshot; this test confirms the snapshot actually imports, factories build, instructions
compose, and pytest exits 0 — i.e. the renderer produces *working* code, not just consistent
text.

Scope today: only the always-on subset (factories, instructions). Route and knowledge tests
ship with the rendered org but are not exercised here because:
  - they require `GOOGLE_API_KEY` for the embedder, and
  - the rendered SQL (CREATE TABLE / queries) is Postgres-flavoured (JSONB, SERIAL,
    TIMESTAMPTZ, gin indexes); SQLite local mode fails at app boot. A dialect-aware
    rewrite of `db/tables.py.jinja` and the route SQL is a separate piece of work; until
    then the embedder-gated tests are best run against the docker fixture.

Slow on cold runs (`uv sync` pulls agno + fastapi + sqlalchemy + chromadb). The
session-scoped fixture syncs once.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ORG_OUTPUT = Path(__file__).parent / 'fixtures' / 'org' / 'output'
ALWAYS_ON_TESTS = ('tests/test_factories.py', 'tests/test_instructions.py')


def _uv_available() -> bool:
    return shutil.which('uv') is not None


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


def test_rendered_factories_and_instructions_pass(synced_org: Path) -> None:
    """Run the rendered org's always-on tests via its own pytest. Exit code 0 = renderer is healthy."""
    result = subprocess.run(  # noqa: S603
        ['uv', 'run', '--quiet', 'pytest', '-q', '--no-header', '--no-cov', *ALWAYS_ON_TESTS],  # noqa: S607
        cwd=str(synced_org),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f'rendered org tests failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}'
