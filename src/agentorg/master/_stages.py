"""Interview stage machine."""

from typing import get_args

from ._seed import PLACEHOLDER_VALUES
from ._state import Stage, State

STAGES: tuple[Stage, ...] = get_args(Stage)

STAGE_LABELS: dict[Stage, str] = {
    'discover': 'Discover',
    'configure': 'Configure',
    'build': 'Build',
    'refine': 'Refine',
    'handoff': 'Handoff',
}


def _is_placeholder(value: object) -> bool:
    """True when `value` is a placeholder string from the seed spec."""
    return isinstance(value, str) and value in PLACEHOLDER_VALUES


def _real(value: object) -> bool:
    """True when `value` is a real string (non-empty, not a placeholder)."""
    return isinstance(value, str) and bool(value) and value not in PLACEHOLDER_VALUES


STAGE2_DESCRIPTION_MIN_LEN = 200


def _discover_blockers(state: State) -> list[str]:
    """Stage 1 (low threshold): a recorded discovery summary is the only requirement.

    Stage 1's job is to understand the SCOPE of the work, not to settle on a name or
    admin info. Identity fields (name / slug / admin / description / infra) all live in
    Stage 2 - the agent's prompt enforces this, and the threshold below mirrors it.
    """
    blockers: list[str] = []
    if state.discovery is None:
        blockers.append(
            'Record your understanding of the business via `record_discovery_summary` '
            "(six structured fields, user-confirmed).",
        )
    return blockers


def _configure_blockers(state: State) -> list[str]:
    """Stage 2 (very high threshold): every required identity + description + infra field.

    Cloud secrets needed by the chosen infra are checked too - we cannot deploy without
    them in Stage 3.
    """
    blockers: list[str] = []
    org = state.spec.org
    if not _real(org.name):
        blockers.append('Pick a name for the group.')
    if not _real(org.slug):
        blockers.append('Pick a URL-safe slug.')
    if not _real(org.package_name):
        blockers.append('Pick a Python package name.')
    if not _real(org.admin_name):
        blockers.append('Admin name (who maintains it).')
    if not _real(org.admin_email):
        blockers.append('Admin email.')
    desc = (org.description or '').strip()
    if (not _real(org.description)) or len(desc) < STAGE2_DESCRIPTION_MIN_LEN:
        blockers.append(
            f'A substantive description (>= {STAGE2_DESCRIPTION_MIN_LEN} chars) covering mission + audience.',
        )
    # Cloud targets need their access tokens declared before we can advance.
    infra = state.spec.runtime.infra
    if infra.api == 'railway' and not _has_env_var(state, 'RAILWAY_TOKEN'):
        blockers.append('Railway deployment needs RAILWAY_TOKEN in env vars.')
    if infra.frontend == 'vercel' and not _has_env_var(state, 'VERCEL_TOKEN'):
        blockers.append('Vercel deployment needs VERCEL_TOKEN in env vars.')
    if state.spec.operations.budget.monthly_usd is None:
        blockers.append('Set a monthly budget in USD with set_budget.')
    return blockers


def _build_blockers(state: State) -> list[str]:
    """Stage 3 (Build): at least one agent in a complete, valid unit tree before we advance to Refine."""
    blockers: list[str] = []
    if not state.spec.ai.agents:
        blockers.append(
            'Design at least one agent, sandbox-test it, commit it, and confirm it works in the live preview.',
        )
    if state.structure_error is not None:
        blockers.append(f'Complete the org structure: {state.structure_error}')
    return blockers


def _refine_blockers(state: State) -> list[str]:
    """Stage 4 (Refine): knowledge / parameters / principles touched or skipped.

    Explicit skip is a valid answer - this stage has no hard blockers; the master agent
    confirms with the user before advancing.
    """
    return []


def _handoff_blockers(state: State) -> list[str]:
    """Stage 5 (Handoff) is terminal - no advance from here."""
    return ['Handoff is the final stage.']


def _has_env_var(state: State, name: str) -> bool:
    """True when `name` appears in either required or optional env vars."""
    env = state.spec.runtime.env_vars
    return any(v.name == name for v in (*env.required, *env.optional))


def current_stage(state: State) -> Stage:
    """Return the stage the interview is currently in."""
    return state.stage


def next_blockers(state: State) -> list[str]:
    """Return the list of reasons Next is disabled for the current stage."""
    fns = {
        'discover': _discover_blockers,
        'configure': _configure_blockers,
        'build': _build_blockers,
        'refine': _refine_blockers,
        'handoff': _handoff_blockers,
    }
    return fns[state.stage](state)


def next_enabled(state: State) -> bool:
    """True when the current stage's threshold predicate is satisfied."""
    return not next_blockers(state)


def advance(state: State) -> tuple[bool, Stage, list[str]]:
    """Try to move `state` to the next stage.

    Returns `(advanced, new_stage, blockers)`. When `advanced` is False, the stage is unchanged and `blockers` lists
    why.
    """
    blockers = next_blockers(state)
    if blockers:
        return (False, state.stage, blockers)
    idx = STAGES.index(state.stage)
    if idx + 1 >= len(STAGES):
        return (False, state.stage, ['Already on the final stage.'])
    state.stage = STAGES[idx + 1]
    return (True, state.stage, [])


def stage_summary(state: State) -> dict[str, object]:
    """Compact payload used by `/api/spec` to drive the Next button + stage bar."""
    return {
        'stage': state.stage,
        'stage_label': STAGE_LABELS[state.stage],
        'stages': list(STAGES),
        'next_enabled': next_enabled(state),
        'next_blockers': next_blockers(state),
    }
