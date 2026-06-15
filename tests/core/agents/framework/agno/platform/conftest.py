"""Shared fixtures for the platform tests."""

import pytest
from agentfield.agent import Agent as AgentFieldNode


@pytest.fixture
def node() -> AgentFieldNode:
    """A bare AgentField node used to verify registration mounts the right reasoners."""
    return AgentFieldNode(node_id='test-node')
