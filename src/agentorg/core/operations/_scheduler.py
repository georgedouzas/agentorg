"""Fire schedule triggers on their cron, once per due time across all workers."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from croniter import croniter

from ..spec import ScheduleTrigger, Spec
from ._intake import Admit, Enqueue, Parameters
from ._prompts import render_prompt
from ._store import Store

TICK = timedelta(seconds=15)
LEASE = timedelta(seconds=45)
ACTIVE_STATUSES = ('queued', 'running', 'awaiting_approval')


def _due_times(trigger: ScheduleTrigger, after: datetime, until: datetime) -> list[datetime]:
    """Return the trigger's fire times in `(after, until]`, in UTC."""
    zone = ZoneInfo(trigger.timezone)
    schedule = croniter(trigger.cron, after.astimezone(zone))
    times: list[datetime] = []
    while (fire := schedule.get_next(datetime).astimezone(UTC)) <= until:
        times.append(fire)
    return times


class Scheduler:
    """Fire the org's schedule triggers while holding the scheduler lease.

    Arguments:
        spec: The org spec.
        store: The operations store, which keeps last fire times and the lease.
        enqueue: Queues a scheduled run.
        admit: Refuses work for targets that may not take it now.
        parameters: Returns the parameter values used in prompts.
        worker_id: This worker's id, used to hold the lease.
        clock: Returns the current UTC time.
        paused: Returns whether the org is paused, in which case nothing ticks and missed fires follow `catch_up`.
    """

    def __init__(
        self,
        spec: Spec,
        store: Store,
        enqueue: Enqueue,
        admit: Admit,
        parameters: Parameters,
        worker_id: str,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        paused: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        self.spec = spec
        self.store = store
        self.enqueue = enqueue
        self.admit = admit
        self.parameters = parameters
        self.worker_id = worker_id
        self.clock = clock
        self.paused = paused
        self._task: asyncio.Task[None] | None = None

    @property
    def triggers(self) -> list[ScheduleTrigger]:
        """The org's enabled schedule triggers."""
        return [t for t in self.spec.operations.triggers if isinstance(t, ScheduleTrigger) and t.enabled]

    async def _overlaps(self, trigger: ScheduleTrigger) -> bool:
        for status in ACTIVE_STATUSES:
            runs = await self.store.list_runs(target=trigger.target, status=status, trigger_kind='schedule', limit=1000)
            if any(run.trigger_id == trigger.id for run in runs):
                return True
        return False

    async def _fire(self, trigger: ScheduleTrigger, now: datetime) -> bool:
        if trigger.overlap == 'skip' and await self._overlaps(trigger):
            return False
        if await self.admit(trigger.target) is not None:
            return False
        prompt = render_prompt(trigger.prompt, trigger_id=trigger.id, parameters=self.parameters(), now=now)
        await self.enqueue(trigger.target, 'schedule', prompt, trigger_id=trigger.id)
        return True

    async def tick_trigger(self, trigger: ScheduleTrigger, now: datetime) -> list[datetime]:
        """Fire `trigger` for the due times since its last fire and return the times that started a run.

        Arguments:
            trigger: The schedule trigger.
            now: The current UTC time.

        Returns:
            fired: The due times that started a run, at most one per tick.
        """
        last = await self.store.get_value('last_fire', trigger.id)
        await self.store.set_value('last_fire', trigger.id, now.isoformat())
        if not isinstance(last, str):
            return []
        due = _due_times(trigger, datetime.fromisoformat(last), now)
        on_time = [time for time in due if now - time <= 2 * TICK]
        if not due or (trigger.catch_up == 'skip' and not on_time):
            return []
        fire_time = due[-1]
        return [fire_time] if await self._fire(trigger, fire_time) else []

    async def tick(self) -> dict[str, list[datetime]]:
        """Fire every due trigger once if this worker holds the scheduler lease.

        Returns:
            fired: The fired due times per trigger id; empty when another worker holds the lease.
        """
        if self.paused is not None and await self.paused():
            return {}
        if not await self.store.acquire_lease('scheduler', self.worker_id, LEASE):
            return {}
        now = self.clock()
        return {trigger.id: await self.tick_trigger(trigger, now) for trigger in self.triggers}

    async def _loop(self) -> None:
        while True:
            await self.tick()
            await asyncio.sleep(TICK.total_seconds())

    def start(self) -> None:
        """Start ticking in the background."""
        self._task = asyncio.get_running_loop().create_task(self._loop())

    async def stop(self) -> None:
        """Stop ticking."""
        if self._task is not None:
            self._task.cancel()
            self._task = None
