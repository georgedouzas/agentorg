"""Tests for the base module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import Spec


def test_spec_round_trips_minimal(spec_dict_minimal: dict[str, Any]) -> None:
    """A Spec assembled from minimal dicts round-trips."""
    spec = Spec.model_validate(spec_dict_minimal)
    assert spec.org.slug == 'acme'
    assert spec.runtime.infra.packaging == 'none'
    assert spec.ai.framework == 'agno'
    assert spec.parameters == []
    assert spec.knowledge.principles.sections == []
    assert spec.ui.app.name == 'Acme'


def test_spec_round_trips_normal(spec_dict_normal: dict[str, Any]) -> None:
    """A Spec assembled from populated dicts round-trips."""
    spec = Spec.model_validate(spec_dict_normal)
    assert spec.org.slug == 'acme-org'
    assert spec.runtime.infra.packaging == 'docker'
    assert spec.parameters[0].name == 'min_sources'
    assert spec.knowledge.principles.sections[0].id == 'mission'
    assert spec.ui.featured_agents == ['analyst']


@pytest.mark.parametrize('missing', ['org', 'runtime', 'ai', 'parameters', 'knowledge', 'ui'])
def test_top_level_fields_are_all_required(spec_dict_minimal: dict[str, Any], missing: str) -> None:
    """Every top-level field is required."""
    del spec_dict_minimal[missing]
    with pytest.raises(ValidationError):
        Spec.model_validate(spec_dict_minimal)
