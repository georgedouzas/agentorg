"""The agno to AgentField runtime adapter."""

from collections.abc import Callable
from typing import Any, cast
from weakref import WeakSet

from agentfield.agent import Agent as AgentFieldNode

from ...agents import AgnoAgent
from ...spec import Spec

_registered_tools: WeakSet[Callable] = WeakSet()


def _register_tools(node: AgentFieldNode, agent: AgnoAgent) -> None:
    """Register every tool in `agent.tools` as an AgentField skill, deduped per process."""
    for tool in getattr(agent, 'tools', None) or []:
        if not callable(tool) or tool in _registered_tools:
            continue
        node.skill(tags=getattr(tool, 'tags', []))(tool)
        _registered_tools.add(tool)


def register_reasoner(node: AgentFieldNode, agent: AgnoAgent, tags: list[str]) -> str:
    """Register `agent` as a reasoner on the AgentField `node` and expose its tools as skills.

    Arguments:
        node: The AgentField node to register on.
        agent: An agno Agent, Team, or Workflow.
        tags: Tags attached to the reasoner so control-plane policies can target it.

    Returns:
        name: The registered reasoner name.
    """
    name = getattr(agent, 'id', None) or getattr(agent, 'name', None) or getattr(agent, '__name__', None)
    name = str(name) if name else 'unnamed'

    _register_tools(node, agent)

    async def _run(message: str, session_id: str | None = None, user_id: str = 'default') -> dict[str, Any]:
        result = await agent.arun(message, session_id=session_id, user_id=user_id)
        return {'output': result.content}

    node.reasoner(name=name, tags=tags)(_run)
    return name


def append_principles(agent: AgnoAgent, principles: str) -> None:
    """Append the org principles to an agno-style agent's `instructions` (no-op for plain callables)."""
    if not principles:
        return
    existing = getattr(agent, 'instructions', None)
    if existing is None or callable(existing):
        return
    if isinstance(existing, list):
        existing = '\n'.join(existing)
    cast(Any, agent).instructions = f'{existing}\n\n## Principles\n\n{principles}'


def register_agents(node: AgentFieldNode, spec: Spec, principles_text: str = '') -> list[str]:
    """Register every user agent in `spec.ai.agents` as a reasoner tagged `agent`.

    The master agent registers separately via
    `agentorg.core.agents.framework.agno.register_master`.

    Arguments:
        node: The AgentField node to register on.
        spec: The org spec.
        principles_text: Rendered org principles to append to each agent's instructions.

    Returns:
        names: The registered reasoner names.
    """
    names: list[str] = []
    for agent in spec.ai.agents:
        append_principles(agent, principles_text)
        names.append(register_reasoner(node, agent, tags=['agent']))
    return names


def register_teams(node: AgentFieldNode, spec: Spec) -> list[str]:
    """Register every team in `spec.ai.teams` as a reasoner tagged `team`.

    Arguments:
        node: The AgentField node to register on.
        spec: The org spec.

    Returns:
        names: The registered reasoner names.
    """
    return [register_reasoner(node, team, tags=['team']) for team in spec.ai.teams]


def register_workflows(node: AgentFieldNode, spec: Spec) -> list[str]:
    """Register every workflow in `spec.ai.workflows` as a reasoner tagged `workflow`.

    Arguments:
        node: The AgentField node to register on.
        spec: The org spec.

    Returns:
        names: The registered reasoner names.
    """
    return [register_reasoner(node, workflow, tags=['workflow']) for workflow in spec.ai.workflows]
