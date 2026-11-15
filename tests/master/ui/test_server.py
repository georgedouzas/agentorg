"""Tests for the server module."""

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agentorg.master import get_state, reset_state, set_budget, set_org_identity
from agentorg.master.ui import _server as ui_server
from agentorg.master.ui import build_app

from ..conftest import build_hub_org, seed_discovery

_LONG_DESC = (
    'Research Org is a small team that gathers sources on a topic and writes structured '
    'weekly reports for internal product squads. It bridges full literature reviews '
    '(slow) and informal Slack summaries (lossy), with cited claims throughout.'
)


class _FakeAgent:
    """Stand-in for the stage agent that records what it was called with and returns a canned reply."""

    def __init__(self, *, response: str = 'hello back', tool_calls: list[dict[str, str]] | None = None) -> None:
        self.response = response
        self.tool_calls = tool_calls or []
        self.calls: list[str] = []

    async def arun(self, message: str, *_args: object, **_kwargs: object) -> Any:
        self.calls.append(message)
        return SimpleNamespace(content=self.response, tool_calls=self.tool_calls)


@pytest.fixture(autouse=True)
def _reset() -> None:
    """Each test starts from a fresh interview state."""
    reset_state()


KEY = 'master-key'


def _chat(client: TestClient, message: str) -> str:
    """Send one message to the `agentorg` model and return the reply text."""
    body = {'model': 'agentorg', 'messages': [{'role': 'user', 'content': message}]}
    response = client.post('/v1/chat/completions', json=body, headers={'Authorization': f'Bearer {KEY}'})
    assert response.status_code == 200, response.text
    return str(response.json()['choices'][0]['message']['content'])


def test_index_serves_the_html_page():
    """`GET /` returns the bundled index.html (we just look for a sentinel string)."""
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 200
    assert 'AgentOrg' in response.text


def test_get_api_spec_returns_the_seed_state_initially():
    """The fresh interview state surfaces as JSON with placeholder org fields and empty collections."""
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    response = client.get('/api/spec')
    assert response.status_code == 200
    body = response.json()
    assert body['spec']['org']['name'] == 'Untitled org'
    assert body['spec']['ai']['agents'] == []
    assert body['custom_tools'] == []
    assert body['custom_skills'] == []


def test_get_api_spec_reflects_state_mutations_between_requests():
    """After an org-identity patch + an agent add, `/api/spec` shows the new values."""
    get_state().stage = 'configure'  # name belongs to Stage 2
    set_org_identity(name='Research Org', description=_LONG_DESC)
    build_hub_org()
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    body = client.get('/api/spec').json()
    assert body['spec']['org']['name'] == 'Research Org'
    assert [agent['id'] for agent in body['spec']['ai']['agents']] == ['lead', 'researcher']
    assert body['spec']['ai']['units'][0]['model'] == 'hub'
    assert body['structure_error'] is None


def test_chat_api_forwards_to_the_stage_agent_with_tool_lines():
    """A chat completion reaches the stage agent; its tool calls and reply come back as text."""
    fake = _FakeAgent(response='ok', tool_calls=['set_org_identity'])
    client = TestClient(build_app(agent_factory=lambda: fake, chat_api_key=KEY))
    assert _chat(client, 'hi') == '> set_org_identity\n\nok'
    assert fake.calls == ['hi']


def test_chat_api_is_absent_without_a_key():
    """Without a chat key the master serves no chat API."""
    client = TestClient(build_app(agent_factory=_FakeAgent))
    assert client.get('/v1/models').status_code == 404


def test_chat_turn_writes_a_draft_when_autosave_is_enabled(tmp_path):
    """When `draft_path` is supplied, each chat turn snapshots state to disk."""
    draft = tmp_path / 'draft.json'
    client = TestClient(build_app(agent_factory=_FakeAgent, draft_path=draft, chat_api_key=KEY))
    _chat(client, 'hello')
    assert '"spec"' in draft.read_text()


def test_chat_app_reports_the_librechat_address():
    """The page asks the server where LibreChat runs."""
    client = TestClient(build_app(agent_factory=_FakeAgent, chat_url='http://chat.local'))
    assert client.get('/api/chat-app').json() == {'url': 'http://chat.local'}


def _make_spec_ready() -> None:
    """Mutate the singleton state so render-readiness AND Stage 1 / Stage 2 thresholds all pass."""
    seed_discovery()  # opens the Stage-1 gate
    get_state().stage = 'configure'  # identity fields belong to Stage 2
    set_org_identity(
        name='Research Org',
        slug='research-org',
        package_name='research_org',
        description=_LONG_DESC,
        admin_name='Maintainer',
        admin_email='maintainer@example.com',
    )
    set_budget(monthly_usd=100)
    get_state().stage = 'discover'  # let the test advance from Stage 1
    build_hub_org()


def test_api_spec_includes_readiness_with_blockers_on_seed():
    """Fresh seed state is not render-ready; blockers name the placeholder org fields."""
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    readiness = client.get('/api/spec').json()['readiness']
    assert readiness['ready'] is False
    assert readiness['blockers']  # any blocker is fine - render-readiness is a separate gate from staging


def test_api_spec_readiness_is_true_after_filling_org_identity():
    """Render readiness now only gates on org identity - agents are a Stage 4 concern."""
    _make_spec_ready()
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    readiness = client.get('/api/spec').json()['readiness']
    assert readiness['ready'] is True
    assert readiness['blockers'] == []
    assert readiness['org_slug'] == 'research-org'


def test_api_spec_includes_stage_summary_on_seed():
    """Fresh seed state starts in Stage 1 (discover) with low-threshold blockers."""
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    summary = client.get('/api/spec').json()['stage_summary']
    assert summary['stage'] == 'discover'
    assert summary['stage_label'] == 'Discover'
    assert summary['next_enabled'] is False
    assert summary['next_blockers']  # need a name + a mission


def test_api_spec_stage_summary_reports_next_enabled_after_recording_discovery():
    """Recording the discovery summary satisfies Stage 1's threshold."""
    seed_discovery()
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    summary = client.get('/api/spec').json()['stage_summary']
    assert summary['stage'] == 'discover'
    assert summary['next_enabled'] is True
    assert summary['next_blockers'] == []


def test_get_api_render_serves_the_zip_for_anchor_clicks(monkeypatch):
    """Plain `<a href="/api/render">` anchor clicks (GET) trigger the download in Stage 3+."""
    _make_spec_ready()

    def fake_render(spec_path, output_dir) -> None:
        (Path(output_dir) / 'README.md').write_text('rendered marker\n')

    monkeypatch.setattr(ui_server, 'render_project', fake_render)

    app = build_app(agent_factory=_FakeAgent, chat_api_key=KEY)
    client = TestClient(app)
    _advance_to_generate_stage(client)
    response = client.get('/api/render')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/zip'
    assert response.headers['x-agentorg-slug'] == 'research-org'


def test_get_api_render_returns_409_when_not_in_generate_or_later():
    """GET, like POST, gates the download to Stage 3+ so early link-clicks fail clearly."""
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    response = client.get('/api/render')
    assert response.status_code == 409


def test_post_api_render_returns_409_when_not_in_generate_stage():
    """Create Organization (render + zip) is only available in Stage 3."""
    _make_spec_ready()  # ready by every other measure, but stage is still 'discover'
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    response = client.post('/api/render', json={})
    assert response.status_code == 409
    detail = response.json()['detail']
    assert any('Stage 3' in b for b in detail['blockers'])


def _advance_to_generate_stage(client: TestClient) -> None:
    """Walk the stage cursor from `discover` to `build` with the `/next` command."""
    assert 'Now in' in _chat(client, '/next')
    assert 'Now in' in _chat(client, '/next')


def test_post_api_render_returns_zip_with_spec_and_invokes_render_when_ready(monkeypatch):
    """In Stage 3, /api/render returns a zip whose tree includes spec.py and was produced by render()."""
    _make_spec_ready()
    calls: list[tuple[Path, Path]] = []

    def fake_render(spec_path, output_dir) -> None:
        calls.append((Path(spec_path), Path(output_dir)))
        (Path(output_dir) / 'README.md').write_text('rendered marker\n')

    monkeypatch.setattr(ui_server, 'render_project', fake_render)

    app = build_app(agent_factory=_FakeAgent, chat_api_key=KEY)
    client = TestClient(app)
    _advance_to_generate_stage(client)

    response = client.post('/api/render', json={})
    assert response.status_code == 200, response.text
    assert response.headers['content-type'] == 'application/zip'
    assert 'attachment' in response.headers['content-disposition']
    assert 'research-org.zip' in response.headers['content-disposition']
    assert response.headers['x-agentorg-slug'] == 'research-org'

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = set(zf.namelist())
    assert 'research-org/spec.py' in names
    assert 'research-org/README.md' in names

    assert len(calls) == 1
    assert calls[0][0].name == 'spec.py'
    assert calls[0][1].name == 'research-org'


class _FlakyAgent:
    """Stand-in agent that raises N times before finally succeeding - used to exercise the retry path."""

    def __init__(self, *, fail_times: int, exception: Exception, response: str = 'ok after retry') -> None:
        self.fail_times = fail_times
        self.exception = exception
        self.response = response
        self.calls: list[str] = []

    async def arun(self, message: str, *_args: object, **_kwargs: object) -> Any:
        self.calls.append(message)
        if len(self.calls) <= self.fail_times:
            raise self.exception
        return SimpleNamespace(content=self.response, tool_calls=[])


def test_chat_retries_transient_upstream_errors_then_succeeds(monkeypatch):
    """A 503 from the upstream model is retried, and the eventual success is returned."""
    monkeypatch.setattr(ui_server, 'CHAT_RETRY_BASE_DELAY', 0.0)
    flaky = _FlakyAgent(fail_times=2, exception=RuntimeError('503 Service Unavailable'))
    client = TestClient(build_app(agent_factory=lambda: flaky, chat_api_key=KEY))
    assert _chat(client, 'hi') == 'ok after retry'
    assert len(flaky.calls) == 3


def test_chat_reports_a_failure_after_retries(monkeypatch):
    """When retries are exhausted the reply says so instead of dropping the stream."""
    monkeypatch.setattr(ui_server, 'CHAT_RETRY_BASE_DELAY', 0.0)
    flaky = _FlakyAgent(fail_times=99, exception=RuntimeError('429 Too Many Requests'))
    client = TestClient(build_app(agent_factory=lambda: flaky, chat_api_key=KEY))
    assert 'The interviewer failed' in _chat(client, 'hi')
    assert len(flaky.calls) == ui_server.CHAT_RETRY_ATTEMPTS


def test_chat_does_not_retry_non_transient_errors():
    """A plain bug fails on the first attempt and is reported in the reply."""
    flaky = _FlakyAgent(fail_times=99, exception=ValueError('bad arg'))
    client = TestClient(build_app(agent_factory=lambda: flaky, chat_api_key=KEY))
    assert 'bad arg' in _chat(client, 'hi')
    assert len(flaky.calls) == 1


def test_post_api_render_returns_500_when_render_raises(monkeypatch):
    """If render itself throws, the endpoint surfaces a 500 with the underlying message."""
    _make_spec_ready()
    monkeypatch.setattr(ui_server, 'render_project', lambda *_a: (_ for _ in ()).throw(RuntimeError('boom')))
    app = build_app(agent_factory=_FakeAgent, chat_api_key=KEY)
    client = TestClient(app)
    _advance_to_generate_stage(client)
    response = client.post('/api/render', json={})
    assert response.status_code == 500
    assert 'boom' in response.json()['detail']
