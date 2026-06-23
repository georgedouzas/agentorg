"""Tests for the interview-time spec models."""

import pytest
from pydantic import ValidationError

from agentorg.master import StepSpec


def test_step_spec_construction():
    """Name + agent_id are sufficient; requires_output_review defaults to False."""
    step = StepSpec(name='Gather', agent_id='researcher')
    assert step.name == 'Gather'
    assert step.agent_id == 'researcher'
    assert step.requires_output_review is False


def test_step_spec_accepts_hitl_flag():
    """requires_output_review can be flipped on."""
    step = StepSpec(name='Approve', agent_id='reviewer', requires_output_review=True)
    assert step.requires_output_review is True


@pytest.mark.parametrize('missing', ['name', 'agent_id'])
def test_step_spec_missing_field_raises(missing: str) -> None:
    """Name and agent_id are both required."""
    kwargs = {'name': 'X', 'agent_id': 'y'}
    del kwargs[missing]
    with pytest.raises(ValidationError):
        StepSpec(**kwargs)
