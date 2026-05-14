"""Tests for `agentorg.core.spec._org.Org`."""

import pytest
from pydantic import ValidationError

from agentorg.core.spec import Org

ORG = {
    'name': 'Acme Organization',
    'slug': 'acme-org',
    'package_name': 'acme_org',
    'description': 'Makes widgets.',
    'repository': 'https://github.com/acme/acme_org',
    'author_name': 'A. Coyote',
    'author_email': 'coyote@acme.com',
    'visibility': 'private',
}


def test_construct_with_all_fields() -> None:
    """All fields are required."""
    org = Org(**ORG)
    for key, value in ORG.items():
        assert getattr(org, key) == value


@pytest.mark.parametrize('missing', list(ORG))
def test_missing_field_raises(missing: str) -> None:
    """Omitting any one field raises a validation error."""
    fields = {k: v for k, v in ORG.items() if k != missing}
    with pytest.raises(ValidationError):
        Org(**fields)


def test_visibility_rejects_unknown_value() -> None:
    """Visibility is either public or private."""
    with pytest.raises(ValidationError):
        Org(**{**ORG, 'visibility': 'secret'})


def test_wrong_type() -> None:
    """All types are strings."""
    with pytest.raises(ValidationError):
        Org(**{k: (list(v) if k == 'visibility' else v) for k, v in ORG.items()})
