"""Adapters that register spec runnables as AgentField reasoners on a rendered org's node."""

from agentorg.core.runtime._base import (
    FRAMEWORK_TOOL_NAMES,
    get_calling_agent,
    register_runnable,
    runnable_name,
    set_calling_agent,
)

__all__ = [
    'FRAMEWORK_TOOL_NAMES',
    'get_calling_agent',
    'register_runnable',
    'runnable_name',
    'set_calling_agent',
]
