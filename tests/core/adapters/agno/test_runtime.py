"""Tests for the runtime module."""

from agentorg.core.adapters.agno import append_principles, register_reasoner


def test_register_reasoner_returns_agent_name(node, agno_agent):
    """The function returns the agent's name (its id, via the fallback chain)."""
    name = register_reasoner(node, agno_agent, tags=['agent'])
    assert name == 'researcher'


class _FakeAgent:
    """Minimal agno-style runnable carrying just an `instructions` string."""

    def __init__(self, instructions: str) -> None:
        self.instructions = instructions


def testappend_principles_adds_principles_block():
    """A non-empty principles is appended under a `## Principles` heading, original instructions kept."""
    agent = _FakeAgent('Do the work.')
    append_principles(agent, 'Always be excellent.')
    assert 'Do the work.' in agent.instructions
    assert '## Principles' in agent.instructions
    assert 'Always be excellent.' in agent.instructions
    assert agent.instructions.rstrip().endswith('Always be excellent.')


def testappend_principles_is_noop_without_text():
    """An empty principles leaves the agent's instructions untouched."""
    agent = _FakeAgent('Do the work.')
    append_principles(agent, '')
    assert agent.instructions == 'Do the work.'


def testappend_principles_is_noop_for_plain_callable():
    """A plain callable agent has no `instructions` attribute and append is a safe no-op."""

    async def plain_agent(message: str) -> dict[str, str]:
        return {'output': message}

    append_principles(plain_agent, 'Always be excellent.')  # must not raise
