"""Serve recorded Anthropic API responses keyed by a normalised request hash."""

import hashlib
import json
import re
import threading
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

ModelMode = Literal['replay', 'record', 'live']

UPSTREAM = 'https://api.anthropic.com'
HASHED_FIELDS = ('model', 'system', 'messages', 'tools', 'max_tokens')
DEFAULT_RULES: tuple[tuple[str, str], ...] = (
    (r'(Platform|OS Version|Shell|Today\'s date is):?[^\n]*', r'\1 <env>'),
    (r'\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?', '<datetime>'),
    (r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<uuid>'),
    (r'/(private/)?(tmp|var/folders)/[^\s"\'`]*', '<tmp>'),
)


def _scrub(value: Any, rules: list[tuple[re.Pattern[str], str]]) -> Any:  # noqa: ANN401
    """Return `value` without cache markers and with every string normalised by `rules`."""
    if isinstance(value, dict):
        return {key: _scrub(item, rules) for key, item in value.items() if key != 'cache_control'}
    if isinstance(value, list):
        return [_scrub(item, rules) for item in value]
    if isinstance(value, str):
        for pattern, replacement in rules:
            value = pattern.sub(replacement, value)
    return value


def canonical_request(path: str, body: dict[str, Any], rules: tuple[tuple[str, str], ...] = DEFAULT_RULES) -> str:
    """Return the canonical JSON of the request fields that decide the response.

    Arguments:
        path: The request path, such as `/v1/messages`.
        body: The decoded request body.
        rules: Regex replacements that strip volatile text such as dates and temp paths.

    Returns:
        canonical: Sorted, normalised JSON of the path and the hashed fields.
    """
    compiled = [(re.compile(pattern), replacement) for pattern, replacement in rules]
    fields = {name: body[name] for name in HASHED_FIELDS if name in body}
    if 'tools' in fields:
        fields['tools'] = [{'name': t.get('name'), 'input_schema': t.get('input_schema')} for t in fields['tools']]
    return json.dumps({'path': path, **_scrub(fields, compiled)}, sort_keys=True, separators=(',', ':'))


def request_hash(path: str, body: dict[str, Any], rules: tuple[tuple[str, str], ...] = DEFAULT_RULES) -> str:
    """Return the SHA-256 hex digest of the canonical request."""
    return hashlib.sha256(canonical_request(path, body, rules).encode()).hexdigest()


@dataclass
class Recording:
    """One recorded response."""

    status: int
    content_type: str
    body: str

    def response(self) -> Response:
        """Return the recorded response, replaying a stream as its full event sequence."""
        return Response(self.body, status_code=self.status, media_type=self.content_type)


@dataclass
class MockAnthropic:
    """Replay, record or proxy Anthropic API calls for one scenario."""

    cassettes: Path
    mode: ModelMode = 'replay'
    api_key: str = ''
    upstream: str = UPSTREAM
    rules: tuple[tuple[str, str], ...] = DEFAULT_RULES
    transport: httpx.AsyncBaseTransport | None = None
    url: str = ''
    misses: list[str] = field(default_factory=list)
    calls: Counter[str] = field(default_factory=Counter)

    def _path(self, digest: str) -> Path:
        return self.cassettes / f'{digest}.json'

    def _load(self, digest: str) -> list[Recording]:
        path = self._path(digest)
        if not path.exists():
            return []
        return [Recording(**item) for item in json.loads(path.read_text())['responses']]

    def _save(self, digest: str, canonical: str, recording: Recording) -> None:
        responses = [*self._load(digest), recording]
        payload = {'request': json.loads(canonical), 'responses': [vars(item) for item in responses]}
        self.cassettes.mkdir(parents=True, exist_ok=True)
        self._path(digest).write_text(json.dumps(payload, indent=2) + '\n')

    async def _forward(self, request: Request, raw: bytes) -> Recording:
        skipped = {'host', 'content-length', 'x-api-key', 'authorization', 'accept-encoding'}
        headers = {key: value for key, value in request.headers.items() if key not in skipped}
        headers['x-api-key'] = self.api_key
        async with httpx.AsyncClient(base_url=self.upstream, transport=self.transport, timeout=600) as client:
            reply = await client.request(
                request.method,
                request.url.path,
                params=request.query_params,
                content=raw,
                headers=headers,
            )
        return Recording(reply.status_code, reply.headers.get('content-type', 'application/json'), reply.text)

    async def handle(self, request: Request) -> Response:
        """Serve one API call according to the model mode."""
        raw = await request.body()
        body = json.loads(raw) if raw else {}
        path = request.url.path
        canonical = canonical_request(path, body, self.rules)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        occurrence = self.calls[digest]
        self.calls[digest] += 1
        if self.mode != 'replay':
            recording = await self._forward(request, raw)
            if self.mode == 'record' and not httpx.codes.is_server_error(recording.status):
                self._save(digest, canonical, recording)
            return recording.response()
        recorded = self._load(digest)
        if not recorded:
            self.misses.append(f'{request.method} {path} {digest}')
            message = (
                f'No recording for {path} request {digest} in {self.cassettes.name}; '
                're-run the scenario with --model-mode record.'
            )
            return JSONResponse({'type': 'error', 'error': {'type': 'invalid_request_error', 'message': message}}, 400)
        return recorded[occurrence % len(recorded)].response()

    def app(self) -> Starlette:
        """Return the ASGI app, which answers every path the Claude Code CLI calls."""
        return Starlette(routes=[Route('/{path:path}', self.handle, methods=['GET', 'POST'])])


@contextmanager
def serve(mock: MockAnthropic, port: int) -> Iterator[str]:
    """Run `mock` on localhost in a background thread and yield its base URL."""
    server = uvicorn.Server(uvicorn.Config(mock.app(), host='127.0.0.1', port=port, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        thread.join(0.05)
    mock.url = f'http://127.0.0.1:{port}'
    try:
        yield mock.url
    finally:
        server.should_exit = True
        thread.join(10)
