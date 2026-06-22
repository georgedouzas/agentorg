"""Tests for ai module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import AI


def test_construction(ai_dict_normal: dict[str, Any]) -> None:
    """Holds the user's agents, teams, and workflows."""
    ai = AI.model_validate(ai_dict_normal)
    assert ai.agents[0].id == 'researcher'
    assert ai.teams[0].id == 'research-team'
    assert ai.workflows[0].id == 'pipeline'


def test_empty_lists_validate(ai_dict_minimal: dict[str, Any]) -> None:
    """All three lists accept being empty."""
    ai = AI.model_validate(ai_dict_minimal)
    assert ai.agents == [] == ai.teams == ai.workflows


def test_framework_defaults_to_agno(ai_dict_minimal: dict[str, Any]) -> None:
    """Framework defaults to agno."""
    del ai_dict_minimal['framework']
    assert AI.model_validate(ai_dict_minimal).framework == 'agno'


def test_framework_rejects_unknown_value(ai_dict_minimal: dict[str, Any]) -> None:
    """Framework is a closed Literal."""
    with pytest.raises(ValidationError):
        AI.model_validate({**ai_dict_minimal, 'framework': 'claude_code'})


@pytest.mark.parametrize('missing', ['agents', 'teams', 'workflows'])
def test_all_fields_required(ai_dict_minimal: dict[str, Any], missing: str) -> None:
    """The agents, teams, and workflows keys are all required."""
    del ai_dict_minimal[missing]
    with pytest.raises(ValidationError):
        AI.model_validate(ai_dict_minimal)
