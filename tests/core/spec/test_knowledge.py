"""Tests for knowledge module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import (
    Knowledge,
    KnowledgeType,
    KnowledgeTypeMetadataField,
    Principles,
    PrincipleSection,
)

SECTION: dict[str, Any] = {'id': 'mission', 'title': 'Mission', 'body': '- Do good work.'}
METADATA_FIELD: dict[str, Any] = {'name': 'author', 'type': 'string'}
KNOWLEDGE_TYPE: dict[str, Any] = {'id': 'report', 'label': 'Reports', 'metadata_fields': [METADATA_FIELD]}
PRINCIPLES: dict[str, Any] = {'sections': [SECTION]}
KNOWLEDGE: dict[str, Any] = {'principles': PRINCIPLES, 'types': [KNOWLEDGE_TYPE]}


def test_principle_section_fields() -> None:
    """`PrincipleSection` is id plus title plus markdown body."""
    section = PrincipleSection(**SECTION)
    assert section.id == 'mission'
    assert section.body.startswith('- Do good work.')


def test_principles_holds_sections() -> None:
    """`Principles` coerces dict sections into their models."""
    principles = Principles(**PRINCIPLES)
    assert principles.sections[0].id == 'mission'


def test_principles_sections_required() -> None:
    """`sections` is a required key on `Principles` (empty list allowed, omission is not)."""
    with pytest.raises(ValidationError):
        Principles()  # type: ignore[call-arg]


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
    assert knowledge.principles.sections[0].id == 'mission'
    assert knowledge.types[0].id == 'report'


@pytest.mark.parametrize('missing', ['principles', 'types'])
def test_knowledge_fields_required(missing: str) -> None:
    """`principles` and `types` are both required on `Knowledge`."""
    with pytest.raises(ValidationError):
        Knowledge.model_validate({k: v for k, v in KNOWLEDGE.items() if k != missing})
