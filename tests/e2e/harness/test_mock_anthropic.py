"""Self-tests for the mock Anthropic API."""

import json
from pathlib import Path
from typing import Any

import httpx
from starlette.testclient import TestClient

from .mock_anthropic import MockAnthropic, Recording, request_hash

SSE = (
    'event: message_start\ndata: {"type":"message_start"}\n\n'
    'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"text":"hi"}}\n\n'
    'event: message_stop\ndata: {"type":"message_stop"}\n\n'
)


def _body(text: str = 'Hello', **fields: Any) -> dict[str, Any]:
    return {
        'model': 'claude-sonnet-5-5',
        'max_tokens': 1024,
        'system': [{'type': 'text', 'text': 'You are helpful.', 'cache_control': {'type': 'ephemeral'}}],
        'messages': [{'role': 'user', 'content': text}],
        **fields,
    }


def _record(mock: MockAnthropic, body: dict[str, Any], *recordings: Recording) -> None:
    payload = {'request': {}, 'responses': [vars(item) for item in recordings]}
    mock.cassettes.mkdir(parents=True, exist_ok=True)
    (mock.cassettes / f'{request_hash("/v1/messages", body)}.json').write_text(json.dumps(payload))


def test_hash_ignores_key_order_cache_markers_and_metadata() -> None:
    """Field order, cache markers and unhashed fields such as metadata do not change the hash."""
    body = _body()
    reordered = dict(reversed(list(body.items())))
    reordered['system'] = [{'text': 'You are helpful.', 'type': 'text'}]
    reordered['metadata'] = {'user_id': 'someone'}
    assert request_hash('/v1/messages', body) == request_hash('/v1/messages', reordered)


def test_hash_normalises_environment_dates_and_temp_paths() -> None:
    """Platform lines, dates, run ids and temp paths are stripped before hashing."""
    first = _body(
        'Platform: darwin\nToday\'s date is 2026-11-12.\nRun 1b4e28ba-2fa1-11d2-883f-0016d3cca427 in /tmp/abc/x',
    )
    second = _body(
        'Platform: linux\nToday\'s date is 2027-01-02.\nRun 6fa459ea-ee8a-3ca4-894e-db77e160355e in /tmp/zz/y',
    )
    assert request_hash('/v1/messages', first) == request_hash('/v1/messages', second)


def test_hash_changes_with_the_prompt_tools_and_path() -> None:
    """A different message, tool schema or endpoint yields a different hash."""
    tool = {'name': 'echo', 'description': 'Echo.', 'input_schema': {'type': 'object'}}
    hashes = {
        request_hash('/v1/messages', _body()),
        request_hash('/v1/messages', _body('Bye')),
        request_hash('/v1/messages', _body(tools=[tool])),
        request_hash('/v1/messages/count_tokens', _body()),
    }
    assert len(hashes) == 4
    assert request_hash('/v1/messages', _body(tools=[tool])) == request_hash(
        '/v1/messages',
        _body(tools=[{**tool, 'description': 'Reworded.'}]),
    )


def test_replay_serves_json_responses_in_order(tmp_path: Path) -> None:
    """Repeated identical requests replay their recordings in the order they were recorded."""
    mock = MockAnthropic(tmp_path / 'scenario')
    first = Recording(200, 'application/json', '{"id": "msg_1"}')
    second = Recording(200, 'application/json', '{"id": "msg_2"}')
    _record(mock, _body(), first, second)
    client = TestClient(mock.app())
    ids = [client.post('/v1/messages', json=_body()).json()['id'] for _ in range(2)]
    assert ids == ['msg_1', 'msg_2']


def test_replay_streams_the_recorded_event_sequence(tmp_path: Path) -> None:
    """A recorded stream replays as the same server-sent events."""
    mock = MockAnthropic(tmp_path / 'scenario')
    _record(mock, _body(stream=True), Recording(200, 'text/event-stream', SSE))
    with TestClient(mock.app()).stream('POST', '/v1/messages', json=_body(stream=True)) as reply:
        assert reply.headers['content-type'].startswith('text/event-stream')
        events = [line.removeprefix('event: ') for line in reply.iter_lines() if line.startswith('event: ')]
    assert events == ['message_start', 'content_block_delta', 'message_stop']


def test_replay_reports_a_missing_recording(tmp_path: Path) -> None:
    """An unrecorded request fails with a message naming the scenario and the record mode."""
    mock = MockAnthropic(tmp_path / 'support-desk')
    reply = TestClient(mock.app()).post('/v1/messages', json=_body())
    assert reply.status_code == 400
    assert 'support-desk' in reply.json()['error']['message']
    assert '--model-mode record' in reply.json()['error']['message']
    assert mock.misses == [f'POST /v1/messages {request_hash("/v1/messages", _body())}']


def test_record_proxies_upstream_and_saves_a_cassette(tmp_path: Path) -> None:
    """Record mode forwards with the real key, returns the upstream reply and saves it for replay."""
    seen: list[httpx.Request] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=SSE, headers={'content-type': 'text/event-stream'})

    cassettes = tmp_path / 'scenario'
    recorder = MockAnthropic(cassettes, mode='record', api_key='real-key', transport=httpx.MockTransport(upstream))
    reply = TestClient(recorder.app()).post('/v1/messages', json=_body(stream=True), headers={'x-api-key': 'fake'})
    assert (reply.status_code, reply.text) == (200, SSE)
    assert seen[0].headers['x-api-key'] == 'real-key'
    replayed = TestClient(MockAnthropic(cassettes).app()).post('/v1/messages', json=_body(stream=True))
    assert replayed.text == SSE


def test_live_proxies_without_saving(tmp_path: Path) -> None:
    """Live mode returns upstream replies and writes no cassette."""

    def upstream(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'id': 'msg_live'})

    cassettes = tmp_path / 'scenario'
    live = MockAnthropic(cassettes, mode='live', api_key='k', transport=httpx.MockTransport(upstream))
    assert TestClient(live.app()).post('/v1/messages', json=_body()).json() == {'id': 'msg_live'}
    assert not cassettes.exists()


def test_parallel_tool_results_hash_the_same_in_any_order() -> None:
    """Tool results of parallel calls match whichever finished first."""
    first = {'type': 'tool_result', 'tool_use_id': 'toolu_a', 'content': 'A'}
    second = {'type': 'tool_result', 'tool_use_id': 'toolu_b', 'content': 'B'}

    def body(*results: dict[str, str]) -> dict[str, object]:
        return {'model': 'claude-opus-5-5', 'messages': [{'role': 'user', 'content': list(results)}]}

    assert request_hash('/v1/messages', body(first, second)) == request_hash('/v1/messages', body(second, first))
