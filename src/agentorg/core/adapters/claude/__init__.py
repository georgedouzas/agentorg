"""Adapter that runs agentorg agents on the Claude Agent SDK."""

from ._options import build_agent_options, resolve_workspace
from ._prompt import compile_system_prompt
from ._runtime import RunTarget, register_org
from ._tools import as_sdk_server, as_sdk_tool, tool_error

__all__ = [
    'RunTarget',
    'as_sdk_server',
    'as_sdk_tool',
    'build_agent_options',
    'compile_system_prompt',
    'register_org',
    'resolve_workspace',
    'tool_error',
]
