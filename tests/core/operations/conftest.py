"""Fixtures for the operations tests, including an in-memory stand-in for the RabbitMQ broker."""

import asyncio
import json
import shutil
import subprocess
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, ClassVar

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage

from agentorg.core.operations import Run, Store

Script = Callable[[ClaudeAgentOptions], AsyncIterator[object]]


def result_message(subtype: str = 'success', result: str | None = 'Done.', **fields: object) -> ResultMessage:
    """Return an SDK result message with test defaults for the timing fields."""
    defaults = {'duration_ms': 1, 'duration_api_ms': 1, 'is_error': False, 'num_turns': 1, 'session_id': 'sdk-1'}
    return ResultMessage(subtype=subtype, result=result, **{**defaults, **fields})  # type: ignore[arg-type]


class FakeClient:
    """Replays a scripted conversation and records the options and prompt it received."""

    opened: ClassVar[list['FakeClient']] = []

    def __init__(self, options: ClaudeAgentOptions, script: Script) -> None:
        """Keep the options and the script."""
        self.options = options
        self.script = script
        self.prompt = ''
        FakeClient.opened.append(self)

    async def __aenter__(self) -> 'FakeClient':
        """Open the fake session."""
        return self

    async def __aexit__(self, *_: type[BaseException] | BaseException | TracebackType | None) -> None:
        """Close the fake session."""
        return

    async def query(self, prompt: str) -> None:
        """Record the prompt."""
        self.prompt = prompt

    def receive_response(self) -> AsyncIterator[object]:
        """Replay the scripted messages."""
        return self.script(self.options)


def scripted(*messages: object) -> Script:
    """Return a script that replays `messages` regardless of the options."""

    async def script(_: ClaudeAgentOptions) -> AsyncIterator[object]:
        for message in messages:
            yield message

    return script


Handler = Callable[['FakeMessage'], Awaitable[None]]


@dataclass
class FakeMessage:
    """A delivered message with the acknowledgement calls a handler makes."""

    body: bytes
    priority: int = 0
    acked: bool = False
    rejected: bool = False
    requeued: bool = False

    async def ack(self) -> None:
        """Acknowledge the message."""
        self.acked = True

    async def reject(self, requeue: bool = False) -> None:
        """Reject the message."""
        self.rejected, self.requeued = True, requeue

    async def nack(self, requeue: bool = True) -> None:
        """Negatively acknowledge the message."""
        self.rejected, self.requeued = True, requeue


@dataclass
class FakeBroker:
    """An in-memory broker with the `Broker` surface; deliveries run as tasks on the current loop."""

    slug: str = 'acme'
    queues: dict[str, list[FakeMessage]] = field(default_factory=dict)
    consumers: dict[str, tuple[str, Handler]] = field(default_factory=dict)
    retries: list[tuple[str, str, int]] = field(default_factory=list)
    dead: list[str] = field(default_factory=list)
    external: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    bindings: dict[str, list[str]] = field(default_factory=dict)
    healthy: bool = True
    tasks: set[asyncio.Task[None]] = field(default_factory=set)

    @property
    def is_healthy(self) -> bool:
        """Whether the fake connection is up."""
        return self.healthy

    async def connect(self) -> None:
        """Connect; the fake has nothing to open."""

    async def declare_targets(self, targets: list[str], retries: int) -> None:
        """Create an empty queue per target."""
        for target in targets:
            self.queues.setdefault(f'runs.{target}', [])

    def _deliver(self, queue: str, message: FakeMessage) -> None:
        handlers = [handler for name, handler in self.consumers.values() if name == queue]
        if not handlers:
            self.queues.setdefault(queue, []).append(message)
            self.queues[queue].sort(key=lambda held: -held.priority)
            return
        task = asyncio.get_running_loop().create_task(handlers[0](message))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def publish_run(self, target: str, run_id: str, priority: int) -> None:
        """Deliver a run message to the target's consumer or hold it."""
        self._deliver(f'runs.{target}', FakeMessage(json.dumps({'run_id': run_id}).encode(), priority))

    async def publish_retry(self, target: str, run_id: str, attempt: int, priority: int = 0) -> None:
        """Record a delayed retry; `release_retries` delivers it."""
        self.retries.append((target, run_id, attempt))

    async def release_retries(self) -> None:
        """Deliver every recorded retry as if its delay had passed."""
        pending, self.retries = self.retries, []
        for target, run_id, _ in pending:
            await self.publish_run(target, run_id, 0)

    async def publish_dead(self, run_id: str) -> None:
        """Deliver to the dead-letter consumer or record the run id."""
        self.dead.append(run_id)
        self._deliver('runs.dead', FakeMessage(json.dumps({'run_id': run_id}).encode()))

    async def publish_event(self, name: str, payload: dict[str, Any], chain: list[str]) -> None:
        """Deliver an event to every trigger queue bound to its name."""
        body = json.dumps({'event': name, 'payload': payload, 'chain': chain}).encode()
        for queue in self.bindings.get(name, []):
            self._deliver(queue, FakeMessage(body))

    async def publish_external(self, exchange: str, routing_key: str, payload: dict[str, Any]) -> None:
        """Record a message published outside the org."""
        self.external.append((exchange, routing_key, payload))

    async def _consume(self, queue: str, handler: Handler) -> str:
        tag = f'ctag-{len(self.consumers) + 1}-{queue}'
        self.consumers[tag] = (queue, handler)
        held, self.queues[queue] = self.queues.get(queue, []), []
        for message in held:
            self._deliver(queue, message)
        return tag

    async def consume_runs(self, target: str, prefetch: int, handler: Handler) -> str:
        """Consume a target's run queue."""
        return await self._consume(f'runs.{target}', handler)

    async def consume_dead(self, handler: Handler) -> str:
        """Consume the dead-letter queue."""
        return await self._consume('runs.dead', handler)

    async def consume_events(self, trigger_id: str, event: str, handler: Handler) -> str:
        """Bind the trigger's queue to the event name and consume it."""
        queue = f'events.{trigger_id}'
        self.bindings.setdefault(event, []).append(queue)
        return await self._consume(queue, handler)

    async def consume_queue(self, name: str, handler: Handler) -> str:
        """Consume an external queue."""
        return await self._consume(name, handler)

    async def push_external(self, queue: str, body: bytes) -> FakeMessage:
        """Simulate an external system publishing to `queue` and return the message."""
        message = FakeMessage(body)
        self._deliver(queue, message)
        await self.drain()
        return message

    async def cancel(self, consumer_tag: str) -> None:
        """Stop a consumer; later messages are held."""
        self.consumers.pop(consumer_tag)

    async def drain(self) -> None:
        """Wait until every in-flight delivery has finished."""
        while self.tasks:
            await asyncio.gather(*list(self.tasks))

    async def close(self) -> None:
        """Close; the fake has nothing to release."""


class Queued:
    """Records enqueued runs instead of executing them."""

    def __init__(self, store: Store) -> None:
        """Keep the store that creates the runs."""
        self.store = store
        self.runs: list[Run] = []

    async def __call__(self, target: str, trigger_kind: str, prompt: str, **fields: Any) -> Run:  # noqa: ANN401
        """Store and record a run."""
        run = await self.store.create_run(target=target, trigger_kind=trigger_kind, prompt=prompt, **fields)
        self.runs.append(run)
        return run


@pytest.fixture
def fake_broker() -> FakeBroker:
    """An in-memory broker."""
    return FakeBroker()


@pytest.fixture
async def store(tmp_path: Path) -> AsyncIterator[Store]:
    """An opened store on a temporary sqlite database."""
    store = Store(f'sqlite+aiosqlite:///{tmp_path / "ops.db"}')
    await store.open()
    yield store
    await store.close()


def docker_available() -> bool:
    """Return whether a Docker daemon answers."""
    docker = shutil.which('docker')
    if docker is None:
        return False
    return subprocess.run([docker, 'info'], capture_output=True, check=False).returncode == 0  # noqa: S603


@pytest.fixture(scope='session')
def amqp_url() -> Iterator[str]:
    """The AMQP URL of a RabbitMQ 3.13 container shared by the session; skips without Docker."""
    if not docker_available():
        pytest.skip('Docker is required for RabbitMQ')
    from testcontainers.rabbitmq import RabbitMqContainer  # noqa: PLC0415 - optional dev dependency, only with Docker

    with RabbitMqContainer('rabbitmq:3.13-management') as container:
        params = container.get_connection_params()
        yield f'amqp://guest:guest@{params.host}:{params.port}/'
