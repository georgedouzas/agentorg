"""Thin wrapper around `make_agent` that fills the constant fields every platform engineer leaves empty."""

from collections.abc import Callable

from agno.agent import Agent

from .. import make_agent
from ._defaults import PLATFORM_DEFAULT_MODEL


def platform_make_agent(
    *,
    name: str,
    agent_id: str,
    role: str,
    tools: list[Callable],
    in_scope: list[str],
    workflow: list[str],
) -> Agent:
    """Build a platform agent with the shared model and empty persona defaults.

    Arguments:
        name: Display name for the agent.
        agent_id: Stable identifier.
        role: Short description of what the agent owns.
        tools: Callables the agent invokes.
        in_scope: Topics the agent handles.
        workflow: Steps the agent follows for an in-scope request.

    Returns:
        agent: A configured `agno.Agent`.
    """
    return make_agent(
        model=PLATFORM_DEFAULT_MODEL,
        name=name,
        agent_id=agent_id,
        role=role,
        tools=tools,
        in_scope=in_scope,
        workflow=workflow,
    )
