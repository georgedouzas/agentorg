"""Charter-prepend tests for the agents factory."""

from org.ai.agents.factory import _prepend_charter


class _FakeAgent:
    """Minimal agno-style runnable — just an `instructions` string."""

    def __init__(self, instructions: str) -> None:
        self.instructions = instructions


def test_prepend_charter_adds_committee_rules_block() -> None:
    """A non-empty charter is prepended under a `## Committee Rules` heading, original instructions kept."""
    agent = _FakeAgent('Do the work.')
    _prepend_charter(agent, 'Always be excellent.')
    assert agent.instructions.startswith('## Committee Rules')
    assert 'Always be excellent.' in agent.instructions
    assert 'Do the work.' in agent.instructions


def test_prepend_charter_is_noop_without_text() -> None:
    """An empty charter leaves the runnable's instructions untouched."""
    agent = _FakeAgent('Do the work.')
    _prepend_charter(agent, '')
    assert agent.instructions == 'Do the work.'


def test_prepend_charter_is_noop_for_plain_callable() -> None:
    """A plain callable agent has no `instructions` attribute — prepend is a safe no-op."""

    async def plain_agent(message: str) -> dict[str, str]:
        return {'output': message}

    _prepend_charter(plain_agent, 'Always be excellent.')  # must not raise
