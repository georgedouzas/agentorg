"""Factory wiring tests that confirm the spec's agents, teams, and workflows register as reasoners."""

from agentfield import Agent

from org.ai.agents.factory import register_agents
from org.ai.teams.factory import register_teams
from org.ai.workflows.factory import register_workflows
from org.spec import spec

EXPECTED_AGENT_COUNT = len(spec.ai.agents)
EXPECTED_TEAM_COUNT = len(spec.ai.teams)
EXPECTED_WORKFLOW_COUNT = len(spec.ai.workflows)


def _node() -> Agent:
    """A standalone in-process node — no control plane, no registration."""
    return Agent(node_id='test-node', auto_register=False, enable_did=False, vc_enabled=False, dev_mode=True)


def test_register_agents_registers_every_spec_agent() -> None:
    """`register_agents` registers one reasoner per spec agent and returns their names."""
    names = register_agents(_node(), spec)
    assert len(names) == EXPECTED_AGENT_COUNT
    assert all(names), 'every agent must produce a non-empty reasoner name'


def test_register_teams_registers_every_spec_team() -> None:
    """`register_teams` registers one reasoner per spec team."""
    assert len(register_teams(_node(), spec)) == EXPECTED_TEAM_COUNT


def test_register_workflows_registers_every_spec_workflow() -> None:
    """`register_workflows` registers one reasoner per spec workflow."""
    assert len(register_workflows(_node(), spec)) == EXPECTED_WORKFLOW_COUNT


def test_registered_agents_are_exposed_as_reasoner_routes() -> None:
    """Every registered agent becomes a `/reasoners/{name}` endpoint on the node."""
    node = _node()
    names = register_agents(node, spec)
    paths = {str(r.path) for r in node.routes}
    for name in names:
        assert f'/reasoners/{name}' in paths, f'{name} not exposed as a reasoner route'
