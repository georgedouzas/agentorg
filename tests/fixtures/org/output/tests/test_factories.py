"""Factory wiring tests — every agent/team/workflow listed in the spec builds without errors."""

from org.ai.agents.factory import build_agents
from org.ai.teams.factory import build_teams
from org.ai.workflows.factory import build_workflows

EXPECTED_AGENT_IDS = ["analyst", "backend-engineer", "frontend-engineer", "knowledge-engineer", "platform-engineer", "qa-engineer", "researcher", "security-engineer"]
EXPECTED_TEAM_COUNT = 1
EXPECTED_WORKFLOW_COUNT = 1


def test_build_agents_returns_every_spec_agent() -> None:
    """`build_agents()` produces one Agent instance per spec entry, keyed by id."""
    agents = build_agents()
    assert sorted(agents.keys()) == EXPECTED_AGENT_IDS


def test_each_agent_has_a_model_and_instructions() -> None:
    """Every built agent has a `model` configured and non-empty `instructions`."""
    for agent_id, agent in build_agents().items():
        assert agent.model is not None, f'{agent_id} missing model'
        assert agent.instructions, f'{agent_id} has empty instructions'


def test_each_agent_has_resolved_tools() -> None:
    """Tool import paths in the spec resolved to real callables (none are still strings)."""
    for agent_id, agent in build_agents().items():
        for tool in getattr(agent, 'tools', None) or []:
            assert callable(tool) or hasattr(tool, 'name'), f'{agent_id} has unresolved tool: {tool!r}'


def test_build_workflows_returns_expected_count() -> None:
    """`build_workflows()` produces one Workflow per spec entry."""
    assert len(build_workflows()) == EXPECTED_WORKFLOW_COUNT


def test_build_teams_returns_expected_count() -> None:
    """`build_teams()` produces one Team per spec entry (or none if `team_architecture` is null)."""
    assert len(build_teams()) == EXPECTED_TEAM_COUNT
