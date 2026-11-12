"""Tests for the consumers module."""

import asyncio
import json
from typing import Any

import aio_pika
import pytest

from agentorg.core.operations import Broker, QueueConsumers, Run, Store, admit_all
from agentorg.core.spec import QueueTrigger, Spec

from .conftest import FakeBroker, Queued


@pytest.fixture
def spec(spec_dict_minimal: dict[str, Any]) -> Spec:
    """A solo org with a CRM queue trigger filtered to orders."""
    spec_dict_minimal['operations'] = {
        'triggers': [
            {
                'kind': 'queue',
                'id': 'crm',
                'target': 'assistant',
                'prompt': 'Order: {message}',
                'queue': 'crm.orders',
                'filter': {'type': 'order'},
            },
        ],
    }
    return Spec.model_validate(spec_dict_minimal)


def _consumers(spec: Spec, broker: Any, enqueue: Any) -> QueueConsumers:
    async def broker_for(_: QueueTrigger) -> Any:
        return broker

    return QueueConsumers(spec, broker_for, enqueue, admit_all, dict)


async def test_queue_consumer_starts_run_then_acks(spec: Spec, store: Store, fake_broker: FakeBroker) -> None:
    """An order message creates a run with the message in its prompt, and is acknowledged after."""
    queued = Queued(store)
    await _consumers(spec, fake_broker, queued).start()
    message = await fake_broker.push_external('crm.orders', json.dumps({'type': 'order', 'id': 'A-1'}).encode())
    assert [(run.trigger_kind, run.prompt) for run in queued.runs] == [
        ('queue', 'Order: {"type": "order", "id": "A-1"}'),
    ]
    assert message.acked


async def test_queue_consumer_ignores_filter_mismatch(spec: Spec, store: Store, fake_broker: FakeBroker) -> None:
    """A message that fails the filter is acknowledged without a run."""
    queued = Queued(store)
    await _consumers(spec, fake_broker, queued).start()
    message = await fake_broker.push_external('crm.orders', json.dumps({'type': 'refund'}).encode())
    assert queued.runs == []
    assert message.acked


async def test_queue_consumer_rejects_unparseable_message(spec: Spec, store: Store, fake_broker: FakeBroker) -> None:
    """A body that is not JSON is rejected without requeue and creates no run."""
    queued = Queued(store)
    await _consumers(spec, fake_broker, queued).start()
    message = await fake_broker.push_external('crm.orders', b'not json')
    assert (message.rejected, message.requeued, queued.runs) == (True, False, [])


async def test_queue_consumer_redelivers_after_crash_before_run(spec: Spec, store: Store, amqp_url: str) -> None:
    """A crash before the run exists leaves the message unacknowledged, and its redelivery creates exactly one run."""
    broker = Broker(amqp_url, 'acme')
    await broker.connect()
    queued = Queued(store)
    attempts: list[int] = []
    done = asyncio.Event()

    async def crashing_once(target: str, trigger_kind: str, prompt: str, **fields: Any) -> Run:
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionError
        run = await queued(target, trigger_kind, prompt, **fields)
        done.set()
        return run

    consumers = _consumers(spec, broker, crashing_once)
    await consumers.start()
    order = aio_pika.Message(json.dumps({'type': 'order', 'id': 'A-1'}).encode())
    await broker.channel.default_exchange.publish(order, routing_key='crm.orders')
    await asyncio.sleep(1)
    await consumers.stop()
    await consumers.start()
    await asyncio.wait_for(done.wait(), 10)
    await consumers.stop()
    await broker.close()
    assert len(queued.runs) == 1
    assert len(attempts) == 2
