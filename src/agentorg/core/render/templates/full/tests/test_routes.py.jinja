"""HTTP route tests for the rendered org's agentorg-specific endpoints."""

import pytest


async def test_get_config_returns_app_metadata(client) -> None:  # noqa: ANN001
    """`GET /api/v1/config` returns the app name, icon, and description block."""
    r = await client.get('/api/v1/config')
    assert r.status_code == 200
    body = r.json()
    assert 'app_name' in body
    assert 'app_icon' in body
    assert 'app_description' in body


async def test_get_config_includes_sidebar_groups(client) -> None:  # noqa: ANN001
    """`GET /api/v1/config` surfaces the UI's agent and workflow groups."""
    body = (await client.get('/api/v1/config')).json()
    assert isinstance(body.get('agent_groups'), list)
    assert isinstance(body.get('workflow_groups'), list)


async def test_get_config_includes_parameters_and_principles(client) -> None:  # noqa: ANN001
    """`GET /api/v1/config` surfaces the org parameters and principle sections from the spec."""
    body = (await client.get('/api/v1/config')).json()
    assert isinstance(body.get('parameters'), list)
    assert 'principles' in body
    assert isinstance(body['principles'].get('sections'), list)


async def test_get_config_includes_knowledge_types(client) -> None:  # noqa: ANN001
    """`GET /api/v1/config` surfaces the knowledge type catalogue from the spec."""
    body = (await client.get('/api/v1/config')).json()
    assert isinstance(body.get('types'), list)


async def test_get_setup_returns_steps(client) -> None:  # noqa: ANN001
    """`GET /api/v1/setup` returns the spec's setup steps."""
    r = await client.get('/api/v1/setup')
    assert r.status_code == 200
    assert isinstance(r.json().get('steps'), list)


@pytest.mark.usefixtures('needs_memory')
async def test_get_parameters_returns_defaults_when_not_set_up(client) -> None:  # noqa: ANN001
    """`GET /api/v1/parameters` returns an empty `parameters` dict before the org is set up."""
    r = await client.get('/api/v1/parameters')
    assert r.status_code == 200
    assert r.json() == {'parameters': {}}


@pytest.mark.usefixtures('needs_memory')
async def test_post_parameters_reset_succeeds(client) -> None:  # noqa: ANN001
    """`POST /api/v1/parameters/reset` is idempotent (works even when nothing exists)."""
    r = await client.post('/api/v1/parameters/reset')
    assert r.status_code == 200
    assert r.json().get('status') == 'reset'


@pytest.mark.usefixtures('needs_memory')
async def test_get_knowledge_returns_list(client) -> None:  # noqa: ANN001
    """`GET /api/v1/knowledge` returns a list."""
    r = await client.get('/api/v1/knowledge')
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.usefixtures('needs_memory')
async def test_get_knowledge_unit_returns_404_for_unknown(client) -> None:  # noqa: ANN001
    """An unknown knowledge unit produces a 404."""
    r = await client.get('/api/v1/knowledge/policy/does-not-exist')
    assert r.status_code == 404


@pytest.mark.usefixtures('needs_memory')
async def test_get_knowledge_search_returns_list(client) -> None:  # noqa: ANN001
    """`GET /api/v1/knowledge/search` returns a (possibly empty) list."""
    r = await client.get('/api/v1/knowledge/search?query=anything')
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.usefixtures('needs_memory')
async def test_get_knowledge_filters_by_agent_id(client) -> None:  # noqa: ANN001
    """`GET /api/v1/knowledge?agent_id=...` returns a list scoped to that agent."""
    r = await client.get('/api/v1/knowledge?agent_id=does-not-exist')
    assert r.status_code == 200
    assert r.json() == []
