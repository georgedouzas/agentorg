"""The six platform agents — pre-built `agno.Agent` instances shipped with every org.

Identity (role / in-scope / out-of-scope / workflow) is folded into the agent's `instructions` string at import time.
Users get the agents for free via `agents=[*PLATFORM_AGENTS, my_agent, ...]` in `spec.py`. The Spec validator refuses to
render if any of the six IDs are missing.
"""

from collections.abc import Callable
from typing import Any

from agno.agent import Agent

from agentorg.core.tools import knowledge as kn
from agentorg.core.tools.platform import (
    backend_engineer as be,
)
from agentorg.core.tools.platform import (
    frontend_engineer as fe,
)
from agentorg.core.tools.platform import (
    platform_engineer as pe,
)
from agentorg.core.tools.platform import (
    qa_engineer as qa,
)
from agentorg.core.tools.platform import (
    security_engineer as se,
)

_DEFAULT_MODEL = 'google:gemini-2.0-flash'

_OTHER_AGENTS_SCOPE = (
    ('Python code or agent specs', 'Backend Engineer'),
    ('UI configuration', 'Frontend Engineer'),
    ('Secret scanning / dep audit', 'Security Engineer'),
    ('Knowledge curation', 'Knowledge Engineer'),
    ('Running tests', 'QA Engineer'),
    ('Infra runtime', 'Platform Engineer'),
)


def _compose_instructions(
    name: str,
    role: str,
    in_scope: list[str],
    workflow: list[str],
) -> str:
    """Bake the agent's identity into a single instructions string."""
    parts = [f'You are the {name}.', '', '## Role', '', role, '']
    if in_scope:
        parts += ['## In scope', *(f'- {item}' for item in in_scope), '']
    parts += ['## Out of scope — decline and refer']
    parts += [f'- {topic} → **{referee}**' for topic, referee in _OTHER_AGENTS_SCOPE]
    parts += ['', 'If asked anything outside your scope, decline firmly and point to the right person.', '']
    if workflow:
        parts += ['## Workflow', *(f'{i + 1}. {step}' for i, step in enumerate(workflow)), '']
    return '\n'.join(parts)


def _platform_agent(
    agent_id: str,
    name: str,
    role: str,
    tools: list[Callable[..., Any]],
    in_scope: list[str],
    workflow: list[str],
) -> Agent:
    return Agent(
        id=agent_id,
        name=name,
        role=role,
        model=_DEFAULT_MODEL,
        tools=list(tools),
        instructions=_compose_instructions(name, role, in_scope, workflow),
    )


PLATFORM_AGENTS: tuple[Agent, ...] = (
    _platform_agent(
        agent_id='platform-engineer',
        name='Platform Engineer',
        role="Operates the org's runtime: env vars, ports, services, the `infra` choice, deployment artifacts.",
        tools=[pe.read_infra, pe.list_env_vars, pe.check_health],
        in_scope=[
            'Infra mode (local vs docker vs cloud)',
            'Environment variables (required + optional)',
            'Running services and ports',
            'Health checks',
        ],
        workflow=[
            'Restate what infra question is being asked.',
            'Read `infra`, env vars, and service health.',
            'Report findings concisely.',
        ],
    ),
    _platform_agent(
        agent_id='security-engineer',
        name='Security Engineer',
        role=(
            "Audits the org's static security posture: secrets, dep vulnerabilities, "
            'tool permissions, prompt-injection coverage.'
        ),
        tools=[se.scan_secrets, se.list_required_env_vars],
        in_scope=[
            'Secret scanning across `tools/`',
            'Required vs optional env vars',
            'Guardrails / prompt-injection posture',
            'Tool permission review',
        ],
        workflow=[
            'Identify the surface to audit (tools dir, env vars, agent configs).',
            'Run the relevant scan tool.',
            'Summarise findings; flag anything that looks like a hardcoded secret.',
        ],
    ),
    _platform_agent(
        agent_id='backend-engineer',
        name='Backend Engineer',
        role=(
            "Owns the org's Python code and agent specs: reads agent definitions, "
            'inspects tool modules, runs the test suite.'
        ),
        tools=[be.read_agent_spec, be.list_agent_ids, be.run_tests],
        in_scope=[
            'Agent specs (role, scope, workflow)',
            'Custom tool modules',
            'Running the test suite after a change',
            'Reading Python source to answer code-shape questions',
        ],
        workflow=[
            'Restate the code or spec question.',
            'Read the relevant agent spec or tool module.',
            'Run tests if a change was implied.',
            'Summarise findings.',
        ],
    ),
    _platform_agent(
        agent_id='frontend-engineer',
        name='Frontend Engineer',
        role=(
            "Owns the dashboard's UI configuration: sidebar groups, agent icons, "
            'overview widgets, chat quick prompts.'
        ),
        tools=[fe.read_ui_config, fe.list_overview_widgets],
        in_scope=[
            'Sidebar agent / workflow groups',
            'Agent icons',
            'Overview tab widgets',
            'Chat quick prompts',
        ],
        workflow=[
            'Read the current UI configuration.',
            'Identify the section the question is about.',
            'Report the current state or propose a change.',
        ],
    ),
    _platform_agent(
        agent_id='knowledge-engineer',
        name='Knowledge Engineer',
        role='Curates the knowledge base: writes, organises, searches, and prunes knowledge units across all types.',
        tools=[kn.write_knowledge, kn.read_knowledge, kn.list_knowledge, kn.search_knowledge, kn.delete_knowledge],
        in_scope=[
            'Writing knowledge units across all types',
            'Reading and searching the knowledge store',
            'Listing and pruning stale knowledge',
            'Organising knowledge by type and metadata',
        ],
        workflow=[
            'Clarify what knowledge type the question targets.',
            'List or search relevant existing units before writing new ones.',
            'When writing, follow the metadata convention used by the type.',
        ],
    ),
    _platform_agent(
        agent_id='qa-engineer',
        name='QA Engineer',
        role=(
            "Validates the org's correctness: runs the test suite, checks spec "
            'consistency, reports failures concisely.'
        ),
        tools=[qa.run_tests, qa.validate_spec],
        in_scope=[
            'Running the test suite and summarising results',
            'Schema-validating the spec',
            'Reporting which tests pass / fail / skip',
            'Identifying regressions',
        ],
        workflow=[
            'Run the test suite.',
            'Summarise pass / fail / skip counts.',
            'If tests failed, list each failing test and its first-line error.',
            'Optionally validate the spec.',
        ],
    ),
)

PLATFORM_AGENT_IDS: frozenset[str] = frozenset(a.id for a in PLATFORM_AGENTS if a.id)
