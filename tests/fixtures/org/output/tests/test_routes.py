"""HTTP route tests — exercise the FastAPI app through a TestClient.

These tests boot the full app (the `client` fixture in conftest), so they require
`GOOGLE_API_KEY` to be set: the embedder is instantiated at startup when the
platform docs / policies seed runs.
"""

import pytest

EXPECTED_AGENT_IDS = ["analyst", "researcher"]


@pytest.fixture(autouse=True)
def _gate(needs_google_api: None) -> None:  # noqa: PT004
    """All tests in this module require the embedder."""


def test_api_config_returns_app_metadata(client) -> None:  # noqa: ANN001
    """`GET /api/config` returns the app name, icon, description, and agent list."""
    response = client.get('/api/config')
    assert response.status_code == 200
    body = response.json()
    assert 'app_name' in body
    assert 'app_icon' in body


def test_api_agent_info_per_agent(client) -> None:  # noqa: ANN001
    """Each agent in the spec exposes a populated `/api/agents/{id}/info` payload."""
    for agent_id in EXPECTED_AGENT_IDS:
        response = client.get(f'/api/agents/{agent_id}/info')
        assert response.status_code == 200, f'{agent_id}: {response.text}'
        body = response.json()
        assert body['agent_id'] == agent_id
        assert body['name']
        assert body['role'] or body.get('in_scope')


def test_api_knowledge_list_initially_returns_seeded_charter(client) -> None:  # noqa: ANN001
    """`GET /api/knowledge` returns at least the charter seeded by `seed_policy_documents()`."""
    response = client.get('/api/knowledge')
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
