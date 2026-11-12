"""Persist runs, approvals, inbox items, lifecycle history and coordination state in the org database."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

RunStatus = Literal['queued', 'running', 'awaiting_approval', 'succeeded', 'failed', 'cancelled']
TERMINAL = ('succeeded', 'failed', 'cancelled')
ACTIVE = ('running', 'awaiting_approval')
PREDECESSORS: dict[str, tuple[str, ...]] = {
    'running': ('queued', 'awaiting_approval'),
    'awaiting_approval': ('running',),
    'succeeded': ('running',),
    'failed': ('running', 'awaiting_approval'),
    'cancelled': ('queued', 'running', 'awaiting_approval'),
}


def _now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(UTC)


def _new_id() -> str:
    """Return a new random id."""
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    """Declarative base of the operations tables."""


class Run(Base):
    """One unit of work against an agent or unit."""

    __tablename__ = 'runs'

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    target: Mapped[str] = mapped_column(String(128), index=True)
    trigger_kind: Mapped[str] = mapped_column(String(16), index=True)
    trigger_id: Mapped[str | None] = mapped_column(String(128))
    parent_id: Mapped[str | None] = mapped_column(String(32), index=True)
    retry_of: Mapped[str | None] = mapped_column(String(32))
    session_id: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[str] = mapped_column(String(128), default='default')
    prompt: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    chain: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), index=True, default='queued')
    worker_id: Mapped[str | None] = mapped_column(String(64))
    output: Mapped[Any] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(64))
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    transcript: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Approval(Base):
    """A held tool call waiting for a human decision."""

    __tablename__ = 'approvals'

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    action_class: Mapped[str] = mapped_column(String(32))
    tool_name: Mapped[str] = mapped_column(String(256))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON)
    approvers: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default='pending', index=True)
    decided_by: Mapped[str | None] = mapped_column(String(256))
    comment: Mapped[str | None] = mapped_column(Text)
    edited_arguments: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InboxItem(Base):
    """Something a human must look at: an escalation or a failed run."""

    __tablename__ = 'inbox'

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    kind: Mapped[str] = mapped_column(String(16))
    run_id: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LifecycleEvent(Base):
    """One lifecycle transition of the org or of a single agent or unit."""

    __tablename__ = 'lifecycle_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(128), default='org', index=True)
    from_state: Mapped[str | None] = mapped_column(String(16))
    to_state: Mapped[str] = mapped_column(String(16))
    actor: Mapped[str] = mapped_column(String(256))
    reason: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class _KeyValue(Base):
    """A coordination value: session owners, idempotency keys, leases and similar."""

    __tablename__ = 'coordination'

    namespace: Mapped[str] = mapped_column(String(32), primary_key=True)
    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Store:
    """Async access to the operations tables of one org database.

    Arguments:
        url: For example `sqlite+aiosqlite:///runs.db` or `postgresql+asyncpg://...`.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self._engine: AsyncEngine = create_async_engine(url)
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    async def open(self) -> None:
        """Create the operations tables when they do not exist."""

        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """Dispose of the database connections."""
        await self._engine.dispose()

    async def create_run(self, **fields: Any) -> Run:  # noqa: ANN401
        """Insert a queued run and return it.

        Arguments:
            **fields: Column values; `target`, `trigger_kind` and `prompt` are required.

        Returns:
            run: The stored run.
        """
        run = Run(**fields)
        async with self._sessions.begin() as session:
            session.add(run)
        return run

    async def get_run(self, run_id: str) -> Run | None:
        """Return the run with id `run_id`, or `None`."""

        async with self._sessions() as session:
            return await session.get(Run, run_id)

    async def count_active(self, target: str) -> int:
        """Return how many runs of `target` are running or awaiting approval."""

        async with self._sessions() as session:
            query = select(func.count()).where(Run.target == target, Run.status.in_(ACTIVE))
            return int(await session.scalar(query) or 0)

    async def claim(self, run_id: str, worker_id: str, max_active: int | None = None) -> bool:
        """Move a queued run to running for `worker_id`, unless its target already has `max_active` active runs.

        Arguments:
            run_id: The run to claim.
            worker_id: The claiming worker.
            max_active: The target's replica cap, or `None` for no cap.

        Returns:
            claimed: Whether this call moved the run to running.
        """

        async with self._sessions.begin() as session:
            run = await session.get(Run, run_id)
            if run is None or run.status != 'queued':
                return False
            condition = and_(Run.id == run_id, Run.status == 'queued')
            if max_active is not None:
                active = select(func.count()).where(Run.target == run.target, Run.status.in_(ACTIVE)).scalar_subquery()
                condition = and_(condition, active < max_active)
            statement = update(Run).where(condition).values(status='running', worker_id=worker_id, started_at=_now())
            result = await session.execute(statement)
            return bool(getattr(result, 'rowcount', 0))

    async def transition(self, run_id: str, status: RunStatus, **fields: Any) -> bool:  # noqa: ANN401
        """Move a run to `status` when its current status allows it, setting `fields` as well.

        Arguments:
            run_id: The run to move.
            status: The new status.
            **fields: Other columns to set, such as `output` or `failure_reason`.

        Returns:
            moved: Whether the run was in an allowed predecessor status and moved.
        """
        values = {**fields, 'status': status}
        if status in TERMINAL:
            values.setdefault('ended_at', _now())
        statement = update(Run).where(Run.id == run_id, Run.status.in_(PREDECESSORS[status])).values(**values)
        async with self._sessions.begin() as session:
            result = await session.execute(statement)
            return bool(getattr(result, 'rowcount', 0))

    async def append_transcript(self, run_id: str, events: list[dict[str, Any]]) -> None:
        """Append stream events to a run's transcript."""

        async with self._sessions.begin() as session:
            run = await session.get(Run, run_id)
            if run is not None:
                run.transcript = [*run.transcript, *events]

    async def list_runs(
        self,
        *,
        target: str | None = None,
        status: str | None = None,
        trigger_kind: str | None = None,
        parent_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[Run]:
        """Return runs matching every given filter, newest first.

        Arguments:
            target: Only runs of this agent or unit.
            status: Only runs in this status.
            trigger_kind: Only runs started by this trigger kind.
            parent_id: Only children of this run.
            since: Only runs created at or after this time.
            until: Only runs created before this time.
            limit: The maximum number of runs.

        Returns:
            runs: The matching runs.
        """
        filters = [
            column == value
            for column, value in (
                (Run.target, target),
                (Run.status, status),
                (Run.trigger_kind, trigger_kind),
                (Run.parent_id, parent_id),
            )
            if value is not None
        ]
        filters += [Run.created_at >= since] if since else []
        filters += [Run.created_at < until] if until else []
        query = select(Run).where(*filters).order_by(Run.created_at.desc()).limit(limit)
        async with self._sessions() as session:
            return list((await session.scalars(query)).all())

    async def month_spend(self, month_start: datetime, target: str | None = None) -> float:
        """Return the summed run cost since `month_start`, optionally for one target only."""
        filters = [Run.created_at >= month_start] + ([Run.target == target] if target else [])
        async with self._sessions() as session:
            total = await session.scalar(select(func.coalesce(func.sum(Run.cost_usd), 0.0)).where(*filters))
        return float(total or 0.0)

    async def purge_runs(self, before: datetime) -> int:
        """Delete terminal runs created before `before` and return how many were deleted."""
        statement = delete(Run).where(Run.created_at < before, Run.status.in_(TERMINAL))
        async with self._sessions.begin() as session:
            return int(getattr(await session.execute(statement), 'rowcount', 0))

    async def add(self, record: Approval | InboxItem | LifecycleEvent) -> None:
        """Insert an approval, inbox item or lifecycle event."""

        async with self._sessions.begin() as session:
            session.add(record)

    async def get_approval(self, approval_id: str) -> Approval | None:
        """Return the approval with id `approval_id`, or `None`."""

        async with self._sessions() as session:
            return await session.get(Approval, approval_id)

    async def decide_approval(self, approval_id: str, **fields: Any) -> bool:  # noqa: ANN401
        """Record a decision on a pending approval.

        Arguments:
            approval_id: The approval to decide.
            **fields: `status`, `decided_by`, `comment` and `edited_arguments`.

        Returns:
            decided: Whether the approval was still pending.
        """
        statement = (
            update(Approval)
            .where(Approval.id == approval_id, Approval.status == 'pending')
            .values(**fields, decided_at=_now())
        )
        async with self._sessions.begin() as session:
            return bool(getattr(await session.execute(statement), 'rowcount', 0))

    async def list_approvals(self, status: str | None = 'pending') -> list[Approval]:
        """Return approvals in `status`, oldest first."""
        filters = [Approval.status == status] if status else []
        async with self._sessions() as session:
            return list((await session.scalars(select(Approval).where(*filters).order_by(Approval.created_at))).all())

    async def list_inbox(self, *, resolved: bool = False) -> list[InboxItem]:
        """Return inbox items, newest first."""
        query = select(InboxItem).where(InboxItem.resolved == resolved).order_by(InboxItem.created_at.desc())
        async with self._sessions() as session:
            return list((await session.scalars(query)).all())

    async def lifecycle_history(self, subject: str = 'org') -> list[LifecycleEvent]:
        """Return the lifecycle transitions of `subject`, oldest first."""
        query = select(LifecycleEvent).where(LifecycleEvent.subject == subject).order_by(LifecycleEvent.id)
        async with self._sessions() as session:
            return list((await session.scalars(query)).all())

    async def get_value(self, namespace: str, key: str) -> object:
        """Return a coordination value, or `None` when it is missing or expired."""

        async with self._sessions() as session:
            row = await session.get(_KeyValue, (namespace, key))
        if row is None or (row.expires_at is not None and row.expires_at.replace(tzinfo=UTC) <= _now()):
            return None
        return row.value

    async def set_value(self, namespace: str, key: str, value: object, ttl: timedelta | None = None) -> None:
        """Store a coordination value, optionally expiring after `ttl`."""
        expires_at = _now() + ttl if ttl else None
        async with self._sessions.begin() as session:
            await session.merge(_KeyValue(namespace=namespace, key=key, value=value, expires_at=expires_at))

    async def acquire_lease(self, name: str, holder: str, ttl: timedelta) -> bool:
        """Take or renew the lease `name` for `holder` when it is free, expired or already held by `holder`.

        Arguments:
            name: The lease name.
            holder: The worker asking for the lease.
            ttl: How long the lease lasts without renewal.

        Returns:
            held: Whether `holder` holds the lease after the call.
        """

        async with self._sessions.begin() as session:
            row = await session.get(_KeyValue, ('lease', name), with_for_update=True)
            expired = row is None or row.expires_at is None or row.expires_at.replace(tzinfo=UTC) <= _now()
            if row is not None and not expired and row.value != holder:
                return False
            await session.merge(_KeyValue(namespace='lease', key=name, value=holder, expires_at=_now() + ttl))
            return True
