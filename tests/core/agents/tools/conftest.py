"""Shared fixtures for the agent tools tests."""

import json
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

import pytest
import pytest_asyncio
import requests
from agentfield import Agent
from httpx import ASGITransport, AsyncClient
from testcontainers.core.container import DockerContainer

from agentorg.core.agents import tools as _tools

HEALTHY = 200
START_TIMEOUT_S = 30


@pytest.fixture(scope='session')
def control_plane() -> Iterator[str]:
    """A running AgentField control plane container that all node-backed tests connect to."""
    container = DockerContainer('agentfield/control-plane:latest').with_exposed_ports(8080)
    container.start()
    url = f'http://localhost:{container.get_exposed_port(8080)}'
    deadline = time.time() + START_TIMEOUT_S
    while time.time() < deadline:
        try:
            if requests.get(f'{url}/health', timeout=1).status_code == HEALTHY:
                break
        except requests.RequestException:
            time.sleep(0.5)
    else:
        container.stop()
        msg = f'AgentField control plane did not become healthy at {url} within {START_TIMEOUT_S}s.'
        raise RuntimeError(msg)
    os.environ['AGENTFIELD_SERVER'] = url
    yield url
    container.stop()


@pytest_asyncio.fixture
async def client(control_plane: str) -> AsyncIterator[AsyncClient]:
    """A test node with every `@tags`-decorated tool registered as a reasoner, fronted by an httpx client."""
    node = Agent(node_id='test-node')
    for fn in (getattr(_tools, n) for n in _tools.__all__):
        if callable(fn) and hasattr(fn, 'tags'):
            node.reasoner(name=fn.__name__, tags=fn.tags)(fn)
    async with AsyncClient(transport=ASGITransport(app=node), base_url='http://test') as client:
        yield client


@pytest.fixture
def call(client: AsyncClient) -> Callable[..., Awaitable[object]]:
    """Invoke a reasoner over HTTP and decode the JSON-string result the tool returns."""

    async def _call(reasoner: str, /, **kwargs: object) -> object:
        r = await client.post(f'/reasoners/{reasoner}', json=kwargs)
        assert r.status_code == HEALTHY, f'/reasoners/{reasoner} -> {r.status_code}: {r.text}'
        payload = r.json()
        try:
            return json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return payload

    return _call


@pytest_asyncio.fixture(autouse=True)
async def _isolate_global_state(client: AsyncClient) -> AsyncIterator[None]:
    """Reset org parameters before each test so shared control-plane state doesn't leak between tests."""
    await client.post('/reasoners/reset_org_parameters', json={})
    yield
