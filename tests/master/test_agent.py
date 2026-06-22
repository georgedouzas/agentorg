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
    STAGE_TOOLS,
    _next_question,
    _placeholders_dependency,
    _working_spec_dependency,
)

from .conftest import advance_to_configure_stage, seed_discovery


def test_build_master_agent_returns_a_raw_agno_agent():
    """`build_master_agent` returns whichever per-stage agent is active (compat shim)."""
    agent = build_master_agent()
    assert isinstance(agent, Agent)
    # The interview always starts on `discover`, so the shim returns the Discover agent.
    assert agent.id == 'master-discover'


def test_build_master_agent_carries_every_patch_tool():
    """The Discover agent only carries the Discover slice, not the full MASTER_TOOLS list."""
    agent = build_master_agent()
    # Sanity: it has its narrow slice, NOT the full union of tools.
    assert list(agent.tools) == STAGE_TOOLS['discover']
    # And MASTER_TOOLS still exists as the legacy union (other modules may reference it).
    assert set(STAGE_TOOLS['discover']).issubset(set(MASTER_TOOLS))


def test_master_instructions_reference_the_interview_workflow():
    """The persona instructions cite live context, the staged flow, and the lifecycle tools."""
    assert 'placeholders' in MASTER_INSTRUCTIONS
    assert 'working_spec' in MASTER_INSTRUCTIONS
    assert 'Stage 1' in MASTER_INSTRUCTIONS
    assert 'Stage 2' in MASTER_INSTRUCTIONS
    assert 'finalize_spec' in MASTER_INSTRUCTIONS


def test_master_tools_include_finalize_and_emit_custom_tool():
    """The lifecycle tools (sandbox emitter + finalizer) are wired in."""
    tool_names = {getattr(t, '__name__', repr(t)) for t in MASTER_TOOLS}
    assert 'emit_custom_tool' in tool_names
    assert 'finalize_spec' in tool_names
    assert 'set_org_identity' in tool_names


def test_master_introduction_greets_and_explains_purpose():
    """The opening message names the agent and tells the user what's coming."""
    assert 'AgentOrg' in MASTER_INTRODUCTION
    assert 'five stages' in MASTER_INTRODUCTION.lower()


def test_build_master_agent_enables_conversation_history_and_live_context():
    """History, dependency injection, and datetime are on - the conversation flows."""
    agent = build_master_agent()
    assert agent.add_history_to_context is True
    assert agent.num_history_runs == 20
    assert agent.add_dependencies_to_context is True
    assert agent.add_datetime_to_context is True
    assert agent.dependencies is not None
    assert set(agent.dependencies) == {'working_spec', 'placeholders', 'next_question', 'stage'}


def test_working_spec_dependency_reflects_current_state():
    """The `working_spec` callable returns a dict snapshot of the live spec on every call."""
    reset_state()
    advance_to_configure_stage()
    set_org_identity(name='Dependency Org')
    snapshot = _working_spec_dependency()
    assert snapshot['org']['name'] == 'Dependency Org'


def test_placeholders_dependency_reflects_current_state():
    """The `placeholders` callable returns the live list of unfilled fields."""
    reset_state()
    paths_before = {p for p, _ in _placeholders_dependency()}
    assert 'org.description' in paths_before

    advance_to_configure_stage()
    long_desc = (
        'Test fixture: a substantive multi-sentence description that clears the Stage-2 '
        'minimum of 200 characters. It explains what the group does, who it serves, and '
        'how it differs from the alternatives so the rendered README has substance.'
    )
    set_org_identity(description=long_desc)
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
    lower = question.lower()
    assert any(keyword in lower for keyword in ('organization', 'admin', 'repository'))


def test_next_question_advances_as_fields_are_filled():
    """As org placeholders get set, `_next_question` moves on to the agents section."""
    reset_state()
    advance_to_configure_stage()
    set_org_identity(
        name='Org',
        slug='org',
        package_name='org',
        description=(
            'Test fixture description long enough to clear the Stage-2 200-char minimum, '
            'so the underlying _next_question priority test can advance past the org '
            'identity fields into the AI section as designed by the placeholder flow.'
        ),
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
    advance_to_configure_stage()
    set_org_identity(
        name='Org',
        slug='org',
        package_name='org',
        description=(
            'Test fixture description long enough to clear the Stage-2 200-char minimum, '
            'so the underlying _next_question priority test can advance past the org '
            'identity fields into the AI section as designed by the placeholder flow.'
        ),
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
    seed_discovery()
    add_or_update_principle_section(
        section_id='p1',
        title='Mission',
        body=(
            'Test fixture: principle body long enough to clear the 200-char Stage-1 '
            'minimum. The principle explains the rule and the trade-off it implies, '
            'with concrete examples of when it applies and when it does not.'
        ),
    )
    add_or_update_parameter(name='param', param_type='string', default='x', label='Param')
    add_or_update_agent_group(label='All', ids=['r'])

    assert _next_question() == ALL_PLACEHOLDERS_FILLED
