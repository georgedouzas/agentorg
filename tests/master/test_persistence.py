"""Tests for the persistence module."""

import json
import textwrap
from pathlib import Path

from agentorg.master import (
    AgentSpec,
    CustomTool,
    TeamSpec,
    WorkflowSpec,
    add_or_update_agent,
    add_or_update_team,
    add_or_update_workflow,
    emit_custom_tool,
    get_state,
    load_draft,
    reset_state,
    save_draft,
    set_org_identity,
)

VALID_TOOL_SOURCE = textwrap.dedent(
    '''
    """Echo tool for persistence tests."""

    async def echo_tool(message: str) -> str:
        """Return the message unchanged."""
        return message
    ''',
).strip()


def _populate_state() -> None:
    set_org_identity(name='Persisted Org', description='Saved.')
    add_or_update_agent(
        agent_id='researcher',
        name='Researcher',
        role='Gather sources.',
        in_scope=['Sources'],
        workflow=['Restate.', 'Cite.'],
    )
    add_or_update_team(team_id='team', name='Team', role='r', workflow=['w'], member_ids=['researcher'])
    add_or_update_workflow(workflow_id='wf', name='WF', steps=[{'name': 's', 'agent_id': 'researcher'}])
    emit_custom_tool(name='echo_tool', source=VALID_TOOL_SOURCE)


def test_save_draft_writes_a_json_snapshot_of_state(tmp_path: Path):
    """`save_draft` produces a JSON file with both `spec` and `custom_tools` keys."""
    _populate_state()
    target = tmp_path / 'draft.json'
    save_draft(target)
    payload = json.loads(target.read_text())
    assert payload['spec']['org']['name'] == 'Persisted Org'
    assert payload['custom_tools'][0]['name'] == 'echo_tool'


def test_load_draft_restores_state_and_revives_pydantic_types(tmp_path: Path):
    """After load_draft, the agents/teams/workflows are real Pydantic models, not dicts."""
    _populate_state()
    target = tmp_path / 'draft.json'
    save_draft(target)

    reset_state()

    load_draft(target)
    state = get_state()
    assert isinstance(state.spec.ai.agents[0], AgentSpec)
    assert isinstance(state.spec.ai.teams[0], TeamSpec)
    assert isinstance(state.spec.ai.workflows[0], WorkflowSpec)
    assert isinstance(state.custom_tools[0], CustomTool)
    assert state.spec.org.name == 'Persisted Org'


def test_save_then_load_round_trips_the_spec(tmp_path: Path):
    """Mutate -> save -> reset -> load returns a Spec equivalent to what was saved."""
    _populate_state()
    target = tmp_path / 'draft.json'
    save_draft(target)
    saved_dump = get_state().spec.model_dump(mode='json')

    reset_state()
    assert get_state().spec.org.name == 'My Org'  # confirm reset worked

    load_draft(target)
    assert get_state().spec.model_dump(mode='json') == saved_dump
