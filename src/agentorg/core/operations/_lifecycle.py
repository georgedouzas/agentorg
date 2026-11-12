"""Move the org through its lifecycle and decide what work each state admits."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from ..spec import Spec, Unit
from ._policy import LifecycleState
from ._store import TERMINAL, LifecycleEvent, Store

TRANSITIONS: dict[str, frozenset[str]] = {
    'draft': frozenset({'trial', 'retired'}),
    'trial': frozenset({'active', 'paused', 'retired'}),
    'active': frozenset({'paused', 'retired'}),
    'paused': frozenset({'active', 'retired'}),
    'retired': frozenset(),
}
AUTOMATIC_FROM = frozenset({'active', 'trial'})

OnChange = Callable[[LifecycleState, LifecycleState], Awaitable[None]]
Publish = Callable[[str, dict[str, Any]], Awaitable[None]]
Notify = Callable[[str, dict[str, Any]], Awaitable[None]]


def _month_start(now: datetime) -> datetime:
    """Return the start of the calendar month of `now`."""
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _subtree_ids(unit: Unit) -> list[str]:
    """Return the ids of every unit and agent inside a unit."""
    ids = []
    for nested in unit.iter_units():
        ids.append(nested.id)
        ids += [member for member in nested.member_refs if isinstance(member, str)]
        ids += [nested.lead] if nested.lead else []
    return ids


class Lifecycle:
    """The org's lifecycle state, per-target switches, circuit breaker and budget watcher.

    Arguments:
        spec: The org spec.
        store: The operations store, which keeps the transition history.
        publish: Publishes `lifecycle.changed` and `budget.alert`.
        notify: Sends notifications of lifecycle changes and budget alerts.
        on_change: Applies a state change, such as pausing consumers.
    """

    def __init__(self, spec: Spec, store: Store, publish: Publish, notify: Notify, on_change: OnChange) -> None:
        self.spec = spec
        self.store = store
        self.publish = publish
        self.notify = notify
        self.on_change = on_change

    async def state(self) -> LifecycleState:
        """Return the current state, recording the spec's initial state on first use."""
        history = await self.store.lifecycle_history()
        if history:
            return history[-1].to_state  # type: ignore[return-value]
        initial = self.spec.operations.lifecycle.initial
        await self.store.add(LifecycleEvent(from_state=None, to_state=initial, actor='system', reason='Initial state.'))
        return initial

    async def transition(self, to: LifecycleState, actor: str, reason: str) -> bool:
        """Move the org to `to` when the transition is allowed, then announce and apply it.

        Arguments:
            to: The new state.
            actor: The approver's email, or `system` for automatic transitions.
            reason: Why the state changes.

        Returns:
            moved: Whether the transition was allowed.
        """
        current = await self.state()
        if to not in TRANSITIONS[current]:
            return False
        await self.store.add(LifecycleEvent(from_state=current, to_state=to, actor=actor, reason=reason))
        payload = {'from': current, 'to': to, 'actor': actor, 'reason': reason}
        await self.publish('lifecycle.changed', payload)
        await self.notify('lifecycle_changed', payload)
        await self.on_change(current, to)
        return True

    async def set_enabled(self, target: str, *, enabled: bool, actor: str) -> None:
        """Enable or disable one agent or unit, and everything nested in a unit, without changing the spec."""
        await self.store.set_value('disabled', target, not enabled)
        state = 'active' if enabled else 'disabled'
        await self.store.add(LifecycleEvent(subject=target, to_state=state, actor=actor, reason=f'{target} {state}.'))

    async def _disabled(self, target: str) -> str | None:
        """Return why a target or one of its units is disabled, or None."""
        ids = [target] + [unit.id for unit in self.spec.ai.path_to(target)]
        for id_ in ids:
            if await self.store.get_value('disabled', id_):
                return f'{id_} is disabled.'
        return None

    async def _trial_exhausted(self) -> bool:
        """Return whether the trial reached its run cap."""
        history = await self.store.lifecycle_history()
        started = next((event.at for event in reversed(history) if event.to_state == 'trial'), None)
        runs = await self.store.list_runs(since=started, limit=self.spec.operations.lifecycle.trial_max_runs + 1)
        return len(runs) >= self.spec.operations.lifecycle.trial_max_runs

    async def _unit_over_budget(self, target: str) -> str | None:
        """Return why a unit above the target is over its budget, or None."""
        month = _month_start(datetime.now(UTC))
        for unit in self.spec.ai.path_to(target):
            if unit.monthly_usd is None:
                continue
            spend = sum([await self.store.month_spend(month, target=id_) for id_ in _subtree_ids(unit)])
            if spend >= unit.monthly_usd:
                return f"Unit '{unit.id}' reached its monthly budget of {unit.monthly_usd} USD."
        return None

    async def admit(self, target: str) -> str | None:
        """Return `None` when new work for `target` is accepted now, or the reason it is refused."""
        state = await self.state()
        if state == 'retired':
            return 'The org is retired.'
        if state == 'draft':
            return 'The org is a draft; only the live preview runs work.'
        if state == 'trial' and await self._trial_exhausted():
            return 'The trial run cap is reached; promote the org to active to continue.'
        return await self._disabled(target) or await self._unit_over_budget(target)

    async def _failure_rate_exceeded(self) -> bool:
        """Return whether too many of the recent runs failed."""
        window = self.spec.operations.lifecycle.failure_window
        recent = [run for run in await self.store.list_runs(limit=window * 4) if run.status in TERMINAL][:window]
        failed = sum(run.status == 'failed' for run in recent)
        return len(recent) == window and failed / window > self.spec.operations.lifecycle.max_failure_rate

    async def _check_budget(self) -> str | None:
        """Alert once per month at the threshold and return `budget` when the org should pause."""
        budget = self.spec.operations.budget
        if budget.monthly_usd is None:
            return None
        month = _month_start(datetime.now(UTC))
        spend = await self.store.month_spend(month)
        alert_key = month.strftime('%Y-%m')
        if spend >= budget.alert_at * budget.monthly_usd and not await self.store.get_value('budget_alert', alert_key):
            await self.store.set_value('budget_alert', alert_key, True)
            payload = {'spend_usd': spend, 'monthly_usd': budget.monthly_usd}
            await self.publish('budget.alert', payload)
            await self.notify('budget_alert', payload)
        exhausted = spend >= budget.monthly_usd and budget.on_exhausted == 'pause'
        return 'budget' if exhausted else None

    async def after_run(self) -> None:
        """Apply the budget watcher and the failure-rate breaker after a run ends."""
        if await self.state() not in AUTOMATIC_FROM:
            return
        reason = await self._check_budget() or ('failure_rate' if await self._failure_rate_exceeded() else None)
        if reason:
            await self.transition('paused', 'system', reason)
