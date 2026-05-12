"""Shared test fixtures.

Sets `AGENTORG_DATA_DIR` to an ephemeral location before any application import so the
SQLite session DB and the Chroma vector store land under a temp dir and don't bleed
across runs. Provides a session-scoped `client` (TestClient bound to the rendered app)
and a `needs_google_api` fixture that skips embedder-dependent tests when the env var
isn't configured.
"""

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_DATA_DIR = Path(tempfile.mkdtemp(prefix='org-test-'))
os.environ['AGENTORG_DATA_DIR'] = str(_DATA_DIR)


@pytest.fixture(scope='session', autouse=True)
def _clean_data_dir() -> Iterator[None]:
    """Wipe the ephemeral data dir at session end."""
    yield
    shutil.rmtree(_DATA_DIR, ignore_errors=True)


@pytest.fixture(scope='session')
def client() -> Iterator[object]:
    """Return a TestClient bound to the rendered org's FastAPI app."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from org.app.main import app  # noqa: PLC0415

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope='session')
def needs_google_api() -> None:
    """Skip the test if `GOOGLE_API_KEY` is not configured (embedder calls would fail)."""
    if not os.getenv('GOOGLE_API_KEY'):
        pytest.skip('GOOGLE_API_KEY not set; skipping embedder-dependent test.')
