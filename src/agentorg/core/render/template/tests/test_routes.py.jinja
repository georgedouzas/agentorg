"""HTTP route tests — exercise the agentorg-specific endpoints in `app.routes`.

These boot the full app via the `client` fixture in conftest. Booting no longer instantiates the embedder (agents
are registered as reasoners, not constructed with knowledge), so these tests don't need `GOOGLE_API_KEY`. Agent
invocation / discovery / workflow continuation aren't tested here — those are AgentField's surface, not agentorg's.
"""


def test_get_config_returns_app_metadata(client) -> None:  # noqa: ANN001
    """`GET /api/config` returns the app name/icon/description block."""
    r = client.get('/api/config')
    assert r.status_code == 200
    body = r.json()
    assert 'app_name' in body
    assert 'app_icon' in body
    assert 'app_description' in body


def test_get_config_includes_sidebar_groups(client) -> None:  # noqa: ANN001
    """`GET /api/config` surfaces the UI's agent/workflow groups."""
    body = client.get('/api/config').json()
    assert isinstance(body.get('agent_groups'), list)
    assert isinstance(body.get('workflow_groups'), list)


def test_get_state_returns_defaults_for_fresh_user(client) -> None:  # noqa: ANN001
    """`GET /api/state` returns the charter defaults for a never-set-up user."""
    r = client.get('/api/state?user_id=fresh_user')
    assert r.status_code == 200


def test_get_setup_guide_returns_steps(client) -> None:  # noqa: ANN001
    """`GET /api/setup-guide` returns the spec's setup steps."""
    r = client.get('/api/setup-guide')
    assert r.status_code == 200
    assert isinstance(r.json().get('steps'), list)


def test_post_reset_succeeds(client) -> None:  # noqa: ANN001
    """`POST /api/reset` is idempotent — works even when nothing exists."""
    r = client.post('/api/reset?user_id=temp_user')
    assert r.status_code == 200


def test_get_documents_returns_list(client) -> None:  # noqa: ANN001
    """`GET /api/documents` returns a list (empty on a fresh DB)."""
    r = client.get('/api/documents')
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_knowledge_is_alias_for_documents(client) -> None:  # noqa: ANN001
    """`GET /api/knowledge` returns the same shape as `/api/documents`."""
    r = client.get('/api/knowledge')
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_document_returns_404_for_unknown(client) -> None:  # noqa: ANN001
    """Unknown document produces a 404."""
    r = client.get('/api/document/policy/does-not-exist')
    assert r.status_code == 404


def test_get_documents_search_returns_list(client) -> None:  # noqa: ANN001
    """`GET /api/documents/search` returns a (possibly empty) list — works on both Postgres + SQLite."""
    r = client.get('/api/documents/search?query=anything')
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_learnings_returns_list(client) -> None:  # noqa: ANN001
    """`GET /api/learnings` returns a list (empty initially)."""
    r = client.get('/api/learnings')
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_agent_reports_returns_grouped_list(client) -> None:  # noqa: ANN001
    """`GET /api/agent-reports` returns `{agents: [...]}` (initially empty)."""
    r = client.get('/api/agent-reports')
    assert r.status_code == 200
    assert isinstance(r.json().get('agents'), list)


def test_get_agent_report_returns_404_for_unknown(client) -> None:  # noqa: ANN001
    """An unknown report id produces a 404."""
    r = client.get('/api/agent-reports/999999')
    assert r.status_code == 404
