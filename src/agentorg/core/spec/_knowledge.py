"""The org's principles plus the catalogue of knowledge types it produces."""

from typing import Any, Literal

from pydantic import BaseModel


class PrincipleParameter(BaseModel):
    """A user-tunable principles parameter (e.g. `min_test_coverage_pct: 80`)."""

    name: str
    type: Literal['int', 'float', 'string', 'bool', 'object', 'array']
    default: Any
    label: str
    format: str | None


class PrincipleSection(BaseModel):
    """One prose section of the principles, rendered into agent instructions."""

    id: str
    title: str
    body: str


class Principles(BaseModel):
    """The org's principles with tunable parameters and prose sections."""

    parameters: list[PrincipleParameter]
    sections: list[PrincipleSection]


class KnowledgeTypeMetadataField(BaseModel):
    """A metadata field on a knowledge type."""

    name: str
    type: Literal['string', 'int', 'float', 'bool']


class KnowledgeType(BaseModel):
    """A typed family of knowledge units (e.g. 'report', 'research')."""

    id: str
    label: str
    metadata_fields: list[KnowledgeTypeMetadataField]


class Knowledge(BaseModel):
    """The principles and the catalogue of knowledge types the org's agents work with."""

    principles: Principles
    types: list[KnowledgeType]
