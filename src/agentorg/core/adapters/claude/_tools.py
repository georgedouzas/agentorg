"""Expose typed Python functions as Claude Agent SDK tools."""

import inspect
import json
from collections.abc import Callable
from typing import Any

from claude_agent_sdk import SdkMcpTool, ToolAnnotations, create_sdk_mcp_server
from claude_agent_sdk.types import McpSdkServerConfig
from pydantic import BaseModel, ValidationError, create_model

from ...agents.tools import side_effect_of


def _input_model(fn: Callable[..., Any]) -> type[BaseModel]:
    """Return a Pydantic model whose fields are the parameters of `fn`."""
    fields: dict[str, Any] = {}
    for name, parameter in inspect.signature(fn).parameters.items():
        annotation = Any if parameter.annotation is inspect.Parameter.empty else parameter.annotation
        default = ... if parameter.default is inspect.Parameter.empty else parameter.default
        fields[name] = (annotation, default)
    return create_model(f'{fn.__name__}_input', **fields)


def _as_text(value: object) -> str:
    """Return `value` as tool result text, serialising non-strings as JSON."""
    return value if isinstance(value, str) else json.dumps(value, default=str)


def as_sdk_tool(fn: Callable[..., Any]) -> SdkMcpTool[Any]:
    """Wrap a sync or async function as an SDK tool with a schema derived from its signature.

    Arguments:
        fn: The tool function. Its docstring summary becomes the tool description.

    Returns:
        tool: An SDK tool whose handler validates the arguments, calls `fn` and returns its result as text.
    """
    model = _input_model(fn)

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            validated = model.model_validate(args)
        except ValidationError as error:
            return {'content': [{'type': 'text', 'text': str(error)}], 'is_error': True}
        result = fn(**dict(validated))
        if inspect.isawaitable(result):
            result = await result
        return {'content': [{'type': 'text', 'text': _as_text(result)}]}

    description = (inspect.getdoc(fn) or fn.__name__).split('\n\n')[0]
    annotations = ToolAnnotations(readOnlyHint=side_effect_of(fn) == 'read')
    return SdkMcpTool(fn.__name__, description, model.model_json_schema(), handler, annotations)


def as_sdk_server(name: str, functions: list[Callable[..., Any]]) -> McpSdkServerConfig:
    """Return an in-process MCP server named `name` that serves `functions` as tools.

    Arguments:
        name: The server name; its tools are exposed to the model as `mcp__<name>__<function>`.
        functions: The tool functions.

    Returns:
        server: The SDK server configuration to pass in `ClaudeAgentOptions.mcp_servers`.
    """
    return create_sdk_mcp_server(name, tools=[as_sdk_tool(fn) for fn in functions])
