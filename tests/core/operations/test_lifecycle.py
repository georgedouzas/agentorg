"""Tests for the lifecycle module."""

from typing import Any

import pytest

from agentorg.core.operations import Lifecycle, LifecycleState, Store
from agentorg.core.spec import Spec


class Changes:
    """Records published events, notifications and applied state changes."""

    def __init__(self) -> None:
        """Start empty."""
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.notes: list[str] = []
        self.applied: list[tuple[str, str]] = []

    async def publish(self, name: str, payload: dict[str, Any]) -> None:
        """Record an event."""
        self.events.append((name, payload))

    async def notify(self, kind: str, payload: dict[str, Any]) -> None:
        """Record a notification kind."""
        self.notes.append(kind)

    async def on_change(self, before: LifecycleState, after: LifecycleState) -> None:
        """Record an applied change."""
        self.applied.append((before, after))


def _lifecycle(spec: Spec, store: Store) -> tuple[Lifecycle, Changes]:
    changes = Changes()
    return Lifecycle(spec, store, changes.publish, changes.notify, changes.on_change), changes


async def _finished(store: Store, status: str, target: str = 'assistant', cost: float = 0.0) -> None:
    run = await store.create_run(target=target, trigger_kind='manual', prompt='x')
    await store.claim(run.id, 'w')
    await store.transition(run.id, status, cost_usd=cost)  # type: ignore[arg-type]


async def test_lifecycle_starts_in_trial(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """A fresh org starts in the spec's initial state, trial by default."""
    lifecycle, _ = _lifecycle(Spec.model_validate(spec_dict_minimal), store)
    assert await lifecycle.state() == 'trial'


async def test_lifecycle_promotion_is_recorded_and_announced(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """Promoting trial to active records who and why, publishes the change and applies it."""
    lifecycle, changes = _lifecycle(Spec.model_validate(spec_dict_minimal), store)
    assert await lifecycle.transition('active', 'admin@acme.com', 'Trial went well')
    history = await store.lifecycle_history()
    assert [(event.to_state, event.actor, event.reason) for event in history][-1] == (
        'active',
        'admin@acme.com',
        'Trial went well',
    )
    assert changes.events[0][0] == 'lifecycle.changed'
    assert changes.notes == ['lifecycle_changed']
    assert changes.applied == [('trial', 'active')]


async def test_lifecycle_rejects_illegal_transition(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """A retired org cannot become active again."""
    lifecycle, _ = _lifecycle(Spec.model_validate(spec_dict_minimal), store)
    await lifecycle.transition('retired', 'admin', 'Done')
    assert not await lifecycle.transition('active', 'admin', 'Oops')
    assert await lifecycle.state() == 'retired'


@pytest.mark.parametrize(
    ('state', 'refused'),
    [('retired', 'retired'), ('draft', 'draft'), ('paused', None), ('active', None)],
)
async def test_lifecycle_admit_by_state(
    spec_dict_minimal: dict[str, Any],
    store: Store,
    state: str,
    refused: str | None,
) -> None:
    """Retired and draft orgs refuse new work; a paused org accepts it so it waits on the broker."""
    spec_dict_minimal['operations'] = {'lifecycle': {'initial': 'draft' if state == 'draft' else 'trial'}}
    lifecycle, _ = _lifecycle(Spec.model_validate(spec_dict_minimal), store)
    if state not in ('draft', 'trial'):
        await lifecycle.transition('active' if state != 'retired' else 'retired', 'admin', 'setup')
    if state == 'paused':
        await lifecycle.transition('paused', 'admin', 'maintenance')
    reason = await lifecycle.admit('assistant')
    assert (reason is None) if refused is None else (refused in (reason or ''))


async def test_lifecycle_trial_cap(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """New work is refused once the trial run cap is reached."""
    spec_dict_minimal['operations'] = {'lifecycle': {'trial_max_runs': 2}}
    lifecycle, _ = _lifecycle(Spec.model_validate(spec_dict_minimal), store)
    await lifecycle.state()
    for _ in range(2):
        await _finished(store, 'succeeded')
    assert 'trial run cap' in (await lifecycle.admit('assistant') or '')


async def test_lifecycle_disabled_unit_cascades(archetype_specs: dict[str, dict[str, Any]], store: Store) -> None:
    """Disabling a unit refuses work for every agent nested in it, and re-enabling restores it."""
    lifecycle, _ = _lifecycle(Spec.model_validate(archetype_specs['support-desk']), store)
    await lifecycle.set_enabled('frontline', enabled=False, actor='admin')
    assert await lifecycle.admit('billing') == 'frontline is disabled.'
    assert await lifecycle.admit('desk-lead') is None
    await lifecycle.set_enabled('frontline', enabled=True, actor='admin')
    assert await lifecycle.admit('billing') is None


async def test_lifecycle_unit_budget_refuses_only_that_unit(
    archetype_specs: dict[str, dict[str, Any]],
    store: Store,
) -> None:
    """A unit at its monthly budget refuses new work while the rest of the org continues."""
    archetype_specs['support-desk']['ai']['root']['members'][0]['monthly_usd'] = 5
    lifecycle, _ = _lifecycle(Spec.model_validate(archetype_specs['support-desk']), store)
    await _finished(store, 'succeeded', target='billing', cost=5.0)
    assert 'frontline' in (await lifecycle.admit('tech') or '')
    assert await lifecycle.admit('desk-lead') is None


async def test_lifecycle_breaker_pauses_on_failure_rate(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """When more than half of the last 20 runs failed, the org pauses with reason failure_rate."""
    lifecycle, changes = _lifecycle(Spec.model_validate(spec_dict_minimal), store)
    for index in range(20):
        await _finished(store, 'failed' if index < 11 else 'succeeded')
    await lifecycle.after_run()
    assert await lifecycle.state() == 'paused'
    assert (await store.lifecycle_history())[-1].reason == 'failure_rate'
    assert changes.applied == [('trial', 'paused')]


async def test_lifecycle_budget_alerts_once_then_pauses(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """Crossing the alert threshold alerts once, and reaching the budget pauses the org."""
    spec_dict_minimal['operations'] = {'budget': {'monthly_usd': 10}}
    lifecycle, changes = _lifecycle(Spec.model_validate(spec_dict_minimal), store)
    await _finished(store, 'succeeded', cost=8.5)
    await lifecycle.after_run()
    await lifecycle.after_run()
    assert [name for name, _ in changes.events] == ['budget.alert']
    await _finished(store, 'succeeded', cost=2.0)
    await lifecycle.after_run()
    assert await lifecycle.state() == 'paused'
    assert (await store.lifecycle_history())[-1].reason == 'budget'
