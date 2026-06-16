"""Tests for the agent module."""

from agentorg.core.agents.framework.agno.platform.knowledge_engineer import agent
from agentorg.core.agents.tools import (
    delete_knowledge,
    list_knowledge,
    read_knowledge,
    search_knowledge,
    write_knowledge,
)


def test_agent_id_and_name():
    """The Knowledge Engineer carries the canonical id and display name."""
    assert agent.id == 'knowledge-engineer'
    assert agent.name == 'Knowledge Engineer'


def test_agent_has_a_role():
    """The Knowledge Engineer declares a non-empty role describing what it owns."""
    assert agent.role


def test_agent_tools_are_the_five_knowledge_tools():
    """The Knowledge Engineer's tools come from `agents.tools` — the shared knowledge surface."""
    expected = {write_knowledge, read_knowledge, list_knowledge, search_knowledge, delete_knowledge}
    assert set(agent.tools or []) == expected
