"""Tests for the notify module."""

import json
from typing import Any

import httpx

from agentorg.core.operations import Notifier, Store
from agentorg.core.spec import Spec

from .conftest import FakeBroker


def _spec(spec_dict_minimal: dict[str, Any], **notifications: Any) -> Spec:
    spec_dict_minimal['runtime']['env_vars']['required'] = [
        {'name': 'OPS_WEBHOOK_URL', 'description': 'Ops webhook.', 'required_label': 'Prod'},
    ]
    spec_dict_minimal['operations'] = {'notifications': notifications}
    return Spec.model_validate(spec_dict_minimal)


async def test_notifier_posts_webhook_json(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """The webhook channel POSTs a JSON description of an escalation to the configured URL."""
    posted: list[tuple[str, dict[str, Any]]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        posted.append((str(request.url), json.loads(request.content)))
        return httpx.Response(204)

    spec = _spec(spec_dict_minimal, channels=['webhook'], webhook_url_env='OPS_WEBHOOK_URL')
    http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    notifier = Notifier(spec, store, environ={'OPS_WEBHOOK_URL': 'https://ops.example/hook'}, http=http)
    await notifier.notify('escalation', {'run_id': 'r1', 'reason': 'Legal threat'})
    assert posted == [
        ('https://ops.example/hook', {'org': 'acme', 'kind': 'escalation', 'run_id': 'r1', 'reason': 'Legal threat'}),
    ]


async def test_notifier_publishes_amqp_with_routing_key(
    spec_dict_minimal: dict[str, Any],
    store: Store,
    fake_broker: FakeBroker,
) -> None:
    """The AMQP channel publishes a message routed by kind, such as `run.failed`."""
    spec = _spec(spec_dict_minimal, channels=['amqp'], amqp_exchange='ops')
    await Notifier(spec, store, environ={}, broker=fake_broker).notify('run_failed', {'run_id': 'r1'})
    assert fake_broker.external == [('ops', 'run.failed', {'org': 'acme', 'kind': 'run_failed', 'run_id': 'r1'})]


async def test_notifier_sends_email_to_recipients(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """The email channel sends a subject naming the org and kind to every recipient."""
    sent: list[tuple[list[str], str, str]] = []

    async def send(recipients: list[str], subject: str, body: str) -> None:
        sent.append((recipients, subject, body))

    spec = _spec(spec_dict_minimal, channels=['email'], email_to=['ops@acme.com'])
    await Notifier(spec, store, environ={}, send_email=send).notify('budget_alert', {'spend_usd': 8})
    assert [(recipients, subject) for recipients, subject, _ in sent] == [(['ops@acme.com'], 'Acme: budget alert')]
    assert json.loads(sent[0][2])['spend_usd'] == 8


async def test_notifier_always_records_dashboard_notification(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """Every notification except an escalation, which is already an inbox item, appears on the dashboard."""
    notifier = Notifier(_spec(spec_dict_minimal), store, environ={})
    await notifier.notify('lifecycle_changed', {'to': 'paused'})
    await notifier.notify('escalation', {'reason': 'x'})
    assert [(item.kind, item.context['kind']) for item in await store.list_inbox()] == [
        ('notification', 'lifecycle_changed'),
    ]
