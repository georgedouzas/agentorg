"""Org instance parameter tools, backed by AgentField global-scope memory."""

import json
from typing import Any

from ._node import current_memory
from ._tags import tool

KEY = 'org_parameters'


@tool('read', tags=('parameters',))
async def get_org_parameters() -> str:
    """Read the org instance parameters.

    Returns:
        state: JSON-encoded `{'parameters': dict}`. Empty dict means the org hasn't been set up.
    """
    state = await current_memory().global_scope.get(KEY)
    return json.dumps({'parameters': state.get('parameters', {}) if state else {}})


@tool('write', tags=('parameters',))
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
    scope = current_memory().global_scope
    state = await scope.get(KEY) or {'parameters': {}}
    state['parameters'][name] = value
    await scope.set(KEY, state)
    return json.dumps({'parameters': state['parameters']})


@tool('write', tags=('parameters',))
async def reset_org_parameters() -> str:
    """Delete the org instance parameters.

    Returns:
        state: JSON-encoded `{'parameters': {}}`.
    """
    await current_memory().global_scope.delete(KEY)
    return json.dumps({'parameters': {}})
