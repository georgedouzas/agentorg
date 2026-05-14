"""Pydantic models for the agentorg spec.

User-facing principles:
- Agents, teams and workflows are **agno-native** (`agno.Agent`, `agno.Team`, `agno.Workflow`). No agentorg wrapper.
- Everything else (UI, charter, env vars, setup, documents, groups) is a typed Pydantic model **that accepts plain
  dicts**. Pydantic v2 coerces them at construction time, so users write one dict literal instead of importing five
  small classes.

The result: a typical `spec.py` imports `Spec`, `Org`, `PLATFORM_AGENTS` from agentorg, and `Agent`/`Team`/`Workflow`/
`Step` from agno — that's it.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agentorg.core.spec._ai import AI
from agentorg.core.spec._org import Org
from agentorg.core.spec._runtime import Runtime


class CharterParameter(BaseModel):
    """A user-tunable charter parameter (e.g. `min_test_coverage_pct: 80`)."""

    name: str
    type: Literal['int', 'float', 'string', 'bool', 'object', 'array']
    default: Any
    label: str = ''
    format: str | None = None


class CharterSection(BaseModel):
    """One section of the org's charter (rendered into agent instructions)."""

    id: str
    title: str
    body: str


class Charter(BaseModel):
    """Org charter — parameters, derived expressions, and prose sections."""

    parameters: list[CharterParameter] = Field(default_factory=list)
    derived: list[dict[str, Any]] = Field(default_factory=list)
    sections: list[CharterSection] = Field(default_factory=list)


class DocumentTypeMetadataField(BaseModel):
    """Metadata field on a knowledge-document type."""

    name: str
    type: Literal['string', 'int', 'float', 'bool']


class DocumentType(BaseModel):
    """A typed family of knowledge documents (e.g. 'report', 'research')."""

    id: str
    label: str
    metadata_fields: list[DocumentTypeMetadataField] = Field(default_factory=list)


class StateField(BaseModel):
    """One field in the org's runtime state (per-user JSON)."""

    name: str
    type: Literal['object', 'array', 'string', 'int', 'float', 'bool']
    default: Any


class StateSchema(BaseModel):
    """Org state schema (Pydantic model name + runtime fields)."""

    model_name: str = 'OrgConfig'
    data_fields: list[StateField] = Field(default_factory=list)


class AppUI(BaseModel):
    """App-level UI metadata."""

    name: str
    icon: str
    description: str = ''


class EmptyState(BaseModel):
    """Empty-state copy shown when the user lands without selecting anything."""

    icon: str
    title: str
    body: str


class KnowledgeEmpty(BaseModel):
    """Empty-state copy for the Knowledge tab."""

    documents: str
    learnings: str


class AgentConfigUI(BaseModel):
    """Per-agent metadata for the UI sidebar / agent picker."""

    model: str
    description: str = ''
    tools: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)


class GroupRef(BaseModel):
    """A sidebar group — a label + the ids it contains."""

    label: str
    ids: list[str] = Field(default_factory=list)


class UI(BaseModel):
    """All UI customisation, consumed by the React frontend."""

    app: AppUI
    empty_state: EmptyState
    knowledge_empty: KnowledgeEmpty
    featured_agents: list[str] = Field(default_factory=list)
    agent_icons: dict[str, str] = Field(default_factory=dict)
    overview: dict[str, Any] = Field(default_factory=dict)
    agent_configs: dict[str, AgentConfigUI] = Field(default_factory=dict)
    chat_quick_prompts: dict[str, list[str]] = Field(default_factory=dict)


def _default_documents() -> dict[str, list[DocumentType]]:
    return {'types': []}


class Spec(BaseModel):
    """The whole org spec — a single Python value the user constructs in `spec.py`."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    org: Org
    runtime: Runtime
    ai: AI

    # org content
    charter: Charter = Field(default_factory=Charter)
    state: StateSchema = Field(default_factory=StateSchema)
    documents: dict[str, list[DocumentType]] = Field(default_factory=_default_documents)
    agent_groups: list[GroupRef] = Field(default_factory=list)
    workflow_groups: list[GroupRef] = Field(default_factory=list)
    ui: UI | None = None
