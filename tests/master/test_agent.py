"""Tests for the agent module."""

from agno.agent import Agent

from agentorg.master import (
    MASTER_INSTRUCTIONS,
    MASTER_INTRODUCTION,
    MASTER_TOOLS,
    add_or_update_agent,
    add_or_update_agent_group,
    add_or_update_knowledge_type,
    add_or_update_parameter,
    add_or_update_principle_section,
    add_or_update_team,
    add_or_update_workflow,
    build_master_agent,
    reset_state,
    set_knowledge_empty,
    set_org_identity,
    set_ui_app,
    set_ui_empty_state,
)
from agentorg.master._agent import (
    ALL_PLACEHOLDERS_FILLED,
    QUESTION_TEMPLATES,
    _next_question,
    _placeholders_dependency,
    _working_spec_dependency,
)


def test_build_master_agent_returns_a_raw_agno_agent():
    """The master agent is a bare `agno.Agent` (no `make_agent` curation)."""
    agent = build_master_agent()
    assert isinstance(agent, Agent)
    assert agent.id == 'master'


def test_build_master_agent_carries_every_patch_tool():
    """Every entry in `MASTER_TOOLS` reaches the agent's `tools` list verbatim."""
    agent = build_master_agent()
    assert list(agent.tools) == MASTER_TOOLS


def test_master_instructions_reference_the_interview_workflow():
    """The persona instructions cite `placeholders`, `working_spec`, and the workflow."""
    assert 'placeholders' in MASTER_INSTRUCTIONS
    assert 'working_spec' in MASTER_INSTRUCTIONS
    assert 'Workflow' in MASTER_INSTRUCTIONS
    assert 'finalize_spec' in MASTER_INSTRUCTIONS


def test_master_tools_include_finalize_and_emit_custom_tool():
    """The lifecycle tools (sandbox emitter + finalizer) are wired in."""
    tool_names = {getattr(t, '__name__', repr(t)) for t in MASTER_TOOLS}
    assert 'emit_custom_tool' in tool_names
    assert 'finalize_spec' in tool_names
    assert 'set_org_identity' in tool_names


def test_master_introduction_greets_and_explains_purpose():
    """The opening message names the agent and tells the user what's coming."""
    assert 'master agent' in MASTER_INTRODUCTION.lower()
    assert 'spec.py' in MASTER_INTRODUCTION


def test_build_master_agent_enables_conversation_history_and_live_context():
    """History, dependency injection, and datetime are on - the conversation flows."""
    agent = build_master_agent()
    assert agent.add_history_to_context is True
    assert agent.num_history_runs == 20
    assert agent.add_dependencies_to_context is True
    assert agent.add_datetime_to_context is True
    assert agent.dependencies is not None
    assert set(agent.dependencies) == {'working_spec', 'placeholders'}


def test_working_spec_dependency_reflects_current_state():
    """The `working_spec` callable returns a dict snapshot of the live spec on every call."""
    reset_state()
    set_org_identity(name='Dependency Org', description='Live snapshot.')
    snapshot = _working_spec_dependency()
    assert snapshot['org']['name'] == 'Dependency Org'
    assert snapshot['org']['description'] == 'Live snapshot.'


def test_placeholders_dependency_reflects_current_state():
    """The `placeholders` callable returns the live list of unfilled fields."""
    reset_state()
    paths_before = {p for p, _ in _placeholders_dependency()}
    assert 'org.description' in paths_before

    set_org_identity(description='Now set.')
    add_or_update_agent(
        agent_id='r',
        name='R',
        role='r',
        in_scope=['s'],
        workflow=['w'],
    )
    paths_after = {p for p, _ in _placeholders_dependency()}
    assert 'org.description' not in paths_after
    assert 'ai.agents' not in paths_after


def test_next_question_picks_an_org_field_first_on_seed():
    """When everything is at seed, the next question prioritises an org-level field."""
    reset_state()
    question = _next_question()
    assert question in QUESTION_TEMPLATES.values()
    # The first placeholder by priority is something on `org.`
    assert 'organisation' in question.lower() or 'author' in question.lower() or 'repository' in question.lower()


def test_next_question_advances_as_fields_are_filled():
    """As org placeholders get set, `_next_question` moves on to the agents section."""
    reset_state()
    set_org_identity(
        name='Org',
        slug='org',
        package_name='org',
        description='Does things.',
        repository='https://example.com/org',
        admin_name='Maintainer',
        admin_email='m@example.com',
    )
    # All org placeholders set; UI app.name placeholder should still trigger before ai.agents.
    # Set UI placeholders too.
    set_ui_app(name='App', icon='icon', description='App description.')
    set_ui_empty_state(icon='icon', title='Title', body='Body.')
    set_knowledge_empty('Nothing yet.')

    # Now the only remaining placeholder is ai.agents.
    assert _next_question() == QUESTION_TEMPLATES['ai.agents']


def test_next_question_returns_finalize_prompt_when_nothing_left():
    """When every section is filled (or explicitly populated), the fallback nudges toward finalising."""
    reset_state()
    set_org_identity(
        name='Org',
        slug='org',
        package_name='org',
        description='Does things.',
        repository='https://example.com/org',
        admin_name='Maintainer',
        admin_email='m@example.com',
    )
    set_ui_app(name='App', icon='icon', description='App description.')
    set_ui_empty_state(icon='icon', title='Title', body='Body.')
    set_knowledge_empty('Nothing yet.')
    add_or_update_agent(
        agent_id='r',
        name='R',
        role='r',
        in_scope=['Pre-purchase questions.'],
        workflow=['Restate the request.'],
        tools=['read_knowledge'],
    )
    add_or_update_team(team_id='t', name='T', role='r', workflow=['Coordinate.'], member_ids=['r'])
    add_or_update_workflow(workflow_id='w', name='W', steps=[{'name': 's', 'agent_id': 'r'}])
    add_or_update_knowledge_type(knowledge_type_id='note', label='Notes')
    add_or_update_principle_section(section_id='p1', title='Mission', body='Be helpful.')
    add_or_update_parameter(name='param', param_type='string', default='x', label='Param')
    add_or_update_agent_group(label='All', ids=['r'])

    assert _next_question() == ALL_PLACEHOLDERS_FILLED
