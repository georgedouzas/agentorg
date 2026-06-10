"""Tests for the parameters module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import Parameter

PARAMETER: dict[str, Any] = {'name': 'min_sources', 'type': 'int', 'default': 3, 'label': 'Min Sources', 'format': None}


def test_parameter_fields() -> None:
    """`Parameter` carries name, type, default, label, and an optional format."""
    param = Parameter(**PARAMETER)
    assert param.name == 'min_sources'
    assert param.type == 'int'
    assert param.default == PARAMETER['default']
    assert param.format is None


@pytest.mark.parametrize('missing', list(PARAMETER))
def test_parameter_missing_field_raises(missing: str) -> None:
    """Every `Parameter` field is required (`format` may be None but must be passed)."""
    with pytest.raises(ValidationError):
        Parameter(**{k: v for k, v in PARAMETER.items() if k != missing})


def test_parameter_rejects_unknown_type() -> None:
    """`type` is a closed `Literal`."""
    with pytest.raises(ValidationError):
        Parameter(**{**PARAMETER, 'type': 'datetime'})
