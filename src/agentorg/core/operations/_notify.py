"""Send notifications to the dashboard, email, a webhook and an AMQP exchange."""

import asyncio
import json
import smtplib
from collections.abc import Awaitable, Callable, Mapping
from email.message import EmailMessage
from typing import Any, Protocol

import httpx

from ..spec import Spec
from ._store import InboxItem, Store

SendEmail = Callable[[list[str], str, str], Awaitable[None]]


class ExternalPublisher(Protocol):
    """Publish a JSON message to an exchange outside the org's prefix."""

    async def publish_external(self, exchange: str, routing_key: str, payload: dict[str, Any]) -> None:
        """Publish `payload` with `routing_key` to `exchange`."""
        ...


def smtp_sender(environ: Mapping[str, str]) -> SendEmail:
    """Return an email sender over the SMTP server set by the `SMTP_*` environment variables."""

    def send(recipients: list[str], subject: str, body: str) -> None:
        message = EmailMessage()
        message['From'], message['To'], message['Subject'] = (
            environ.get('SMTP_FROM', ''),
            ', '.join(recipients),
            subject,
        )
        message.set_content(body)
        with smtplib.SMTP(environ.get('SMTP_HOST', 'localhost'), int(environ.get('SMTP_PORT', '587'))) as server:
            server.starttls()
            if environ.get('SMTP_USER'):
                server.login(environ['SMTP_USER'], environ.get('SMTP_PASSWORD', ''))
            server.send_message(message)

    async def send_async(recipients: list[str], subject: str, body: str) -> None:
        await asyncio.to_thread(send, recipients, subject, body)

    return send_async


class Notifier:
    """Fan a notification out to every channel the org declares.

    Arguments:
        spec: The org spec, whose `operations.notifications` names the channels.
        store: The operations store, which backs the dashboard channel.
        environ: The environment holding the webhook URL and SMTP settings.
        broker: Publishes to the AMQP exchange.
        send_email: Sends email; SMTP from `environ` by default.
        http: The HTTP client for the webhook channel.
    """

    def __init__(
        self,
        spec: Spec,
        store: Store,
        *,
        environ: Mapping[str, str],
        broker: ExternalPublisher | None = None,
        send_email: SendEmail | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.spec = spec
        self.store = store
        self.environ = environ
        self.broker = broker
        self.send_email = send_email or smtp_sender(environ)
        self.http = http or httpx.AsyncClient(timeout=10)

    async def notify(self, kind: str, payload: dict[str, Any]) -> None:
        """Send a notification of `kind`, such as `run_failed` or `budget_alert`, to every declared channel.

        Arguments:
            kind: The notification kind, in snake case.
            payload: The JSON-serialisable details.
        """
        settings = self.spec.operations.notifications
        summary = f'{self.spec.org.name}: {kind.replace("_", " ")}'
        if kind != 'escalation':
            await self.store.add(InboxItem(kind='notification', reason=summary, context={'kind': kind, **payload}))
        message = {'org': self.spec.org.slug, 'kind': kind, **payload}
        if 'email' in settings.channels:
            await self.send_email(settings.email_to, summary, json.dumps(message, indent=2, default=str))
        if 'webhook' in settings.channels and settings.webhook_url_env:
            await self.http.post(self.environ.get(settings.webhook_url_env, ''), json=message)
        if 'amqp' in settings.channels and settings.amqp_exchange and self.broker is not None:
            await self.broker.publish_external(settings.amqp_exchange, kind.replace('_', '.'), message)
