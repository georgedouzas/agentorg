"""Tests for the writer module."""

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from agentorg.core.spec import Org, Spec
from agentorg.master import (
    add_or_update_agent,
    add_or_update_knowledge_type,
    add_or_update_parameter,
    add_or_update_principle_section,
    add_or_update_team,
    add_or_update_workflow,
    emit_custom_tool,
    finalize_spec,
    get_state,
    python_literal,
    render_spec,
    set_org_identity,
)

from .conftest import advance_to_configure_stage, seed_discovery

VALID_TOOL_SOURCE = '\n'.join(
    [
        '"""A simple custom tool that echoes its input."""',
        '',
        'async def echo_tool(message: str) -> str:',
        '    """Return the message unchanged - used as a smoke test for the sandbox."""',
        '    return message',
    ],
)


def _populate_minimum_viable_spec() -> None:
    advance_to_configure_stage()  # identity fields belong to Stage 2
    set_org_identity(
        name='Research Org',
        slug='research-org',
        package_name='research_org',
        description=(
            'Test fixture: a substantive multi-sentence description clearing the '
            'Stage-2 200-char minimum so the writer + finalize_spec tests can drive '
            'a complete spec round-trip without tripping the description gate.'
        ),
        repository='https://github.com/example/research-org',
        admin_name='Research Authors',
        admin_email='authors@example.com',
        visibility='private',
    )
    add_or_update_agent(
        agent_id='researcher',
        name='Researcher',
        role='Gather source material on a topic and write a structured research document.',
        in_scope=['Source gathering', 'Drafting research docs'],
        workflow=['Restate the topic.', 'Gather at least three sources.', 'Draft the doc.'],
        tools=['write_knowledge', 'read_knowledge'],
    )


def _import_spec_from_path(path: Path) -> ModuleType:
    """Import the rendered spec.py as a module."""
    spec_module = importlib.util.spec_from_file_location('rendered_spec_under_test', path)
    assert spec_module is not None
    module = importlib.util.module_from_spec(spec_module)
    sys.modules['rendered_spec_under_test'] = module
    assert spec_module.loader is not None
    spec_module.loader.exec_module(module)
    return module


def test_python_literal_renders_primitives_via_repr():
    """Strings, ints, bools, None come out as Python's `repr()` would format them."""
    assert python_literal('hello') == "'hello'"
    assert python_literal(42) == '42'
    assert python_literal(True) == 'True'
    assert python_literal(None) == 'None'


def test_python_literal_renders_pydantic_models_as_constructor_calls():
    """A Pydantic model becomes `ClassName(field=value)` source."""
    org = Org(
        name='X',
        slug='x',
        package_name='x',
        description='Y',
        repository='r',
        admin_name='a',
        admin_email='a@b.c',
        visibility='private',
        budget='medium',
    )
    source = python_literal(org)
    assert source.startswith('Org(')
    assert "name='X'" in source
    assert "visibility='private'" in source


def test_render_spec_produces_syntactically_valid_python():
    """The output parses as Python source - no syntax errors."""
    _populate_minimum_viable_spec()
    source = render_spec(get_state().spec)
    ast.parse(source)  # raises SyntaxError if invalid


def test_render_spec_emits_one_make_agent_call_per_agent():
    """Each `AgentSpec` becomes a top-level `<id> = make_agent(...)` assignment."""
    _populate_minimum_viable_spec()
    source = render_spec(get_state().spec)
    assert 'researcher = make_agent(' in source


def test_render_spec_references_imported_tools_as_bare_identifiers():
    """`tools=['write_knowledge']` renders as `tools=[write_knowledge]`, with a matching import."""
    _populate_minimum_viable_spec()
    source = render_spec(get_state().spec)
    assert 'from agentorg.core.agents.tools import read_knowledge, write_knowledge' in source
    assert 'tools=[write_knowledge, read_knowledge]' in source


def test_render_spec_emits_skills_via_default_skills_refs_catalog(tmp_path: Path):
    """`skills=['superpowers']` renders as `GitHubSkills(**DEFAULT_SKILLS_REFS['superpowers'])`."""
    _populate_minimum_viable_spec()
    add_or_update_agent(
        agent_id='analyst',
        name='Analyst',
        role='Skill-using analyst.',
        in_scope=['Reasoning over research docs.'],
        workflow=['Read docs.', 'Reason.', 'Write report.'],
        skills=['superpowers'],
    )
    target = tmp_path / 'spec.py'
    finalize_spec(target)
    source = target.read_text()
    assert 'from agentorg.core.agents.framework.agno import GitHubSkills, make_agent' in source
    assert 'from agentorg.core.agents.skills import DEFAULT_SKILLS_REFS' in source
    assert "GitHubSkills(**DEFAULT_SKILLS_REFS['superpowers'])" in source

    module = _import_spec_from_path(target)
    assert len(module.spec.ai.agents) == 2  # researcher + analyst


def test_render_spec_ai_agents_uses_bare_identifiers_not_agentspec_constructors():
    """`spec.ai.agents` references module-level agents by name, not as inline `AgentSpec(...)`."""
    _populate_minimum_viable_spec()
    source = render_spec(get_state().spec)
    assert 'agents=[researcher]' in source
    assert 'AgentSpec(' not in source


def test_finalize_spec_writes_a_file_that_imports_and_yields_a_real_spec(tmp_path: Path):
    """End-to-end: finalize -> import the file -> the `spec` symbol is a `Spec` with one agent."""
    _populate_minimum_viable_spec()
    target = tmp_path / 'spec.py'
    finalize_spec(target)

    assert target.exists()
    module = _import_spec_from_path(target)
    assert isinstance(module.spec, Spec)
    assert module.spec.org.name == 'Research Org'
    assert len(module.spec.ai.agents) == 1


@pytest.mark.parametrize('overhead_field', ['package_name', 'admin_name'])
def test_finalize_spec_round_trips_provided_org_fields(tmp_path: Path, overhead_field: str):
    """Org fields set during the interview survive the render -> import round trip."""
    _populate_minimum_viable_spec()
    target = tmp_path / 'spec.py'
    finalize_spec(target)

    module = _import_spec_from_path(target)
    assert getattr(module.spec.org, overhead_field) == getattr(get_state().spec.org, overhead_field)


def _populate_full_spec() -> None:
    """Mirror the `org` fixture: researcher + analyst, a team, a workflow, parameters, knowledge."""
    _populate_minimum_viable_spec()
    add_or_update_agent(
        agent_id='analyst',
        name='Analyst',
        role='Synthesise research into a final report.',
        in_scope=['Reading research docs'],
        workflow=['List docs.', 'Read.', 'Draft.'],
        tools=['read_knowledge', 'list_knowledge'],
    )
    add_or_update_team(
        team_id='research-team',
        name='Research Team',
        role='Coordinate research and analysis.',
        workflow=['Delegate to researcher.', 'Hand off to analyst.'],
        member_ids=['researcher', 'analyst'],
    )
    add_or_update_workflow(
        workflow_id='pipeline',
        name='Research Pipeline',
        steps=[
            {'name': 'Gather', 'agent_id': 'researcher'},
            {'name': 'Analyse', 'agent_id': 'analyst', 'requires_output_review': True},
        ],
        description='Gather then analyse.',
    )
    add_or_update_parameter(name='min_sources', param_type='int', default=3, label='Minimum Sources')
    add_or_update_knowledge_type(knowledge_type_id='research', label='Research Docs')
    seed_discovery()  # bypass the Stage-1 discovery gate before drafting principles
    add_or_update_principle_section(
        section_id='mission',
        title='Mission',
        body=(
            'Test fixture: principle body long enough to clear the 200-char Stage-1 minimum. '
            'Cite at least {min_sources} sources per claim; when no source supports a claim, '
            'flag it as inference rather than fact so the reviewer can verify quickly.'
        ),
    )


def test_finalize_spec_renders_a_full_org_with_teams_workflows_parameters_and_knowledge(tmp_path: Path):
    """End-to-end: a fully populated state -> finalize -> import yields a `Spec` with all sections set."""
    _populate_full_spec()
    target = tmp_path / 'spec.py'
    finalize_spec(target)
    module = _import_spec_from_path(target)
    assert isinstance(module.spec, Spec)
    assert len(module.spec.ai.agents) == 2
    assert len(module.spec.ai.teams) == 1
    assert len(module.spec.ai.workflows) == 1
    assert module.spec.parameters[0].name == 'min_sources'
    assert module.spec.knowledge.types[0].id == 'research'
    assert module.spec.knowledge.principles.sections[0].id == 'mission'


def test_finalize_spec_inlines_custom_tools_into_the_rendered_file(tmp_path: Path):
    """A registered custom tool appears verbatim at the top of spec.py and is callable after import."""
    emit_custom_tool(
        name='echo_tool',
        source=VALID_TOOL_SOURCE,
        test_cases=[{'input': {'message': 'pong'}, 'expected_contains': 'pong'}],
    )
    _populate_minimum_viable_spec()
    add_or_update_agent(
        agent_id='echoer',
        name='Echoer',
        role='Echo user input.',
        in_scope=['Echoing'],
        workflow=['Receive a message.', 'Echo it.'],
        tools=['echo_tool'],
    )
    target = tmp_path / 'spec.py'
    finalize_spec(target)

    rendered = target.read_text()
    assert 'async def echo_tool' in rendered
    assert 'tools=[echo_tool]' in rendered
    assert rendered.index('async def echo_tool') < rendered.index('echoer = make_agent')

    module = _import_spec_from_path(target)
    assert module.echo_tool.__name__ == 'echo_tool'
