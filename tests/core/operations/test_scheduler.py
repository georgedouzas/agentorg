"""Tests for the scheduler module."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from agentorg.core.operations import Scheduler, Store, admit_all, scheduler_clock
from agentorg.core.spec import Spec

from .conftest import Queued


class Clock:
    """A settable clock."""

    def __init__(self, now: datetime) -> None:
        """Start at `now`."""
        self.now = now

    def __call__(self) -> datetime:
        """Return the current time."""
        return self.now


def _spec(spec_dict_minimal: dict[str, Any], **trigger: Any) -> Spec:
    base = {'kind': 'schedule', 'id': 'job', 'target': 'assistant', 'prompt': 'Run at {now}.', 'cron': '0 * * * *'}
    spec_dict_minimal['operations'] = {'triggers': [{**base, **trigger}]}
    return Spec.model_validate(spec_dict_minimal)


def _scheduler(spec: Spec, store: Store, clock: Clock, worker: str = 'w1') -> tuple[Scheduler, Queued]:
    queued = Queued(store)
    return Scheduler(spec, store, queued, admit_all, parameters=dict, worker_id=worker, clock=clock), queued


START = datetime(2026, 11, 9, 7, 59, tzinfo=UTC)


async def test_scheduler_fires_weekly_report_in_timezone(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """A Monday 08:00 Athens schedule fires at 06:00 UTC on Monday."""
    spec = _spec(spec_dict_minimal, cron='0 8 * * MON', timezone='Europe/Athens')
    clock = Clock(datetime(2026, 11, 9, 5, 59, 50, tzinfo=UTC))
    scheduler, queued = _scheduler(spec, store, clock)
    assert await scheduler.tick() == {'job': []}
    clock.now = datetime(2026, 11, 9, 6, 0, 5, tzinfo=UTC)
    assert await scheduler.tick() == {'job': [datetime(2026, 11, 9, 6, 0, tzinfo=UTC)]}
    assert [run.prompt for run in queued.runs] == ['Run at 2026-11-09T06:00+00:00.']


async def test_scheduler_skips_overlapping_fire(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """With `overlap='skip'`, an hourly fire is dropped while the previous run is still active."""
    clock = Clock(START)
    scheduler, queued = _scheduler(_spec(spec_dict_minimal), store, clock)
    await scheduler.tick()
    clock.now = START + timedelta(minutes=1, seconds=5)
    await scheduler.tick()
    await store.claim(queued.runs[0].id, 'w1')
    clock.now = START + timedelta(hours=1, minutes=1, seconds=5)
    assert await scheduler.tick() == {'job': []}
    assert len(queued.runs) == 1


@pytest.mark.parametrize(('catch_up', 'runs'), [('run_once', 1), ('skip', 0)])
async def test_scheduler_catch_up_after_downtime(
    spec_dict_minimal: dict[str, Any],
    store: Store,
    catch_up: str,
    runs: int,
) -> None:
    """After missing three daily fires, `run_once` starts exactly one run and `skip` starts none."""
    clock = Clock(datetime(2026, 11, 1, 12, 0, tzinfo=UTC))
    scheduler, queued = _scheduler(_spec(spec_dict_minimal, cron='0 9 * * *', catch_up=catch_up), store, clock)
    await scheduler.tick()
    clock.now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    await scheduler.tick()
    assert len(queued.runs) == runs


async def test_scheduler_fires_once_with_two_workers(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """Two workers ticking at the same due time create one run, because only the lease holder fires."""
    spec = _spec(spec_dict_minimal)
    clock = Clock(START)
    first, queued_first = _scheduler(spec, store, clock, 'w1')
    second, queued_second = _scheduler(spec, store, clock, 'w2')
    await first.tick()
    await second.tick()
    clock.now = START + timedelta(minutes=1, seconds=5)
    await first.tick()
    await second.tick()
    assert len(queued_first.runs) + len(queued_second.runs) == 1


async def test_scheduler_skips_disabled_trigger(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """A disabled schedule is not ticked."""
    scheduler, _ = _scheduler(_spec(spec_dict_minimal, enabled=False), store, Clock(START))
    assert await scheduler.tick() == {}


async def test_scheduler_does_not_tick_while_paused(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """While the org is paused nothing fires, and on resume the missed fires follow `catch_up`."""
    paused = True

    async def is_paused() -> bool:
        return paused

    clock = Clock(datetime(2026, 11, 1, 12, 0, tzinfo=UTC))
    queued = Queued(store)
    spec = _spec(spec_dict_minimal, cron='0 9 * * *', catch_up='run_once')
    scheduler = Scheduler(
        spec,
        store,
        queued,
        admit_all,
        parameters=dict,
        worker_id='w1',
        clock=clock,
        paused=is_paused,
    )
    paused = False
    await scheduler.tick()
    paused = True
    clock.now = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
    assert await scheduler.tick() == {}
    paused = False
    clock.now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    await scheduler.tick()
    assert len(queued.runs) == 1


def test_scheduler_clock_runs_from_a_start_instant(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a start the clock is real UTC time; with one it starts there and advances in real time."""
    before = datetime.now(UTC)
    assert scheduler_clock(None)() >= before
    ticks = iter([100.0, 100.0, 107.5])
    monkeypatch.setattr('time.monotonic', lambda: next(ticks))
    clock = scheduler_clock('2026-11-16T07:59:50+00:00')
    assert clock() == datetime(2026, 11, 16, 7, 59, 50, tzinfo=UTC)
    assert clock() == datetime(2026, 11, 16, 7, 59, 57, 500000, tzinfo=UTC)
