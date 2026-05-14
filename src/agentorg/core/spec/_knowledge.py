"""Knowledge — the org's charter plus the catalogue of document types it produces.

The charter is itself a piece of knowledge: prose sections that get baked into agent prompts, and tunable parameters
that become the org's per-user state. `document_types` is the catalogue of structured artifacts agents read and write.
"""

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
    """The org's charter — tunable parameters and prose sections."""

    parameters: list[CharterParameter]
    sections: list[CharterSection]


class DocumentTypeMetadataField(BaseModel):
    """A metadata field on a knowledge-document type."""

    name: str
    type: Literal['string', 'int', 'float', 'bool']


class DocumentType(BaseModel):
    """A typed family of knowledge documents (e.g. 'report', 'research')."""

    id: str
    label: str
    metadata_fields: list[DocumentTypeMetadataField]


class Knowledge(BaseModel):
    """The charter and the catalogue of document types the org's agents work with."""

    charter: Charter
    document_types: list[DocumentType]
