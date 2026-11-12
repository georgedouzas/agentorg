"""Wire the store, broker, dispatcher, runner, units, intake, governance and lifecycle of one rendered org."""

import asyncio
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agentfield.agent import Agent as AgentFieldNode
from claude_agent_sdk import ClaudeSDKClient
from fastapi import APIRouter

from .._errors import ConfigurationError
from ..agents.tools import bind_node, write_knowledge
from ..spec import Agent, QueueTrigger, Spec
from ._approvals import ApprovalGate, Approvals
from ._broker import Broker
from ._bus import EventBus
from ._comms import OrgTools
from ._consumers import QueueBroker, QueueConsumers
from ._lifecycle import Lifecycle
from ._notify import Notifier
from ._policy import LifecycleState
from ._queue import HEARTBEAT, Dispatcher, InlineDispatcher, resolve_amqp_url
from ._runner import ClientFactory, Runner
from ._scheduler import Scheduler
from ._store import TERMINAL, InboxItem, Run, Store
from ._units import UnitEngine
from ._webhooks import build_webhook_router

WAIT_POLL_S = 0.5


def database_url(spec: Spec, environ: Mapping[str, str], data_dir: Path, *, preview: bool = False) -> str:
    """Return the async database URL of the org's operations store.

    Arguments:
        spec: The org spec, whose `runtime.infra.database` picks sqlite or postgres.
        environ: The environment; postgres reads `DATABASE_URL`.
        data_dir: The directory of the sqlite file.
        preview: Whether the node runs as the live preview, which always uses sqlite.

    Returns:
        url: A SQLAlchemy async URL.

    Raises:
        ConfigurationError: The org uses postgres and `DATABASE_URL` is unset.
    """
    if preview or spec.runtime.infra.database == 'sqlite':
        return f'sqlite+aiosqlite:///{data_dir / "operations.db"}'
    if not environ.get('DATABASE_URL'):
        msg = 'DATABASE_URL is not set; this org uses postgres. Set DATABASE_URL to its postgresql:// URL.'
        raise ConfigurationError(msg)
    return environ['DATABASE_URL'].replace('postgresql://', 'postgresql+asyncpg://', 1)


class _NoBroker:
    """Event broker that drops events, used by the live preview."""

    async def publish_event(self, name: str, payload: dict[str, Any], chain: list[str]) -> None:
        del name, payload, chain

    async def consume_events(self, trigger_id: str, event: str, handler: Any) -> str:  # noqa: ANN401
        del trigger_id, event, handler
        return ''

    async def cancel(self, consumer_tag: str) -> None:
        del consumer_tag


class OrgRuntime:
    """Every operations service of one org, connected to each other.

    Arguments:
        spec: The org spec.
        environ: The environment, which holds `AMQP_URL`, secrets and `AGENTORG_PREVIEW_MODE`.
        data_dir: The directory holding the sqlite store and run workspaces.
        skills_dir: The directory of the org's skills.
        client_factory: Opens an SDK client for given options.
    """

    def __init__(
        self,
        spec: Spec,
        *,
        environ: Mapping[str, str],
        data_dir: Path,
        skills_dir: Path,
        client_factory: ClientFactory = ClaudeSDKClient,
    ) -> None:
        self.spec = spec
        self.environ = environ
        self.preview = environ.get('AGENTORG_PREVIEW_MODE', '').lower() == 'true'
        amqp_url = resolve_amqp_url(dict(environ), preview=self.preview)
        self.store = Store(database_url(spec, environ, data_dir, preview=self.preview))
        self.broker = Broker(amqp_url, spec.org.slug) if amqp_url else None
        self.notifier = Notifier(spec, self.store, environ=environ, broker=self.broker)
        self.bus = EventBus(
            spec,
            self.store,
            self.broker or _NoBroker(),
            self.enqueue,
            admit=self.admit,
            parameters=self.parameters,
        )
        self.lifecycle = Lifecycle(spec, self.store, self.bus.publish, self.notifier.notify, self._apply_lifecycle)
        self.approvals = Approvals(spec, self.store, self.bus.publish, self.notifier.notify)
        self.org_tools = OrgTools(spec, self.store, self.bus, self.call_target)
        gate = ApprovalGate(spec, self.approvals, self.lifecycle.state, preview=self.preview)
        self.runner = Runner(
            spec,
            self.store,
            workspace_root=data_dir / 'workspaces',
            skills_dir=skills_dir,
            gate=gate,
            org_tools=self.org_tools.tools_for,
            file_output=self._file_output,
            client_factory=client_factory,
        )
        self.units = UnitEngine(spec, self.store, self.call_target, self.approvals)
        self.dispatcher: Dispatcher | InlineDispatcher = (
            InlineDispatcher(self.store, self.execute)
            if self.broker is None
            else Dispatcher(spec, self.store, self.broker, self.execute, on_failure=self.apply_failure_policy)
        )
        worker_id = getattr(self.dispatcher, 'worker_id', 'preview')
        self.scheduler = Scheduler(
            spec,
            self.store,
            self.enqueue,
            self.admit,
            parameters=self.parameters,
            worker_id=worker_id,
            paused=self._paused,
        )
        self.consumers = QueueConsumers(spec, self._broker_for, self.enqueue, self.admit, self.parameters)
        self._background: list[asyncio.Task[None]] = []

    def parameters(self) -> dict[str, object]:
        """Return the org's parameter values, which are the spec defaults."""
        return {parameter.name: parameter.default for parameter in self.spec.parameters}

    async def admit(self, target: str) -> str | None:
        """Return why new work for `target` is refused, or `None` to accept it."""
        return await self.lifecycle.admit(target)

    async def enqueue(self, target: str, trigger_kind: str, prompt: str, **fields: Any) -> Run:  # noqa: ANN401
        """Queue a run through the dispatcher."""
        return await self.dispatcher.enqueue(target, trigger_kind, prompt, **fields)

    async def _paused(self) -> bool:
        """Return whether the org is paused."""
        return await self.lifecycle.state() == 'paused'

    async def _broker_for(self, trigger: QueueTrigger) -> QueueBroker:
        """Return the broker a queue trigger consumes from."""
        if trigger.url_env:
            broker = Broker(self.environ[trigger.url_env], self.spec.org.slug)
            await broker.connect()
            return broker
        if self.broker is None:
            msg = 'Queue triggers need a broker.'
            raise RuntimeError(msg)
        return self.broker

    async def _file_output(self, agent: Agent, run: Run, output: str) -> None:
        """Write a run's output as a knowledge unit and announce it."""
        if self.preview or agent.output.knowledge_type is None:
            return
        name = f'{agent.id}-{run.id[:8]}'
        await write_knowledge(agent.output.knowledge_type, name, output)
        await self.bus.publish_knowledge('created', {'type': agent.output.knowledge_type, 'name': name})

    async def wait_for(self, run_id: str) -> Run:
        """Return run `run_id` once it reaches a terminal status."""
        while (run := await self.store.get_run(run_id)) is None or run.status not in TERMINAL:
            await asyncio.sleep(WAIT_POLL_S)
        return run

    async def call_target(self, target: str, task: str, parent: Run) -> dict[str, Any]:
        """Run `target` on `task` as a child of `parent` and return its status and output."""
        child = await self.enqueue(
            target,
            'delegation',
            task,
            parent_id=parent.id,
            session_id=parent.session_id,
            user_id=parent.user_id,
            chain=parent.chain,
        )
        finished = await self.wait_for(child.id)
        return {'run_id': finished.id, 'status': finished.status, 'output': finished.output}

    async def start_run(self, target: str, message: str, session_id: str | None, user_id: str) -> dict[str, Any]:
        """Queue a manual run of `target`, or of the agent that owns the session after a handoff, without waiting.

        Arguments:
            target: The agent or unit the user addressed.
            message: The user's message.
            session_id: The chat session, which routes to its current owner.
            user_id: The user.

        Returns:
            started: The run id and status `queued` or `running`, or status `refused` with the reason as output.
        """
        owner = await self.store.get_value('session_owner', session_id) if session_id else None
        if isinstance(owner, dict):
            target, message = owner['agent'], f'Handoff note: {owner["note"]}\n\n{message}'
        refusal = await self.admit(target)
        if refusal is not None:
            return {'status': 'refused', 'output': refusal}
        run = await self.enqueue(target, 'manual', message, session_id=session_id, user_id=user_id)
        return {'run_id': run.id, 'status': run.status}

    async def run_target(self, target: str, message: str, session_id: str | None, user_id: str) -> dict[str, Any]:
        """Start a manual run like `start_run` and wait for its result.

        Arguments:
            target: The agent or unit the user addressed.
            message: The user's message.
            session_id: The chat session.
            user_id: The user.

        Returns:
            result: The run id, status and output, or the refusal.
        """
        started = await self.start_run(target, message, session_id, user_id)
        if started['status'] == 'refused':
            return started
        finished = await self.wait_for(started['run_id'])
        return {'run_id': finished.id, 'status': finished.status, 'output': finished.output}

    async def execute(self, run: Run) -> None:
        """Execute a claimed run of an agent or unit, then announce it and apply the lifecycle checks."""
        is_unit = any(unit.id == run.target for unit in self.spec.ai.units)
        await (self.units.execute(run) if is_unit else self.runner.execute(run))
        finished = await self.store.get_run(run.id)
        if finished is not None and finished.status in ('succeeded', 'failed'):
            payload = {'run_id': run.id, 'target': run.target, 'trigger': run.trigger_id}
            await self.bus.publish(f'run.{finished.status}', payload, run.chain)
        await self.lifecycle.after_run()

    async def apply_failure_policy(self, run: Run) -> None:
        """Notify, escalate to the inbox, or hand off to the fallback agent for a run whose retries are exhausted."""
        policy = self.spec.operations.runs
        payload = {'run_id': run.id, 'target': run.target, 'reason': run.failure_reason}
        await self.notifier.notify('run_failed', payload)
        if policy.on_failure == 'escalate':
            reason = f"Run of '{run.target}' failed with {run.failure_reason} after retries."
            await self.store.add(InboxItem(kind='escalation', run_id=run.id, reason=reason, context=payload))
        if policy.on_failure == 'handoff' and policy.fallback_agent:
            prompt = f'This run failed with {run.failure_reason}. Take it over.\n\nOriginal request:\n{run.prompt}'
            await self.enqueue(policy.fallback_agent, 'manual', prompt, parent_id=run.id, session_id=run.session_id)

    async def _consumers_on(self, on: bool) -> None:
        """Start or stop consuming runs, events and external queues."""
        if not isinstance(self.dispatcher, Dispatcher):
            return
        for target in self.dispatcher.targets:
            await (self.dispatcher.resume(target) if on else self.dispatcher.pause(target))
        await (self.bus.start() if on else self.bus.stop())
        await (self.consumers.start() if on else self.consumers.stop())

    async def _apply_lifecycle(self, before: LifecycleState, after: LifecycleState) -> None:
        """Stop consumers when the org pauses or retires and restart them on resume."""
        if after in ('paused', 'retired'):
            await self._consumers_on(on=False)
        elif before == 'paused':
            await self._consumers_on(on=True)

    async def _heartbeat(self) -> None:
        """Record this worker as alive at a fixed interval."""
        while isinstance(self.dispatcher, Dispatcher):
            await self.dispatcher.heartbeat()
            await asyncio.sleep(HEARTBEAT.total_seconds())

    @property
    def router(self) -> APIRouter:
        """The webhook router of the org."""
        return build_webhook_router(
            self.spec,
            self.store,
            self.enqueue,
            self.admit,
            self.parameters,
            environ=self.environ,
            broker_healthy=lambda: self.broker is not None and self.broker.is_healthy,
        )

    async def start(self) -> None:
        """Open the store, connect the broker and, outside preview, start consuming and scheduling."""
        await self.store.open()
        state = await self.lifecycle.state()
        if self.broker is None:
            return
        await self.broker.connect()
        assert isinstance(self.dispatcher, Dispatcher)
        await self.dispatcher.start([] if state in ('paused', 'retired') else None)
        if state not in ('paused', 'retired', 'draft'):
            await self.bus.start()
            await self.consumers.start()
        self.scheduler.start()
        self._background.append(asyncio.get_running_loop().create_task(self._heartbeat()))

    async def stop(self) -> None:
        """Stop scheduling and consuming, and close the broker and store."""
        await self.scheduler.stop()
        for task in self._background:
            task.cancel()
        if isinstance(self.dispatcher, Dispatcher):
            await self.dispatcher.stop()
        if self.broker is not None:
            await self.broker.close()
        await self.store.close()


def start_operations(
    app: AgentFieldNode,
    spec: Spec,
    *,
    data_dir: Path,
    skills_dir: Path,
    environ: Mapping[str, str] | None = None,
    client_factory: ClientFactory = ClaudeSDKClient,
) -> OrgRuntime:
    """Create the org's operations runtime, mount its webhook routes and start it with the app.

    Arguments:
        app: The org's FastAPI application, usually its AgentField node.
        spec: The org spec.
        data_dir: The directory holding the sqlite store and run workspaces.
        skills_dir: The directory of the org's skills.
        environ: The environment; the process environment by default.
        client_factory: Opens an SDK client for given options.

    Returns:
        runtime: The runtime; its `run_target` is what reasoners call.
    """
    runtime = OrgRuntime(
        spec,
        environ=dict(os.environ) if environ is None else environ,
        data_dir=data_dir,
        skills_dir=skills_dir,
        client_factory=client_factory,
    )
    bind_node(app)
    app.include_router(runtime.router)
    app.router.add_event_handler('startup', runtime.start)
    app.router.add_event_handler('shutdown', runtime.stop)
    return runtime
