"""Tests for the make module."""

from agentorg.core.agents.framework.agno.platform import PLATFORM_DEFAULT_MODEL, platform_make_agent


def _noop() -> str:
    """Placeholder callable used as a stand-in tool."""
    return ''


def test_platform_make_agent_pins_the_shared_model():
    """Every platform agent inherits `PLATFORM_DEFAULT_MODEL`."""
    agent = platform_make_agent(
        name='Test Engineer',
        agent_id='test-engineer',
        role='Tests things.',
        tools=[],
        in_scope=[],
        workflow=[],
    )
    model = agent.model
    model_id = getattr(model, 'id', None) or str(model)
    expected_leaf = PLATFORM_DEFAULT_MODEL.split(':', 1)[-1]
    assert expected_leaf in model_id


def test_platform_make_agent_carries_caller_provided_fields():
    """`name`, `agent_id`, `role`, and `tools` reach the constructed agent verbatim."""
    agent = platform_make_agent(
        name='Test Engineer',
        agent_id='test-engineer',
        role='Tests things.',
        tools=[_noop],
        in_scope=['testing'],
        workflow=['Run a test.'],
    )
    assert agent.name == 'Test Engineer'
    assert agent.id == 'test-engineer'
    assert agent.role == 'Tests things.'
    assert _noop in (agent.tools or [])


def test_platform_make_agent_passes_in_scope_and_workflow_through_to_instructions():
    """`in_scope` and `workflow` arguments are reachable in the composed system prompt."""
    agent = platform_make_agent(
        name='Test Engineer',
        agent_id='test-engineer',
        role='Tests things.',
        tools=[],
        in_scope=['unique-scope-token-zeta'],
        workflow=['unique-workflow-token-eta'],
    )
    assert 'unique-scope-token-zeta' in (agent.instructions or '')
    assert 'unique-workflow-token-eta' in (agent.instructions or '')
