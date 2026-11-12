"""Decorator that declares a tool's side effect and its AgentField skill tags."""

from collections.abc import Callable
from typing import Literal, TypeVar

T = TypeVar('T', bound=Callable)

SideEffect = Literal['read', 'write']


def tool(side_effect: SideEffect = 'write', *, outbound: bool = False, tags: tuple[str, ...] = ()) -> Callable[[T], T]:
    """Declare how a tool function affects the world and which skill tags it carries.

    Arguments:
        side_effect: `read` for tools that only observe, `write` for tools that change state.
        outbound: Whether the tool sends a message to a person outside the org, such as an email or a chat message.
        tags: Skill tags the control plane targets policies against.

    Returns:
        decorator: A decorator that sets `side_effect`, `outbound` and `tags` on the function and returns it unchanged.
    """

    def decorator(fn: T) -> T:
        fn.side_effect = side_effect  # type: ignore[attr-defined]
        fn.outbound = outbound  # type: ignore[attr-defined]
        fn.tags = list(tags)  # type: ignore[attr-defined]
        return fn

    return decorator


def side_effect_of(fn: Callable) -> SideEffect:
    """Return a tool's declared side effect, treating an undecorated tool as `write`."""
    return getattr(fn, 'side_effect', 'write')
