"""Shared contracts of the paths through which work enters the org."""

from collections.abc import Mapping
from typing import Any, Protocol

from ._store import Run


class Enqueue(Protocol):
    """Store and queue a run of an agent or unit."""

    async def __call__(self, target: str, trigger_kind: str, prompt: str, **fields: Any) -> Run:  # noqa: ANN401
        """Queue a run of `target` started by `trigger_kind` and return it."""
        ...


class Admit(Protocol):
    """Decide whether new work for a target is accepted now."""

    async def __call__(self, target: str) -> str | None:
        """Return `None` to accept work for `target`, or the reason it is refused."""
        ...


class Parameters(Protocol):
    """Return the org's current parameter values."""

    def __call__(self) -> Mapping[str, object]:
        """Return the parameter values used to render prompts."""
        ...


def payload_tags(payload: object) -> list[str]:
    """Return the `tags` list a webhook, queue or event payload carries for pool routing, or an empty list."""
    tags = payload.get('tags') if isinstance(payload, dict) else None
    return [str(tag) for tag in tags] if isinstance(tags, list) else []


async def admit_all(target: str) -> str | None:
    """Accept work for every target."""
    del target
    return None
