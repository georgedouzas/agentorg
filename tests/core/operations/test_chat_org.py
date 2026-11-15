"""Tests for the chat org module."""

import asyncio
import json
from collections.abc import Callable, Coroutine
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from agentorg.core.operations import Approval, Approvals, Lifecycle, OrgChat, Store, build_chat_router
from agentorg.core.spec import Spec

KEY = 'chat-test-key'
AUTH = {'Authorization': f'Bearer {KEY}'}
Script = Callable[[Store, str], Coroutine[Any, Any, None]]


async def reply_with(store: Store, run_id: str, text: str = 'Hello there.') -> None:
    """Run `run_id` to success with one text event."""
    await store.transition(run_id, 'running')
    await store.append_transcript(run_id, [{'type': 'text', 'text': text}])
    await store.transition(run_id, 'succeeded', output=text, input_tokens=7, output_tokens=3)


async def _ignore(*_: object) -> None:
    return None


class Org:
    """A fake runtime that records chat runs and plays each one with a script."""

    def __init__(self, store: Store, script: Script = reply_with, refusal: str | None = None) -> None:
        """Play every new run with `script`, or refuse every run with `refusal`."""
        self.store = store
        self.script = script
        self.refusal = refusal
        self.calls: list[tuple[str, str, str, str]] = []
        self.tasks: list[asyncio.Task[None]] = []

    async def start_run(self, target: str, message: str, session_id: str | None, user_id: str) -> dict[str, Any]:
        """Record the call and queue a run that the script plays in the background."""
        self.calls.append((target, message, session_id or '', user_id))
        if self.refusal is not None:
            return {'status': 'refused', 'output': self.refusal}
        run = await self.store.create_run(
            target=target,
            trigger_kind='manual',
            prompt=message,
            session_id=session_id,
            user_id=user_id,
        )
        self.tasks.append(asyncio.get_running_loop().create_task(self.script(self.store, run.id)))
        return {'run_id': run.id, 'status': 'queued'}


@pytest.fixture
def spec(spec_dict_minimal: dict[str, Any]) -> Spec:
    """A solo org with one agent."""
    return Spec.model_validate(spec_dict_minimal)


def _client(spec: Spec, org: Org, email: str = '', **options: Any) -> httpx.AsyncClient:
    approvals = Approvals(spec, org.store, _ignore, _ignore)
    lifecycle = Lifecycle(spec, org.store, _ignore, _ignore, _ignore)
    chat = OrgChat(
        spec,
        org.store,
        org.start_run,
        approvals,
        lifecycle=lifecycle,
        broker_status=lambda: 'ok',
        console_url='http://console',
    )
    app = FastAPI()
    app.include_router(build_chat_router(chat, api_key=KEY, owner='acme', poll=0.01, **options))
    headers = {**AUTH, 'X-Agentorg-User-Email': email}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://org', headers=headers)


def _messages(*texts: str) -> list[dict[str, str]]:
    return [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': text} for i, text in enumerate(texts)]


def _sse(text: str) -> list[Any]:
    data = [line.removeprefix('data: ') for line in text.splitlines() if line.startswith('data: ')]
    return [item if item == '[DONE]' else json.loads(item) for item in data]


async def test_models_list_enabled_agents_and_units(spec: Spec, store: Store) -> None:
    """Every enabled agent and unit is a model; a disabled one is not."""

    async with _client(spec, Org(store)) as client:
        before = (await client.get('/v1/models')).json()
        await store.set_value('disabled', 'assistant', True)
        after = (await client.get('/v1/models')).json()
    assert before['object'] == 'list'
    assert {model['id'] for model in before['data']} == {'assistant', 'org'}
    assert {model['id'] for model in after['data']} == {'org'}


async def test_completion_runs_the_target_and_returns_its_reply(spec: Spec, store: Store) -> None:
    """A non-streaming completion starts a manual run for the header's user and returns its output and usage."""
    org = Org(store)
    async with _client(spec, org) as client:
        reply = await client.post(
            '/v1/chat/completions',
            json={'model': 'assistant', 'messages': [{'role': 'system', 'content': 'Be brief.'}, *_messages('Hi')]},
            headers={'X-Agentorg-User-Id': 'dana'},
        )
    body = reply.json()
    run = (await store.list_runs())[0]
    assert (org.calls[0][0], org.calls[0][1], org.calls[0][3]) == ('assistant', 'Hi', 'dana')
    assert (run.trigger_kind, run.user_id) == ('manual', 'dana')
    assert reply.headers['X-Agentorg-Run-Id'] == run.id
    assert body['choices'][0]['message'] == {'role': 'assistant', 'content': 'Hello there.'}
    assert body['usage'] == {'prompt_tokens': 7, 'completion_tokens': 3, 'total_tokens': 10}


async def test_refused_run_is_answered_with_the_reason(spec: Spec, store: Store) -> None:
    """When the runtime refuses the run, the reply is the refusal and no run exists."""
    org = Org(store, refusal='The org is retired.')
    async with _client(spec, org) as client:
        reply = await client.post('/v1/chat/completions', json={'model': 'assistant', 'messages': _messages('Hi')})
        streamed = await client.post(
            '/v1/chat/completions',
            json={'model': 'assistant', 'messages': _messages('Hi'), 'stream': True},
        )
    assert reply.json()['choices'][0]['message']['content'] == 'The org is retired.'
    assert _sse(streamed.text)[0]['choices'][0]['delta']['content'] == 'The org is retired.'
    assert await store.list_runs() == []


async def test_stream_sends_deltas_finish_usage_and_done(spec: Spec, store: Store) -> None:
    """A streaming reply opens with the role, carries the text, then a stop chunk with usage, then [DONE]."""

    async with _client(spec, Org(store)) as client:
        reply = await client.post(
            '/v1/chat/completions',
            json={'model': 'assistant', 'messages': _messages('Hi'), 'stream': True},
        )
    events = _sse(reply.text)
    assert reply.headers['content-type'].startswith('text/event-stream')
    assert events[0]['choices'][0]['delta'] == {'role': 'assistant', 'content': ''}
    assert ''.join(e['choices'][0]['delta'].get('content', '') for e in events[1:-1]) == 'Hello there.'
    assert events[-2]['choices'][0]['finish_reason'] == 'stop'
    assert events[-2]['usage']['total_tokens'] == 10
    assert events[-1] == '[DONE]'


async def test_stream_shows_tools_delegation_and_failure(spec: Spec, store: Store) -> None:
    """Tool calls and delegations stream as lines, and a failed run ends with its reason."""

    async def script(store: Store, run_id: str) -> None:
        await store.transition(run_id, 'running')
        await store.append_transcript(
            run_id,
            [{'type': 'tool_call', 'id': 't1', 'name': 'search', 'input': {'q': 'x'}}],
        )
        await store.create_run(target='helper', trigger_kind='delegation', prompt='Help.', parent_id=run_id)
        await asyncio.sleep(0.05)
        await store.transition(run_id, 'failed', failure_reason='budget')

    async with _client(spec, Org(store, script)) as client:
        reply = await client.post('/v1/chat/completions', json={'model': 'assistant', 'messages': _messages('Hi')})
    content = reply.json()['choices'][0]['message']['content']
    assert '> search {"q": "x"}' in content
    assert '> delegated to helper' in content
    assert content.rstrip().endswith('The run failed: budget.')


async def test_approval_hold_links_the_console_and_continues(spec: Spec, store: Store) -> None:
    """A held action streams a console link once, keeps the stream alive, and the reply continues after approval."""
    decided = asyncio.Event()

    async def script(store: Store, run_id: str) -> None:
        await store.transition(run_id, 'running')
        await store.transition(run_id, 'awaiting_approval')
        await store.add(
            Approval(id='ap1', run_id=run_id, action_class='outbound', tool_name='send_email', arguments={}),
        )
        await decided.wait()
        await store.decide_approval('ap1', status='approved', decided_by='dana')
        await store.transition(run_id, 'running')
        await reply_with(store, run_id, 'Sent.')

    async def approve_later() -> None:
        while not await store.list_approvals():
            await asyncio.sleep(0.01)
        # Long enough past the 0.03 s keep-alive for the stream to send one even on a loaded machine.
        await asyncio.sleep(1.0)
        decided.set()

    async with _client(spec, Org(store, script), keepalive=0.03) as client:
        approver = asyncio.create_task(approve_later())
        reply = await client.post(
            '/v1/chat/completions',
            json={'model': 'assistant', 'messages': _messages('Email them'), 'stream': True},
        )
        await approver
    content = ''.join(e['choices'][0]['delta'].get('content', '') for e in _sse(reply.text)[:-1])
    assert content.count('http://console/?tab=inbox&approval=ap1') == 1
    assert '`send_email` is waiting for approval' in content
    assert content.endswith('Sent.')
    assert ': keep-alive' in reply.text


async def test_follow_up_resumes_the_previous_turn(spec: Spec, store: Store) -> None:
    """The second turn gets a new session seeded with the SDK session and owner of the first."""
    org = Org(store)
    async with _client(spec, org) as client:
        await client.post('/v1/chat/completions', json={'model': 'assistant', 'messages': _messages('Hi')})
        first = org.calls[0][2]
        await store.set_value('sdk_session', f'assistant:{first}', 'sdk-1')
        await store.set_value('session_owner', first, {'agent': 'helper', 'note': 'Over to you.'})
        follow_up = _messages('Hi', 'Hello there.', 'And now?')
        await client.post('/v1/chat/completions', json={'model': 'assistant', 'messages': follow_up})
    second = org.calls[1][2]
    assert second != first
    assert await store.get_value('sdk_session', f'assistant:{second}') == 'sdk-1'
    assert await store.get_value('session_owner', second) == {'agent': 'helper', 'note': 'Over to you.'}


async def test_regenerate_branches_from_the_earlier_turn(spec: Spec, store: Store) -> None:
    """Resending an earlier prefix resumes that turn's snapshot, not the latest one."""
    org = Org(store)
    async with _client(spec, org) as client:
        await client.post('/v1/chat/completions', json={'model': 'assistant', 'messages': _messages('Hi')})
        await store.set_value('sdk_session', f'assistant:{org.calls[0][2]}', 'sdk-1')
        second = _messages('Hi', 'Hello there.', 'Two')
        await client.post('/v1/chat/completions', json={'model': 'assistant', 'messages': second})
        await store.set_value('sdk_session', f'assistant:{org.calls[1][2]}', 'sdk-2')
        await client.post('/v1/chat/completions', json={'model': 'assistant', 'messages': second})
    assert await store.get_value('sdk_session', f'assistant:{org.calls[2][2]}') == 'sdk-1'


async def test_sessions_are_isolated_by_user(spec: Spec, store: Store) -> None:
    """The same conversation id and history from another user starts a fresh session."""
    org = Org(store)
    headers = {'X-Agentorg-Conversation-Id': 'c1'}
    async with _client(spec, org) as client:
        await client.post(
            '/v1/chat/completions',
            json={'model': 'assistant', 'messages': _messages('Hi')},
            headers={**headers, 'X-Agentorg-User-Id': 'dana'},
        )
        await store.set_value('sdk_session', f'assistant:{org.calls[0][2]}', 'sdk-dana')
        await client.post(
            '/v1/chat/completions',
            json={'model': 'assistant', 'messages': _messages('Hi', 'Hello there.', 'Next')},
            headers={**headers, 'X-Agentorg-User-Id': 'eve'},
        )
    assert await store.get_value('sdk_session', f'assistant:{org.calls[1][2]}') is None


async def test_conversation_id_recovers_an_unmatched_history(spec: Spec, store: Store) -> None:
    """When the client changes the displayed history, the conversation id still finds the latest turn."""
    org = Org(store)
    headers = {'X-Agentorg-Conversation-Id': 'c1'}
    async with _client(spec, org) as client:
        await client.post(
            '/v1/chat/completions',
            json={'model': 'assistant', 'messages': _messages('Hi')},
            headers=headers,
        )
        await store.set_value('sdk_session', f'assistant:{org.calls[0][2]}', 'sdk-1')
        changed = _messages('Hi', 'A different rendering of the reply.', 'Next')
        await client.post('/v1/chat/completions', json={'model': 'assistant', 'messages': changed}, headers=headers)
    assert await store.get_value('sdk_session', f'assistant:{org.calls[1][2]}') == 'sdk-1'


async def _command(client: httpx.AsyncClient, text: str) -> str:
    reply = await client.post('/v1/chat/completions', json={'model': 'assistant', 'messages': _messages(text)})
    return str(reply.json()['choices'][0]['message']['content'])


async def _held(store: Store, approvers: list[str]) -> Approval:
    run = await store.create_run(target='assistant', trigger_kind='manual', prompt='Email them.')
    approval = Approval(id='ap1', run_id=run.id, action_class='outbound', tool_name='send_email', arguments={})
    approval.approvers = approvers
    await store.add(approval)
    return approval


async def test_commands_start_no_run(spec: Spec, store: Store) -> None:
    """Status and help are answered from state, without a run or a model call."""
    org = Org(store)
    async with _client(spec, org) as client:
        status = await _command(client, '/status')
        unknown = await _command(client, '/frobnicate')
    assert 'Lifecycle: **trial**' in status
    assert 'broker: **ok**' in status
    assert '/approve <id>' in unknown
    assert (org.calls, await store.list_runs()) == ([], [])


async def test_approver_decides_in_chat(spec: Spec, store: Store) -> None:
    """An approver approves with /approve, recorded with their email as the actor."""
    await _held(store, ['dana@acme.com'])
    async with _client(spec, Org(store), email='Dana@acme.com') as client:
        reply = await _command(client, '/approve ap1 looks fine')
    decided = await store.get_approval('ap1')
    assert '`send_email` approved' in reply
    assert decided is not None
    assert (decided.status, decided.decided_by, decided.comment) == ('approved', 'Dana@acme.com', 'looks fine')


async def test_non_approver_cannot_decide(spec: Spec, store: Store) -> None:
    """Someone outside the approvers is told who can decide, and the approval stays pending."""
    await _held(store, ['dana@acme.com'])
    async with _client(spec, Org(store), email='eve@acme.com') as client:
        reply = await _command(client, '/approve ap1')
    assert 'not an approver' in reply
    assert 'dana@acme.com' in reply
    assert (await store.get_approval('ap1')).status == 'pending'  # type: ignore[union-attr]


async def test_rejection_needs_a_comment(spec: Spec, store: Store) -> None:
    """A bare /reject asks for a comment; with one, the approval is rejected."""
    await _held(store, ['dana@acme.com'])
    async with _client(spec, Org(store), email='dana@acme.com') as client:
        bare = await _command(client, '/reject ap1')
        pending = (await store.get_approval('ap1')).status  # type: ignore[union-attr]
        done = await _command(client, '/reject ap1 wrong customer')
    assert ('needs a comment' in bare, pending) == (True, 'pending')
    assert '`send_email` rejected' in done


async def test_unknown_approval_is_reported(spec: Spec, store: Store) -> None:
    """Deciding an approval that does not exist says so."""

    async with _client(spec, Org(store), email='admin@acme.com') as client:
        reply = await _command(client, '/approve nope')
    assert 'no pending approval `nope`' in reply


async def test_runs_run_and_inbox(spec: Spec, store: Store) -> None:
    """The read commands list runs, show one run's output and report an empty inbox."""
    run = await store.create_run(target='assistant', trigger_kind='webhook', prompt='Hi.')
    await reply_with(store, run.id, 'All done.')
    async with _client(spec, Org(store)) as client:
        runs = await _command(client, '/runs')
        one = await _command(client, f'/run {run.id}')
        missing = await _command(client, '/run nope')
        inbox = await _command(client, '/inbox')
    assert f'| `{run.id}` | assistant | webhook | succeeded |' in runs
    assert 'All done.' in one
    assert 'no run `nope`' in missing
    assert inbox == 'The inbox is empty.'


async def test_pause_and_resume_need_an_org_approver(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """Only the org approvers pause and resume; the lifecycle follows."""
    spec_dict_minimal['operations'] = {'governance': {'approvers': ['ops@acme.com']}}
    spec = Spec.model_validate(spec_dict_minimal)
    lifecycle = Lifecycle(spec, store, _ignore, _ignore, _ignore)
    async with _client(spec, Org(store), email='eve@acme.com') as client:
        refused = await _command(client, '/pause testing')
    async with _client(spec, Org(store), email='ops@acme.com') as client:
        paused = await _command(client, '/pause testing')
        state = await lifecycle.state()
        resumed = await _command(client, '/resume')
    assert 'Only the org approvers' in refused
    assert ('paused' in paused, state) == (True, 'paused')
    assert 'active again' in resumed
    assert await lifecycle.state() == 'active'


async def test_hold_message_names_the_commands(spec: Spec, store: Store) -> None:
    """The approval-hold line tells approvers how to decide in chat."""

    async def script(store: Store, run_id: str) -> None:
        await store.transition(run_id, 'running')
        await store.add(Approval(id='ap2', run_id=run_id, action_class='outbound', tool_name='send', arguments={}))
        await store.transition(run_id, 'awaiting_approval')
        await asyncio.sleep(0.05)
        await store.transition(run_id, 'running')
        await reply_with(store, run_id, 'Done.')

    async with _client(spec, Org(store, script)) as client:
        reply = await client.post('/v1/chat/completions', json={'model': 'assistant', 'messages': _messages('Go')})
    assert '`/approve ap2`' in reply.json()['choices'][0]['message']['content']
