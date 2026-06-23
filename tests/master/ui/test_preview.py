"""Tests for the preview module."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentorg.master import reset_state
from agentorg.master.ui import PreviewManager, PreviewSnapshot, build_app


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_state()


def test_snapshot_reports_idle_on_a_fresh_manager(tmp_path: Path):
    """A fresh PreviewManager reports idle status and null URLs."""
    pm = PreviewManager(cache_root=tmp_path)
    snap = pm.snapshot()
    assert isinstance(snap, PreviewSnapshot)
    assert snap.status == 'idle'
    assert snap.api_url is None
    assert snap.frontend_url is None


def test_get_api_preview_returns_disabled_when_no_preview_attached():
    """build_app without a preview manager surfaces a disabled snapshot via /api/preview."""
    app = build_app()
    client = TestClient(app)
    body = client.get('/api/preview').json()
    assert body['status'] == 'disabled'
    assert body['api_url'] is None
    assert body['frontend_url'] is None


def test_get_api_preview_reports_manager_state(tmp_path: Path):
    """When a preview manager is attached, /api/preview mirrors its snapshot."""
    pm = PreviewManager(cache_root=tmp_path)
    pm.status = 'ready'
    pm.api_port = 31231
    pm.frontend_port = 31232
    pm.slug = 'demo-org'
    app = build_app(preview=pm)
    client = TestClient(app)
    body = client.get('/api/preview').json()
    assert body['status'] == 'ready'
    assert body['api_url'] == 'http://127.0.0.1:31231'
    assert body['frontend_url'] == 'http://127.0.0.1:31232'
    assert body['slug'] == 'demo-org'


def test_boot_flips_to_error_status_when_render_fails(tmp_path: Path, monkeypatch):
    """If the render step throws, status moves to 'error' with a human-readable detail."""
    pm = PreviewManager(cache_root=tmp_path)

    def _explode(_self, _spec_path: Path) -> None:
        msg = 'render-time bug'
        raise RuntimeError(msg)

    monkeypatch.setattr(PreviewManager, '_render_to_disk', _explode)
    asyncio.run(pm.boot())
    assert pm.status == 'error'
    assert 'render-time bug' in (pm.detail or '')


def test_schedule_rerender_is_a_noop_until_status_is_ready(tmp_path: Path):
    """schedule_rerender does nothing in 'idle' / 'booting' / 'error' - prevents wasted work."""
    pm = PreviewManager(cache_root=tmp_path)
    pm.schedule_rerender()
    assert pm._re_render_task is None
    pm.status = 'error'
    pm.schedule_rerender()
    assert pm._re_render_task is None


def test_patch_pyproject_appends_local_agentorg_source(tmp_path: Path):
    """The rendered pyproject gets a `[tool.uv.sources]` block pointing at this repo.

    Required because the rendered org declares `agentorg` as a dependency, and `agentorg` is not published to PyPI.
    Without this patch `uv sync` would fail with `No solution found when resolving dependencies`.
    """
    pm = PreviewManager(cache_root=tmp_path)
    pm.work_dir = tmp_path / 'rendered'
    pm.work_dir.mkdir()
    pyproject = pm.work_dir / 'pyproject.toml'
    pyproject.write_text('[project]\nname = "demo"\nversion = "0.1.0"\n')

    pm._patch_pyproject_for_local_agentorg()

    text = pyproject.read_text()
    assert '[tool.uv.sources]' in text
    assert 'agentorg = { path = "' in text
    assert 'editable = true' in text

    # Idempotent: a second call must not duplicate the block.
    pm._patch_pyproject_for_local_agentorg()
    assert text.count('[tool.uv.sources]') == pyproject.read_text().count('[tool.uv.sources]') == 1


def test_patch_pyproject_is_noop_when_no_pyproject_present(tmp_path: Path):
    """Defensive: don't crash if the rendered tree has no pyproject (shouldn't happen, but)."""
    pm = PreviewManager(cache_root=tmp_path)
    pm.work_dir = tmp_path / 'empty'
    pm.work_dir.mkdir()
    pm._patch_pyproject_for_local_agentorg()  # must not raise
    assert not (pm.work_dir / 'pyproject.toml').exists()
