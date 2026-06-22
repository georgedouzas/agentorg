"""Shared fixtures - reset the master agent's state before each test so order doesn't matter."""

import pytest

from agentorg.master import Discovery, get_state, reset_state


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Reset the singleton interview state at the start of every test."""
    reset_state()


def advance_to_configure_stage() -> None:
    """Bypass Stage 1's identity gate for tests by jumping the cursor to 'configure'.

    Most pre-existing `set_org_identity` tests are unit tests of the underlying tool;
    they predate the staged interview machinery and treat the tool as stage-agnostic.
    Calling this in the test body lets them keep doing so without dragging the rest of
    the conftest through a fake interview.
    """
    get_state().stage = 'configure'


def seed_discovery() -> None:
    """Pre-fill `state.discovery` so tests can call principle / budget tools directly.

    Bypasses the full Stage-1 Phase-A interview gate. Use this in tests that need to drive
    `add_or_update_principle_section` or `set_org_identity(budget=...)` without conducting
    a fake interview first. Field values are deliberately long enough to pass the per-
    field minimum-length validation enforced by `record_discovery_summary`.
    """
    get_state().discovery = Discovery(
        what_the_group_does=(
            'Test fixture: this group designs and operates X end-to-end, covering both '
            'the upstream research and downstream delivery to internal stakeholders.'
        ),
        who_serves=(
            'Test fixture: internal product teams and external researchers who need '
            'curated digests of recent work on a target topic.'
        ),
        concrete_tasks_owned=(
            'Test fixture: literature review; source curation; weekly brief drafting; '
            'review-with-stakeholder; publish + archive in knowledge store.'
        ),
        typical_flow=(
            'Test fixture: topic arrives -> agents search literature -> shortlist sources '
            "-> distil findings -> draft brief -> review with the requester -> publish."
        ),
        business_context=(
            'Test fixture: internal research-ops team inside a model-evaluation org, '
            'serving 4 product squads on a weekly cadence.'
        ),
        current_pain_or_alternative=(
            'Test fixture: today a single PhD spends a week per brief; the group lets us '
            'survey 5x more topics per quarter without hiring more researchers.'
        ),
    )
