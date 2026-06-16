"""Tests for the agent module."""

from agentorg.core.agents.framework.agno.platform.qa_engineer import agent, run_tests, validate_spec


def test_agent_id_and_name():
    """The QA Engineer carries the canonical id and display name."""
    assert agent.id == 'qa-engineer'
    assert agent.name == 'QA Engineer'


def test_agent_has_a_role():
    """The QA Engineer declares a non-empty role describing what it owns."""
    assert agent.role


def test_agent_tools_match_the_engineer_module():
    """The agent's tool list is exactly the two callables exported by `_tools.py`."""
    assert set(agent.tools or []) == {run_tests, validate_spec}
