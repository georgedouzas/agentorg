"""Tests for the agent module."""

from agentorg.core.agents.framework.agno.platform.security_engineer import (
    agent,
    list_required_env_vars,
    scan_secrets,
)


def test_agent_id_and_name():
    """The Security Engineer carries the canonical id and display name."""
    assert agent.id == 'security-engineer'
    assert agent.name == 'Security Engineer'


def test_agent_has_a_role():
    """The Security Engineer declares a non-empty role describing what it owns."""
    assert agent.role


def test_agent_tools_match_the_engineer_module():
    """The agent's tool list is exactly the two callables exported by `_tools.py`."""
    assert set(agent.tools or []) == {list_required_env_vars, scan_secrets}
