"""Tests for the agent module."""

from agentorg.core.agents.framework.agno.platform._backend_engineer import agent
from agentorg.core.agents.framework.agno.platform._backend_engineer._tools import (
    list_agent_ids,
    read_agent_spec,
    run_tests,
)


def test_agent_id_and_name():
    """The Backend Engineer carries the canonical id and display name."""
    assert agent.id == 'backend-engineer'
    assert agent.name == 'Backend Engineer'


def test_agent_has_a_role():
    """The Backend Engineer declares a non-empty role describing what it owns."""
    assert agent.role


def test_agent_tools_match_the_engineer_module():
    """The agent's tool list is exactly the three callables exported by `_tools.py`."""
    assert set(agent.tools or []) == {list_agent_ids, read_agent_spec, run_tests}
