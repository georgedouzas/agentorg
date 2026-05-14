"""Agent factory — returns the agno agents declared in `spec.py`.

Charter integration: each agent's `instructions` string is prefixed with the rendered charter (if any) so the agent
sees the committee rules at every turn. Tools, models, and knowledge come from the user's spec — agentorg does not
re-wire them.
"""

from agno.agent import Agent

from agentorg.core.spec import Spec


def _prepend_charter(agent: Agent, charter_text: str) -> Agent:
    if not charter_text:
        return agent
    existing = agent.instructions or ''
    if isinstance(existing, list):
        existing = '\n'.join(existing)
    elif callable(existing):
        return agent  # caller-supplied callable — leave it alone
    agent.instructions = f'## Committee Rules\n\n{charter_text}\n\n{existing}'
    return agent


def build_agents(spec: Spec, charter_text: str = '') -> dict[str, Agent]:
    """Return ``{agent_id: agno.Agent}`` for every agent declared in the spec."""
    return {a.id: _prepend_charter(a, charter_text) for a in spec.agents if a.id}
