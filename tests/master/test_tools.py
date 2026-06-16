"""Tests for the tools module."""

import textwrap

import pytest
from pydantic import ValidationError

from agentorg.master import (
    AgentSpec,
    add_or_update_agent,
    add_or_update_agent_group,
    add_or_update_env_var,
    add_or_update_knowledge_type,
    add_or_update_overview_block,
    add_or_update_parameter,
    add_or_update_principle_section,
    add_or_update_setup_step,
    add_or_update_team,
    add_or_update_workflow,
    emit_custom_tool,
    get_state,
    list_placeholders,
    remove_agent,
    remove_agent_group,
    remove_custom_tool,
    remove_env_var,
    remove_knowledge_type,
    remove_overview_block,
    remove_parameter,
    remove_principle_section,
    remove_setup_step,
    remove_team,
    remove_workflow,
    set_agent_icons,
    set_featured_agents,
    set_knowledge_empty,
    set_org_identity,
    set_runtime_infra,
    set_ui_app,
    set_ui_empty_state,
)

VALID_TOOL_SOURCE = textwrap.dedent(
    '''
    """A simple custom tool that echoes its input."""

    async def echo_tool(message: str) -> str:
        """Return the message unchanged - used as a smoke test for the sandbox."""
        return message
    '''

       ,
).strip()


def _add_basic_agent(agent_id: str = 'researcher') -> str:
    return add_or_update_agent(
        agent_id=agent_id,
        name='Researcher',
        role='Gather sources on a topic.',
        in_scope=['Source gathering on the requested topic'],
        workflow=['Restate the topic.', 'Cite at least three sources.'],
    )


# ---- Placeholders ----


def test_list_placeholders_on_seed_reports_org_fields_and_empty_agents():
    """A fresh seed reports every TODO field on `org`/`ui` plus the empty `ai.agents`."""
    paths = {path for path, _ in list_placeholders()}
    assert 'org.description' in paths
    assert 'org.repository' in paths
    assert 'org.author_name' in paths
    assert 'ai.agents' in paths


# ---- Org ----


def test_set_org_identity_clears_only_provided_fields():
    """Only fields passed to `set_org_identity` are updated; unmentioned fields stay as placeholders."""
    set_org_identity(name='Research Org', description='Reads papers, writes reports.')
    spec = get_state().spec
    assert spec.org.name == 'Research Org'
    assert spec.org.description == 'Reads papers, writes reports.'
    assert spec.org.repository == 'TODO'  # untouched
    paths = {path for path, _ in list_placeholders()}
    assert 'org.repository' in paths
    assert 'org.description' not in paths


def test_set_org_identity_rejects_invalid_visibility():
    """`visibility` outside the literal union is rejected by Pydantic validation."""
    with pytest.raises(ValidationError):
        set_org_identity(visibility='internal')  # type: ignore[arg-type]


def test_set_org_identity_with_no_args_is_a_noop():
    """Calling with no arguments returns a no-op message and changes nothing."""
    result = set_org_identity()
    assert 'No changes' in result


# ---- Agents ----


def test_add_or_update_agent_adds_a_new_agent():
    """Adding a never-seen `agent_id` appends an `AgentSpec` to `ai.agents`."""
    message = _add_basic_agent()
    assert message.startswith('Added')
    agents = get_state().spec.ai.agents
    assert len(agents) == 1
    assert isinstance(agents[0], AgentSpec)
    assert agents[0].agent_id == 'researcher'


def test_add_or_update_agent_updates_an_existing_agent():
    """Re-adding the same `agent_id` replaces the existing `AgentSpec`."""
    _add_basic_agent()
    message = add_or_update_agent(
        agent_id='researcher',
        name='Researcher',
        role='Updated role: synthesise + cite.',
        in_scope=['Updated scope'],
        workflow=['Updated workflow.'],
    )
    assert message.startswith('Updated')
    agents = get_state().spec.ai.agents
    assert len(agents) == 1
    assert agents[0].role.startswith('Updated role')


def test_add_or_update_agent_clears_the_agents_placeholder():
    """Adding the first agent removes `ai.agents` from the placeholder list."""
    _add_basic_agent()
    paths = {path for path, _ in list_placeholders()}
    assert 'ai.agents' not in paths


def test_remove_agent_drops_an_existing_agent():
    """Removing by `agent_id` shrinks the list and returns a confirmation."""
    _add_basic_agent()
    message = remove_agent('researcher')
    assert 'Removed' in message
    assert get_state().spec.ai.agents == []


def test_remove_agent_returns_a_not_found_message_for_unknown_id():
    """Removing an unknown `agent_id` is a safe no-op with a clear message."""
    message = remove_agent('does-not-exist')
    assert 'No agent' in message


# ---- Teams ----


def test_add_or_update_team_adds_a_new_team():
    """A new team appears in `spec.ai.teams` keyed by `team_id`."""
    _add_basic_agent()
    _add_basic_agent('analyst')
    msg = add_or_update_team(
        team_id='research-team',
        name='Research Team',
        role='Coordinate research and analysis.',
        workflow=['Delegate to researcher.', 'Hand off to analyst.'],
        member_ids=['researcher', 'analyst'],
    )
    assert msg.startswith('Added')
    teams = get_state().spec.ai.teams
    assert len(teams) == 1
    assert teams[0].team_id == 'research-team'
    assert teams[0].member_ids == ['researcher', 'analyst']


def test_add_or_update_team_updates_an_existing_team():
    """Re-adding the same `team_id` replaces the entry."""
    add_or_update_team(team_id='t1', name='T', role='r', workflow=['w'], member_ids=[])
    msg = add_or_update_team(team_id='t1', name='T renamed', role='r2', workflow=['w2'], member_ids=[])
    assert msg.startswith('Updated')
    assert get_state().spec.ai.teams[0].name == 'T renamed'


def test_remove_team_drops_the_team():
    """Removing by `team_id` empties the teams list."""
    add_or_update_team(team_id='t1', name='T', role='r', workflow=['w'], member_ids=[])
    msg = remove_team('t1')
    assert 'Removed' in msg
    assert get_state().spec.ai.teams == []


# ---- Workflows ----


def test_add_or_update_workflow_with_steps_referencing_agents():
    """Steps reference agents by id; workflow is keyed by `workflow_id`."""
    msg = add_or_update_workflow(
        workflow_id='pipeline',
        name='Pipeline',
        steps=[
            {'name': 'Gather', 'agent_id': 'researcher'},
            {'name': 'Analyse', 'agent_id': 'analyst', 'requires_output_review': True},
        ],
        description='Gather then analyse.',
    )
    assert msg.startswith('Added')
    workflows = get_state().spec.ai.workflows
    assert workflows[0].workflow_id == 'pipeline'
    assert workflows[0].steps[1].requires_output_review is True


def test_remove_workflow_drops_the_workflow():
    """Removing by `workflow_id` empties the workflows list."""
    add_or_update_workflow(workflow_id='w1', name='W', steps=[{'name': 's', 'agent_id': 'researcher'}])
    msg = remove_workflow('w1')
    assert 'Removed' in msg


# ---- Parameters ----


def test_add_or_update_parameter_adds_a_typed_default():
    """A new parameter appears in `spec.parameters`."""
    msg = add_or_update_parameter(name='min_sources', param_type='int', default=3, label='Minimum Sources')
    assert msg.startswith('Added')
    params = get_state().spec.parameters
    assert params[0].name == 'min_sources'
    assert params[0].default == 3


def test_remove_parameter_drops_the_parameter():
    """Removing by `name` shrinks `spec.parameters`."""
    add_or_update_parameter(name='p1', param_type='string', default='x', label='P1')
    msg = remove_parameter('p1')
    assert 'Removed' in msg


# ---- Knowledge ----


def test_add_or_update_knowledge_type_adds_a_type_with_metadata_fields():
    """A new knowledge type appears with the supplied metadata field schema."""
    add_or_update_knowledge_type(
        knowledge_type_id='research',
        label='Research Docs',
        metadata_fields=[{'name': 'author', 'type': 'string'}],
    )
    types = get_state().spec.knowledge.types
    assert types[0].id == 'research'
    assert types[0].metadata_fields[0].name == 'author'


def test_remove_knowledge_type_drops_it():
    """Removing by `id` shrinks the types list."""
    add_or_update_knowledge_type(knowledge_type_id='research', label='Research Docs')
    msg = remove_knowledge_type('research')
    assert 'Removed' in msg


def test_add_or_update_principle_section_adds_a_section():
    """A new principle section appears under `knowledge.principles.sections`."""
    add_or_update_principle_section(section_id='mission', title='Mission', body='Cite at least {min_sources} sources.')
    sections = get_state().spec.knowledge.principles.sections
    assert sections[0].id == 'mission'
    assert '{min_sources}' in sections[0].body


def test_remove_principle_section_drops_it():
    """Removing by `id` shrinks the sections list."""
    add_or_update_principle_section(section_id='s1', title='T', body='B')
    msg = remove_principle_section('s1')
    assert 'Removed' in msg


# ---- Runtime ----


def test_set_runtime_infra_changes_only_provided_fields():
    """Only fields passed to `set_runtime_infra` are updated."""
    set_runtime_infra(packaging='docker', api='railway')
    infra = get_state().spec.runtime.infra
    assert infra.packaging == 'docker'
    assert infra.api == 'railway'
    assert infra.database == 'sqlite'  # untouched


def test_set_runtime_infra_validates_combinations():
    """Pydantic's infra validator rejects invalid combinations (e.g. pgvector without postgres)."""
    with pytest.raises(ValidationError):
        set_runtime_infra(vector_db='pgvector')  # database is still sqlite


def test_add_or_update_env_var_routes_to_required_or_optional():
    """`required=True` adds to the required list; `required=False` to the optional list."""
    add_or_update_env_var(name='GOOGLE_API_KEY', description='Gemini key.', required_label='Prod', required=True)
    add_or_update_env_var(name='LOG_LEVEL', description='Logging.', required_label='Dev', required=False)
    env = get_state().spec.runtime.env_vars
    assert env.required[0].name == 'GOOGLE_API_KEY'
    assert env.optional[0].name == 'LOG_LEVEL'


def test_remove_env_var_drops_from_either_list():
    """`remove_env_var` finds the var regardless of which list it lives in."""
    add_or_update_env_var(name='X', description='x', required_label='Dev', required=False)
    msg = remove_env_var('X')
    assert 'Removed' in msg
    assert get_state().spec.runtime.env_vars.optional == []


def test_add_or_update_setup_step_adds_and_removes():
    """Adding a setup step appends; removing by `id` drops it."""
    add_or_update_setup_step(
        step_id='secrets',
        title='Set GOOGLE_API_KEY',
        description='...',
        variables=['GOOGLE_API_KEY'],
    )
    assert get_state().spec.runtime.setup[0].id == 'secrets'
    assert remove_setup_step('secrets').startswith('Removed')


# ---- UI ----


def test_set_ui_app_changes_only_provided_fields():
    """`set_ui_app` patches the app block in place."""
    set_ui_app(name='Research Org', icon='microscope')
    assert get_state().spec.ui.app.name == 'Research Org'
    assert get_state().spec.ui.app.icon == 'microscope'


def test_set_ui_empty_state_changes_only_provided_fields():
    """`set_ui_empty_state` patches the empty-state block in place."""
    set_ui_empty_state(title='Get started')
    assert get_state().spec.ui.empty_state.title == 'Get started'


def test_set_knowledge_empty_updates_copy():
    """`set_knowledge_empty` updates the copy shown on the empty knowledge tab."""
    set_knowledge_empty('No knowledge yet, run the researcher first.')
    assert 'No knowledge yet' in get_state().spec.ui.knowledge_empty


def test_agent_group_add_and_remove():
    """An agent group is keyed by its display label."""
    add_or_update_agent_group(label='Research Team', ids=['researcher', 'analyst'])
    assert get_state().spec.ui.agent_groups[0].ids == ['researcher', 'analyst']
    remove_agent_group('Research Team')
    assert get_state().spec.ui.agent_groups == []


def test_set_featured_agents_and_agent_icons():
    """`set_featured_agents` and `set_agent_icons` overwrite their respective fields wholesale."""
    set_featured_agents(['analyst'])
    set_agent_icons({'analyst': 'flask'})
    assert get_state().spec.ui.featured_agents == ['analyst']
    assert get_state().spec.ui.agent_icons == {'analyst': 'flask'}


def test_overview_block_add_and_remove():
    """An overview block is keyed by its title."""
    add_or_update_overview_block(title='How it works', body='Researcher then Analyst.')
    assert get_state().spec.ui.overview[0].title == 'How it works'
    remove_overview_block('How it works')
    assert get_state().spec.ui.overview == []


# ---- Custom tools ----


def test_emit_custom_tool_registers_validated_source():
    """A valid emission appears in `state.custom_tools`."""
    msg = emit_custom_tool(name='echo_tool', source=VALID_TOOL_SOURCE)
    assert msg.startswith('Registered')
    custom = get_state().custom_tools
    assert len(custom) == 1
    assert custom[0].name == 'echo_tool'


def test_emit_custom_tool_updates_existing_tool_by_name():
    """Re-emitting with the same name replaces the source."""
    emit_custom_tool(name='echo_tool', source=VALID_TOOL_SOURCE)
    new_source = VALID_TOOL_SOURCE.replace('return message', 'return message + "!"')
    msg = emit_custom_tool(name='echo_tool', source=new_source)
    assert msg.startswith('Updated')
    assert '+ "!"' in get_state().custom_tools[0].source


def test_emit_custom_tool_returns_a_message_on_validation_failure():
    """A bad source returns an error message; state is not mutated."""
    msg = emit_custom_tool(name='broken', source='async def broken(:')
    assert 'Validation failed' in msg
    assert get_state().custom_tools == []


def test_remove_custom_tool_drops_a_registered_tool():
    """Removing by name shrinks the custom tools list."""
    emit_custom_tool(name='echo_tool', source=VALID_TOOL_SOURCE)
    assert remove_custom_tool('echo_tool').startswith('Removed')
    assert get_state().custom_tools == []


def test_remove_custom_tool_returns_not_found_for_unknown_name():
    """Removing a tool that was never registered is a safe no-op."""
    assert 'No custom tool' in remove_custom_tool('never_registered')
