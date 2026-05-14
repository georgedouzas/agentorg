"""Agent factory — registers the spec's agents as reasoners on the AgentField node.

Each agent is "anything runnable" (a plain async callable, or an agno `Agent` / any object with `.arun()`).
`register_agents` adapts each into a reasoner. Charter integration: for runnables that carry an `instructions`
string (agno-style agents), the rendered charter is prepended so the agent sees the committee rules every turn.
"""

from typing import Any

from agentorg.core.spec import PLATFORM_AGENT_IDS, Spec
from agentorg.core.tools.runtime import register_runnable, runnable_name


def _prepend_charter(runnable: Any, charter_text: str) -> None:
    """Prepend the charter to an agno-style runnable's `instructions` (no-op for plain callables)."""
    if not charter_text:
        return
    existing = getattr(runnable, 'instructions', None)
    if existing is None or callable(existing):
        return
    if isinstance(existing, list):
        existing = '\n'.join(existing)
    runnable.instructions = f'## Committee Rules\n\n{charter_text}\n\n{existing}'


def register_agents(app: Any, spec: Spec, charter_text: str = '') -> list[str]:
    """Register every agent in the spec as a reasoner, tagged for control-plane policies."""
    names: list[str] = []
    for agent in spec.ai.agents:
        _prepend_charter(agent, charter_text)
        tags = ['agent', 'platform'] if runnable_name(agent) in PLATFORM_AGENT_IDS else ['agent']
        names.append(register_runnable(app, agent, tags=tags))
    return names
