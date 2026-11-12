"""Register an org's agents, units and master on its AgentField node."""

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from agentfield.agent import Agent as AgentFieldNode

from ...spec import Spec


class RunTarget(Protocol):
    """Start a run of an agent or unit and return its result."""

    def __call__(self, target_id: str, message: str, session_id: str | None, user_id: str) -> Awaitable[dict[str, Any]]:
        """Run `target_id` on `message` for `user_id`, continuing `session_id` when given."""
        ...


def _register_reasoner(node: AgentFieldNode, name: str, tags: list[str], run_target: RunTarget) -> str:
    async def run(message: str, session_id: str | None = None, user_id: str = 'default') -> dict[str, Any]:
        return await run_target(name, message, session_id, user_id)

    run.__name__ = name.replace('-', '_')
    node.reasoner(name=name, tags=tags)(run)
    return name


def _register_skills(node: AgentFieldNode, spec: Spec) -> None:
    registered: set[str] = {skill['id'] for skill in node.skills}
    for agent in spec.ai.agents:
        for fn in agent.tools:
            if fn.__name__ not in registered:
                node.skill(tags=getattr(fn, 'tags', []))(fn)
                registered.add(fn.__name__)


def register_org(
    node: AgentFieldNode,
    spec: Spec,
    run_target: RunTarget,
    master: Callable[..., Awaitable[dict[str, Any]]] | None = None,
) -> list[str]:
    """Register every agent and unit of `spec` as a tagged reasoner, and every custom tool as a node skill.

    Arguments:
        node: The org's AgentField node.
        spec: The org spec.
        run_target: The operations entry point that runs an agent or unit.
        master: The master agent's reasoner function, registered as `master` when given.

    Returns:
        names: The registered reasoner names, agents first, then units, then the master.
    """
    names = [_register_reasoner(node, agent.id, ['agent', spec.org.slug], run_target) for agent in spec.ai.agents]
    for unit in spec.ai.root.iter_units():
        names.append(_register_reasoner(node, unit.id, ['unit', unit.model, spec.org.slug], run_target))
    if master is not None:
        node.reasoner(name='master', tags=['agent', 'master', spec.org.slug])(master)
        names.append('master')
    _register_skills(node, spec)
    return names
