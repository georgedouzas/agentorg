"""Serve chat backends through an OpenAI-compatible chat API."""

import hashlib
import hmac
import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

DONE = 'data: [DONE]\n\n'


@dataclass(frozen=True)
class ChatUser:
    """Who sent a chat request, from the headers LibreChat fills in."""

    id: str = 'default'
    email: str = ''
    conversation: str = ''


class ChatReply(Protocol):
    """The reply to one chat message, streamed as text deltas."""

    content: str
    run_id: str | None

    def deltas(self, poll: float, keepalive: float) -> AsyncIterator[str | None]:
        """Yield text as it is produced, and `None` after `keepalive` seconds without any."""
        ...

    def usage(self) -> dict[str, int]:
        """Return the prompt, completion and total token counts."""
        ...

    async def finish(self) -> None:
        """Record whatever must outlive the reply, once it is complete."""
        ...


class ChatBackend(Protocol):
    """What the chat models are and how they answer."""

    async def models(self) -> dict[str, str]:
        """Return the model ids that can be chatted with, mapped to their display names."""
        ...

    async def command(self, model: str, text: str, user: ChatUser) -> str:
        """Return the Markdown answer to a `/` command sent to `model`."""
        ...

    async def turn(self, model: str, messages: list[dict[str, Any]], user: ChatUser) -> ChatReply | str:
        """Start answering the last user message, or return why it is refused."""
        ...


def message_text(content: object) -> str:
    """Return the text of an OpenAI message content, which is a string or a list of parts."""
    if isinstance(content, list):
        return '\n'.join(str(part['text']) for part in content if isinstance(part, dict) and part.get('type') == 'text')
    return str(content or '')


def conversation_key(user_id: str, target: str, conversation_id: str, messages: list[dict[str, Any]]) -> str:
    """Return the key of a conversation at the point after `messages`.

    Arguments:
        user_id: The user the conversation belongs to.
        target: The model it talks to.
        conversation_id: The client's conversation id, or an empty string.
        messages: The user and assistant messages so far; system messages are ignored.

    Returns:
        key: A SHA-256 hex digest that changes with any message.
    """
    turns = [
        [m.get('role'), message_text(m.get('content')).strip()]
        for m in messages
        if m.get('role') in ('user', 'assistant')
    ]
    payload = json.dumps([user_id, target, conversation_id, turns], separators=(',', ':'))
    return hashlib.sha256(payload.encode()).hexdigest()


def _error(status: int, message: str, kind: str = 'invalid_request_error') -> JSONResponse:
    return JSONResponse({'error': {'message': message, 'type': kind}}, status_code=status)


def _chunk(completion_id: str, model: str, delta: dict[str, Any], finish: str | None = None, **extra: object) -> str:
    body = {
        'id': completion_id,
        'object': 'chat.completion.chunk',
        'created': int(time.time()),
        'model': model,
        'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}],
        **extra,
    }
    return f'data: {json.dumps(body)}\n\n'


def _completion(completion_id: str, model: str, content: str, usage: dict[str, int]) -> dict[str, Any]:
    return {
        'id': completion_id,
        'object': 'chat.completion',
        'created': int(time.time()),
        'model': model,
        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}],
        'usage': usage,
    }


def _whole(completion_id: str, model: str, text: str, *, stream: bool) -> StreamingResponse | JSONResponse:
    """Answer with a complete text at once, as a command reply or a refusal."""
    empty = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    if not stream:
        return JSONResponse(_completion(completion_id, model, text, empty))
    chunks = [_chunk(completion_id, model, {'role': 'assistant', 'content': text}, 'stop', usage=empty), DONE]
    return StreamingResponse(iter(chunks), media_type='text/event-stream')


def _invalid(model: str, messages: list[dict[str, Any]], models: dict[str, str]) -> JSONResponse | None:
    if model not in models:
        return _error(404, f"The model '{model}' is not available here.")
    if not messages or messages[-1].get('role') != 'user':
        return _error(400, 'The last message must come from the user.')
    return None


async def _events(
    reply: ChatReply,
    completion_id: str,
    model: str,
    poll: float,
    keepalive: float,
) -> AsyncIterator[str]:
    """Stream a reply as OpenAI chunks with keep-alive comments, ending with usage and `[DONE]`."""
    yield _chunk(completion_id, model, {'role': 'assistant', 'content': ''})
    async for delta in reply.deltas(poll, keepalive):
        yield ': keep-alive\n\n' if delta is None else _chunk(completion_id, model, {'content': delta})
    await reply.finish()
    yield _chunk(completion_id, model, {}, 'stop', usage=reply.usage())
    yield DONE


def build_chat_router(
    backend: ChatBackend,
    *,
    api_key: str,
    owner: str,
    poll: float = 0.5,
    keepalive: float = 15,
) -> APIRouter:
    """Return the router serving `/v1/models` and `/v1/chat/completions` for `backend`.

    Arguments:
        backend: Lists the models and answers messages and commands.
        api_key: The bearer key clients must send.
        owner: The `owned_by` value of the listed models.
        poll: Seconds between checks for new reply text.
        keepalive: Seconds of silence before a keep-alive comment is streamed.

    Returns:
        router: The chat router.
    """

    def authorize(authorization: str = Header(default='')) -> None:
        if not hmac.compare_digest(authorization.encode(), f'Bearer {api_key}'.encode()):
            raise HTTPException(status_code=401, detail='Invalid API key.')

    router = APIRouter(prefix='/v1', dependencies=[Depends(authorize)])

    @router.get('/models')
    async def list_models() -> dict[str, Any]:
        models = await backend.models()
        data = [{'id': id_, 'object': 'model', 'owned_by': owner, 'name': name} for id_, name in models.items()]
        return {'object': 'list', 'data': data}

    @router.post('/chat/completions', response_model=None)
    async def complete(
        request: Request,
        x_agentorg_user_id: str = Header(default='default'),
        x_agentorg_user_email: str = Header(default=''),
        x_agentorg_conversation_id: str = Header(default=''),
    ) -> StreamingResponse | JSONResponse:
        body = await request.json()
        model, messages, stream = body.get('model', ''), list(body.get('messages') or []), bool(body.get('stream'))
        invalid = _invalid(model, messages, await backend.models())
        if invalid is not None:
            return invalid
        user = ChatUser(x_agentorg_user_id or 'default', x_agentorg_user_email, x_agentorg_conversation_id)
        completion_id = f'chatcmpl-{uuid.uuid4().hex}'
        text = message_text(messages[-1].get('content')).strip()
        if text.startswith('/'):
            return _whole(completion_id, model, await backend.command(model, text, user), stream=stream)
        reply = await backend.turn(model, messages, user)
        if isinstance(reply, str):
            return _whole(completion_id, model, reply, stream=stream)
        headers = {'X-Agentorg-Run-Id': reply.run_id} if reply.run_id else {}
        if stream:
            events = _events(reply, completion_id, model, poll, keepalive)
            return StreamingResponse(events, media_type='text/event-stream', headers=headers)
        async for _ in reply.deltas(poll, keepalive):
            pass
        await reply.finish()
        return JSONResponse(_completion(completion_id, model, reply.content, reply.usage()), headers=headers)

    return router
