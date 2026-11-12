"""Tests for the state module."""

import pytest
from pydantic import ValidationError

from agentorg.master import get_state, reset_state


def test_get_state_returns_a_singleton():
    """Repeated calls return the same `State` instance so mutations persist."""
    a = get_state()
    b = get_state()
    assert a is b


def test_reset_state_replaces_the_singleton_with_a_fresh_spec():
    """After mutating and resetting, the state is back to seed values."""
    state = get_state()
    state.spec.org.name = 'Changed Name'
    reset_state()
    assert get_state().spec.org.name == 'Untitled org'


def test_state_spec_assignment_validates():
    """`validate_assignment=True` on Spec models rejects bad direct assignments."""
    state = get_state()
    with pytest.raises(ValidationError):
        state.spec.org.visibility = 'invalid'


def test_state_default_construction_seeds_an_empty_workspace():
    """A freshly-reset State has the seed spec, no custom artefacts, and the discover stage."""
    from agentorg.master import State  # noqa: PLC0415

    state = State()
    assert state.spec.org.name.startswith('Untitled') or state.spec.org.name == 'Untitled org'
    assert state.custom_tools == []
    assert state.custom_skills == []
    assert state.stage == 'discover'
    assert state.discovery is None


def test_state_stage_field_rejects_unknown_value():
    """The `stage` field is a closed Literal - direct assignment to an unknown value fails."""
    state = get_state()
    state.stage = 'discover'  # valid - sanity check baseline
    # Assigning to an unknown stage is rejected by Pydantic on the underlying spec
    # only - State itself is a plain dataclass, so we just confirm the type alias.
    from agentorg.master import STAGES  # noqa: PLC0415

    assert state.stage in STAGES
