"""Definition of the Platform Engineer — operates the org's runtime."""

from agno.agent import Agent

from agentorg.core.platform._common import platform_agent
from agentorg.core.platform._platform_engineer._tools import check_health, list_env_vars, read_infra

agent: Agent = platform_agent(
    agent_id='platform-engineer',
    name='Platform Engineer',
    role="Operates the org's runtime: env vars, ports, services, the `infra` choice, deployment artifacts.",
    tools=[read_infra, list_env_vars, check_health],
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
)
