"""Configuration for the pytest test suite of `agentorg.adapters` module."""

import pytest
from agentfield.agent import Agent as AgentFieldNode
from agno.agent import Agent as AgnoAgent
from agno.agent import RunOutput


@pytest.fixture
def node() -> AgentFieldNode:
    """Pytest fixture that returns a simple AgentFieldNode instance for testing purposes."""
    return AgentFieldNode(node_id='test-node')


@pytest.fixture
def agno_agent(monkeypatch: pytest.MonkeyPatch) -> AgnoAgent:
    """Pytest fixture that returns a simple AgnoAgent instance for testing purposes."""
    agent = AgnoAgent(id='researcher', name='Researcher')

    async def _arun(*args: object, **kwargs: object) -> RunOutput:
        return RunOutput(content='Test output')

    monkeypatch.setattr(agent, 'arun', _arun)
    return agent
