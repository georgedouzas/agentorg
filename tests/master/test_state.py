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
        state.spec.org.visibility = 'invalid'  # type: ignore[assignment]
