"""Org instance parameter tools, backed by AgentField global-scope memory.

Org instance parameters are the configurable knobs that distinguish one instance of an org from another (e.g.,
`domain_focus`, `min_sources`). They are set once at initialization via the dashboard's setup form, and may be adjusted
afterwards by a Platform Engineer in response to a user request. Parameters are org-wide — one set per org, shared by
every user — not per-user.
"""

import json
from typing import Any

from agentfield import Agent

from ._tags import tags

KEY = 'org_parameters'


def _get_node() -> Agent:
    node = Agent.get_current()
    if node is None:
        error_msg = 'Parameter tools must run inside a reasoner execution.'
        raise RuntimeError(error_msg)
    return node


@tags('parameters')
async def get_org_parameters() -> str:
    """Read the org instance parameters.

    Returns:
        state: JSON-encoded `{'parameters': dict}`. Empty dict means the org hasn't been set up.
    """
    state = await _get_node().memory.global_scope.get(KEY)
    return json.dumps({'parameters': state.get('parameters', {}) if state else {}})


@tags('parameters')
async def set_org_parameter(
    name: str,
    value: str | int | float | bool | dict[str, Any] | list[Any],
) -> str:
    """Set a single org instance parameter.

    Arguments:
        name: The parameter name.
        value: The parameter value (any JSON-serializable scalar or container).

    Returns:
        state: JSON-encoded `{'parameters': dict}` with the new value applied.
    """
    scope = _get_node().memory.global_scope
    state = await scope.get(KEY) or {'parameters': {}}
    state['parameters'][name] = value
    await scope.set(KEY, state)
    return json.dumps({'parameters': state['parameters']})


@tags('parameters')
async def reset_org_parameters() -> str:
    """Delete the org instance parameters.

    Returns:
        state: JSON-encoded `{'parameters': {}}`.
    """
    await _get_node().memory.global_scope.delete(KEY)
    return json.dumps({'parameters': {}})
