"""Shared fixtures - reset the master agent's state before each test so order doesn't matter."""

import pytest

from agentorg.master import reset_state


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Reset the singleton interview state at the start of every test."""
    reset_state()
