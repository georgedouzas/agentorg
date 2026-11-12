"""Start runs from messages on external AMQP queues."""

import json
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any, Protocol

from ..spec import QueueTrigger, Spec
from ._intake import Admit, Enqueue, Parameters, payload_tags
from ._prompts import render_prompt


class InboundMessage(Protocol):
    """The part of a broker message a queue consumer uses."""

    body: bytes

    async def ack(self) -> None:
        """Acknowledge the message."""
        ...

    async def reject(self, requeue: bool = False) -> None:
        """Reject the message."""
        ...


class QueueBroker(Protocol):
    """The broker operations a queue consumer uses."""

    async def consume_queue(self, name: str, handler: Callable[[Any], Awaitable[None]]) -> str:
        """Consume an external queue."""
        ...

    async def cancel(self, consumer_tag: str) -> None:
        """Stop a consumer."""
        ...


BrokerFor = Callable[[QueueTrigger], Awaitable[QueueBroker]]


class QueueConsumers:
    """Consume the queues named by the org's queue triggers.

    Arguments:
        spec: The org spec.
        broker_for: Returns the broker a trigger consumes from: its `url_env` broker or the org broker.
        enqueue: Queues the triggered run.
        admit: Refuses work for targets that may not take it now.
        parameters: Returns the parameter values used in prompts.
    """

    def __init__(
        self,
        spec: Spec,
        broker_for: BrokerFor,
        enqueue: Enqueue,
        admit: Admit,
        parameters: Parameters,
    ) -> None:
        self.spec = spec
        self.broker_for = broker_for
        self.enqueue = enqueue
        self.admit = admit
        self.parameters = parameters
        self._consumers: list[tuple[QueueBroker, str]] = []

    @property
    def triggers(self) -> list[QueueTrigger]:
        """The org's enabled queue triggers."""
        return [t for t in self.spec.operations.triggers if isinstance(t, QueueTrigger) and t.enabled]

    async def _handle(self, trigger: QueueTrigger, message: InboundMessage) -> None:
        """Start the trigger's run for a matching message, then acknowledge it."""
        try:
            payload = json.loads(message.body)
        except json.JSONDecodeError:
            await message.reject(requeue=False)
            return
        matches = isinstance(payload, dict) and all(payload.get(k) == v for k, v in trigger.filter.items())
        if matches and await self.admit(trigger.target) is None:
            prompt = render_prompt(trigger.prompt, trigger_id=trigger.id, parameters=self.parameters(), message=payload)
            await self.enqueue(trigger.target, 'queue', prompt, trigger_id=trigger.id, tags=payload_tags(payload))
        await message.ack()

    async def start(self) -> None:
        """Start consuming every enabled queue trigger's queue."""
        for trigger in self.triggers:
            broker = await self.broker_for(trigger)
            self._consumers.append((broker, await broker.consume_queue(trigger.queue, partial(self._handle, trigger))))

    async def stop(self) -> None:
        """Stop every consumer, leaving messages on their queues."""
        for broker, tag in self._consumers:
            await broker.cancel(tag)
        self._consumers.clear()
