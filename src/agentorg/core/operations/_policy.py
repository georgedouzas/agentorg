"""Decide whether an agent's tool call is allowed, denied or held for approval."""

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from ..agents.tools import side_effect_of
from ..spec import ActionClass, Agent, Autonomy, Spec

LifecycleState = Literal['draft', 'trial', 'active', 'paused', 'retired']
ToolKind = Literal['read', 'workspace_write', 'action', 'org', 'unknown']

READ_BUILTINS = frozenset({'Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch', 'TodoWrite', 'Skill'})
WORKSPACE_WRITES = frozenset({'Write', 'Edit'})
AUTONOMY_ORDER: tuple[Autonomy, ...] = ('read_only', 'propose', 'act', 'autonomous')
ORG_ACTIONS: dict[str, ActionClass] = {'write_knowledge': 'knowledge_publish', 'delete_knowledge': 'knowledge_publish'}


@dataclass(frozen=True)
class ToolClass:
    """What a tool call does: its kind and, for consequential actions, its action class."""

    kind: ToolKind
    action_class: ActionClass | None = None


@dataclass(frozen=True)
class Decision:
    """The policy outcome for one tool call."""

    verdict: Literal['allow', 'deny', 'hold']
    reason: str = ''
    action_class: ActionClass | None = None


def _classify_function(fn: Callable[..., Any]) -> ToolClass:
    if side_effect_of(fn) == 'read':
        return ToolClass('read')
    return ToolClass('action', 'outbound_message' if getattr(fn, 'outbound', False) else 'external_write')


def _classify_mcp(agent: Agent, server_name: str, tool: str, custom: Mapping[str, Callable[..., Any]]) -> ToolClass:
    if server_name == 'org':
        return ToolClass('action', ORG_ACTIONS[tool]) if tool in ORG_ACTIONS else ToolClass('org')
    if server_name == 'custom':
        return _classify_function(custom[tool]) if tool in custom else ToolClass('unknown')
    server = next((server for server in agent.mcp_servers if server.name == server_name), None)
    if server is None or (server.allowed_tools is not None and tool not in server.allowed_tools):
        return ToolClass('unknown')
    if tool in server.read_tools:
        return ToolClass('read')
    return ToolClass('action', 'outbound_message' if tool in server.outbound_tools else 'external_write')


def _decide_action(
    tool_name: str,
    action_class: ActionClass | None,
    autonomy: Autonomy,
    governed: Collection[ActionClass],
    lifecycle: LifecycleState,
    preview: bool,
) -> Decision:
    if preview and action_class != 'knowledge_publish':
        return Decision('deny', f'{tool_name} is disabled in preview mode; describe what you would do instead.')
    if action_class in governed or lifecycle == 'trial' or autonomy == 'propose':
        return Decision('hold', action_class=action_class)
    return Decision('allow')


def classify_tool(agent: Agent, tool_name: str) -> ToolClass:
    """Classify an SDK tool name for `agent` as a read, a workspace write, an org tool or a consequential action.

    Arguments:
        agent: The agent making the call.
        tool_name: The SDK tool name, such as `Bash` or `mcp__crm__update_deal`.

    Returns:
        tool_class: The kind of call and, for actions, the action class that governance targets.
    """
    if tool_name in READ_BUILTINS:
        return ToolClass('read')
    if tool_name in WORKSPACE_WRITES:
        return ToolClass('workspace_write')
    if tool_name == 'Bash':
        return ToolClass('action', 'code_execution')
    if tool_name.startswith('mcp__') and tool_name.count('__') >= 2:  # noqa: PLR2004 - mcp__<server>__<tool>
        _, server_name, tool = tool_name.split('__', 2)
        return _classify_mcp(agent, server_name, tool, {fn.__name__: fn for fn in agent.tools})
    return ToolClass('unknown')


def decide(
    agent: Agent,
    tool_name: str,
    *,
    autonomy: Autonomy,
    governed: Collection[ActionClass],
    lifecycle: LifecycleState,
    preview: bool,
) -> Decision:
    """Decide one tool call from the agent's effective autonomy, the governed classes and the org's state.

    Arguments:
        agent: The agent making the call.
        tool_name: The SDK tool name.
        autonomy: The agent's effective autonomy after unit ceilings.
        governed: The effective governed action classes after unit additions.
        lifecycle: The org lifecycle state.
        preview: Whether the node runs as the master's live preview.

    Returns:
        decision: `allow`, `deny` with a reason the agent reads, or `hold` with the action class to approve.
    """
    tool_class = classify_tool(agent, tool_name)
    if tool_class.kind == 'unknown':
        return Decision('deny', f'{tool_name} is not one of your tools.')
    if tool_class.kind in ('read', 'org'):
        return Decision('allow')
    if autonomy == 'read_only' or lifecycle == 'draft':
        return Decision('deny', f'{tool_name} changes state, and you may only read in this org.')
    if tool_class.kind == 'workspace_write':
        return Decision('allow')
    return _decide_action(tool_name, tool_class.action_class, autonomy, governed, lifecycle, preview)


def effective_autonomy(spec: Spec, agent_id: str) -> Autonomy:
    """Return the agent's autonomy capped by every `max_autonomy` on its path from the root unit."""
    levels = [spec.ai.agent(agent_id).autonomy]
    levels += [unit.max_autonomy for unit in spec.ai.path_to(agent_id) if unit.max_autonomy]
    return min(levels, key=AUTONOMY_ORDER.index)


def effective_governed(spec: Spec, agent_id: str) -> set[ActionClass]:
    """Return the org's governed action classes plus those added by every unit on the agent's path."""
    governed = set(spec.operations.governance.approval_required)
    for unit in spec.ai.path_to(agent_id):
        governed |= set(unit.approval_required)
    return governed


def approvers_for(spec: Spec, target_id: str) -> list[str]:
    """Return the owners of the nearest unit above `target_id` that has owners, else the org approvers or admin."""
    for unit in reversed(spec.ai.path_to(target_id)):
        if unit.owners:
            return list(unit.owners)
    return list(spec.operations.governance.approvers) or [spec.org.admin_email]
