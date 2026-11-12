"""Tests for the broker module against a real RabbitMQ in a container."""

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from aio_pika.abc import AbstractIncomingMessage

from agentorg.core.operations import Broker


@pytest.fixture
async def broker(amqp_url: str) -> AsyncIterator[Broker]:
    """A connected broker with one target and a one-second retry delay."""
    broker = Broker(amqp_url, 'acme', retry_base_s=1.0)
    await broker.connect()
    await broker.declare_targets(['analyst'], retries=1)
    yield broker
    await broker.close()


async def _collect(broker: Broker, target: str, count: int, timeout: float) -> list[dict[str, str]]:
    received: list[dict[str, str]] = []
    done = asyncio.Event()

    async def handler(message: AbstractIncomingMessage) -> None:
        received.append(json.loads(message.body))
        await message.ack()
        if len(received) == count:
            done.set()

    tag = await broker.consume_runs(target, prefetch=10, handler=handler)
    await asyncio.wait_for(done.wait(), timeout)
    await broker.cancel(tag)
    return received


async def test_broker_declares_topology_idempotently(broker: Broker) -> None:
    """Declaring the topology twice succeeds."""
    await broker.connect()
    await broker.declare_targets(['analyst'], retries=1)
    assert broker.is_healthy


async def test_broker_delivers_by_priority(broker: Broker) -> None:
    """Queued runs are delivered highest priority first."""
    await broker.publish_run('analyst', 'scheduled', priority=0)
    await broker.publish_run('analyst', 'manual', priority=4)
    received = await _collect(broker, 'analyst', 2, timeout=10)
    assert [item['run_id'] for item in received] == ['manual', 'scheduled']


async def test_broker_retry_returns_to_target_after_delay(broker: Broker) -> None:
    """A retry waits on its delay queue and then reappears on the target's run queue."""
    loop = asyncio.get_running_loop()
    started = loop.time()
    await broker.publish_retry('analyst', 'r-1', attempt=0)
    received = await _collect(broker, 'analyst', 1, timeout=15)
    assert received == [{'run_id': 'r-1'}]
    assert loop.time() - started >= 0.9


async def test_broker_routes_events_to_bound_trigger(broker: Broker) -> None:
    """An event reaches the queue of the trigger bound to its name, with its chain."""
    received: list[dict[str, object]] = []
    done = asyncio.Event()

    async def handler(message: AbstractIncomingMessage) -> None:
        received.append(json.loads(message.body))
        await message.ack()
        done.set()

    tag = await broker.consume_events('on-report', 'knowledge.created', handler)
    await broker.publish_event('knowledge.created', {'type': 'report'}, chain=['weekly'])
    await asyncio.wait_for(done.wait(), 10)
    await broker.cancel(tag)
    assert received == [{'event': 'knowledge.created', 'payload': {'type': 'report'}, 'chain': ['weekly']}]
