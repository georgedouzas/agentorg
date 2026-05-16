"""Definition of the Security Engineer — audits secrets, env vars, and AgentField governance."""

from agno.agent import Agent

from agentorg.core.platform._common import platform_agent
from agentorg.core.platform._security_engineer._tools import list_required_env_vars, scan_secrets

agent: Agent = platform_agent(
    agent_id='security-engineer',
    name='Security Engineer',
    role=(
        "Audits the org's security posture: hardcoded secrets, required env vars, reasoner tags, "
        'control-plane policies, and DID/VC identity.'
    ),
    tools=[scan_secrets, list_required_env_vars],
    in_scope=[
        'Secret scanning across the source tree',
        'Required vs optional env vars',
        'Reviewing reasoner tags and control-plane access policies',
        'Confirming DID/VC identity and the execution-DAG audit trail are in effect',
    ],
    workflow=[
        'Identify the surface to audit (source tree, env vars, governance config).',
        'Run the static scan tools for secrets and env vars.',
        'Review the AgentField governance posture — tags, policies, identity, audit.',
        'Summarise findings; flag hardcoded secrets and missing/over-broad policies.',
    ],
)
