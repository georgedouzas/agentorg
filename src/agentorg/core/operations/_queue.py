"""Queue runs on the broker, claim and execute them within caps, retry failures and dead-letter the rest."""

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from .._errors import ConfigurationError
from ..spec import Spec
from ._store import Run, Store

PRIORITY = {'manual': 4, 'webhook': 3, 'queue': 3, 'event': 2, 'schedule': 1, 'delegation': 4, 'retry': 0}
NON_RETRYABLE = frozenset(
    {
        'max_turns',
        'max_run_usd',
        'timeout',
        'invalid_output',
        'review_rejected',
        'unit_budget',
        'no_consensus',
        'no_match',
    },
)
HEARTBEAT = timedelta(seconds=15)
STALE_AFTER = timedelta(seconds=60)


class Message(Protocol):
    """The part of a broker message the dispatcher uses."""

    body: bytes

    async def ack(self) -> None:
        """Acknowledge the message."""
        ...


class RunBroker(Protocol):
    """The broker operations the dispatcher uses."""

    async def declare_targets(self, targets: list[str], retries: int) -> None:
        """Declare the run queues."""
        ...

    async def publish_run(self, target: str, run_id: str, priority: int) -> None:
        """Queue a run."""
        ...

    async def publish_retry(self, target: str, run_id: str, attempt: int, priority: int = 0) -> None:
        """Queue a delayed retry."""
        ...

    async def publish_dead(self, run_id: str) -> None:
        """Dead-letter a run."""
        ...

    async def consume_runs(self, target: str, prefetch: int, handler: Callable[[Any], Awaitable[None]]) -> str:
        """Consume a target's run queue."""
        ...

    async def consume_dead(self, handler: Callable[[Any], Awaitable[None]]) -> str:
        """Consume the dead-letter queue."""
        ...

    async def cancel(self, consumer_tag: str) -> None:
        """Stop a consumer."""
        ...


Execute = Callable[[Run], Awaitable[None]]
FailureHandler = Callable[[Run], Awaitable[None]]


class Dispatcher:
    """Move runs from the broker to execution, within the per-worker and per-agent caps.

    Arguments:
        spec: The org spec.
        store: The operations store.
        broker: The run broker.
        execute: Executes a claimed run of an agent or unit.
        on_failure: Applies the org's failure policy to a dead-lettered run.
        worker_id: This worker's id; a random one by default.
    """

    def __init__(
        self,
        spec: Spec,
        store: Store,
        broker: RunBroker,
        execute: Execute,
        *,
        on_failure: FailureHandler,
        worker_id: str | None = None,
    ) -> None:
        self.spec = spec
        self.store = store
        self.broker = broker
        self.execute = execute
        self.on_failure = on_failure
        self.worker_id = worker_id or uuid.uuid4().hex[:12]
        self._slots = asyncio.Semaphore(spec.operations.runs.max_concurrent)
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._consumers: dict[str, str] = {}

    @property
    def targets(self) -> list[str]:
        """Every agent and unit id of the org."""
        return [agent.id for agent in self.spec.ai.agents] + [unit.id for unit in self.spec.ai.units]

    def _replicas(self, target: str) -> int | None:
        """Return the replica cap of an agent target, or None for a unit."""
        agents = {agent.id: agent for agent in self.spec.ai.agents}
        return agents[target].replicas if target in agents else None

    async def enqueue(self, target: str, trigger_kind: str, prompt: str, **fields: Any) -> Run:  # noqa: ANN401
        """Store a queued run and publish it to its target's queue.

        Arguments:
            target: The agent or unit id.
            trigger_kind: What started the run, which sets its priority.
            prompt: The run's input.
            **fields: Other run columns, such as `session_id` or `parent_id`.

        Returns:
            run: The queued run.
        """
        priority = PRIORITY.get(trigger_kind, 0)
        run = await self.store.create_run(
            target=target,
            trigger_kind=trigger_kind,
            prompt=prompt,
            priority=priority,
            **fields,
        )
        await self.broker.publish_run(target, run.id, priority)
        return run

    async def _handle(self, message: Message) -> None:
        """Claim and execute a delivered run, or defer it when its target is at capacity."""
        run_id = json.loads(message.body)['run_id']
        async with self._slots:
            run = await self.store.get_run(run_id)
            if run is None or not await self.store.claim(run_id, self.worker_id, self._replicas(run.target)):
                if run is not None and run.status == 'queued':
                    await self.broker.publish_retry(run.target, run_id, 0, run.priority)
                await message.ack()
                return
            await message.ack()
            task = asyncio.current_task()
            if task is not None:
                self._tasks[run_id] = task
            try:
                await self.execute(run)
            except asyncio.CancelledError:
                return
            finally:
                self._tasks.pop(run_id, None)
        await self._after(run_id)

    async def _after(self, run_id: str) -> None:
        """Retry a failed run by policy, or dead-letter it."""
        run = await self.store.get_run(run_id)
        if run is None or run.status != 'failed':
            return
        retries = self.spec.operations.runs.retries
        if run.failure_reason in NON_RETRYABLE or run.attempt >= retries:
            await self.broker.publish_dead(run.id)
            return
        retry = await self.store.create_run(
            target=run.target,
            trigger_kind=run.trigger_kind,
            trigger_id=run.trigger_id,
            parent_id=run.parent_id,
            session_id=run.session_id,
            user_id=run.user_id,
            prompt=run.prompt,
            priority=run.priority,
            chain=run.chain,
            tags=run.tags,
            attempt=run.attempt + 1,
            retry_of=run.retry_of or run.id,
        )
        await self.broker.publish_retry(run.target, retry.id, run.attempt, run.priority)

    async def _handle_dead(self, message: Message) -> None:
        """Apply the failure policy to a dead-lettered run."""
        run = await self.store.get_run(json.loads(message.body)['run_id'])
        await message.ack()
        if run is not None:
            await self.on_failure(run)

    async def cancel(self, run_id: str) -> bool:
        """Cancel a queued, running or held run and every run it delegated.

        Arguments:
            run_id: The run to cancel.

        Returns:
            cancelled: Whether the run was still cancellable.
        """
        cancelled = await self.store.transition(run_id, 'cancelled', failure_reason='cancelled')
        if cancelled and run_id in self._tasks:
            self._tasks[run_id].cancel()
        for child in await self.store.list_runs(parent_id=run_id, limit=1000):
            await self.cancel(child.id)
        return cancelled

    async def heartbeat(self) -> None:
        """Record that this worker is alive."""
        await self.store.set_value('worker', self.worker_id, datetime.now(UTC).isoformat(), ttl=STALE_AFTER)

    async def sweep_interrupted(self) -> list[str]:
        """Fail active runs whose worker stopped sending heartbeats, and retry them by policy.

        Returns:
            run_ids: The runs marked `interrupted`.
        """
        swept: list[str] = []
        for status in ('running', 'awaiting_approval'):
            for run in await self.store.list_runs(status=status, limit=10_000):
                alive = run.worker_id == self.worker_id or await self.store.get_value('worker', run.worker_id or '')
                if not alive and await self.store.transition(run.id, 'failed', failure_reason='interrupted'):
                    swept.append(run.id)
                    await self._after(run.id)
        return swept

    async def start(self, targets: list[str] | None = None) -> None:
        """Declare the run queues, sweep interrupted runs and start consuming.

        Arguments:
            targets: The targets to consume; every agent and unit by default.
        """
        await self.heartbeat()
        await self.broker.declare_targets(self.targets, self.spec.operations.runs.retries)
        await self.sweep_interrupted()
        for target in targets or self.targets:
            await self.resume(target)
        self._consumers['dead'] = await self.broker.consume_dead(self._handle_dead)

    async def pause(self, target: str) -> None:
        """Stop consuming `target`'s queue so its runs wait on the broker."""
        if target in self._consumers:
            await self.broker.cancel(self._consumers.pop(target))

    async def resume(self, target: str) -> None:
        """Start consuming `target`'s queue."""
        if target not in self._consumers:
            prefetch = self._replicas(target) or self.spec.operations.runs.max_concurrent
            self._consumers[target] = await self.broker.consume_runs(target, prefetch, self._handle)

    async def stop(self) -> None:
        """Stop every consumer."""
        for tag in list(self._consumers.values()):
            await self.broker.cancel(tag)
        self._consumers.clear()


class InlineDispatcher:
    """Start work at once in a background task, without a broker, for the live preview.

    Arguments:
        store: The operations store.
        execute: Executes a claimed run of an agent or unit.
        worker_id: The worker id recorded on claimed runs.
    """

    def __init__(self, store: Store, execute: Execute, worker_id: str = 'preview') -> None:
        self.store = store
        self.execute = execute
        self.worker_id = worker_id
        self._tasks: set[asyncio.Future[None]] = set()

    async def enqueue(self, target: str, trigger_kind: str, prompt: str, **fields: Any) -> Run:  # noqa: ANN401
        """Store a run, claim it and start executing it in the background.

        Arguments:
            target: The agent or unit id.
            trigger_kind: What started the run.
            prompt: The run's input.
            **fields: Other run columns.

        Returns:
            run: The run, already running.
        """
        run = await self.store.create_run(target=target, trigger_kind=trigger_kind, prompt=prompt, **fields)
        await self.store.claim(run.id, self.worker_id)
        claimed = await self.store.get_run(run.id) or run
        task: asyncio.Future[None] = asyncio.ensure_future(self.execute(claimed))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return claimed

    async def cancel(self, run_id: str) -> bool:
        """Cancel a run that has not finished."""
        return await self.store.transition(run_id, 'cancelled', failure_reason='cancelled')


def resolve_amqp_url(environ: dict[str, str], *, preview: bool) -> str | None:
    """Return the broker URL, which preview mode does not need and every other mode requires.

    Arguments:
        environ: The process environment.
        preview: Whether the node runs as the master's live preview.

    Returns:
        url: The value of `AMQP_URL`, or `None` in preview mode.

    Raises:
        ConfigurationError: `AMQP_URL` is unset outside preview mode.
    """
    if preview:
        return None
    url = environ.get('AMQP_URL')
    if not url:
        msg = (
            'AMQP_URL is not set; rendered orgs need RabbitMQ. Set AMQP_URL, for example amqp://guest:guest@localhost/.'
        )
        raise ConfigurationError(msg)
    return url


def broker_health(broker: Any | None) -> str:  # noqa: ANN401
    """Return `disabled` without a broker, else `ok` or `unavailable` from its connection state."""
    if broker is None:
        return 'disabled'
    return 'ok' if broker.is_healthy else 'unavailable'
