"""Tests for `agentorg.core.spec._knowledge`."""

import pytest
from pydantic import ValidationError

from agentorg.core.spec import (
    Charter,
    CharterParameter,
    CharterSection,
    Knowledge,
    KnowledgeType,
    KnowledgeTypeMetadataField,
)

PARAMETER = {'name': 'min_sources', 'type': 'int', 'default': 3, 'label': 'Min Sources', 'format': None}
SECTION = {'id': 'charter', 'title': 'Charter', 'body': '## Mission\n- Do good work.'}
METADATA_FIELD = {'name': 'author', 'type': 'string'}
KNOWLEDGE_TYPE = {'id': 'report', 'label': 'Reports', 'metadata_fields': [METADATA_FIELD]}
CHARTER = {'parameters': [PARAMETER], 'sections': [SECTION]}
KNOWLEDGE = {'charter': CHARTER, 'types': [KNOWLEDGE_TYPE]}


# ── CharterParameter ─────────────────────────────────────────────────────────


def test_charter_parameter_fields() -> None:
    """`CharterParameter` carries name, type, default, label, and an optional format."""
    param = CharterParameter(**PARAMETER)
    assert param.name == 'min_sources'
    assert param.type == 'int'
    assert param.default == PARAMETER['default']
    assert param.format is None


@pytest.mark.parametrize('missing', list(PARAMETER))
def test_charter_parameter_missing_field_raises(missing: str) -> None:
    """Every `CharterParameter` field is required (`format` may be None but must be passed)."""
    with pytest.raises(ValidationError):
        CharterParameter(**{k: v for k, v in PARAMETER.items() if k != missing})


def test_charter_parameter_rejects_unknown_type() -> None:
    """`type` is a closed `Literal`."""
    with pytest.raises(ValidationError):
        CharterParameter(**{**PARAMETER, 'type': 'datetime'})


# ── CharterSection / Charter ─────────────────────────────────────────────────


def test_charter_section_fields() -> None:
    """`CharterSection` is id plus title plus markdown body."""
    section = CharterSection(**SECTION)
    assert section.id == 'charter'
    assert section.body.startswith('## Mission')


def test_charter_holds_parameters_and_sections() -> None:
    """`Charter` coerces dict parameters and sections into their models."""
    charter = Charter(**CHARTER)
    assert charter.parameters[0].name == 'min_sources'
    assert charter.sections[0].id == 'charter'


@pytest.mark.parametrize('missing', ['parameters', 'sections'])
def test_charter_fields_required(missing: str) -> None:
    """`parameters` and `sections` are required keys (empty lists allowed, omission is not)."""
    with pytest.raises(ValidationError):
        Charter(**{k: v for k, v in CHARTER.items() if k != missing})


# ── KnowledgeType ────────────────────────────────────────────────────────────


def test_knowledge_type_fields() -> None:
    """`KnowledgeType` is id plus label plus metadata field schema."""
    knowledge_type = KnowledgeType(**KNOWLEDGE_TYPE)
    assert knowledge_type.id == 'report'
    assert knowledge_type.metadata_fields[0].name == 'author'


def test_knowledge_type_metadata_field_rejects_unknown_type() -> None:
    """A metadata field's `type` is a closed `Literal`."""
    with pytest.raises(ValidationError):
        KnowledgeTypeMetadataField(name='count', type='list')


@pytest.mark.parametrize('missing', list(KNOWLEDGE_TYPE))
def test_knowledge_type_missing_field_raises(missing: str) -> None:
    """Every `KnowledgeType` field is required."""
    with pytest.raises(ValidationError):
        KnowledgeType(**{k: v for k, v in KNOWLEDGE_TYPE.items() if k != missing})


# ── Knowledge ────────────────────────────────────────────────────────────────


def test_knowledge_construction() -> None:
    """`Knowledge` wraps a charter and the knowledge-type catalogue, coercing dicts."""
    knowledge = Knowledge.model_validate(KNOWLEDGE)
    assert knowledge.charter.parameters[0].name == 'min_sources'
    assert knowledge.types[0].id == 'report'


@pytest.mark.parametrize('missing', ['charter', 'types'])
def test_knowledge_fields_required(missing: str) -> None:
    """`charter` and `types` are both required on `Knowledge`."""
    with pytest.raises(ValidationError):
        Knowledge.model_validate({k: v for k, v in KNOWLEDGE.items() if k != missing})
