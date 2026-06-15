"""Tests for the base module."""

from agno.agent import Agent

from agentorg.core.agents.framework.agno.platform import PLATFORM_AGENT_IDS, PLATFORM_AGENTS

_EXPECTED_AGENT_COUNT = 6
_EXPECTED_IDS = frozenset({
    'platform-engineer',
    'security-engineer',
    'backend-engineer',
    'frontend-engineer',
    'knowledge-engineer',
    'qa-engineer',
})


def test_platform_agents_has_six_entries():
    """`PLATFORM_AGENTS` ships exactly the six built-in engineers."""
    assert len(PLATFORM_AGENTS) == _EXPECTED_AGENT_COUNT


def test_every_platform_agent_is_an_agno_agent():
    """Each entry in `PLATFORM_AGENTS` is an `agno.Agent` instance."""
    for agent in PLATFORM_AGENTS:
        assert isinstance(agent, Agent), f'{agent}: not an agno.Agent'


def test_platform_agent_ids_matches_the_expected_engineer_set():
    """`PLATFORM_AGENT_IDS` is the canonical set of engineer ids."""
    assert PLATFORM_AGENT_IDS == _EXPECTED_IDS


def test_platform_agent_ids_is_derived_from_platform_agents():
    """The id set is internally consistent with the agent tuple."""
    assert {a.id for a in PLATFORM_AGENTS} == PLATFORM_AGENT_IDS


def test_platform_agent_ids_are_unique():
    """No two platform agents share an id."""
    ids = [a.id for a in PLATFORM_AGENTS]
    assert len(ids) == len(set(ids))
