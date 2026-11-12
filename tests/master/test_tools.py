"""Tests for the tools module."""

import pytest
from pydantic import ValidationError

from agentorg.master import (
    STAGE_TOOLS,
    add_or_update_agent,
    add_or_update_agent_group,
    add_or_update_env_var,
    add_or_update_knowledge_type,
    add_or_update_overview_block,
    add_or_update_parameter,
    add_or_update_principle_section,
    add_or_update_setup_step,
    add_or_update_trigger,
    add_or_update_unit,
    advance_to_next_stage,
    emit_custom_skill,
    emit_custom_tool,
    get_current_spec,
    get_state,
    list_placeholders,
    record_discovery_summary,
    remove_agent,
    remove_agent_group,
    remove_custom_skill,
    remove_custom_tool,
    remove_env_var,
    remove_knowledge_type,
    remove_overview_block,
    remove_parameter,
    remove_principle_section,
    remove_setup_step,
    remove_trigger,
    remove_unit,
    set_agent_icons,
    set_approvers,
    set_budget,
    set_featured_agents,
    set_governance,
    set_knowledge_empty,
    set_lifecycle,
    set_notifications,
    set_org_identity,
    set_pipeline_step,
    set_run_policy,
    set_runtime_infra,
    set_ui_app,
    set_ui_empty_state,
)

from .conftest import ECHO_TOOL_SOURCE, advance_to_configure_stage, build_hub_org, seed_discovery

# Long description used in tests that need a Stage-2-grade `org.description`.
_LONG_DESC = (
    'Research Org gathers sources on a topic, distils the findings into structured '
    'weekly briefs, and ships them to internal product teams. The group bridges the '
    'gap between full literature reviews (slow) and informal Slack summaries (lossy).'
)

VALID_TOOL_SOURCE = '\n'.join(
    [
        '"""A simple custom tool that echoes its input."""',
        '',
        'async def echo_tool(message: str) -> str:',
        '    """Return the message unchanged - used as a smoke test for the sandbox."""',
        '    return message',
    ],
)
VALID_TEST_CASES = [{'input': {'message': 'pong'}, 'expected_contains': 'pong'}]


def test_list_placeholders_on_seed_reports_org_fields_and_empty_agents():
    """A fresh seed reports every TODO field on `org`/`ui` plus the empty `ai.agents`."""
    paths = {path for path, _ in list_placeholders()}
    assert 'org.description' in paths
    assert 'org.repository' in paths
    assert 'org.admin_name' in paths
    assert 'ai.agents' in paths


def test_set_org_identity_clears_only_provided_fields():
    """Only fields passed to `set_org_identity` are updated; unmentioned fields stay as placeholders."""
    advance_to_configure_stage()  # set_org_identity identity fields belong to Stage 2
    set_org_identity(name='Research Org', description=_LONG_DESC)
    spec = get_state().spec
    assert spec.org.name == 'Research Org'
    assert spec.org.description == _LONG_DESC
    assert spec.org.repository == 'Not set yet'  # untouched
    paths = {path for path, _ in list_placeholders()}
    assert 'org.repository' in paths
    assert 'org.description' not in paths


def test_set_org_identity_rejects_invalid_visibility():
    """`visibility` outside the literal union is rejected by Pydantic validation."""
    advance_to_configure_stage()
    with pytest.raises(ValidationError):
        set_org_identity(visibility='internal')


def test_set_org_identity_with_no_args_is_a_noop():
    """Calling with no arguments returns a no-op message and changes nothing."""
    advance_to_configure_stage()
    result = set_org_identity()
    assert 'No changes' in result


def test_set_org_identity_rejects_malformed_repository_url():
    """A bare word for `repository` is rejected with a guidance message; state is not mutated."""
    advance_to_configure_stage()
    result = set_org_identity(repository='not-a-url')
    assert "doesn't look right" in result
    assert get_state().spec.org.repository == 'Not set yet'  # unchanged


def test_set_org_identity_accepts_https_github_repository():
    """A well-formed GitHub HTTPS URL is accepted."""
    advance_to_configure_stage()
    set_org_identity(repository='https://github.com/example/research-org')
    assert get_state().spec.org.repository == 'https://github.com/example/research-org'


def test_set_org_identity_accepts_git_ssh_repository():
    """A `git@host:owner/repo.git` URL is accepted."""
    advance_to_configure_stage()
    set_org_identity(repository='git@github.com:example/research-org.git')
    assert get_state().spec.org.repository.startswith('git@')


def test_set_org_identity_accepts_example_com_todo_placeholder():
    """`https://example.com/TODO` (the master's "skip" placeholder) is accepted."""
    advance_to_configure_stage()
    set_org_identity(repository='https://example.com/TODO')
    assert get_state().spec.org.repository == 'https://example.com/TODO'


def test_set_org_identity_rejects_malformed_admin_email():
    """A junk string for `admin_email` is rejected with a guidance message; state is not mutated."""
    advance_to_configure_stage()
    result = set_org_identity(admin_email='qwfe')
    assert "doesn't look like an email" in result
    assert get_state().spec.org.admin_email == 'you@example.com'  # unchanged seed


def test_set_org_identity_accepts_well_formed_admin_email():
    """A reasonable email is accepted."""
    advance_to_configure_stage()
    set_org_identity(admin_email='admin@example.com')
    assert get_state().spec.org.admin_email == 'admin@example.com'


def test_add_or_update_agent_needs_an_existing_unit():
    """Agents are placed in units, so the unit must exist first."""
    assert 'Create it first' in add_or_update_agent(agent_id='a', name='A', role='Works.', unit_id='ghost')
    assert get_state().agents == []


def test_build_hub_org_produces_a_valid_tree():
    """A hub with its lead and a member assembles into the live spec."""
    build_hub_org()
    spec = get_state().spec
    assert get_state().structure_error is None
    assert spec.ai.root is not None
    assert (spec.ai.root.lead, spec.ai.root.members) == ('lead', ['researcher'])


def test_incomplete_structure_is_reported_and_keeps_last_valid_spec():
    """A hub without its lead is saved as a draft, reported, and leaves the spec's tree unset."""
    add_or_update_unit(unit_id='research', name='Research', model='hub')
    message = add_or_update_agent(agent_id='a', name='A', role='Works.', unit_id='research')
    assert 'not complete yet' in message
    assert 'needs a `lead`' in message
    assert get_state().spec.ai.root is None
    assert [agent.id for agent in get_state().agents] == ['a']


def test_add_or_update_agent_updates_in_place_and_moves_units():
    """Re-adding an agent updates it and moves it to the named unit."""
    build_hub_org()
    add_or_update_unit(unit_id='desk', name='Desk', model='solo', parent_id='research')
    message = add_or_update_agent(agent_id='researcher', name='R2', role='Gathers.', unit_id='desk', model='haiku')
    assert message.startswith("Updated agent 'researcher'")
    spec = get_state().spec
    assert spec.ai.agent('researcher').model == 'haiku'
    assert [unit.id for unit in spec.ai.path_to('researcher')] == ['research', 'desk']


def test_add_or_update_agent_returns_validation_errors_as_text():
    """Invalid agent fields come back as text and nothing is saved."""
    build_hub_org()
    message = add_or_update_agent(
        agent_id='bad',
        name='B',
        role='r',
        unit_id='research',
        autonomy='read_only',
        builtin_tools=['bash'],
    )
    assert message.startswith('Agent not saved')
    assert 'bad' not in {agent.id for agent in get_state().agents}


def test_add_or_update_agent_resolves_custom_tools():
    """Custom tools are referenced by name and stored as the compiled functions."""
    emit_custom_tool(
        name='echo_tool',
        source=ECHO_TOOL_SOURCE,
        test_cases=[{'input': {'message': 'x'}, 'expected_contains': 'x'}],
    )
    build_hub_org()
    assert 'Unknown custom tools' in add_or_update_agent(
        agent_id='x',
        name='X',
        role='r',
        unit_id='research',
        tools=['nope'],
    )
    add_or_update_agent(agent_id='researcher', name='R', role='r', unit_id='research', tools=['echo_tool'])
    assert get_state().spec.ai.agent('researcher').tools[0].__name__ == 'echo_tool'
    assert 'used by' in remove_custom_tool('echo_tool')


def test_remove_agent_detaches_it_from_its_unit():
    """Removing an agent takes it out of its unit."""
    build_hub_org()
    assert remove_agent('researcher').startswith("Removed agent 'researcher'")
    assert get_state().spec.ai.root.members == []
    assert remove_agent('ghost') == "No agent named 'ghost'."


def test_remove_unit_refuses_until_empty():
    """A unit holding agents cannot be removed."""
    build_hub_org()
    assert 'still holds' in remove_unit('research')


def test_set_pipeline_step_sets_review_gate():
    """A pipeline step gets its instruction and review gate."""
    add_or_update_unit(unit_id='content', name='Content', model='pipeline')
    add_or_update_agent(agent_id='drafter', name='Drafter', role='Drafts.', unit_id='content')
    set_pipeline_step(unit_id='content', member_id='drafter', instruction='Write it.', review='human')
    step = get_state().spec.ai.root.members[0]
    assert (step.member, step.review, step.instruction) == ('drafter', 'human', 'Write it.')


def test_add_or_update_trigger_rejects_invalid_cron_and_keeps_spec():
    """An invalid trigger returns an error and leaves the triggers unchanged."""
    build_hub_org()
    message = add_or_update_trigger(
        trigger_id='nightly',
        kind='schedule',
        target='research',
        prompt='Go.',
        cron='not cron',
    )
    assert "Trigger 'nightly' not saved" in message
    assert get_state().spec.operations.triggers == []


def test_add_or_update_and_remove_trigger():
    """A valid schedule is saved against an existing target and can be removed."""
    build_hub_org()
    add_or_update_trigger(
        trigger_id='weekly',
        kind='schedule',
        target='research',
        prompt='Report for {now}.',
        cron='0 8 * * MON',
    )
    assert [t.id for t in get_state().spec.operations.triggers] == ['weekly']
    assert "not saved" in add_or_update_trigger(
        trigger_id='x',
        kind='event',
        target='ghost',
        prompt='Go.',
        event='custom.x',
    )
    assert remove_trigger('weekly') == "Removed trigger 'weekly'."


def test_operations_tools_update_their_sections():
    """Budget, lifecycle, approvers, governance, notifications and run policy land in operations."""
    assert set_budget(monthly_usd=120).startswith('Budget set')
    set_lifecycle(initial='active', trial_max_runs=10)
    set_approvers(['ops@acme.com'])
    set_governance(approval_required=['code_execution'])
    set_notifications(channels=['email'], email_to=['ops@acme.com'])
    set_run_policy(retries=2, on_failure='escalate')
    ops = get_state().spec.operations
    assert (ops.budget.monthly_usd, ops.lifecycle.initial, ops.governance.approvers) == (
        120,
        'active',
        ['ops@acme.com'],
    )
    assert ops.governance.approval_required == ['code_execution']
    assert (ops.notifications.channels, ops.runs.retries, ops.runs.on_failure) == (
        ['dashboard', 'email'],
        2,
        'escalate',
    )


def test_operations_tools_return_errors_as_text():
    """Invalid operations values come back as text."""
    assert set_approvers(['nope']).startswith('These do not look like emails')
    assert set_notifications(channels=['webhook']).startswith('Notifications not saved')
    assert set_run_policy(on_failure='handoff').startswith('Run policy not saved')


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


_FIXTURE_PRINCIPLE_BODY = (
    'Test fixture: principle paragraph long enough to satisfy the 200-char Stage-1 '
    'minimum. It explains the concrete trade-offs the principle implies for day-to-day '
    'decisions, references parameters as {min_sources}, and grounds the rule in the '
    'actual work the group does.'
)


def test_add_or_update_principle_section_adds_a_section():
    """A new principle section appears under `knowledge.principles.sections`."""
    seed_discovery()  # bypass the Stage-1 discovery gate
    add_or_update_principle_section(section_id='mission', title='Mission', body=_FIXTURE_PRINCIPLE_BODY)
    sections = get_state().spec.knowledge.principles.sections
    assert sections[0].id == 'mission'
    assert '{min_sources}' in sections[0].body


def test_remove_principle_section_drops_it():
    """Removing by `id` shrinks the sections list."""
    seed_discovery()
    add_or_update_principle_section(section_id='s1', title='T', body=_FIXTURE_PRINCIPLE_BODY)
    msg = remove_principle_section('s1')
    assert 'Removed' in msg


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
    assert [var.name for var in env.required] == ['ANTHROPIC_API_KEY', 'AMQP_URL', 'GOOGLE_API_KEY']
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


def test_emit_custom_tool_registers_validated_source():
    """A valid emission appears in `state.custom_tools`."""
    msg = emit_custom_tool(name='echo_tool', source=VALID_TOOL_SOURCE, test_cases=VALID_TEST_CASES)
    assert msg.startswith('Registered')
    custom = get_state().custom_tools
    assert len(custom) == 1
    assert custom[0].name == 'echo_tool'


def test_emit_custom_tool_updates_existing_tool_by_name():
    """Re-emitting with the same name replaces the source."""
    emit_custom_tool(name='echo_tool', source=VALID_TOOL_SOURCE, test_cases=VALID_TEST_CASES)
    new_source = VALID_TOOL_SOURCE.replace('return message', 'return message + "!"')
    msg = emit_custom_tool(name='echo_tool', source=new_source, test_cases=VALID_TEST_CASES)
    assert msg.startswith('Updated')
    assert '+ "!"' in get_state().custom_tools[0].source


def test_emit_custom_tool_runs_supplied_smoke_test_cases():
    """A passing smoke case keeps the tool; a failing one rejects it and leaves state untouched."""
    ok = emit_custom_tool(
        name='echo_tool',
        source=VALID_TOOL_SOURCE,
        test_cases=[{'input': {'message': 'pong'}, 'expected_contains': 'pong'}],
    )
    assert ok.startswith('Registered')

    bad = emit_custom_tool(
        name='other_tool',
        source=VALID_TOOL_SOURCE.replace('echo_tool', 'other_tool'),
        test_cases=[{'input': {'message': 'hello'}, 'expected_equals': 'pong'}],
    )
    assert 'Validation failed' in bad
    names = {t.name for t in get_state().custom_tools}
    assert names == {'echo_tool'}  # 'other_tool' was rejected


def test_emit_custom_tool_returns_a_message_on_validation_failure():
    """A bad source returns an error message; state is not mutated."""
    msg = emit_custom_tool(name='broken', source='async def broken(:', test_cases=VALID_TEST_CASES)
    assert 'Validation failed' in msg
    assert get_state().custom_tools == []


def test_emit_custom_tool_rejects_when_test_cases_omitted_as_empty_list():
    """The bare emit path without smoke cases is rejected so placeholders cannot sneak through."""
    msg = emit_custom_tool(name='echo_tool', source=VALID_TOOL_SOURCE, test_cases=[])
    assert 'requires at least one test case' in msg
    assert get_state().custom_tools == []


def test_emit_custom_tool_rejects_placeholder_body_with_notimplementederror():
    """A body that raises NotImplementedError is rejected even with a passing-looking test case."""
    source = '\n'.join(
        [
            'async def stub_tool() -> str:',
            '    """Configure later."""',
            '    raise NotImplementedError("configure foo")',
        ],
    )
    msg = emit_custom_tool(
        name='stub_tool',
        source=source,
        test_cases=[{'input': {}, 'expected_raises': 'NotImplementedError'}],
    )
    assert 'NotImplementedError' in msg  # the validator names the rejected pattern
    assert get_state().custom_tools == []


def test_remove_custom_tool_drops_a_registered_tool():
    """Removing by name shrinks the custom tools list."""
    emit_custom_tool(name='echo_tool', source=VALID_TOOL_SOURCE, test_cases=VALID_TEST_CASES)
    assert remove_custom_tool('echo_tool').startswith('Removed')
    assert get_state().custom_tools == []


def test_remove_custom_tool_returns_not_found_for_unknown_name():
    """Removing a tool that was never registered is a safe no-op."""
    assert 'No custom tool' in remove_custom_tool('never_registered')


_LONG_DISCOVERY = {
    'what_the_group_does': (
        'Curates research on transformer interpretability and ships weekly briefs to '
        'product teams. Runs literature surveys + structured digests every Monday.'
    ),
    'who_serves': (
        'Internal product teams (4 squads on the model-evaluation side) and external '
        'ML researchers who follow the public briefs published each quarter.'
    ),
    'concrete_tasks_owned': (
        'Survey new papers + preprints; classify by sub-domain; distil 5-bullet '
        'takeaways; cite-check claims against sources; assemble the weekly brief.'
    ),
    'typical_flow': (
        'Topic arrives via Slack -> agents search arXiv + Semantic Scholar -> shortlist '
        '5-8 papers -> distil -> brief drafted -> reviewer signs off -> publish.'
    ),
    'business_context': (
        'Internal research-ops team inside a model-evaluation org, funded by the '
        'evaluation program; competes with manual literature reviews done by PhDs.'
    ),
    'current_pain_or_alternative': (
        'Today a single PhD spends 2-3 weeks per topic; we want to compress this to 48 '
        'hours so the team can cover 10x more topics per quarter without hiring.'
    ),
}

_LONG_PRINCIPLE_BODY = (
    'Test fixture: This principle states that every brief is grounded in cited sources, '
    'not the agent\'s own paraphrase, so reviewers can verify claims in under five '
    'minutes. In practice it means every bullet links to a paper or report; when no '
    'source supports a claim, the agent flags it as inference rather than fact.'
)


def test_record_discovery_summary_unlocks_principle_section_drafting():
    """A successful `record_discovery_summary` call lets the agent draft principle sections."""
    msg = record_discovery_summary(**_LONG_DISCOVERY, user_confirmed=True)
    assert 'Recorded' in msg
    # Now the principle gate is open. Body must be 200+ chars too.
    ack = add_or_update_principle_section(section_id='mission', title='Mission', body=_LONG_PRINCIPLE_BODY)
    assert ack.startswith('Added')


def test_record_discovery_summary_rejects_short_fields():
    """Each text field needs at least 100 characters; thin content is rejected."""
    msg = record_discovery_summary(
        what_the_group_does='Sells stuff.',
        who_serves='People online.',
        concrete_tasks_owned='Things.',
        typical_flow='They buy.',
        business_context='Online.',
        current_pain_or_alternative='Nothing.',
        user_confirmed=True,
    )
    assert 'REJECTED' in msg
    assert "'what_the_group_does'" in msg
    assert "'who_serves'" in msg
    assert "'concrete_tasks_owned'" in msg
    assert "'current_pain_or_alternative'" in msg


def test_record_discovery_summary_rejects_when_user_not_confirmed():
    """Without `user_confirmed=True`, the tool refuses and tells the agent to ask first."""
    msg = record_discovery_summary(**_LONG_DISCOVERY, user_confirmed=False)
    assert 'REJECTED' in msg
    assert 'user_confirmed' in msg


def test_add_or_update_principle_section_rejects_short_body_in_stage1():
    """Stage-1 principle bodies must be 200+ chars - one-line slogans are blocked."""
    seed_discovery()
    msg = add_or_update_principle_section(section_id='m', title='Mission', body='Quality matters.')
    assert 'too short' in msg
    assert 'paragraph' in msg


def test_set_org_identity_not_in_discover_agent_toolset():
    """The Discover agent's narrow tool slice excludes `set_org_identity` entirely.

    The cross-stage gate that used to live in `_check_stage_gates_for_org_identity` is
    gone: with per-stage agents, drift is impossible at the *tool* layer. Discover's agent
    cannot invoke a tool it does not have.
    """
    assert set_org_identity not in STAGE_TOOLS['discover']
    assert set_org_identity in STAGE_TOOLS['configure']


def test_set_org_identity_short_description_in_stage2_is_rejected():
    """In Stage 2 a too-short description is rejected with a length hint."""
    advance_to_configure_stage()
    msg = set_org_identity(description='Too short.')
    assert 'too short' in msg
    assert '200' in msg


def test_set_org_identity_long_description_in_stage2_is_accepted():
    """In Stage 2 a 200+-char description is accepted."""
    advance_to_configure_stage()
    msg = set_org_identity(description=_LONG_DESC)
    assert msg.startswith('Updated')
    assert get_state().spec.org.description == _LONG_DESC


def test_add_or_update_principle_section_blocked_in_stage1_without_discovery():
    """The gate returns an instructive error instead of silently drafting."""
    msg = add_or_update_principle_section(section_id='mission', title='Mission', body='Anything')
    assert 'Blocked' in msg
    assert 'record_discovery_summary' in msg
    # And the spec is unchanged.
    assert get_state().spec.knowledge.principles.sections == []


def test_get_current_spec_returns_spec_source():
    """`get_current_spec` returns the spec.py source of the working spec."""
    assert get_current_spec().startswith('"""Spec for Untitled org."""')


def test_get_current_spec_reflects_mutations():
    """A subsequent state mutation is visible through `get_current_spec`."""
    advance_to_configure_stage()
    set_org_identity(slug='research-org')
    assert "slug='research-org'" in get_current_spec()


_VALID_SKILL_MD = '\n'.join(
    [
        '---',
        'name: negotiation-playbook',
        'description: Steps for negotiating with a counterparty.',
        '---',
        '',
        '# Negotiation playbook',
        '',
        '1. Anchor high.',
    ],
)


def test_emit_custom_skill_registers_validated_skill():
    """A valid SKILL.md is stored in `state.custom_skills`."""
    msg = emit_custom_skill(name='negotiation-playbook', skill_md=_VALID_SKILL_MD)
    assert msg.startswith('Registered')
    skills = get_state().custom_skills
    assert len(skills) == 1
    assert skills[0].name == 'negotiation-playbook'


def test_emit_custom_skill_updates_existing_skill_by_name():
    """Re-emitting with the same name overwrites in place."""
    emit_custom_skill(name='negotiation-playbook', skill_md=_VALID_SKILL_MD)
    new_md = _VALID_SKILL_MD.replace('Anchor high.', 'Open with the high anchor.')
    emit_custom_skill(name='negotiation-playbook', skill_md=new_md)
    skills = get_state().custom_skills
    assert len(skills) == 1
    assert 'Open with the high anchor.' in skills[0].skill_md


def test_emit_custom_skill_rejects_invalid_skill_md():
    """Validation fails surface to the caller; the skill is NOT registered."""
    msg = emit_custom_skill(name='bad-skill', skill_md='no frontmatter here')
    assert 'YAML frontmatter' in msg or 'failed' in msg.lower()
    assert get_state().custom_skills == []


def test_remove_custom_skill_drops_a_registered_skill():
    """Removing by name shrinks the custom skills list."""
    emit_custom_skill(name='negotiation-playbook', skill_md=_VALID_SKILL_MD)
    assert remove_custom_skill('negotiation-playbook').startswith('Removed')
    assert get_state().custom_skills == []


def test_remove_custom_skill_returns_not_found_for_unknown_name():
    """Removing a skill that was never registered is a safe no-op."""
    assert 'No custom skill' in remove_custom_skill('never-registered')


def test_advance_to_next_stage_reports_blockers_when_unsatisfied():
    """The first stage's blockers gate the advance; the returned message lists them."""
    assert get_state().stage == 'discover'
    msg = advance_to_next_stage()
    assert 'Cannot advance' in msg
    assert get_state().stage == 'discover'


def test_advance_to_next_stage_moves_cursor_when_blockers_clear():
    """Once blockers are resolved, the cursor advances and the message confirms it."""
    seed_discovery()
    msg = advance_to_next_stage()
    assert msg.startswith('Advanced from Stage 1')
    assert get_state().stage == 'configure'


def test_advance_to_next_stage_at_the_final_stage_is_a_noop():
    """Trying to advance past the terminal stage returns the already-final message."""
    get_state().stage = 'handoff'
    msg = advance_to_next_stage()
    assert 'final stage' in msg.lower()
    assert get_state().stage == 'handoff'
