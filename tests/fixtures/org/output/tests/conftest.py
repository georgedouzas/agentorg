"""Shared test fixtures for the rendered org's pytest suite."""

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio


@pytest.fixture(scope='session')
def needs_memory() -> None:
    """Skip the test unless a control plane is configured (knowledge/state can't round-trip without one)."""
    if not os.getenv('AGENTFIELD_SERVER'):
        pytest.skip('AGENTFIELD_SERVER not set; knowledge/state need an AgentField control plane.')


@pytest_asyncio.fixture(scope='session')
async def client() -> AsyncIterator[object]:
    """An async httpx client bound to the rendered node's FastAPI app."""
    from httpx import ASGITransport, AsyncClient  # noqa: PLC0415

    from org.app.main import app  # noqa: PLC0415

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as c:
        yield c


@pytest.fixture(scope='session')
def node() -> Iterator[object]:
    """The rendered node, with `Agent.get_current()` resolving to it.

    Knowledge/state tools resolve the running node via `Agent.get_current()`, which is only set inside a reasoner
    execution. This fixture patches it so the tools can be exercised directly in tests.
    """
    from agentfield import Agent  # noqa: PLC0415

    from org.app.main import app  # noqa: PLC0415

    original = Agent.get_current
    Agent.get_current = staticmethod(lambda: app)  # type: ignore[method-assign]
    yield app
    Agent.get_current = original  # type: ignore[method-assign]
