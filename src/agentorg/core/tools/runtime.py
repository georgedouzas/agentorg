"""Adapt spec runnables into AgentField reasoners."""

from typing import Any


def runnable_name(runnable: object) -> str:
    """Best-effort stable name for a runnable: `.id`, then `.name`, then `.__name__`."""
    name = getattr(runnable, 'id', None) or getattr(runnable, 'name', None) or getattr(runnable, '__name__', None)
    return str(name) if name else 'unnamed'


def register_runnable(app: object, runnable: object, tags: list[str] | None = None) -> str:
    """Register `runnable` as a reasoner on the AgentField `app`; return the reasoner name.

    A plain async callable is registered as-is (it already has a typed signature). An object exposing `.arun()` is
    wrapped in a `message -> {"output": ...}` reasoner. `tags` are attached so control-plane policies can target it.
    """
    name = runnable_name(runnable)
    reasoner = getattr(app, 'reasoner')  # noqa: B009 — duck-typed AgentField node
    tags = tags or []

    if callable(runnable) and not hasattr(runnable, 'arun'):
        reasoner(name=name, tags=tags)(runnable)
        return name

    arun = getattr(runnable, 'arun')  # noqa: B009 — agno-style runnable

    async def _run(message: str) -> dict[str, Any]:
        result = await arun(message)
        return {'output': getattr(result, 'content', None) or str(result)}

    _run.__name__ = name
    reasoner(name=name, tags=tags)(_run)
    return name
