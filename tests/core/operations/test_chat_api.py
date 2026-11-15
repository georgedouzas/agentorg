"""Tests for the chat API module."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import FastAPI

from agentorg.core.operations import ChatUser, build_chat_router, conversation_key, message_text

KEY = 'chat-test-key'
AUTH = {'Authorization': f'Bearer {KEY}'}


class Reply:
    """A reply that streams fixed parts with a pause in the middle."""

    def __init__(self, parts: list[str | None]) -> None:
        """Stream `parts`, where `None` stands for a quiet period."""
        self.parts = parts
        self.content = ''
        self.run_id: str | None = 'run-1'
        self.finished = False

    async def deltas(self, poll: float, keepalive: float) -> AsyncIterator[str | None]:
        """Yield the parts."""
        del poll, keepalive
        for part in self.parts:
            self.content += part or ''
            yield part

    def usage(self) -> dict[str, int]:
        """Report fixed usage."""
        return {'prompt_tokens': 2, 'completion_tokens': 1, 'total_tokens': 3}

    async def finish(self) -> None:
        """Note that the reply was finished."""
        self.finished = True


class Backend:
    """A backend with one model that records what it was asked."""

    def __init__(self, refusal: str | None = None) -> None:
        """Answer turns with a fixed reply, or refuse them with `refusal`."""
        self.refusal = refusal
        self.reply = Reply(['Hel', None, 'lo'])
        self.commands: list[tuple[str, str, ChatUser]] = []
        self.turns: list[tuple[str, list[dict[str, Any]], ChatUser]] = []

    async def models(self) -> dict[str, str]:
        """List one model."""
        return {'helper': 'Helper'}

    async def command(self, model: str, text: str, user: ChatUser) -> str:
        """Echo the command."""
        self.commands.append((model, text, user))
        return f'ran {text}'

    async def turn(self, model: str, messages: list[dict[str, Any]], user: ChatUser) -> Reply | str:
        """Return the fixed reply or the refusal."""
        self.turns.append((model, messages, user))
        return self.refusal if self.refusal is not None else self.reply


def _client(backend: Backend) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(build_chat_router(backend, api_key=KEY, owner='acme', poll=0.01))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://org', headers=AUTH)


def _body(text: str, **fields: object) -> dict[str, Any]:
    return {'model': 'helper', 'messages': [{'role': 'user', 'content': text}], **fields}


def _sse(text: str) -> list[Any]:
    data = [line.removeprefix('data: ') for line in text.splitlines() if line.startswith('data: ')]
    return [item if item == '[DONE]' else json.loads(item) for item in data]


async def test_models_are_listed_in_openai_format() -> None:
    """The backend's models are listed with their names and owner."""

    async with _client(Backend()) as client:
        body = (await client.get('/v1/models')).json()
    assert body == {
        'object': 'list',
        'data': [{'id': 'helper', 'object': 'model', 'owned_by': 'acme', 'name': 'Helper'}],
    }


async def test_requests_without_the_key_are_rejected() -> None:
    """A missing or wrong bearer key returns 401 and reaches no backend."""
    backend = Backend()
    async with _client(backend) as client:
        missing = await client.post('/v1/chat/completions', json=_body('Hi'), headers={'Authorization': ''})
        wrong = await client.get('/v1/models', headers={'Authorization': 'Bearer other'})
    assert (missing.status_code, wrong.status_code, backend.turns) == (401, 401, [])


async def test_unknown_model_and_bad_messages_are_rejected() -> None:
    """An unknown model is 404 and a request not ending with a user message is 400, in the OpenAI error format."""

    async with _client(Backend()) as client:
        unknown = await client.post('/v1/chat/completions', json={**_body('Hi'), 'model': 'ghost'})
        assistant_last = {'model': 'helper', 'messages': [{'role': 'assistant', 'content': 'Yo'}]}
        no_user = await client.post('/v1/chat/completions', json=assistant_last)
    assert (unknown.status_code, no_user.status_code) == (404, 400)
    assert 'ghost' in unknown.json()['error']['message']


async def test_headers_become_the_chat_user() -> None:
    """The user id, email and conversation id headers reach the backend."""
    backend = Backend()
    headers = {'X-Agentorg-User-Id': 'u1', 'X-Agentorg-User-Email': 'dana@acme.com', 'X-Agentorg-Conversation-Id': 'c1'}
    async with _client(backend) as client:
        await client.post('/v1/chat/completions', json=_body('Hi'), headers=headers)
    assert backend.turns[0][2] == ChatUser('u1', 'dana@acme.com', 'c1')


async def test_slash_messages_go_to_commands() -> None:
    """A message starting with a slash is a command, answered whole, and starts no turn."""
    backend = Backend()
    async with _client(backend) as client:
        plain = await client.post('/v1/chat/completions', json=_body(' /status '))
        streamed = await client.post('/v1/chat/completions', json=_body('/status', stream=True))
    assert plain.json()['choices'][0]['message']['content'] == 'ran /status'
    assert _sse(streamed.text)[0]['choices'][0]['delta']['content'] == 'ran /status'
    assert _sse(streamed.text)[-1] == '[DONE]'
    assert (len(backend.commands), backend.turns) == (2, [])


async def test_refusal_is_answered_whole() -> None:
    """A refused turn answers with the reason and no run id."""

    async with _client(Backend(refusal='The org is retired.')) as client:
        reply = await client.post('/v1/chat/completions', json=_body('Hi'))
    assert reply.json()['choices'][0]['message']['content'] == 'The org is retired.'
    assert 'X-Agentorg-Run-Id' not in reply.headers


async def test_stream_sends_role_deltas_keepalive_usage_and_done() -> None:
    """A streamed reply opens with the role, carries deltas and keep-alives, then usage, then [DONE]."""
    backend = Backend()
    async with _client(backend) as client:
        reply = await client.post('/v1/chat/completions', json=_body('Hi', stream=True))
    events = _sse(reply.text)
    assert reply.headers['X-Agentorg-Run-Id'] == 'run-1'
    assert events[0]['choices'][0]['delta'] == {'role': 'assistant', 'content': ''}
    assert ''.join(e['choices'][0]['delta'].get('content', '') for e in events[1:-1]) == 'Hello'
    assert ': keep-alive' in reply.text
    assert (events[-2]['choices'][0]['finish_reason'], events[-2]['usage']['total_tokens']) == ('stop', 3)
    assert events[-1] == '[DONE]'
    assert backend.reply.finished


async def test_plain_completion_collects_the_reply() -> None:
    """Without streaming the whole reply comes back with usage, after the reply is finished."""
    backend = Backend()
    async with _client(backend) as client:
        body = (await client.post('/v1/chat/completions', json=_body('Hi'))).json()
    assert body['choices'][0]['message'] == {'role': 'assistant', 'content': 'Hello'}
    assert body['usage']['total_tokens'] == 3
    assert backend.reply.finished


def test_message_text_joins_parts() -> None:
    """List contents keep their text parts only."""
    assert message_text([{'type': 'text', 'text': 'a'}, {'type': 'image_url'}, {'type': 'text', 'text': 'b'}]) == 'a\nb'
    assert message_text(None) == ''


def test_conversation_key_ignores_system_messages_and_whitespace() -> None:
    """System prompts and surrounding whitespace do not change the key, but any turn does."""
    hi = [{'role': 'user', 'content': 'Hi'}]
    base = conversation_key('dana', 'assistant', '', hi)
    assert (
        conversation_key(
            'dana',
            'assistant',
            '',
            [{'role': 'system', 'content': 'x'}, {'role': 'user', 'content': ' Hi\n'}],
        )
        == base
    )
    assert (
        conversation_key('dana', 'assistant', '', [{'role': 'user', 'content': [{'type': 'text', 'text': 'Hi'}]}])
        == base
    )
    assert conversation_key('dana', 'assistant', '', [{'role': 'user', 'content': 'Hello'}]) != base
    assert conversation_key('eve', 'assistant', '', hi) != base
