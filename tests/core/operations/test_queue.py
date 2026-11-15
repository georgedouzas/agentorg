"""Tests for the queue module."""

import asyncio
import json
from typing import Any

import pytest

from agentorg.core import ConfigurationError
from agentorg.core.operations import Dispatcher, InlineDispatcher, Run, Store, broker_health, resolve_amqp_url
from agentorg.core.spec import Spec

from .conftest import FakeBroker, FakeMessage


class Recorder:
    """Executes runs by moving them to a scripted status, recording the order."""

    def __init__(self, store: Store, outcomes: dict[str, tuple[str, str | None]] | None = None) -> None:
        """Keep the store and the status each prompt should end in."""
        self.store = store
        self.outcomes = outcomes or {}
        self.order: list[str] = []
        self.failed: list[str] = []
        self.release = asyncio.Event()
        self.release.set()

    async def execute(self, run: Run) -> None:
        """Record the run and end it as scripted, succeeding by default."""
        self.order.append(run.prompt)
        await self.release.wait()
        status, reason = self.outcomes.get(run.prompt, ('succeeded', None))
        await self.store.transition(run.id, status, failure_reason=reason)  # type: ignore[arg-type]

    async def on_failure(self, run: Run) -> None:
        """Record dead-lettered runs."""
        self.failed.append(run.prompt)


@pytest.fixture
def spec(spec_dict_minimal: dict[str, Any]) -> Spec:
    """A solo org whose agent has two replicas and a run policy with one retry."""
    spec_dict_minimal['ai']['agents'][0]['replicas'] = 2
    return Spec.model_validate(spec_dict_minimal)


def _dispatcher(spec: Spec, store: Store, broker: FakeBroker, recorder: Recorder, worker: str = 'w1') -> Dispatcher:
    return Dispatcher(spec, store, broker, recorder.execute, on_failure=recorder.on_failure, worker_id=worker)


async def test_dispatcher_runs_manual_before_schedule(spec: Spec, store: Store, fake_broker: FakeBroker) -> None:
    """Queued work starts in priority order, manual first."""
    recorder = Recorder(store)
    dispatcher = _dispatcher(spec, store, fake_broker, recorder)
    scheduled = await dispatcher.enqueue('assistant', 'schedule', 'scheduled')
    manual = await dispatcher.enqueue('assistant', 'manual', 'manual')
    await dispatcher.start()
    await fake_broker.drain()
    delivered = [
        json.loads(message.body)['run_id'] for queue, message in fake_broker.delivered if queue == 'runs.assistant'
    ]
    assert delivered == [manual.id, scheduled.id]
    assert sorted(recorder.order) == ['manual', 'scheduled']


async def test_dispatcher_retries_transient_failure_once(spec: Spec, store: Store, fake_broker: FakeBroker) -> None:
    """A transient failure creates one linked retry, and a second failure is dead-lettered."""
    recorder = Recorder(store, {'flaky': ('failed', 'error')})
    dispatcher = _dispatcher(spec, store, fake_broker, recorder)
    await dispatcher.start()
    original = await dispatcher.enqueue('assistant', 'manual', 'flaky')
    await fake_broker.drain()
    assert [target for target, _, _ in fake_broker.retries] == ['assistant']
    retry_id = fake_broker.retries[0][1]
    assert (await store.get_run(retry_id)).retry_of == original.id  # type: ignore[union-attr]
    await fake_broker.release_retries()
    await fake_broker.drain()
    assert recorder.order == ['flaky', 'flaky']
    assert fake_broker.retries == []
    assert recorder.failed == ['flaky']


async def test_dispatcher_does_not_retry_budget_failure(spec: Spec, store: Store, fake_broker: FakeBroker) -> None:
    """A run that hit its budget is dead-lettered without a retry."""
    recorder = Recorder(store, {'costly': ('failed', 'max_run_usd')})
    dispatcher = _dispatcher(spec, store, fake_broker, recorder)
    await dispatcher.start()
    run = await dispatcher.enqueue('assistant', 'manual', 'costly')
    await fake_broker.drain()
    assert fake_broker.retries == []
    assert fake_broker.dead == [run.id]
    assert recorder.failed == ['costly']


async def test_dispatcher_executes_duplicate_delivery_once(spec: Spec, store: Store, fake_broker: FakeBroker) -> None:
    """A redelivered message for a claimed run is acknowledged and dropped."""
    recorder = Recorder(store)
    dispatcher = _dispatcher(spec, store, fake_broker, recorder)
    await dispatcher.start()
    run = await dispatcher.enqueue('assistant', 'manual', 'once')
    await fake_broker.drain()
    duplicate = FakeMessage(json.dumps({'run_id': run.id}).encode())
    await fake_broker.consumers[next(iter(fake_broker.consumers))][1](duplicate)
    assert recorder.order == ['once']
    assert duplicate.acked


async def test_dispatcher_defers_claims_beyond_replicas(spec: Spec, store: Store, fake_broker: FakeBroker) -> None:
    """With two replicas busy, a third run is sent to the retry delay instead of starting."""
    recorder = Recorder(store)
    recorder.release.clear()
    dispatcher = _dispatcher(spec, store, fake_broker, recorder)
    await dispatcher.start()
    for prompt in ('one', 'two', 'three'):
        await dispatcher.enqueue('assistant', 'manual', prompt)
    async with asyncio.timeout(5):
        while len(recorder.order) < 2 or not fake_broker.retries:
            await asyncio.sleep(0.01)
    await asyncio.sleep(0.05)
    assert len(recorder.order) == 2
    assert len(fake_broker.retries) == 1
    recorder.release.set()
    await fake_broker.drain()
    await fake_broker.release_retries()
    await fake_broker.drain()
    assert sorted(recorder.order) == ['one', 'three', 'two']


async def test_dispatcher_cancel_cascades_to_delegated_runs(spec: Spec, store: Store, fake_broker: FakeBroker) -> None:
    """Cancelling a run cancels the runs it delegated."""
    dispatcher = _dispatcher(spec, store, fake_broker, Recorder(store))
    parent = await dispatcher.enqueue('assistant', 'manual', 'parent')
    child = await dispatcher.enqueue('assistant', 'delegation', 'child', parent_id=parent.id)
    assert await dispatcher.cancel(parent.id)
    assert [(await store.get_run(run.id)).status for run in (parent, child)] == ['cancelled', 'cancelled']  # type: ignore[union-attr]


async def test_dispatcher_sweeps_runs_of_dead_workers(spec: Spec, store: Store, fake_broker: FakeBroker) -> None:
    """A run left running by a worker without heartbeats is failed as interrupted and retried."""
    run = await store.create_run(target='assistant', trigger_kind='manual', prompt='orphaned')
    await store.claim(run.id, 'dead-worker')
    dispatcher = _dispatcher(spec, store, fake_broker, Recorder(store))
    assert await dispatcher.sweep_interrupted() == [run.id]
    assert (await store.get_run(run.id)).failure_reason == 'interrupted'  # type: ignore[union-attr]
    assert len(fake_broker.retries) == 1


async def test_dispatcher_pause_holds_runs_until_resume(spec: Spec, store: Store, fake_broker: FakeBroker) -> None:
    """A paused target's runs wait on the broker and start on resume."""
    recorder = Recorder(store)
    dispatcher = _dispatcher(spec, store, fake_broker, recorder)
    await dispatcher.start()
    await dispatcher.pause('assistant')
    await dispatcher.enqueue('assistant', 'webhook', 'held')
    await fake_broker.drain()
    assert recorder.order == []
    await dispatcher.resume('assistant')
    await fake_broker.drain()
    assert recorder.order == ['held']


def test_resolve_amqp_url_requires_url_outside_preview() -> None:
    """Outside preview, a missing AMQP_URL stops startup with an error naming it."""
    with pytest.raises(ConfigurationError, match='AMQP_URL'):
        resolve_amqp_url({}, preview=False)
    assert resolve_amqp_url({'AMQP_URL': 'amqp://x/'}, preview=False) == 'amqp://x/'


def test_resolve_amqp_url_is_not_needed_in_preview() -> None:
    """The live preview starts without a broker."""
    assert resolve_amqp_url({}, preview=True) is None


async def test_inline_dispatcher_runs_chat_without_broker(store: Store) -> None:
    """In preview, a manual run starts at once without a broker and finishes in the background."""
    recorder = Recorder(store)
    run = await InlineDispatcher(store, recorder.execute).enqueue('assistant', 'manual', 'hello')
    assert run.status == 'running'
    while (stored := await store.get_run(run.id)) is not None and stored.status == 'running':
        await asyncio.sleep(0.01)
    assert (recorder.order, stored.status) == (['hello'], 'succeeded')  # type: ignore[union-attr]


def test_broker_health_reports_connection_state(fake_broker: FakeBroker) -> None:
    """Health is `ok` while connected, `unavailable` after a disconnect, and `disabled` without a broker."""
    assert broker_health(fake_broker) == 'ok'
    fake_broker.healthy = False
    assert broker_health(fake_broker) == 'unavailable'
    assert broker_health(None) == 'disabled'
