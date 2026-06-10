"""The org's principles plus the catalogue of knowledge types it produces."""

from typing import Literal

from pydantic import BaseModel


class PrincipleSection(BaseModel):
    """One prose section of the principles, rendered into agent instructions."""

    id: str
    title: str
    body: str


class Principles(BaseModel):
    """The org's principles — prose sections rendered into every agent's instructions."""

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
