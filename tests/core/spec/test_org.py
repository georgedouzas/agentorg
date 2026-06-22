"""Tests for org module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import Org


def test_construct_with_all_fields(org_dict_normal: dict[str, Any]) -> None:
    """All fields land on the model verbatim."""
    org = Org(**org_dict_normal)
    for key, value in org_dict_normal.items():
        assert getattr(org, key) == value


@pytest.mark.parametrize(
    'missing',
    [
        'name',
        'slug',
        'package_name',
        'description',
        'repository',
        'admin_name',
        'admin_email',
        'visibility',
        'budget',
    ],
)
def test_missing_field_raises(org_dict_minimal: dict[str, Any], missing: str) -> None:
    """Omitting any one field raises a validation error."""
    org_dict_minimal.pop(missing)
    with pytest.raises(ValidationError):
        Org(**org_dict_minimal)


def test_visibility_rejects_unknown_value(org_dict_minimal: dict[str, Any]) -> None:
    """Visibility is either public or private."""
    org_dict_minimal['visibility'] = 'secret'
    with pytest.raises(ValidationError):
        Org(**org_dict_minimal)


def test_budget_rejects_unknown_value(org_dict_minimal: dict[str, Any]) -> None:
    """Budget is one of low, medium, high."""
    org_dict_minimal['budget'] = 'enormous'
    with pytest.raises(ValidationError):
        Org(**org_dict_minimal)


@pytest.mark.parametrize(
    'field',
    [
        'name',
        'slug',
        'package_name',
        'description',
        'repository',
        'admin_name',
        'admin_email',
    ],
)
def test_wrong_type(org_dict_minimal: dict[str, Any], field: str) -> None:
    """String fields reject non-string input."""
    org_dict_minimal[field] = 123
    with pytest.raises(ValidationError):
        Org(**org_dict_minimal)
