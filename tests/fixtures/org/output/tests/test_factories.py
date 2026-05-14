"""Factory wiring tests — every agent/team/workflow listed in the spec builds without errors."""

from org.ai.agents.factory import build_agents
from org.ai.teams.factory import build_teams
from org.ai.workflows.factory import build_workflows
from org.spec import spec

EXPECTED_AGENT_IDS = sorted(a.id for a in spec.ai.agents if a.id)
EXPECTED_TEAM_COUNT = len(spec.ai.teams)
EXPECTED_WORKFLOW_COUNT = len(spec.ai.workflows)


def test_build_agents_returns_every_spec_agent() -> None:
    """`build_agents(spec)` produces one Agent instance per spec entry, keyed by id."""
    agents = build_agents(spec)
    assert sorted(agents.keys()) == EXPECTED_AGENT_IDS


def test_each_agent_has_a_model_and_instructions() -> None:
    """Every built agent has a `model` configured and non-empty `instructions`."""
    for agent_id, agent in build_agents(spec).items():
        assert agent.model is not None, f'{agent_id} missing model'
        assert agent.instructions, f'{agent_id} has empty instructions'


def test_each_agent_has_resolved_tools() -> None:
    """Every tool on every spec agent is a real callable (not a string path)."""
    for agent in spec.ai.agents:
        for tool in agent.tools or []:
            assert callable(tool), f'{agent.id} has non-callable tool: {tool!r}'


def test_build_workflows_returns_expected_count() -> None:
    """`build_workflows(spec)` returns one Workflow per spec entry."""
    assert len(build_workflows(spec)) == EXPECTED_WORKFLOW_COUNT


def test_build_teams_returns_expected_count() -> None:
    """`build_teams(spec)` returns one Team per spec entry (empty if no teams)."""
    assert len(build_teams(spec)) == EXPECTED_TEAM_COUNT
