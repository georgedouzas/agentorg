"""Tests for the stage state machine."""

import pytest

from agentorg.master import (
    STAGE_LABELS,
    STAGES,
    add_or_update_agent,
    add_or_update_env_var,
    advance,
    current_stage,
    get_state,
    next_blockers,
    next_enabled,
    reset_state,
    set_org_identity,
    stage_summary,
)

from .conftest import seed_discovery


def _fill_stage1() -> None:
    """Satisfy the Stage 1 (discover) threshold by seeding a recorded discovery."""
    seed_discovery()


_LONG_DESC = (
    'Acme Real Estate is a downtown agency helping first-time buyers find condos and '
    'townhouses, with a focus on neighbourhood walkability and proximity to transit. '
    'We compete on local knowledge and a hand-held buying experience.'
)


def _fill_stage2() -> None:
    """Satisfy the Stage 2 (configure) threshold by filling identity + description."""
    _fill_stage1()
    get_state().stage = 'configure'  # advance() will normally do this; tests skip ahead
    set_org_identity(
        name='Acme Real Estate',
        slug='acme-real-estate',
        package_name='acme_real_estate',
        description=_LONG_DESC,
        admin_name='Maintainer',
        admin_email='maintainer@example.com',
    )
    get_state().stage = 'discover'  # reset cursor; the test will call advance() to move it


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_state()


def test_state_starts_in_discover_stage():
    """Fresh state begins on Stage 1."""
    assert current_stage(get_state()) == 'discover'


def test_seed_has_blocker_demanding_record_discovery_summary():
    """The seed Stage-1 blocker tells the agent to call record_discovery_summary."""
    blockers = next_blockers(get_state())
    assert any('record_discovery_summary' in b for b in blockers)


def test_stage1_threshold_satisfied_by_recorded_discovery():
    """Recording the discovery summary satisfies Stage 1 - no name/description needed yet."""
    _fill_stage1()
    assert next_enabled(get_state()) is True
    assert next_blockers(get_state()) == []


def test_advance_from_discover_to_configure():
    """Calling advance() moves from discover to configure once the threshold is met."""
    _fill_stage1()
    ok, new_stage, blockers = advance(get_state())
    assert ok is True
    assert new_stage == 'configure'
    assert blockers == []
    assert current_stage(get_state()) == 'configure'


def test_advance_refuses_when_stage1_threshold_unmet():
    """Premature advance returns blockers and leaves the cursor unchanged."""
    ok, new_stage, blockers = advance(get_state())
    assert ok is False
    assert new_stage == 'discover'
    assert blockers


def test_stage2_has_high_threshold_requiring_admin_package_and_description():
    """On Stage 2 the threshold lists name/slug/package/admin/email AND a substantive description."""
    _fill_stage1()
    advance(get_state())  # -> configure
    blockers = next_blockers(get_state())
    assert any('slug' in b.lower() for b in blockers)
    assert any('admin' in b.lower() for b in blockers)
    assert any('description' in b.lower() for b in blockers)


def test_stage2_threshold_satisfied_by_full_identity_and_long_description():
    """Filling slug/package/admin/email plus a 200+-char description satisfies Stage 2."""
    _fill_stage2()
    advance(get_state())  # -> configure
    assert next_enabled(get_state()) is True


def test_stage2_threshold_requires_railway_token_when_railway_chosen():
    """Picking Railway as the API target adds RAILWAY_TOKEN as a blocker."""
    _fill_stage2()
    advance(get_state())  # -> configure
    state = get_state()
    state.spec.runtime.infra = state.spec.runtime.infra.model_copy(
        update={'api': 'railway', 'packaging': 'docker'},
    )
    blockers = next_blockers(state)
    assert any('RAILWAY_TOKEN' in b for b in blockers)

    # Once the token is declared, the blocker clears.
    add_or_update_env_var(
        name='RAILWAY_TOKEN',
        description='Railway API token.',
        required_label='Prod',
        required=True,
    )
    assert next_enabled(state) is True


def test_advance_through_all_five_stages():
    """Once thresholds are met (build needs at least one agent), advance walks 1 -> 5."""
    _fill_stage2()
    advance(get_state())  # discover -> configure
    advance(get_state())  # configure -> build
    assert current_stage(get_state()) == 'build'
    add_or_update_agent(
        agent_id='broker',
        name='Broker',
        role='Match buyers with listings.',
        in_scope=['First-time buyer questions.'],
        workflow=['Restate request.', 'Pull listings.'],
        tools=['read_knowledge'],
    )
    advance(get_state())  # build -> refine
    assert current_stage(get_state()) == 'refine'
    advance(get_state())  # refine -> handoff
    assert current_stage(get_state()) == 'handoff'


def test_advance_refuses_past_handoff():
    """Handoff is terminal - advance returns False with a clear message."""
    state = get_state()
    state.stage = 'handoff'
    ok, _, blockers = advance(state)
    assert ok is False
    assert blockers
    assert state.stage == 'handoff'


def test_stage_summary_shape():
    """`stage_summary` carries the keys the UI relies on."""
    summary = stage_summary(get_state())
    assert summary['stage'] == 'discover'
    assert summary['stage_label'] == STAGE_LABELS['discover']
    assert summary['stages'] == list(STAGES)
    assert isinstance(summary['next_enabled'], bool)
    assert isinstance(summary['next_blockers'], list)
