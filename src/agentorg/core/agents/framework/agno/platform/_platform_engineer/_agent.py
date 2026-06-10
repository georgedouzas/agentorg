"""The Platform Engineer — operates the org's runtime."""

from agentorg.core.agents.tools import (
    get_org_parameters,
    get_setup_status,
    reset_org_parameters,
    set_org_parameter,
)

from .._make import platform_make_agent
from ._tools import check_health, list_env_vars, read_infra

agent = platform_make_agent(
    name='Platform Engineer',
    agent_id='platform-engineer',
    role=(
        "Operates the org's runtime: env vars, ports, services, infra mode, the org instance "
        'parameters that distinguish this instance from another, and setup status.'
    ),
    tools=[
        read_infra,
        list_env_vars,
        check_health,
        get_org_parameters,
        set_org_parameter,
        reset_org_parameters,
        get_setup_status,
    ],
    in_scope=[
        'Infra mode (local vs docker vs cloud)',
        'Environment variables (required + optional)',
        'Running services and ports',
        'Health checks',
        'Org instance parameters (read, set one, reset all)',
        'Setup checklist status',
    ],
    workflow=[
        'Restate what runtime, parameter, or setup question is being asked.',
        'Read `infra`, env vars, service health, org instance parameters, or setup status.',
        'For a parameter change request, call `set_org_parameter` once per parameter the user named.',
        'Report findings or the applied change concisely.',
    ],
)
