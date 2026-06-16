"""The org's principles plus the catalogue of knowledge types it produces."""

from typing import Literal

from ._config import SpecModel


class PrincipleSection(SpecModel):
    """One prose section of the principles, rendered into agent instructions."""

    id: str
    title: str
    body: str


class Principles(SpecModel):
    """The org's principles - prose sections rendered into every agent's instructions."""

    sections: list[PrincipleSection]


class KnowledgeTypeMetadataField(SpecModel):
    """A metadata field on a knowledge type."""

    name: str
    type: Literal['string', 'int', 'float', 'bool']


class KnowledgeType(SpecModel):
    """A typed family of knowledge units (e.g. 'report', 'research')."""

    id: str
    label: str
    metadata_fields: list[KnowledgeTypeMetadataField]


class Knowledge(SpecModel):
    """The principles and the catalogue of knowledge types the org's agents work with."""

    principles: Principles
    types: list[KnowledgeType]
