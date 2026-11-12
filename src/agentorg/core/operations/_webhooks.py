"""Accept signed webhook calls and start the runs of their webhook triggers."""

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from datetime import timedelta

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from ..spec import Spec, WebhookTrigger
from ._intake import Admit, Enqueue, Parameters, payload_tags
from ._prompts import render_prompt
from ._store import Store

IDEMPOTENCY_WINDOW = timedelta(hours=24)


def sign(secret: str, body: bytes) -> str:
    """Return the `sha256=<hex>` signature of `body` under `secret`, as senders put in `X-Agentorg-Signature`."""
    return 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def build_webhook_router(
    spec: Spec,
    store: Store,
    enqueue: Enqueue,
    admit: Admit,
    parameters: Parameters,
    *,
    environ: Mapping[str, str],
    broker_healthy: Callable[[], bool],
) -> APIRouter:
    """Return the router serving `POST /hooks/{trigger_id}` for the org's webhook triggers.

    Arguments:
        spec: The org spec.
        store: The operations store, which keeps idempotency keys.
        enqueue: Queues the triggered run.
        admit: Refuses work for targets that may not take it now.
        parameters: Returns the parameter values used in prompts.
        environ: The environment holding each trigger's secret.
        broker_healthy: Returns whether the broker can take new runs.

    Returns:
        router: The webhook router.
    """
    triggers = {t.id: t for t in spec.operations.triggers if isinstance(t, WebhookTrigger) and t.enabled}
    router = APIRouter()

    @router.post('/hooks/{trigger_id}', status_code=202)
    async def receive(
        trigger_id: str,
        request: Request,
        x_agentorg_signature: str = Header(default=''),
        idempotency_key: str | None = Header(default=None),
    ) -> JSONResponse:
        trigger = triggers.get(trigger_id)
        if trigger is None:
            raise HTTPException(status_code=404, detail=f"No webhook trigger '{trigger_id}'.")
        body = await request.body()
        expected = sign(environ.get(trigger.secret_env, ''), body)
        if not environ.get(trigger.secret_env) or not hmac.compare_digest(expected, x_agentorg_signature):
            raise HTTPException(status_code=401, detail='Invalid signature.')
        key = f'{trigger_id}:{idempotency_key}' if idempotency_key else None
        known = await store.get_value('idempotency', key) if key else None
        if isinstance(known, str):
            return JSONResponse({'run_id': known}, status_code=202)
        if not broker_healthy():
            raise HTTPException(status_code=503, detail='The broker is unavailable; retry later.')
        refusal = await admit(trigger.target)
        if refusal is not None:
            raise HTTPException(status_code=409, detail=refusal)
        payload = json.loads(body) if body else None
        prompt = render_prompt(trigger.prompt, trigger_id=trigger_id, parameters=parameters(), body=payload)
        run = await enqueue(trigger.target, 'webhook', prompt, trigger_id=trigger_id, tags=payload_tags(payload))
        if key:
            await store.set_value('idempotency', key, run.id, ttl=IDEMPOTENCY_WINDOW)
        return JSONResponse({'run_id': run.id}, status_code=202)

    return router
