"""Tests for the agent module."""

from agentorg.core.agents.framework.agno.platform._frontend_engineer import agent
from agentorg.core.agents.framework.agno.platform._frontend_engineer._tools import (
    list_overview_widgets,
    read_ui_config,
)


def test_agent_id_and_name():
    """The Frontend Engineer carries the canonical id and display name."""
    assert agent.id == 'frontend-engineer'
    assert agent.name == 'Frontend Engineer'


def test_agent_has_a_role():
    """The Frontend Engineer declares a non-empty role describing what it owns."""
    assert agent.role


def test_agent_tools_match_the_engineer_module():
    """The agent's tool list is exactly the two callables exported by `_tools.py`."""
    assert set(agent.tools or []) == {list_overview_widgets, read_ui_config}
