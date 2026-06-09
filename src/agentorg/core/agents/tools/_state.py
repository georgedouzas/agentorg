"""Per-user org state tools, backed by AgentField actor-scope memory."""

import json
from typing import Any

from agentfield import Agent

from ._tags import tags

_KEY = 'org_state'


def _actor(user_id: str) -> Any:
    """Return the actor-scope memory client of the running node.

    Arguments:
        user_id: The user whose actor scope to return.

    Returns:
        actor: The actor-scope memory client.
    """
    node = Agent.get_current()
    if node is None:
        msg = 'State tools must run inside a reasoner execution.'
        raise RuntimeError(msg)
    return node.memory.actor(user_id)


@tags('state')
async def get_state(user_id: str = 'default') -> str:
    """Read the org state for a user.

    Arguments:
        user_id: The user whose state to read.

    Returns:
        state: JSON-encoded state document.
    """
    state = await _actor(user_id).get(_KEY)
    if state is None:
        return json.dumps({'configured': False, 'parameters': {}, 'data': {}})
    return json.dumps({'configured': True, **state}, indent=2)


@tags('state')
async def update_state(parameters: dict[str, Any] | None = None, user_id: str = 'default') -> str:
    """Update the org state's parameters for a user.

    Arguments:
        parameters: The new parameter dictionary.
        user_id: The user whose state to update.

    Returns:
        message: Confirmation of update.
    """
    actor = _actor(user_id)
    state = await actor.get(_KEY) or {'parameters': {}, 'data': {}}
    state['parameters'] = parameters or {}
    await actor.set(_KEY, state)
    return f"Updated state for user '{user_id}'."


@tags('state')
async def reset_state(user_id: str = 'default') -> str:
    """Delete the org state for a user.

    Arguments:
        user_id: The user whose state to delete.

    Returns:
        message: Confirmation of reset.
    """
    await _actor(user_id).delete(_KEY)
    return f"Reset state for user '{user_id}'."
