"""Shared fixtures for the agents test package."""

from pathlib import Path

import pytest


@pytest.fixture
def cache_root(tmp_path: Path, monkeypatch: object) -> Path:
    """Redirect the on-disk skills cache to a temp dir so each test clones fresh and in isolation."""
    root = tmp_path / 'skills'
    monkeypatch.setattr('agentorg.core.agents.agno._skills.CACHE_ROOT', root)
    return root
