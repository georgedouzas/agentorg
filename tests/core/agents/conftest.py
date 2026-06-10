"""Shared fixtures for the `agentorg.core.agents` module."""

from pathlib import Path

import pytest


@pytest.fixture
def cache_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the on-disk skills cache to a temp dir so each test clones fresh and in isolation."""
    root = tmp_path / 'skills'
    monkeypatch.setattr('agentorg.core.agents.framework.agno._skills_loaders.CACHE_ROOT', root)
    return root
