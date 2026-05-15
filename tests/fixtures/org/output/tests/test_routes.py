"""HTTP route tests for the rendered org's agentorg-specific endpoints."""

import pytest


async def test_get_config_returns_app_metadata(client) -> None:  # noqa: ANN001
    """`GET /api/config` returns the app name/icon/description block."""
    r = await client.get('/api/config')
    assert r.status_code == 200
    body = r.json()
    assert 'app_name' in body
    assert 'app_icon' in body
    assert 'app_description' in body


async def test_get_config_includes_sidebar_groups(client) -> None:  # noqa: ANN001
    """`GET /api/config` surfaces the UI's agent/workflow groups."""
    body = (await client.get('/api/config')).json()
    assert isinstance(body.get('agent_groups'), list)
    assert isinstance(body.get('workflow_groups'), list)


async def test_get_setup_guide_returns_steps(client) -> None:  # noqa: ANN001
    """`GET /api/setup-guide` returns the spec's setup steps."""
    r = await client.get('/api/setup-guide')
    assert r.status_code == 200
    assert isinstance(r.json().get('steps'), list)


async def test_get_learnings_returns_list(client) -> None:  # noqa: ANN001
    """`GET /api/learnings` returns a list (empty — learnings aren't tracked in this pass)."""
    r = await client.get('/api/learnings')
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.usefixtures('needs_memory')
async def test_get_state_returns_defaults_for_fresh_user(client) -> None:  # noqa: ANN001
    """`GET /api/state` returns `configured: False` for a never-set-up user."""
    r = await client.get('/api/state?user_id=fresh_user')
    assert r.status_code == 200
    assert r.json().get('configured') is False


@pytest.mark.usefixtures('needs_memory')
async def test_post_reset_succeeds(client) -> None:  # noqa: ANN001
    """`POST /api/reset` is idempotent — works even when nothing exists."""
    r = await client.post('/api/reset?user_id=temp_user')
    assert r.status_code == 200
    assert r.json().get('status') == 'reset'


@pytest.mark.usefixtures('needs_memory')
async def test_get_documents_returns_list(client) -> None:  # noqa: ANN001
    """`GET /api/documents` returns a list."""
    r = await client.get('/api/documents')
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.usefixtures('needs_memory')
async def test_get_knowledge_is_alias_for_documents(client) -> None:  # noqa: ANN001
    """`GET /api/knowledge` returns the same shape as `/api/documents`."""
    r = await client.get('/api/knowledge')
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.usefixtures('needs_memory')
async def test_get_document_returns_404_for_unknown(client) -> None:  # noqa: ANN001
    """An unknown document produces a 404."""
    r = await client.get('/api/document/policy/does-not-exist')
    assert r.status_code == 404


@pytest.mark.usefixtures('needs_memory')
async def test_get_documents_search_returns_list(client) -> None:  # noqa: ANN001
    """`GET /api/documents/search` returns a (possibly empty) list."""
    r = await client.get('/api/documents/search?query=anything')
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.usefixtures('needs_memory')
async def test_get_agent_reports_returns_grouped_list(client) -> None:  # noqa: ANN001
    """`GET /api/agent-reports` returns `{agents: [...]}` (initially empty)."""
    r = await client.get('/api/agent-reports')
    assert r.status_code == 200
    assert isinstance(r.json().get('agents'), list)


@pytest.mark.usefixtures('needs_memory')
async def test_get_agent_report_returns_404_for_unknown(client) -> None:  # noqa: ANN001
    """An unknown report name produces a 404."""
    r = await client.get('/api/agent-reports/does-not-exist')
    assert r.status_code == 404
