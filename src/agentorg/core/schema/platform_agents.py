"""The six required platform agents — default content of `Generated.agents`.

Identity (role / in_scope / out_of_scope / workflow / tools) is the agentorg contract. Users can add their own custom
agents alongside these but the Spec validator refuses to proceed if any of these six are removed.
"""

from agentorg.core.schema.models import Agent, ScopeRef
from agentorg.core.tools import knowledge as kn
from agentorg.core.tools.platform import backend_engineer as be
from agentorg.core.tools.platform import frontend_engineer as fe
from agentorg.core.tools.platform import platform_engineer as pe
from agentorg.core.tools.platform import qa_engineer as qa
from agentorg.core.tools.platform import security_engineer as se


def _other_platform_agents(self_id: str) -> list[ScopeRef]:
    """Boilerplate out-of-scope refs to every OTHER platform agent."""
    return [
        ScopeRef(topic='Python code or agent specs', refer_to='Backend Engineer'),
        ScopeRef(topic='UI configuration', refer_to='Frontend Engineer'),
        ScopeRef(topic='Secret scanning / dep audit', refer_to='Security Engineer'),
        ScopeRef(topic='Knowledge curation', refer_to='Knowledge Engineer'),
        ScopeRef(topic='Running tests', refer_to='QA Engineer'),
        ScopeRef(topic='Infra runtime', refer_to='Platform Engineer'),
    ]


PLATFORM_AGENTS: tuple[Agent, ...] = (
    Agent(
        id='platform-engineer',
        name='Platform Engineer',
        role="Operates the org's runtime: env vars, ports, services, the `infra` choice, deployment artifacts.",
        tools=[pe.read_infra, pe.list_env_vars, pe.check_health],
        in_scope=[
            'Infra mode (local vs docker vs cloud)',
            'Environment variables (required + optional)',
            'Running services and ports',
            'Health checks',
        ],
        out_of_scope=_other_platform_agents('platform-engineer'),
        workflow=[
            'Restate what infra question is being asked.',
            'Read `infra`, env vars, and service health.',
            'Report findings concisely.',
        ],
    ),
    Agent(
        id='security-engineer',
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
        out_of_scope=_other_platform_agents('security-engineer'),
        workflow=[
            'Identify the surface to audit (tools dir, env vars, agent configs).',
            'Run the relevant scan tool.',
            'Summarise findings; flag anything that looks like a hardcoded secret.',
        ],
    ),
    Agent(
        id='backend-engineer',
        name='Backend Engineer',
        role=(
            "Owns the org's Python code and agent specs: reads agent definitions, "
            'inspects tool modules, runs the test suite.'
        ),
        tools=[be.read_agent_spec, be.list_agent_ids, be.run_tests],
        learning=True,
        in_scope=[
            'Agent specs (role, scope, workflow)',
            'Custom tool modules',
            'Running the test suite after a change',
            'Reading Python source to answer code-shape questions',
        ],
        out_of_scope=_other_platform_agents('backend-engineer'),
        workflow=[
            'Restate the code or spec question.',
            'Read the relevant agent spec or tool module.',
            'Run tests if a change was implied.',
            'Summarise findings.',
        ],
    ),
    Agent(
        id='frontend-engineer',
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
        out_of_scope=_other_platform_agents('frontend-engineer'),
        workflow=[
            'Read the current UI configuration.',
            'Identify the section the question is about.',
            'Report the current state or propose a change.',
        ],
    ),
    Agent(
        id='knowledge-engineer',
        name='Knowledge Engineer',
        role='Curates the knowledge base: writes, organises, searches, and prunes knowledge units across all types.',
        tools=[kn.write_knowledge, kn.read_knowledge, kn.list_knowledge, kn.search_knowledge, kn.delete_knowledge],
        learning=True,
        in_scope=[
            'Writing knowledge units across all types',
            'Reading and searching the knowledge store',
            'Listing and pruning stale knowledge',
            'Organising knowledge by type and metadata',
        ],
        out_of_scope=_other_platform_agents('knowledge-engineer'),
        workflow=[
            'Clarify what knowledge type the question targets.',
            'List or search relevant existing units before writing new ones.',
            'When writing, follow the metadata convention used by the type.',
        ],
    ),
    Agent(
        id='qa-engineer',
        name='QA Engineer',
        role=(
            "Validates the org's correctness: runs the test suite, checks spec "
            'consistency, reports failures concisely.'
        ),
        tools=[qa.run_tests, qa.validate_spec],
        learning=True,
        in_scope=[
            'Running the test suite and summarising results',
            'Schema-validating the spec',
            'Reporting which tests pass / fail / skip',
            'Identifying regressions',
        ],
        out_of_scope=_other_platform_agents('qa-engineer'),
        workflow=[
            'Run the test suite.',
            'Summarise pass / fail / skip counts.',
            'If tests failed, list each failing test and its first-line error.',
            'Optionally validate the spec.',
        ],
    ),
)

PLATFORM_AGENT_IDS: frozenset[str] = frozenset(a.id for a in PLATFORM_AGENTS)
