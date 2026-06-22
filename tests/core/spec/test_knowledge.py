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


def test_principle_section_fields(knowledge_dict_normal: dict[str, Any]) -> None:
    """PrincipleSection is id + title + markdown body."""
    section = PrincipleSection(**knowledge_dict_normal['principles']['sections'][0])
    assert section.id == 'mission'
    assert section.body.startswith('- Do good work.')


def test_principles_holds_sections(knowledge_dict_normal: dict[str, Any]) -> None:
    """Principles coerces dict sections into models."""
    principles = Principles.model_validate(knowledge_dict_normal['principles'])
    assert principles.sections[0].id == 'mission'


def test_principles_sections_required() -> None:
    """The sections field is required."""
    with pytest.raises(ValidationError):
        Principles()  # type: ignore[call-arg]


def test_knowledge_type_fields(knowledge_dict_normal: dict[str, Any]) -> None:
    """KnowledgeType is id + label + metadata field schema."""
    knowledge_type = KnowledgeType(**knowledge_dict_normal['types'][0])
    assert knowledge_type.id == 'report'
    assert knowledge_type.metadata_fields[0].name == 'author'


def test_knowledge_type_metadata_field_rejects_unknown_type() -> None:
    """A metadata field's type is a closed Literal."""
    with pytest.raises(ValidationError):
        KnowledgeTypeMetadataField(name='count', type='list')  # type: ignore[arg-type]


@pytest.mark.parametrize('missing', ['id', 'label', 'metadata_fields'])
def test_knowledge_type_missing_field_raises(knowledge_dict_normal: dict[str, Any], missing: str) -> None:
    """Every KnowledgeType field is required."""
    kt = dict(knowledge_dict_normal['types'][0])
    del kt[missing]
    with pytest.raises(ValidationError):
        KnowledgeType(**kt)


def test_knowledge_empty_principles_and_types(knowledge_dict_minimal: dict[str, Any]) -> None:
    """Empty principles + types is a valid Knowledge."""
    knowledge = Knowledge.model_validate(knowledge_dict_minimal)
    assert knowledge.principles.sections == []
    assert knowledge.types == []


def test_knowledge_with_section_and_type(knowledge_dict_normal: dict[str, Any]) -> None:
    """Knowledge coerces nested dicts into models."""
    knowledge = Knowledge.model_validate(knowledge_dict_normal)
    assert knowledge.principles.sections[0].id == 'mission'
    assert knowledge.types[0].id == 'report'


@pytest.mark.parametrize('missing', ['principles', 'types'])
def test_knowledge_fields_required(knowledge_dict_minimal: dict[str, Any], missing: str) -> None:
    """Both principles and types are required."""
    del knowledge_dict_minimal[missing]
    with pytest.raises(ValidationError):
        Knowledge.model_validate(knowledge_dict_minimal)
