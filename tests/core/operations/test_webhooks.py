"""Tests for the webhooks module."""

import json
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from agentorg.core.operations import Store, admit_all, build_webhook_router, sign
from agentorg.core.spec import Spec

from .conftest import Queued

SIGNING_KEY = 'test-signing-key'


@pytest.fixture
def spec(spec_dict_minimal: dict[str, Any]) -> Spec:
    """A solo org with a helpdesk webhook trigger."""
    spec_dict_minimal['runtime']['env_vars']['required'] = [
        {'name': 'HELPDESK_SECRET', 'description': 'Webhook secret.', 'required_label': 'Prod'},
    ]
    spec_dict_minimal['operations'] = {
        'triggers': [
            {
                'kind': 'webhook',
                'id': 'helpdesk',
                'target': 'assistant',
                'prompt': 'Ticket: {body}',
                'secret_env': 'HELPDESK_SECRET',
            },
        ],
    }
    return Spec.model_validate(spec_dict_minimal)


def _client(
    spec: Spec,
    store: Store,
    queued: Queued,
    healthy: bool = True,
    admit: Any = admit_all,
) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(
        build_webhook_router(spec, store, queued, admit, dict, {'HELPDESK_SECRET': SIGNING_KEY}, lambda: healthy),
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://org')


def _signed(payload: dict[str, Any], key: str = SIGNING_KEY) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload).encode()
    return body, {'X-Agentorg-Signature': sign(key, body), 'Content-Type': 'application/json'}


async def test_webhook_accepts_signed_call(spec: Spec, store: Store) -> None:
    """A correctly signed call returns 202 with the id of the run it created."""
    queued = Queued(store)
    body, headers = _signed({'ticket': 42})
    async with _client(spec, store, queued) as client:
        response = await client.post('/hooks/helpdesk', content=body, headers=headers)
    assert response.status_code == 202
    assert response.json() == {'run_id': queued.runs[0].id}
    assert (queued.runs[0].trigger_kind, queued.runs[0].prompt) == ('webhook', 'Ticket: {"ticket": 42}')


async def test_webhook_rejects_bad_signature(spec: Spec, store: Store) -> None:
    """A call signed with the wrong secret is rejected and creates no run."""
    queued = Queued(store)
    body, headers = _signed({'ticket': 42}, key='other-key')
    async with _client(spec, store, queued) as client:
        response = await client.post('/hooks/helpdesk', content=body, headers=headers)
    assert response.status_code == 401
    assert queued.runs == []


async def test_webhook_deduplicates_by_idempotency_key(spec: Spec, store: Store) -> None:
    """A retried delivery with the same key returns the original run id without a new run."""
    queued = Queued(store)
    body, headers = _signed({'ticket': 42})
    headers['Idempotency-Key'] = 'delivery-1'
    async with _client(spec, store, queued) as client:
        first = await client.post('/hooks/helpdesk', content=body, headers=headers)
        second = await client.post('/hooks/helpdesk', content=body, headers=headers)
    assert first.json() == second.json()
    assert len(queued.runs) == 1


async def test_webhook_returns_503_when_broker_is_down(spec: Spec, store: Store) -> None:
    """With the broker unavailable the call is refused so the sender retries."""
    queued = Queued(store)
    body, headers = _signed({'ticket': 42})
    async with _client(spec, store, queued, healthy=False) as client:
        response = await client.post('/hooks/helpdesk', content=body, headers=headers)
    assert response.status_code == 503
    assert queued.runs == []


async def test_webhook_returns_409_when_target_refuses_work(spec: Spec, store: Store) -> None:
    """A target that refuses work, for example in a retired org, yields 409 with the reason."""

    async def refuse(target: str) -> str | None:
        return 'The org is retired.'

    body, headers = _signed({'ticket': 42})
    async with _client(spec, store, Queued(store), admit=refuse) as client:
        response = await client.post('/hooks/helpdesk', content=body, headers=headers)
    assert (response.status_code, response.json()['detail']) == (409, 'The org is retired.')


async def test_webhook_unknown_trigger_is_404(spec: Spec, store: Store) -> None:
    """A path that names no webhook trigger is not found."""
    async with _client(spec, store, Queued(store)) as client:
        response = await client.post('/hooks/nope', content=b'{}')
    assert response.status_code == 404
