"""Tests for knowledge module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import (
    Knowledge,
    KnowledgeType,
    KnowledgeTypeMetadataField,
    PrincipleParameter,
    Principles,
    PrincipleSection,
)

PARAMETER: dict[str, Any] = {'name': 'min_sources', 'type': 'int', 'default': 3, 'label': 'Min Sources', 'format': None}
SECTION: dict[str, Any] = {'id': 'mission', 'title': 'Mission', 'body': '- Do good work.'}
METADATA_FIELD: dict[str, Any] = {'name': 'author', 'type': 'string'}
KNOWLEDGE_TYPE: dict[str, Any] = {'id': 'report', 'label': 'Reports', 'metadata_fields': [METADATA_FIELD]}
PRINCIPLES: dict[str, Any] = {'parameters': [PARAMETER], 'sections': [SECTION]}
KNOWLEDGE: dict[str, Any] = {'principles': PRINCIPLES, 'types': [KNOWLEDGE_TYPE]}


def test_principle_parameter_fields() -> None:
    """`PrincipleParameter` carries name, type, default, label, and an optional format."""
    param = PrincipleParameter(**PARAMETER)
    assert param.name == 'min_sources'
    assert param.type == 'int'
    assert param.default == PARAMETER['default']
    assert param.format is None


@pytest.mark.parametrize('missing', list(PARAMETER))
def test_principle_parameter_missing_field_raises(missing: str) -> None:
    """Every `PrincipleParameter` field is required (`format` may be None but must be passed)."""
    with pytest.raises(ValidationError):
        PrincipleParameter(**{k: v for k, v in PARAMETER.items() if k != missing})


def test_principle_parameter_rejects_unknown_type() -> None:
    """`type` is a closed `Literal`."""
    with pytest.raises(ValidationError):
        PrincipleParameter(**{**PARAMETER, 'type': 'datetime'})


def test_principle_section_fields() -> None:
    """`PrincipleSection` is id plus title plus markdown body."""
    section = PrincipleSection(**SECTION)
    assert section.id == 'mission'
    assert section.body.startswith('- Do good work.')


def test_principles_holds_parameters_and_sections() -> None:
    """`Principles` coerces dict parameters and sections into their models."""
    principles = Principles(**PRINCIPLES)
    assert principles.parameters[0].name == 'min_sources'
    assert principles.sections[0].id == 'mission'


@pytest.mark.parametrize('missing', ['parameters', 'sections'])
def test_principles_fields_required(missing: str) -> None:
    """`parameters` and `sections` are required keys (empty lists allowed, omission is not)."""
    with pytest.raises(ValidationError):
        Principles(**{k: v for k, v in PRINCIPLES.items() if k != missing})


def test_knowledge_type_fields() -> None:
    """`KnowledgeType` is id plus label plus metadata field schema."""
    knowledge_type = KnowledgeType(**KNOWLEDGE_TYPE)
    assert knowledge_type.id == 'report'
    assert knowledge_type.metadata_fields[0].name == 'author'


def test_knowledge_type_metadata_field_rejects_unknown_type() -> None:
    """A metadata field's `type` is a closed `Literal`."""
    with pytest.raises(ValidationError):
        KnowledgeTypeMetadataField(name='count', type='list')  # type: ignore[arg-type]


@pytest.mark.parametrize('missing', list(KNOWLEDGE_TYPE))
def test_knowledge_type_missing_field_raises(missing: str) -> None:
    """Every `KnowledgeType` field is required."""
    with pytest.raises(ValidationError):
        KnowledgeType(**{k: v for k, v in KNOWLEDGE_TYPE.items() if k != missing})


def test_knowledge_construction() -> None:
    """`Knowledge` wraps the principles and the knowledge-type catalogue, coercing dicts."""
    knowledge = Knowledge.model_validate(KNOWLEDGE)
    assert knowledge.principles.parameters[0].name == 'min_sources'
    assert knowledge.types[0].id == 'report'


@pytest.mark.parametrize('missing', ['principles', 'types'])
def test_knowledge_fields_required(missing: str) -> None:
    """`principles` and `types` are both required on `Knowledge`."""
    with pytest.raises(ValidationError):
        Knowledge.model_validate({k: v for k, v in KNOWLEDGE.items() if k != missing})
