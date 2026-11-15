"""Tests for the runtime module."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from agentfield.agent import Agent as AgentFieldNode
from claude_agent_sdk import ClaudeAgentOptions

from agentorg.core import ConfigurationError
from agentorg.core.operations import OrgRuntime, database_url, output_name, start_operations
from agentorg.core.spec import Spec

from .conftest import FakeClient, result_message

PREVIEW = {'AGENTORG_PREVIEW_MODE': 'true'}


def _echo_client(options: ClaudeAgentOptions) -> FakeClient:
    async def script(opts: ClaudeAgentOptions) -> AsyncIterator[object]:
        yield result_message(result=f'{str(opts.system_prompt).split(",")[0]} answered')

    return FakeClient(options, script)


def _runtime(spec_dict: dict[str, Any], tmp_path: Path, environ: dict[str, str] | None = None) -> OrgRuntime:
    return OrgRuntime(
        Spec.model_validate(spec_dict),
        environ=PREVIEW if environ is None else environ,
        data_dir=tmp_path,
        skills_dir=tmp_path / 'skills',
        client_factory=_echo_client,
    )


@pytest.fixture
async def runtime(spec_dict_normal: dict[str, Any], tmp_path: Path) -> AsyncIterator[OrgRuntime]:
    """A started preview runtime of the research org: a hub led by analyst over researcher and a pipeline."""
    runtime = _runtime(spec_dict_normal, tmp_path)
    await runtime.start()
    yield runtime
    await runtime.stop()


def test_runtime_requires_broker_outside_preview(spec_dict_minimal: dict[str, Any], tmp_path: Path) -> None:
    """Outside preview, a missing AMQP_URL stops the runtime from being built."""
    with pytest.raises(ConfigurationError, match='AMQP_URL'):
        _runtime(spec_dict_minimal, tmp_path, environ={})


async def test_runtime_preview_does_not_schedule(spec_dict_normal: dict[str, Any], tmp_path: Path) -> None:
    """In preview, a schedule that is due creates no run because the scheduler never starts."""
    runtime = _runtime(spec_dict_normal, tmp_path)
    await runtime.start()
    assert runtime.broker is None
    assert runtime.scheduler._task is None
    assert await runtime.store.list_runs() == []
    await runtime.stop()


async def test_runtime_runs_agent_chat_inline(runtime: OrgRuntime) -> None:
    """A chat message to an agent runs at once on the SDK and returns its output."""
    result = await runtime.run_target('researcher', 'Find sources', 'chat-1', 'ana')
    assert (result['status'], result['output']) == ('succeeded', 'You are Researcher answered')


async def test_runtime_unit_run_enters_at_lead(runtime: OrgRuntime) -> None:
    """A message to the hub runs its lead as a child of the unit run."""
    result = await runtime.run_target('research', 'Plan the week', None, 'ana')
    children = await runtime.store.list_runs(parent_id=result['run_id'])
    assert (result['status'], result['output']) == ('succeeded', 'You are Analyst answered')
    assert [(child.target, child.trigger_kind) for child in children] == [('analyst', 'delegation')]


async def test_runtime_routes_session_to_handoff_owner(runtime: OrgRuntime) -> None:
    """After a handoff, the next message in the session goes to the new owner with the note."""
    await runtime.store.set_value('session_owner', 'chat-1', {'agent': 'writer', 'note': 'Customer wants a summary'})
    result = await runtime.run_target('researcher', 'Hello again', 'chat-1', 'ana')
    run = await runtime.store.get_run(result['run_id'])
    assert run is not None
    assert run.target == 'writer'
    assert run.prompt.startswith('Handoff note: Customer wants a summary')


async def test_runtime_refuses_work_for_disabled_agent(runtime: OrgRuntime) -> None:
    """A disabled agent refuses chat with the reason and no run is created."""
    await runtime.lifecycle.set_enabled('researcher', enabled=False, actor='admin')
    assert await runtime.run_target('researcher', 'Hi', None, 'ana') == {
        'status': 'refused',
        'output': 'researcher is disabled.',
    }
    assert await runtime.store.list_runs(target='researcher') == []


@pytest.mark.parametrize(('policy', 'inbox', 'handed_off'), [('escalate', True, False), ('handoff', False, True)])
async def test_runtime_failure_policy(
    spec_dict_normal: dict[str, Any],
    tmp_path: Path,
    policy: str,
    inbox: bool,
    handed_off: bool,
) -> None:
    """A dead-lettered run is escalated to the inbox or handed to the fallback agent."""
    spec_dict_normal['operations']['runs'] = {'on_failure': policy, 'fallback_agent': 'analyst'}
    spec_dict_normal['operations']['notifications'] = {}
    runtime = _runtime(spec_dict_normal, tmp_path)
    await runtime.start()
    failed = await runtime.store.create_run(
        target='researcher',
        trigger_kind='manual',
        prompt='x',
        failure_reason='error',
    )
    await runtime.apply_failure_policy(failed)
    escalations = [item for item in await runtime.store.list_inbox() if item.kind == 'escalation']
    assert bool(escalations) == inbox
    assert bool(await runtime.store.list_runs(target='analyst')) == handed_off
    await runtime.stop()


async def test_start_operations_mounts_webhooks(spec_dict_normal: dict[str, Any], tmp_path: Path) -> None:
    """Starting operations on an app mounts the webhook route, which answers for unknown triggers."""
    app = AgentFieldNode(node_id='acme-org')
    start_operations(
        app,
        Spec.model_validate(spec_dict_normal),
        data_dir=tmp_path,
        skills_dir=tmp_path,
        environ=PREVIEW,
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://org') as client:
        response = await client.post('/hooks/nope', content=b'{}')
    assert (response.status_code, response.json()['detail']) == (404, "No webhook trigger 'nope'.")


@pytest.mark.parametrize(('key', 'expected'), [('secret', 200), (None, 404)])
async def test_start_operations_mounts_chat_api_with_a_key(
    spec_dict_normal: dict[str, Any],
    tmp_path: Path,
    key: str | None,
    expected: int,
) -> None:
    """The chat API answers only when `CHAT_API_KEY` is set."""
    app = AgentFieldNode(node_id='acme-org')
    environ = {**PREVIEW, 'CHAT_API_KEY': key} if key else PREVIEW
    runtime = start_operations(
        app,
        Spec.model_validate(spec_dict_normal),
        data_dir=tmp_path,
        skills_dir=tmp_path,
        environ=environ,
    )
    await runtime.start()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://org') as client:
        response = await client.get('/v1/models', headers={'Authorization': f'Bearer {key}'})
    await runtime.stop()
    assert response.status_code == expected


def test_database_url_by_infra(spec_dict_minimal: dict[str, Any], tmp_path: Path) -> None:
    """Sqlite orgs store operations next to their data, postgres orgs use DATABASE_URL with asyncpg."""
    assert (
        database_url(Spec.model_validate(spec_dict_minimal), {}, tmp_path)
        == f'sqlite+aiosqlite:///{tmp_path}/operations.db'
    )
    spec_dict_minimal['runtime']['infra'] |= {'database': 'postgres', 'vector_db': 'pgvector'}
    spec = Spec.model_validate(spec_dict_minimal)
    assert database_url(spec, {'DATABASE_URL': 'postgresql://u@db/org'}, tmp_path) == 'postgresql+asyncpg://u@db/org'
    assert database_url(spec, {}, tmp_path, preview=True).startswith('sqlite+aiosqlite')
    with pytest.raises(ConfigurationError, match='DATABASE_URL'):
        database_url(spec, {}, tmp_path)


def test_output_name_follows_the_content() -> None:
    """The same output always files under the same name, and different output under another."""
    assert output_name('lead', 'Report.') == output_name('lead', 'Report.')
    assert output_name('lead', 'Report.') != output_name('lead', 'Other.')
    assert output_name('lead', {'b': 1, 'a': 2}) == output_name('lead', {'a': 2, 'b': 1})
    assert output_name('lead', 'Report.').startswith('lead-')
