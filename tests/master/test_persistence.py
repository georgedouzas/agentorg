"""Tests for the persistence module."""

import json
from pathlib import Path

from agentorg.master import (
    add_or_update_agent,
    emit_custom_tool,
    get_state,
    load_draft,
    render_spec,
    reset_state,
    save_draft,
    set_org_identity,
)

from .conftest import ECHO_TOOL_SOURCE, build_hub_org


def _populate_state() -> None:
    get_state().stage = 'configure'
    set_org_identity(name='Persisted Org')
    emit_custom_tool(
        name='echo_tool',
        source=ECHO_TOOL_SOURCE,
        test_cases=[{'input': {'message': 'pong'}, 'expected_contains': 'pong'}],
    )
    build_hub_org()
    add_or_update_agent(
        agent_id='researcher',
        name='Researcher',
        role='Gathers.',
        unit_id='research',
        tools=['echo_tool'],
    )


def test_save_draft_writes_agents_units_and_tool_names(tmp_path: Path) -> None:
    """The draft stores the spec without its tree, the agent and unit drafts, and tools by name."""
    _populate_state()
    data = json.loads(save_draft(tmp_path / 'draft.json').read_text())
    assert 'ai' not in data['spec']
    assert [agent['id'] for agent in data['agents']] == ['lead', 'researcher']
    assert data['agents'][1]['tools'] == ['echo_tool']
    assert data['units'][0]['id'] == 'research'


def test_save_then_load_round_trips_the_spec(tmp_path: Path) -> None:
    """Mutate, save, reset and load reproduce the same spec, with custom tools compiled back into functions."""
    _populate_state()
    target = save_draft(tmp_path / 'draft.json')
    saved = render_spec(get_state().spec, custom_tools=get_state().custom_tools)
    reset_state()
    assert get_state().spec.org.name == 'Untitled org'
    state = load_draft(target)
    assert render_spec(state.spec, custom_tools=state.custom_tools) == saved
    assert callable(state.spec.ai.agent('researcher').tools[0])
    assert state.structure_error is None


def test_load_draft_keeps_incomplete_structure(tmp_path: Path) -> None:
    """A draft saved mid-build loads with the structure error and an empty tree."""
    get_state().stage = 'build'
    from agentorg.master import add_or_update_unit  # noqa: PLC0415

    add_or_update_unit(unit_id='research', name='Research', model='hub')
    state = load_draft(save_draft(tmp_path / 'draft.json'))
    assert state.spec.ai.root is None
    assert state.structure_error is not None
    assert [unit.id for unit in state.units] == ['research']
