"""Tests for the agents module."""

import pytest
from pydantic import ValidationError

from agentorg.core.spec import Agent, McpServer, Output, Step, Unit


def _agent(**fields: object) -> Agent:
    return Agent.model_validate({'id': 'a', 'name': 'A', 'role': 'Does things.', **fields})


def test_agent_defaults_to_sonnet_propose_ephemeral_session() -> None:
    """An agent with only identity fields gets the documented defaults."""
    agent = _agent()
    assert (agent.model, agent.autonomy, agent.workspace, agent.memory, agent.replicas) == (
        'sonnet',
        'propose',
        'ephemeral',
        'session',
        1,
    )
    assert (agent.limits.max_turns, agent.limits.timeout_s) == (30, 600)


def test_agent_rejects_non_claude_model() -> None:
    """A provider-prefixed model string is rejected."""
    with pytest.raises(ValidationError):
        _agent(model='google:gemini-2.5-flash')


def test_agent_read_only_default_tools() -> None:
    """A read_only agent without `builtin_tools` gets exactly the research tools."""
    assert _agent(autonomy='read_only').builtin_tools == ['read', 'glob', 'grep', 'web_search', 'web_fetch', 'todo']


def test_agent_autonomous_default_tools_include_bash() -> None:
    """Only autonomous agents get `bash` by default."""
    assert 'bash' in (_agent(autonomy='autonomous').builtin_tools or [])
    assert 'bash' not in (_agent(autonomy='act').builtin_tools or [])


def test_agent_rejects_write_grant_for_read_only() -> None:
    """Granting `bash` to a read_only agent is a contradiction."""
    with pytest.raises(ValidationError, match='read_only'):
        _agent(autonomy='read_only', builtin_tools=['bash'])


def test_agent_rejects_bad_id() -> None:
    """Ids are lowercase kebab-case."""
    with pytest.raises(ValidationError):
        _agent(id='Bad_Id')


def test_mcp_server_stdio_needs_command() -> None:
    """A stdio server without a command is rejected."""
    with pytest.raises(ValidationError, match='command'):
        McpServer(name='crm', transport='stdio')


def test_mcp_server_http_needs_url() -> None:
    """An http server without a url is rejected."""
    with pytest.raises(ValidationError, match='url'):
        McpServer(name='crm', transport='http')


def test_mcp_server_keeps_tool_filters() -> None:
    """Allowed, read and outbound tool lists are stored as given."""
    server = McpServer(
        name='crm',
        transport='http',
        url='https://crm.example/mcp',
        env=['CRM_TOKEN'],
        allowed_tools=['search_issues'],
        read_tools=['search_issues'],
    )
    assert (server.allowed_tools, server.read_tools, server.env) == (
        ['search_issues'],
        ['search_issues'],
        ['CRM_TOKEN'],
    )


def test_output_json_needs_schema() -> None:
    """A json output without a schema is rejected."""
    with pytest.raises(ValidationError, match='json_schema'):
        Output(format='json')


@pytest.mark.parametrize(
    ('fields', 'match'),
    [
        ({'model': 'solo', 'members': ['a', 'b']}, 'exactly one agent'),
        ({'model': 'hub', 'members': ['a']}, 'needs a `lead`'),
        ({'model': 'hub', 'lead': 'a', 'members': ['a', 'b']}, 'must not also be a member'),
        ({'model': 'pipeline', 'lead': 'a', 'members': ['b']}, 'no lead'),
        ({'model': 'hub', 'lead': 'l', 'members': [{'member': 'a'}]}, 'only allowed in a pipeline'),
        ({'model': 'council', 'decision': 'majority', 'members': ['a', 'b', 'c', 'd']}, 'odd number'),
        ({'model': 'council', 'decision': 'judge', 'members': ['a', 'b', 'c']}, 'needs a `lead`'),
        ({'model': 'council', 'members': ['a', 'b', 'c']}, '3 to 9 members'),
        ({'model': 'hub', 'lead': 'l', 'members': [f'm{i}' for i in range(15)]}, 'allows 12'),
        ({'model': 'democracy', 'members': ['a']}, 'model'),
    ],
)
def test_unit_rejects_invalid_model_shapes(fields: dict[str, object], match: str) -> None:
    """Each model's structural rule is enforced at validation time."""
    with pytest.raises(ValidationError, match=match):
        Unit.model_validate({'id': 'u', 'name': 'U', **fields})


def test_unit_pool_allows_one_hundred_members() -> None:
    """Pools allow up to 100 members because their dispatcher is code."""
    unit = Unit(id='u', name='U', model='pool', members=[f'm{i}' for i in range(100)])
    assert len(unit.members) == 100


def test_unit_iter_units_and_depth_cover_nested_units() -> None:
    """Nested units are yielded depth first and counted as levels."""
    inner = Unit(id='inner', name='Inner', model='solo', members=['a'])
    root = Unit(id='root', name='Root', model='pipeline', members=[Step(member=inner, review='human'), 'b'])
    assert [unit.id for unit in root.iter_units()] == ['root', 'inner']
    assert root.depth() == 2
    assert root.member_refs == [inner, 'b']
