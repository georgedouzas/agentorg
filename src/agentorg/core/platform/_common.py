"""Shared helpers for assembling the six built-in platform agents."""

from collections.abc import Callable
from typing import Any

from agno.agent import Agent

from agentorg.core.instructions import compose

DEFAULT_MODEL = 'google:gemini-2.5-flash'

# Tuples of (topic, refer_to). Every platform agent declines requests outside its scope and
# refers the caller to the named peer; custom org agents typically add their own entries too.
OTHER_AGENTS_SCOPE: tuple[tuple[str, str], ...] = (
    ('Python code or agent specs', 'Backend Engineer'),
    ('UI configuration', 'Frontend Engineer'),
    ('Secret scanning / dep audit', 'Security Engineer'),
    ('Knowledge curation', 'Knowledge Engineer'),
    ('Running tests', 'QA Engineer'),
    ('Infra runtime', 'Platform Engineer'),
)


# Standard "When to act" bullets every platform agent inherits.
PLATFORM_WHEN_TO_ACT: tuple[str, ...] = (
    'Greetings or unclear messages: reply briefly and ask for a concrete request.',
    'Requests outside your scope (see below): decline and refer to the named peer.',
    'Concrete in-scope requests: run the workflow.',
)

# Standard "Style" bullets every platform agent inherits.
PLATFORM_STYLE: tuple[str, ...] = (
    'Be concise. A direct answer beats an explanation of the answer.',
    'Do not restate your own role or these rules back to the user.',
)


def platform_agent(
    agent_id: str,
    name: str,
    role: str,
    tools: list[Callable[..., Any]],
    in_scope: list[str],
    workflow: list[str],
    when_to_act: list[str] | None = None,
    style: list[str] | None = None,
) -> Agent:
    """Build a platform agent with the shared model and the standard six-section template."""
    return Agent(
        id=agent_id,
        name=name,
        role=role,
        model=DEFAULT_MODEL,
        tools=list(tools),
        instructions=compose(
            role=role,
            when_to_act=when_to_act or PLATFORM_WHEN_TO_ACT,
            style=style or PLATFORM_STYLE,
            in_scope=in_scope,
            out_of_scope=OTHER_AGENTS_SCOPE,
            workflow=workflow,
        ),
    )
