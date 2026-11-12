"""Publish org events and start the runs of the event triggers subscribed to them."""

import json
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any, Protocol

from ..spec import EventTrigger, Spec
from ._intake import Admit, Enqueue, Parameters, payload_tags
from ._prompts import render_prompt
from ._queue import Message
from ._store import InboxItem, Store


class EventBroker(Protocol):
    """The broker operations the event bus uses."""

    async def publish_event(self, name: str, payload: dict[str, Any], chain: list[str]) -> None:
        """Publish an event."""
        ...

    async def consume_events(self, trigger_id: str, event: str, handler: Callable[[Any], Awaitable[None]]) -> str:
        """Consume a trigger's event queue."""
        ...

    async def cancel(self, consumer_tag: str) -> None:
        """Stop a consumer."""
        ...


class EventBus:
    """The org event bus: built-in and `custom.*` events routed to event triggers.

    Arguments:
        spec: The org spec.
        store: The operations store, where loop warnings are recorded.
        broker: The broker carrying events.
        enqueue: Queues a triggered run.
        admit: Refuses work for targets that may not take it now.
        parameters: Returns the parameter values used in prompts.
    """

    def __init__(
        self,
        spec: Spec,
        store: Store,
        broker: EventBroker,
        enqueue: Enqueue,
        *,
        admit: Admit,
        parameters: Parameters,
    ) -> None:
        self.spec = spec
        self.store = store
        self.broker = broker
        self.enqueue = enqueue
        self.admit = admit
        self.parameters = parameters
        self._consumers: list[str] = []

    @property
    def triggers(self) -> list[EventTrigger]:
        """The org's enabled event triggers."""
        return [
            trigger
            for trigger in self.spec.operations.triggers
            if isinstance(trigger, EventTrigger) and trigger.enabled
        ]

    async def publish(self, name: str, payload: dict[str, Any], chain: list[str] | None = None) -> None:
        """Publish event `name` with `payload`, carrying the chain of triggers that caused it."""
        await self.broker.publish_event(name, payload, chain or [])

    async def publish_knowledge(self, action: str, unit: dict[str, Any]) -> None:
        """Publish `knowledge.created` or `knowledge.updated` for a knowledge unit written to memory."""
        await self.publish(f'knowledge.{action}', {'type': unit.get('type'), 'name': unit.get('name')})

    async def _handle(self, trigger: EventTrigger, message: Message) -> None:
        """Start the trigger's run for a matching event, unless the chain is too long."""
        data = json.loads(message.body)
        payload, chain = data['payload'], data['chain']
        if any(payload.get(key) != value for key, value in trigger.filter.items()):
            await message.ack()
            return
        if len(chain) >= self.spec.operations.communication.max_chain_depth:
            reason = f"Event chain stopped at trigger '{trigger.id}' after {' -> '.join(chain)}; check for a loop."
            await self.store.add(InboxItem(kind='warning', reason=reason, context={'chain': [*chain, trigger.id]}))
            await message.ack()
            return
        if await self.admit(trigger.target) is None:
            prompt = render_prompt(trigger.prompt, trigger_id=trigger.id, parameters=self.parameters(), event=payload)
            await self.enqueue(
                trigger.target,
                'event',
                prompt,
                trigger_id=trigger.id,
                chain=[*chain, trigger.id],
                tags=payload_tags(payload),
            )
        await message.ack()

    async def start(self) -> None:
        """Subscribe every enabled event trigger to its event."""
        for trigger in self.triggers:
            self._consumers.append(
                await self.broker.consume_events(trigger.id, trigger.event, partial(self._handle, trigger)),
            )

    async def stop(self) -> None:
        """Unsubscribe every event trigger, leaving events queued."""
        for tag in self._consumers:
            await self.broker.cancel(tag)
        self._consumers.clear()
