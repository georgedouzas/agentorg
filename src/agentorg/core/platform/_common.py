"""Shared helpers for assembling the six built-in platform agents."""

from collections.abc import Callable
from typing import Any

from agno.agent import Agent

DEFAULT_MODEL = 'google:gemini-2.0-flash'

OTHER_AGENTS_SCOPE = (
    ('Python code or agent specs', 'Backend Engineer'),
    ('UI configuration', 'Frontend Engineer'),
    ('Secret scanning / dep audit', 'Security Engineer'),
    ('Knowledge curation', 'Knowledge Engineer'),
    ('Running tests', 'QA Engineer'),
    ('Infra runtime', 'Platform Engineer'),
)


def compose_instructions(name: str, role: str, in_scope: list[str], workflow: list[str]) -> str:
    """Bake the agent's identity into a single instructions string."""
    parts = [f'You are the {name}.', '', '## Role', '', role, '']
    if in_scope:
        parts += ['## In scope', *(f'- {item}' for item in in_scope), '']
    parts += ['## Out of scope — decline and refer']
    parts += [f'- {topic} → **{referee}**' for topic, referee in OTHER_AGENTS_SCOPE]
    parts += ['', 'If asked anything outside your scope, decline firmly and point to the right person.', '']
    if workflow:
        parts += ['## Workflow', *(f'{i + 1}. {step}' for i, step in enumerate(workflow)), '']
    return '\n'.join(parts)


def platform_agent(
    agent_id: str,
    name: str,
    role: str,
    tools: list[Callable[..., Any]],
    in_scope: list[str],
    workflow: list[str],
) -> Agent:
    """Build a platform agent with the shared model + composed instructions."""
    return Agent(
        id=agent_id,
        name=name,
        role=role,
        model=DEFAULT_MODEL,
        tools=list(tools),
        instructions=compose_instructions(name, role, in_scope, workflow),
    )
