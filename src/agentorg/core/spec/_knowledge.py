"""The org's charter plus the catalogue of knowledge types it produces."""

from typing import Any, Literal

from pydantic import BaseModel


class CharterParameter(BaseModel):
    """A user-tunable charter parameter (e.g. `min_test_coverage_pct: 80`)."""

    name: str
    type: Literal['int', 'float', 'string', 'bool', 'object', 'array']
    default: Any
    label: str
    format: str | None


class CharterSection(BaseModel):
    """One prose section of the charter, rendered into agent instructions."""

    id: str
    title: str
    body: str


class Charter(BaseModel):
    """The org's charter with tunable parameters and prose sections."""

    parameters: list[CharterParameter]
    sections: list[CharterSection]


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
    """The charter and the catalogue of knowledge types the org's agents work with."""

    charter: Charter
    types: list[KnowledgeType]
