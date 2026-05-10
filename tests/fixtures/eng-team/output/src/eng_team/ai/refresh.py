"""Knowledge refresh worker + async scheduler.

The DB row is the source of truth for what should refresh and how. The scheduler
mirrors DB state into running asyncio tasks; survives restarts since the schedule
lives in the row.

Schedule formats supported:
- 'on_request'  — no background task; data computed when /api/knowledge/.../data is hit
- 'every:Ns' / 'every:Nm' / 'every:Nh' — interval refresh

Cron syntax can be added later; not needed for v1.
"""

import asyncio
import json
import logging
import re
from typing import Any

from sqlalchemy import text

from eng_team.ai.tools.providers import get_provider
from eng_team.db import get_engine

log = logging.getLogger(__name__)

_INTERVAL_RE = re.compile(r"^every:(\d+)(s|m|h)$")
_tasks: dict[str, asyncio.Task] = {}


def parse_interval_seconds(schedule: str) -> int | None:
    """Return interval in seconds for 'every:Ns' format. None for non-interval schedules."""
    if not schedule:
        return None
    m = _INTERVAL_RE.match(schedule)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    return n * {"s": 1, "m": 60, "h": 3600}[unit]


def refresh_knowledge_row(name: str, extra_args: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Run the row's provider with its stored args (merged with `extra_args` if given)
    and write the result to `data`. Returns the computed data or None on failure.

    `extra_args` lets callers inject per-request kwargs (e.g. user_id) without storing
    them in the row.
    """
    with get_engine().begin() as conn:
        row = conn.execute(
            text("SELECT name, provider, args FROM knowledge WHERE name = :n"),
            {"n": name},
        ).first()
        if row is None or not row.provider:
            return None
        merged: dict[str, Any] = {**(row.args or {}), **(extra_args or {})}
        try:
            fn = get_provider(row.provider)
            result = fn(**merged)
            conn.execute(
                text(
                    "UPDATE knowledge SET data = CAST(:d AS JSONB), last_computed = NOW(),"
                    " last_error = NULL, updated_at = NOW() WHERE name = :n",
                ),
                {"d": json.dumps(result), "n": name},
            )
            return result
        except Exception as e:  # noqa: BLE001
            log.warning("Refresh failed for %s: %s", name, e)
            conn.execute(
                text(
                    "UPDATE knowledge SET last_error = :e, last_computed = NOW(),"
                    " updated_at = NOW() WHERE name = :n",
                ),
                {"e": str(e), "n": name},
            )
            return None


async def _refresh_loop(name: str, interval_s: int) -> None:
    """Sleep+refresh forever, until cancelled. Runs the (sync) refresh on a thread to
    avoid blocking the event loop on slow providers (e.g. yfinance)."""
    # Initial run on startup so callers see fresh data without waiting one interval.
    try:
        await asyncio.to_thread(refresh_knowledge_row, name)
    except Exception:  # noqa: BLE001
        log.exception("Initial refresh failed for %s", name)
    while True:
        try:
            await asyncio.sleep(interval_s)
            await asyncio.to_thread(refresh_knowledge_row, name)
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001
            log.exception("Periodic refresh failed for %s", name)


def schedule_row(name: str, schedule: str | None) -> None:
    """Register/update an asyncio task for this row. Cancels any prior task."""
    cancel_row(name)
    if not schedule or schedule == "on_request":
        return
    interval = parse_interval_seconds(schedule)
    if interval is None:
        log.warning("Unsupported schedule for %s: %r", name, schedule)
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _tasks[name] = loop.create_task(_refresh_loop(name, interval))


def cancel_row(name: str) -> None:
    """Cancel the asyncio task for this row, if any."""
    task = _tasks.pop(name, None)
    if task and not task.done():
        task.cancel()


async def _sync_loop(poll_s: int = 30) -> None:
    """Periodically reconcile in-memory tasks with DB state. Catches schedule changes
    made by other API replicas or by direct DB edits."""
    while True:
        try:
            await asyncio.sleep(poll_s)
            with get_engine().connect() as conn:
                rows = conn.execute(
                    text("SELECT name, schedule FROM knowledge WHERE schedule IS NOT NULL"),
                ).fetchall()
            wanted = {r.name: r.schedule for r in rows if r.schedule and r.schedule != "on_request"}
            for name in list(_tasks):
                if name not in wanted:
                    cancel_row(name)
            for name, schedule in wanted.items():
                if name not in _tasks:
                    schedule_row(name, schedule)
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001
            log.exception("Sync loop iteration failed")


def start_scheduler() -> None:
    """Boot the scheduler: register tasks for every scheduled row in the DB, plus the
    background sync loop. Call once from the FastAPI startup event."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        log.warning("No running event loop; scheduler not started")
        return
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT name, schedule FROM knowledge"
                " WHERE schedule IS NOT NULL AND schedule <> 'on_request'",
            ),
        ).fetchall()
    for r in rows:
        schedule_row(r.name, r.schedule)
    loop.create_task(_sync_loop())
    log.info("Knowledge scheduler started: %d initial tasks", len(_tasks))
