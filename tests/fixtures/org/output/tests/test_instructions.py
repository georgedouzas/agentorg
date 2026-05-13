"""Instruction-composer tests — every built agent has a well-formed prompt."""

from org.ai.agents.factory import build_agents
from org.spec import spec


def test_every_agent_has_non_empty_instructions() -> None:
    """Every built agent has a non-empty instruction string (or callable)."""
    for agent_id, agent in build_agents(spec).items():
        assert agent.instructions, f'{agent_id} produced an empty prompt'


def test_charter_is_prepended_when_supplied() -> None:
    """When `build_agents` receives a `charter_text`, agents start with a `## Committee Rules` block."""
    for agent_id, agent in build_agents(spec, charter_text='Always be excellent.').items():
        text = agent.instructions if isinstance(agent.instructions, str) else ''
        assert '## Committee Rules' in text, f'{agent_id} missing charter block'
