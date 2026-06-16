"""Tests for the register module."""

from agentfield.agent import Agent as AgentFieldNode

from agentorg.core.agents.framework.agno.platform import PLATFORM_AGENT_IDS, PLATFORM_AGENTS, register_platform_agents

_EXPECTED_COUNT = 6


def test_register_platform_agents_returns_every_platform_agent_id(node: AgentFieldNode) -> None:
    """The return value is the list of registered reasoner names — one per platform agent."""
    names = register_platform_agents(node)
    assert set(names) == PLATFORM_AGENT_IDS
    assert len(names) == _EXPECTED_COUNT


def test_register_platform_agents_mounts_a_reasoner_endpoint_per_agent(node: AgentFieldNode) -> None:
    """Every registered name becomes a `/reasoners/{name}` HTTP route on the node."""
    names = register_platform_agents(node)
    paths = {str(r.path) for r in node.routes}
    for name in names:
        assert f'/reasoners/{name}' in paths, f'{name} not exposed as a reasoner route'


def test_register_platform_agents_appends_principles_to_every_agent(node: AgentFieldNode) -> None:
    """The `principles_text` argument is appended to each platform agent's instructions."""
    principles = 'ALWAYS-INCLUDED-MARKER'
    register_platform_agents(node, principles_text=principles)

    for agent in PLATFORM_AGENTS:
        assert principles in (agent.instructions or ''), f'{agent.id}: principles not appended'
