"""Per-user org-state tools backed by AgentField memory.

Each user's state lives in **actor-scope** memory under the `org_state` key. These are agent *tools*: they run inside a
reasoner execution, so they resolve the running node via `Agent.get_current()`.
"""

import json
from typing import Any

from agentfield import Agent

_KEY = 'org_state'


def _actor(user_id: str) -> Any:
    """Actor-scope memory client of the running node (state tools run inside a reasoner)."""
    node = Agent.get_current()
    if node is None:
        msg = 'State tools must run inside a reasoner execution.'
        raise RuntimeError(msg)
    return node.memory.actor(user_id)


async def get_state(user_id: str = 'default') -> str:
    """Read the org state for a user.

    Returns JSON-encoded {configured, parameters, data}.
    """
    state = await _actor(user_id).get(_KEY)
    if state is None:
        return json.dumps({'configured': False, 'parameters': {}, 'data': {}})
    return json.dumps({'configured': True, **state}, indent=2)


async def update_state(parameters: dict[str, Any] | None = None, user_id: str = 'default') -> str:
    """Update the org state's parameters for a user.

    Returns confirmation.
    """
    actor = _actor(user_id)
    state = await actor.get(_KEY) or {'parameters': {}, 'data': {}}
    state['parameters'] = parameters or {}
    await actor.set(_KEY, state)
    return f"Updated state for user '{user_id}'."


async def reset_state(user_id: str = 'default') -> str:
    """Delete the org state for a user."""
    await _actor(user_id).delete(_KEY)
    return f"Reset state for user '{user_id}'."
