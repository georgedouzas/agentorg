"""Map an agent definition onto Claude Agent SDK options."""

import os
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.types import CanUseTool, McpHttpServerConfig, McpServerConfig, McpSSEServerConfig

from ...spec import Agent, McpServer, Spec
from ._prompt import compile_system_prompt
from ._tools import as_sdk_server

BUILTIN_TOOL_NAMES = {
    'read': 'Read',
    'write': 'Write',
    'edit': 'Edit',
    'glob': 'Glob',
    'grep': 'Grep',
    'bash': 'Bash',
    'web_search': 'WebSearch',
    'web_fetch': 'WebFetch',
    'todo': 'TodoWrite',
}
ALWAYS_DISALLOWED = ['Task', 'NotebookEdit']


def _external_server(server: McpServer) -> McpServerConfig:
    """Return the SDK config of an external MCP server, reading its secrets from the environment."""
    values = {name: os.environ.get(name, '') for name in server.env}
    if server.transport == 'stdio':
        return {'type': 'stdio', 'command': server.command or '', 'args': server.args, 'env': values}
    headers = {'Authorization': f'Bearer {values[server.env[0]]}'} if server.env else {}
    if server.transport == 'sse':
        return McpSSEServerConfig(type='sse', url=server.url or '', headers=headers)
    return McpHttpServerConfig(type='http', url=server.url or '', headers=headers)


def _install_skills(agent: Agent, skills_dir: Path, workspace: Path) -> None:
    """Copy the agent's skills into the workspace's project skills directory."""
    target = workspace / '.claude' / 'skills'
    for name in agent.skills:
        shutil.copytree(skills_dir / name, target / name, dirs_exist_ok=True)


def resolve_workspace(agent: Agent, spec: Spec, root: Path, run_id: str) -> Path:
    """Return the working directory of one run of `agent` under the org's workspace root.

    Arguments:
        agent: The agent being run.
        spec: The org spec, used to find the unit that shares a `shared` workspace.
        root: The org's workspace root directory.
        run_id: The run id, which names an `ephemeral` workspace.

    Returns:
        workspace: `runs/<run_id>` for ephemeral, `agents/<agent_id>` for persistent, `units/<unit_id>` for shared.
    """
    if agent.workspace == 'persistent':
        return root / 'agents' / agent.id
    if agent.workspace == 'shared':
        return root / 'units' / spec.ai.path_to(agent.id)[-1].id
    return root / 'runs' / run_id


def build_agent_options(
    agent: Agent,
    spec: Spec,
    *,
    workspace: Path,
    skills_dir: Path,
    org_tools: list[Callable[..., Any]],
    can_use_tool: CanUseTool,
    parameter_values: Mapping[str, object] | None = None,
    resume: str | None = None,
) -> ClaudeAgentOptions:
    """Build the SDK options that run `agent` with exactly the tools, servers and skills its definition grants.

    Arguments:
        agent: The agent definition.
        spec: The org spec.
        workspace: The run's working directory; it is created if missing.
        skills_dir: The directory holding one folder per skill the org ships.
        org_tools: The org communication and knowledge tools this agent's position permits.
        can_use_tool: The permission callback consulted before every tool call.
        parameter_values: Current parameter values for principle placeholders.
        resume: The SDK session id to fork and continue, when the agent keeps session memory.

    Returns:
        options: The SDK options for one run.
    """
    workspace.mkdir(parents=True, exist_ok=True)
    _install_skills(agent, skills_dir, workspace)
    servers: dict[str, McpServerConfig] = {'org': as_sdk_server('org', org_tools)}
    if agent.tools:
        servers['custom'] = as_sdk_server('custom', agent.tools)
    servers |= {server.name: _external_server(server) for server in agent.mcp_servers}
    output_format = (
        {'type': 'json_schema', 'schema': agent.output.json_schema} if agent.output.format == 'json' else None
    )
    return ClaudeAgentOptions(
        model=agent.model,
        system_prompt=compile_system_prompt(agent, spec, parameter_values),
        tools=[BUILTIN_TOOL_NAMES[name] for name in agent.builtin_tools or []],
        allowed_tools=[],
        disallowed_tools=list(ALWAYS_DISALLOWED),
        mcp_servers=servers,
        skills=list(agent.skills),
        setting_sources=['project'] if agent.skills else [],
        cwd=workspace,
        max_turns=agent.limits.max_turns,
        max_budget_usd=agent.limits.max_run_usd or spec.operations.budget.per_run_usd,
        output_format=output_format,
        permission_mode='default',
        can_use_tool=can_use_tool,
        resume=resume if agent.memory != 'none' else None,
        fork_session=resume is not None and agent.memory != 'none',
    )
