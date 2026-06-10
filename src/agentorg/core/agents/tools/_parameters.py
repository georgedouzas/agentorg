"""Org instance parameter tools, backed by AgentField actor-scope memory.

Org instance parameters are the configurable knobs that distinguish one instance of an
org from another (e.g., `domain_focus`, `min_sources`). They are set once at initialization
via the dashboard's setup form, and may be adjusted afterwards by a Platform Engineer
in response to a user request.
"""

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
        msg = 'Parameter tools must run inside a reasoner execution.'
        raise RuntimeError(msg)
    return node.memory.actor(user_id)


@tags('parameters')
async def get_org_parameters(user_id: str = 'default') -> str:
    """Read the org instance parameters for a user.

    Arguments:
        user_id: The user whose parameters to read.

    Returns:
        parameters: JSON-encoded parameters with a `configured` flag.
    """
    state = await _actor(user_id).get(_KEY)
    if state is None:
        return json.dumps({'configured': False, 'parameters': {}})
    return json.dumps({'configured': True, 'parameters': state.get('parameters', {})}, indent=2)


@tags('parameters')
async def set_org_parameter(
    name: str,
    value: str | int | float | bool | dict[str, Any] | list[Any],
    user_id: str = 'default',
) -> str:
    """Set a single org instance parameter for a user.

    Arguments:
        name: The parameter name.
        value: The parameter value (any JSON-serializable scalar or container).
        user_id: The user whose parameter to set.

    Returns:
        message: Confirmation of the update.
    """
    actor = _actor(user_id)
    state = await actor.get(_KEY) or {'parameters': {}, 'data': {}}
    state['parameters'][name] = value
    await actor.set(_KEY, state)
    return f"Set '{name}' = {value!r} for user '{user_id}'."


@tags('parameters')
async def reset_org_parameters(user_id: str = 'default') -> str:
    """Delete the org instance parameters for a user.

    Arguments:
        user_id: The user whose parameters to delete.

    Returns:
        message: Confirmation of reset.
    """
    await _actor(user_id).delete(_KEY)
    return f"Reset parameters for user '{user_id}'."
