"""Tests for the bus module."""

from typing import Any

import pytest

from agentorg.core.operations import EventBus, Store, admit_all
from agentorg.core.spec import Spec

from .conftest import FakeBroker, Queued


def _spec(spec_dict_minimal: dict[str, Any], *triggers: dict[str, Any], max_chain_depth: int = 5) -> Spec:
    spec_dict_minimal['operations'] = {
        'triggers': list(triggers),
        'communication': {'max_chain_depth': max_chain_depth},
    }
    return Spec.model_validate(spec_dict_minimal)


def _event_trigger(trigger_id: str, event: str, **fields: Any) -> dict[str, Any]:
    return {
        'kind': 'event',
        'id': trigger_id,
        'target': 'assistant',
        'prompt': 'Handle {event}',
        'event': event,
        **fields,
    }


async def test_event_bus_starts_run_with_payload(
    spec_dict_minimal: dict[str, Any],
    store: Store,
    fake_broker: FakeBroker,
) -> None:
    """A matching event starts a run whose prompt carries the payload and whose chain names the trigger."""
    spec = _spec(spec_dict_minimal, _event_trigger('on-report', 'knowledge.created', filter={'type': 'report'}))
    queued = Queued(store)
    bus = EventBus(spec, store, fake_broker, queued, admit=admit_all, parameters=dict)
    await bus.start()
    await bus.publish_knowledge('created', {'type': 'report', 'name': 'weekly'})
    await fake_broker.drain()
    assert [(run.target, run.trigger_kind, run.prompt, run.chain) for run in queued.runs] == [
        ('assistant', 'event', 'Handle {"type": "report", "name": "weekly"}', ['on-report']),
    ]


async def test_event_bus_ignores_filter_mismatch(
    spec_dict_minimal: dict[str, Any],
    store: Store,
    fake_broker: FakeBroker,
) -> None:
    """An event whose payload fails the filter starts nothing."""
    spec = _spec(spec_dict_minimal, _event_trigger('on-report', 'knowledge.created', filter={'type': 'report'}))
    queued = Queued(store)
    bus = EventBus(spec, store, fake_broker, queued, admit=admit_all, parameters=dict)
    await bus.start()
    await bus.publish_knowledge('created', {'type': 'note', 'name': 'n'})
    await fake_broker.drain()
    assert queued.runs == []


async def test_event_bus_breaks_loops_at_max_chain_depth(
    spec_dict_minimal: dict[str, Any],
    store: Store,
    fake_broker: FakeBroker,
) -> None:
    """Two triggers feeding each other stop at the chain limit, and a warning names the chain."""
    spec = _spec(
        spec_dict_minimal,
        _event_trigger('ping', 'custom.ping'),
        _event_trigger('pong', 'custom.pong'),
        max_chain_depth=3,
    )
    queued = Queued(store)
    bus = EventBus(spec, store, fake_broker, queued, admit=admit_all, parameters=dict)
    await bus.start()
    await bus.publish('custom.ping', {})
    for _ in range(5):
        await fake_broker.drain()
        if queued.runs:
            last = queued.runs[-1]
            await bus.publish('custom.pong' if last.trigger_id == 'ping' else 'custom.ping', {}, last.chain)
    await fake_broker.drain()
    assert [run.chain for run in queued.runs] == [['ping'], ['ping', 'pong'], ['ping', 'pong', 'ping']]
    warnings = await store.list_inbox()
    assert len(warnings) >= 1
    assert 'ping -> pong -> ping' in warnings[0].reason


@pytest.mark.parametrize('enabled', [False])
async def test_event_bus_skips_disabled_trigger(
    spec_dict_minimal: dict[str, Any],
    store: Store,
    fake_broker: FakeBroker,
    enabled: bool,
) -> None:
    """A disabled event trigger is not subscribed."""
    spec = _spec(spec_dict_minimal, _event_trigger('ping', 'custom.ping', enabled=enabled))
    bus = EventBus(spec, store, fake_broker, Queued(store), admit=admit_all, parameters=dict)
    await bus.start()
    assert fake_broker.consumers == {}


async def test_event_bus_respects_admission(
    spec_dict_minimal: dict[str, Any],
    store: Store,
    fake_broker: FakeBroker,
) -> None:
    """An event for a target that refuses work is acknowledged without a run."""

    async def refuse(target: str) -> str | None:
        return f'{target} is disabled'

    queued = Queued(store)
    bus = EventBus(
        _spec(spec_dict_minimal, _event_trigger('ping', 'custom.ping')),
        store,
        fake_broker,
        queued,
        admit=refuse,
        parameters=dict,
    )
    await bus.start()
    await bus.publish('custom.ping', {})
    await fake_broker.drain()
    assert queued.runs == []
