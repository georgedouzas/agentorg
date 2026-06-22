"""Tests for the server module."""

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agentorg.master import add_or_update_agent, get_state, reset_state, set_org_identity
from agentorg.master.ui import _server as ui_server
from agentorg.master.ui import build_app

from ..conftest import seed_discovery

_LONG_DESC = (
    'Research Org is a small team that gathers sources on a topic and writes structured '
    'weekly reports for internal product squads. It bridges full literature reviews '
    '(slow) and informal Slack summaries (lossy), with cited claims throughout.'
)


class _FakeAgent:
    """Stand-in for `agno.Agent` that records what it was called with and returns a canned RunOutput."""

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
    add_or_update_agent(
        agent_id='researcher',
        name='Researcher',
        role='Gather sources.',
        in_scope=['Source gathering.'],
        workflow=['Restate.', 'Cite three sources.'],
        tools=['read_knowledge', 'write_knowledge'],
    )
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    body = client.get('/api/spec').json()
    assert body['spec']['org']['name'] == 'Research Org'
    assert len(body['spec']['ai']['agents']) == 1
    assert body['spec']['ai']['agents'][0]['agent_id'] == 'researcher'
    assert body['spec']['ai']['agents'][0]['tools'] == ['read_knowledge', 'write_knowledge']


def test_post_api_chat_forwards_to_arun_and_returns_response_plus_tool_calls():
    """A chat POST is routed to `agent.arun`; the reply text and tool call names are returned."""
    fake = _FakeAgent(response='ok', tool_calls=[{'tool_name': 'set_org_identity'}])
    app = build_app(agent_factory=lambda: fake)
    client = TestClient(app)
    response = client.post('/api/chat', json={'message': 'hi'})
    assert response.status_code == 200
    body = response.json()
    assert body['response'] == 'ok'
    assert body['tool_calls'] == ['set_org_identity']
    assert fake.calls == ['hi']


def test_post_api_chat_reuses_the_same_agent_instance_across_requests():
    """The agent is built lazily once and reused, so chat history accumulates."""
    fake = _FakeAgent()
    app = build_app(agent_factory=lambda: fake)
    client = TestClient(app)
    client.post('/api/chat', json={'message': 'one'})
    client.post('/api/chat', json={'message': 'two'})
    assert fake.calls == ['one', 'two']


def test_post_api_reset_drops_state_and_agent(tmp_path):
    """`POST /api/reset` resets the singleton state; a subsequent chat builds a fresh agent."""
    get_state().stage = 'configure'
    set_org_identity(name='To Be Reset')
    fakes: list[_FakeAgent] = []

    def factory() -> _FakeAgent:
        fake = _FakeAgent()
        fakes.append(fake)
        return fake

    app = build_app(agent_factory=factory)
    client = TestClient(app)
    client.post('/api/chat', json={'message': 'first'})
    assert len(fakes) == 1

    response = client.post('/api/reset')
    assert response.status_code == 200
    body = client.get('/api/spec').json()
    assert body['spec']['org']['name'] == 'Untitled org'  # back to seed

    client.post('/api/chat', json={'message': 'second'})
    assert len(fakes) == 2  # a fresh agent was built after reset


def test_post_api_chat_writes_a_draft_when_autosave_is_enabled(tmp_path):
    """When `draft_path` is supplied, each chat turn snapshots state to disk."""
    draft = tmp_path / 'draft.json'
    fake = _FakeAgent()
    app = build_app(agent_factory=lambda: fake, draft_path=draft)
    client = TestClient(app)
    client.post('/api/chat', json={'message': 'hello'})
    assert draft.exists()
    assert '"spec"' in draft.read_text()


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
    get_state().stage = 'discover'  # let the test exercise /api/advance from Stage 1
    add_or_update_agent(
        agent_id='researcher',
        name='Researcher',
        role='Gather sources and write reports.',
        in_scope=['Source gathering.'],
        workflow=['Restate.', 'Cite three sources.'],
        tools=['read_knowledge', 'write_knowledge'],
    )


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


# ---------- stage machine (explicit, advanced by /api/advance) ----------


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


def test_post_api_advance_advances_when_threshold_satisfied():
    """`POST /api/advance` moves the cursor when the current stage's threshold is satisfied."""
    seed_discovery()
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    response = client.post('/api/advance')
    assert response.status_code == 200
    assert response.json()['stage'] == 'configure'


def test_post_api_advance_returns_agent_narration_for_the_new_stage():
    """The advance handler invokes the agent so the UI can show stage-specific instructions."""
    seed_discovery()
    fake = _FakeAgent(response='## Stage 2 - Configure\n\nLet me know the slug and admin info.')
    app = build_app(agent_factory=lambda: fake)
    client = TestClient(app)
    response = client.post('/api/advance')
    assert response.status_code == 200
    body = response.json()
    assert body['stage'] == 'configure'
    assert 'Stage 2' in body['response']
    # The agent was invoked with a transition prompt naming both stages so it can branch.
    assert any('Discover' in c and 'Configure' in c for c in fake.calls)


def test_post_api_advance_returns_silent_advance_when_agent_fails():
    """If the agent raises while narrating, the stage still advances and the UI sees an empty response."""
    seed_discovery()

    boom = RuntimeError('model down')

    class _BoomAgent:
        async def arun(self, _message: str, *_a: object, **_kw: object) -> Any:
            raise boom

    app = build_app(agent_factory=_BoomAgent)
    client = TestClient(app)
    response = client.post('/api/advance')
    assert response.status_code == 200
    body = response.json()
    assert body['stage'] == 'configure'
    assert body['response'] == ''


def test_post_api_advance_returns_409_with_blockers_when_threshold_not_met():
    """A premature advance is rejected with the blocker list."""
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    response = client.post('/api/advance')
    assert response.status_code == 409
    assert response.json()['detail']['stage'] == 'discover'
    assert response.json()['detail']['blockers']


def test_get_api_render_serves_the_zip_for_anchor_clicks(monkeypatch):
    """Plain `<a href="/api/render">` anchor clicks (GET) trigger the download in Stage 3+."""
    _make_spec_ready()

    def fake_render(spec_path, output_dir) -> None:
        (Path(output_dir) / 'README.md').write_text('rendered marker\n')

    monkeypatch.setattr(ui_server, 'render_project', fake_render)

    app = build_app(agent_factory=_FakeAgent)
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
    """Walk the stage cursor from `discover` to `generate` via /api/advance."""
    # Discover -> Configure
    r = client.post('/api/advance')
    assert r.status_code == 200, r.text
    # Configure -> Generate (requires admin name/email; we've already set them in _make_spec_ready)
    r = client.post('/api/advance')
    assert r.status_code == 200, r.text


def test_post_api_render_returns_zip_with_spec_and_invokes_render_when_ready(monkeypatch):
    """In Stage 3, /api/render returns a zip whose tree includes spec.py and was produced by render()."""
    _make_spec_ready()
    calls: list[tuple[Path, Path]] = []

    def fake_render(spec_path, output_dir) -> None:
        calls.append((Path(spec_path), Path(output_dir)))
        (Path(output_dir) / 'README.md').write_text('rendered marker\n')

    monkeypatch.setattr(ui_server, 'render_project', fake_render)

    app = build_app(agent_factory=_FakeAgent)
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


def test_post_api_chat_retries_transient_upstream_errors_then_succeeds(monkeypatch):
    """A 503 from the upstream model is retried, and the eventual success is returned to the client."""
    monkeypatch.setattr(ui_server, '_CHAT_RETRY_BASE_DELAY', 0.0)
    flaky = _FlakyAgent(fail_times=2, exception=RuntimeError('503 Service Unavailable'))
    app = build_app(agent_factory=lambda: flaky)
    client = TestClient(app)
    response = client.post('/api/chat', json={'message': 'hi'})
    assert response.status_code == 200
    assert response.json()['response'] == 'ok after retry'
    assert len(flaky.calls) == 3  # 2 failures + 1 success


def test_post_api_chat_returns_503_when_retries_are_exhausted(monkeypatch):
    """When every retry hits the same transient error, the endpoint surfaces a clean 503."""
    monkeypatch.setattr(ui_server, '_CHAT_RETRY_BASE_DELAY', 0.0)
    flaky = _FlakyAgent(fail_times=99, exception=RuntimeError('429 Too Many Requests'))
    app = build_app(agent_factory=lambda: flaky)
    client = TestClient(app)
    response = client.post('/api/chat', json={'message': 'hi'})
    assert response.status_code == 503
    assert 'temporarily unavailable' in response.json()['detail'].lower()
    assert len(flaky.calls) == ui_server._CHAT_RETRY_ATTEMPTS


def test_post_api_chat_does_not_retry_non_transient_errors():
    """A plain bug in a tool call propagates immediately - no retry, surfaces as 500."""
    flaky = _FlakyAgent(fail_times=99, exception=ValueError('bad arg'))
    app = build_app(agent_factory=lambda: flaky)
    client = TestClient(app)
    response = client.post('/api/chat', json={'message': 'hi'})
    assert response.status_code == 500
    assert 'bad arg' in response.json()['detail']
    assert len(flaky.calls) == 1  # only the first attempt


def test_post_api_render_returns_500_when_render_raises(monkeypatch):
    """If render itself throws, the endpoint surfaces a 500 with the underlying message."""
    _make_spec_ready()
    monkeypatch.setattr(ui_server, 'render_project', lambda *_a: (_ for _ in ()).throw(RuntimeError('boom')))
    app = build_app(agent_factory=_FakeAgent)
    client = TestClient(app)
    _advance_to_generate_stage(client)
    response = client.post('/api/render', json={})
    assert response.status_code == 500
    assert 'boom' in response.json()['detail']
