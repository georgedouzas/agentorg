"""Registration of agentorg's platform agents on the AgentField node."""

from typing import Any

from agentorg.core.adapters.agno import register_reasoner
from agentorg.core.adapters.agno._runtime import _append_principles

from ._base import PLATFORM_AGENTS


def register_platform_agents(node: Any, principles_text: str = '') -> list[str]:
    """Register the six built-in platform agents as reasoners tagged `agent` and `platform`.

    Each agent's tools are registered on the node as skills inside `register_reasoner`.

    Arguments:
        node: The AgentField node to register on.
        principles_text: Rendered org principles to append to each agent's instructions.

    Returns:
        names: The registered reasoner names.
    """
    names: list[str] = []
    for agent in PLATFORM_AGENTS:
        _append_principles(agent, principles_text)
        names.append(register_reasoner(node, agent, tags=['agent', 'platform']))
    return names
