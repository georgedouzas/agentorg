"""Agent factory — registers the spec's agents as reasoners on the AgentField node.

Each agent is "anything runnable" (a plain async callable, or an agno `Agent` / any object with `.arun()`).
`register_agents` adapts each into a reasoner. Principles integration: for runnables that carry an
`instructions` string, the rendered principles are appended under a `## Principles` heading so the
agent sees the org's rules on every turn.
"""

from typing import Any

from agentorg.core.instructions import append_principles
from agentorg.core.runtime import register_runnable, runnable_name
from agentorg.core.spec import PLATFORM_AGENT_IDS, Spec


def _append_principles(runnable: Any, principles: str) -> None:
    """Append the org principles to an agno-style runnable's `instructions` (no-op for plain callables)."""
    if not principles:
        return
    existing = getattr(runnable, 'instructions', None)
    if existing is None or callable(existing):
        return
    if isinstance(existing, list):
        existing = '\n'.join(existing)
    runnable.instructions = append_principles(existing, principles)


def register_agents(app: Any, spec: Spec, principles_text: str = '') -> list[str]:
    """Register every agent in the spec as a reasoner, tagged for control-plane policies."""
    names: list[str] = []
    for agent in spec.ai.agents:
        _append_principles(agent, principles_text)
        tags = ['agent', 'platform'] if runnable_name(agent) in PLATFORM_AGENT_IDS else ['agent']
        names.append(register_runnable(app, agent, tags=tags))
    return names
