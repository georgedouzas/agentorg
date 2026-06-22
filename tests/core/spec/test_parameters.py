"""Tests for the parameters module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import Parameter


def test_parameter_fields(parameters_list_normal: list[dict[str, Any]]) -> None:
    """Parameter carries name, type, default, label, and an optional format."""
    param = Parameter(**parameters_list_normal[0])
    assert param.name == 'min_sources'
    assert param.type == 'int'
    assert param.default == 3
    assert param.format is None


@pytest.mark.parametrize('missing', ['name', 'type', 'default', 'label', 'format'])
def test_parameter_missing_field_raises(parameters_list_normal: list[dict[str, Any]], missing: str) -> None:
    """Every Parameter field is required."""
    param = dict(parameters_list_normal[0])
    del param[missing]
    with pytest.raises(ValidationError):
        Parameter(**param)


def test_parameter_rejects_unknown_type(parameters_list_normal: list[dict[str, Any]]) -> None:
    """The type field is a closed Literal."""
    with pytest.raises(ValidationError):
        Parameter(**{**parameters_list_normal[0], 'type': 'datetime'})
