"""Tag decorator that attaches AgentField skill tags to a tool function."""

from collections.abc import Callable
from typing import TypeVar

T = TypeVar('T', bound=Callable)


def tags(*labels: str) -> Callable[[T], T]:
    """Attach skill tags to a tool function for per-agent node registration.

    Arguments:
        *labels: Tag strings the control plane targets policies against.

    Returns:
        decorator: A no-op wrapper that sets `fn.tags = list(labels)`.
    """

    def decorator(fn: T) -> T:
        fn.tags = list(labels)  # type: ignore[attr-defined]
        return fn

    return decorator
