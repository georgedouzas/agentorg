"""Tests for the store module."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from agentorg.core.operations import Approval, InboxItem, LifecycleEvent, Store


@pytest.fixture
async def store(tmp_path: Path) -> AsyncIterator[Store]:
    """An opened store on a temporary sqlite database."""
    store = Store(f'sqlite+aiosqlite:///{tmp_path / "ops.db"}')
    await store.open()
    yield store
    await store.close()


async def _queued(store: Store, target: str = 'analyst') -> str:
    run = await store.create_run(target=target, trigger_kind='manual', prompt='Go.')
    return run.id


async def test_store_run_survives_reopen(tmp_path: Path) -> None:
    """A succeeded run with its output and cost is still there after reopening the database."""
    url = f'sqlite+aiosqlite:///{tmp_path / "ops.db"}'
    first = Store(url)
    await first.open()
    run_id = await _queued(first)
    assert await first.claim(run_id, 'w1')
    assert await first.transition(run_id, 'succeeded', output='Report', cost_usd=0.12)
    await first.close()
    second = Store(url)
    await second.open()
    run = await second.get_run(run_id)
    await second.close()
    assert run is not None
    assert (run.status, run.output, run.cost_usd) == ('succeeded', 'Report', 0.12)
    assert run.ended_at is not None


async def test_store_terminal_status_is_immutable(store: Store) -> None:
    """A cancel request on a succeeded run is refused."""
    run_id = await _queued(store)
    await store.claim(run_id, 'w1')
    await store.transition(run_id, 'succeeded')
    assert not await store.transition(run_id, 'cancelled')
    assert (await store.get_run(run_id)).status == 'succeeded'  # type: ignore[union-attr]


async def test_store_second_claim_fails(store: Store) -> None:
    """Only the first worker to claim a queued run gets it."""
    run_id = await _queued(store)
    assert await store.claim(run_id, 'w1')
    assert not await store.claim(run_id, 'w2')
    assert (await store.get_run(run_id)).worker_id == 'w1'  # type: ignore[union-attr]


async def test_store_claim_respects_max_active(store: Store) -> None:
    """A claim is refused while the target already has `max_active` active runs."""
    first, second = await _queued(store), await _queued(store)
    assert await store.claim(first, 'w1', max_active=1)
    assert not await store.claim(second, 'w2', max_active=1)
    await store.transition(first, 'awaiting_approval')
    assert not await store.claim(second, 'w2', max_active=1)
    await store.transition(first, 'running')
    await store.transition(first, 'failed', failure_reason='timeout')
    assert await store.claim(second, 'w2', max_active=1)


@pytest.mark.parametrize(
    ('path', 'allowed'),
    [
        (['awaiting_approval', 'running', 'succeeded'], True),
        (['cancelled'], True),
        (['succeeded', 'running'], False),
    ],
)
async def test_store_transition_follows_status_machine(store: Store, path: list[str], allowed: bool) -> None:
    """Transitions out of running follow the status machine."""
    run_id = await _queued(store)
    await store.claim(run_id, 'w1')
    results = [await store.transition(run_id, status) for status in path]  # type: ignore[arg-type]
    assert all(results) is allowed


async def test_store_list_runs_filters_newest_first(store: Store) -> None:
    """Runs are filtered by status and target and ordered newest first."""
    ids = [await _queued(store, target) for target in ('a', 'b', 'a')]
    await store.claim(ids[0], 'w')
    await store.transition(ids[0], 'failed')
    assert [run.id for run in await store.list_runs(status='failed')] == [ids[0]]
    assert [run.id for run in await store.list_runs(target='a')] == [ids[2], ids[0]]


async def test_store_month_spend_sums_costs(store: Store) -> None:
    """Spend is the sum of run costs since the start of the month, optionally per target."""
    for target, cost in (('a', 0.5), ('b', 1.25)):
        run_id = await _queued(store, target)
        await store.claim(run_id, 'w')
        await store.transition(run_id, 'succeeded', cost_usd=cost)
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    assert await store.month_spend(month_start) == 1.75
    assert await store.month_spend(month_start, target='b') == 1.25


async def test_store_records_approvals_inbox_and_lifecycle(store: Store) -> None:
    """Approvals are decided once, and inbox items and lifecycle events are listed."""
    approval = Approval(run_id='r', action_class='outbound_message', tool_name='send', arguments={'to': 'x'})
    await store.add(approval)
    await store.add(InboxItem(kind='escalation', run_id='r', reason='Stuck'))
    await store.add(LifecycleEvent(from_state='trial', to_state='active', actor='admin', reason='Ready'))
    assert [item.id for item in await store.list_approvals()] == [approval.id]
    assert await store.decide_approval(approval.id, status='approved', decided_by='admin')
    assert not await store.decide_approval(approval.id, status='rejected', decided_by='admin')
    assert [item.reason for item in await store.list_inbox()] == ['Stuck']
    assert [event.to_state for event in await store.lifecycle_history()] == ['active']


async def test_store_values_expire(store: Store) -> None:
    """Coordination values can expire."""
    await store.set_value('idempotency', 'k', 'run-1', ttl=timedelta(seconds=-1))
    await store.set_value('session_owner', 's', 'billing')
    assert await store.get_value('idempotency', 'k') is None
    assert await store.get_value('session_owner', 's') == 'billing'


async def test_store_lease_has_one_holder(store: Store) -> None:
    """A lease is held by one worker until it expires."""
    assert await store.acquire_lease('scheduler', 'w1', timedelta(seconds=45))
    assert not await store.acquire_lease('scheduler', 'w2', timedelta(seconds=45))
    assert await store.acquire_lease('scheduler', 'w1', timedelta(seconds=45))
    await store.set_value('lease', 'scheduler', 'w1', ttl=timedelta(seconds=-1))
    assert await store.acquire_lease('scheduler', 'w2', timedelta(seconds=45))
