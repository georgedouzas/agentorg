"""Carry runs, retries, dead letters and org events over RabbitMQ."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

import aio_pika
from aio_pika.abc import (
    AbstractChannel,
    AbstractIncomingMessage,
    AbstractQueue,
    AbstractRobustChannel,
    AbstractRobustConnection,
)

MAX_PRIORITY = 4

MessageHandler = Callable[[AbstractIncomingMessage], Awaitable[None]]


class Broker:
    """The org's RabbitMQ topology and the operations that publish to and consume from it.

    Arguments:
        url: The AMQP URL, read from `AMQP_URL`.
        slug: The org slug.
        retry_base_s: The delay of the first retry; retry `n` waits `retry_base_s * 2**n` seconds.
    """

    def __init__(self, url: str, slug: str, retry_base_s: float = 30.0) -> None:
        self.url = url
        self.slug = slug
        self.retry_base_s = retry_base_s
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractRobustChannel | None = None
        self._consumers: dict[str, tuple[AbstractQueue, AbstractChannel]] = {}

    def _name(self, *parts: str) -> str:
        return '.'.join((self.slug, *parts))

    @property
    def channel(self) -> AbstractRobustChannel:
        """The open channel; `connect` must have been awaited."""
        if self._channel is None:
            msg = 'The broker is not connected; await Broker.connect() first.'
            raise RuntimeError(msg)
        return self._channel

    @property
    def is_healthy(self) -> bool:
        """Whether the connection is open."""
        return self._connection is not None and not self._connection.is_closed

    async def connect(self) -> None:
        """Open a reconnecting connection and declare the run, retry, dead-letter and event exchanges."""
        self._connection = await aio_pika.connect_robust(self.url)
        self._channel = await self._connection.channel()
        await self.channel.declare_exchange(self._name('runs'), aio_pika.ExchangeType.DIRECT, durable=True)
        await self.channel.declare_exchange(self._name('events'), aio_pika.ExchangeType.TOPIC, durable=True)
        dead = await self.channel.declare_exchange(self._name('dead'), aio_pika.ExchangeType.FANOUT, durable=True)
        queue = await self.channel.declare_queue(self._name('runs', 'dead'), durable=True)
        await queue.bind(dead)

    async def declare_targets(self, targets: list[str], retries: int) -> None:
        """Declare one priority run queue per target and one delay queue per retry attempt."""
        exchange = await self.channel.get_exchange(self._name('runs'))
        for target in targets:
            arguments = {'x-max-priority': MAX_PRIORITY, 'x-dead-letter-exchange': self._name('dead')}
            queue = await self.channel.declare_queue(self._name('runs', target), durable=True, arguments=arguments)
            await queue.bind(exchange, routing_key=target)
        for attempt in range(max(retries, 1)):
            ttl_ms = int(self.retry_base_s * 2**attempt * 1000)
            arguments = {'x-message-ttl': ttl_ms, 'x-dead-letter-exchange': self._name('runs')}
            name = self._name('runs', 'retry', str(attempt))
            delay = await self.channel.declare_exchange(name, aio_pika.ExchangeType.FANOUT, durable=True)
            queue = await self.channel.declare_queue(name, durable=True, arguments=arguments)
            await queue.bind(delay)

    async def _publish(self, exchange: str, routing_key: str, payload: dict[str, Any], priority: int = 0) -> None:
        message = aio_pika.Message(
            json.dumps(payload).encode(),
            content_type='application/json',
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            priority=priority,
        )
        await (await self.channel.get_exchange(exchange)).publish(message, routing_key=routing_key)

    async def publish_run(self, target: str, run_id: str, priority: int) -> None:
        """Queue run `run_id` on its target's run queue with `priority` (0 to 4, higher first)."""
        await self._publish(self._name('runs'), target, {'run_id': run_id}, priority)

    async def publish_retry(self, target: str, run_id: str, attempt: int, priority: int = 0) -> None:
        """Delay run `run_id` on the queue of retry `attempt`, after which it returns to its target's run queue."""
        await self._publish(self._name('runs', 'retry', str(attempt)), target, {'run_id': run_id}, priority)

    async def publish_dead(self, run_id: str) -> None:
        """Send run `run_id` to the dead-letter queue."""
        await self._publish(self._name('dead'), '', {'run_id': run_id})

    async def publish_event(self, name: str, payload: dict[str, Any], chain: list[str]) -> None:
        """Publish an org event with the chain of triggers that led to it."""
        await self._publish(self._name('events'), name, {'event': name, 'payload': payload, 'chain': chain})

    async def publish_external(self, exchange: str, routing_key: str, payload: dict[str, Any]) -> None:
        """Publish a persistent JSON message to an exchange outside the org's prefix."""
        declared = await self.channel.declare_exchange(exchange, aio_pika.ExchangeType.TOPIC, durable=True)
        message = aio_pika.Message(json.dumps(payload).encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT)
        await declared.publish(message, routing_key=routing_key)

    async def _consume(self, queue_name: str, handler: MessageHandler, prefetch: int, declare: bool) -> str:
        if self._connection is None:
            msg = 'The broker is not connected; await Broker.connect() first.'
            raise RuntimeError(msg)
        channel = await self._connection.channel()
        await channel.set_qos(prefetch_count=prefetch)
        queue = (
            await channel.declare_queue(queue_name, durable=True) if declare else await channel.get_queue(queue_name)
        )
        tag = await queue.consume(handler)
        self._consumers[tag] = (queue, channel)
        return tag

    async def consume_runs(self, target: str, prefetch: int, handler: MessageHandler) -> str:
        """Consume run messages of `target` with at most `prefetch` unacknowledged, and return the consumer tag."""
        return await self._consume(self._name('runs', target), handler, prefetch, declare=False)

    async def consume_dead(self, handler: MessageHandler) -> str:
        """Consume dead-lettered runs and return the consumer tag."""
        return await self._consume(self._name('runs', 'dead'), handler, 1, declare=False)

    async def consume_events(self, trigger_id: str, event: str, handler: MessageHandler) -> str:
        """Consume events named `event` on a durable queue owned by `trigger_id` and return the consumer tag."""
        exchange = await self.channel.get_exchange(self._name('events'))
        queue = await self.channel.declare_queue(self._name('events', trigger_id), durable=True)
        await queue.bind(exchange, routing_key=event)
        return await self._consume(queue.name, handler, 1, declare=False)

    async def consume_queue(self, name: str, handler: MessageHandler) -> str:
        """Consume an external queue by its full name and return the consumer tag."""
        return await self._consume(name, handler, 1, declare=True)

    async def cancel(self, consumer_tag: str) -> None:
        """Stop the consumer `consumer_tag`, leaving its messages queued."""
        queue, channel = self._consumers.pop(consumer_tag)
        await queue.cancel(consumer_tag)
        await channel.close()

    async def close(self) -> None:
        """Close the connection."""
        if self._connection is not None:
            await self._connection.close()
