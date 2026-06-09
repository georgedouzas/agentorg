"""The Platform Engineer — operates the org's runtime."""

from ....tools import get_setup_status, get_state, reset_state, update_state
from .._make import platform_make_agent
from ._tools import check_health, list_env_vars, read_infra

agent = platform_make_agent(
    name='Platform Engineer',
    agent_id='platform-engineer',
    role="Operates the org's runtime: env vars, ports, services, infra mode, state, and setup status.",
    tools=[
        read_infra,
        list_env_vars,
        check_health,
        get_state,
        update_state,
        reset_state,
        get_setup_status,
    ],
    in_scope=[
        'Infra mode (local vs docker vs cloud)',
        'Environment variables (required + optional)',
        'Running services and ports',
        'Health checks',
        'Per-user org state (read, update, reset)',
        'Setup checklist status',
    ],
    workflow=[
        'Restate what infra / runtime / state question is being asked.',
        'Read `infra`, env vars, service health, state, or setup status.',
        'Report findings concisely.',
    ],
)
