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

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class EnvVar(BaseModel):
    """A declared environment variable the rendered org expects."""

    name: str
    description: str = ''
    required_label: str = 'Dev'


class EnvVars(BaseModel):
    """Required + optional env vars the rendered org expects."""

    required: list[EnvVar] = Field(default_factory=list)
    optional: list[EnvVar] = Field(default_factory=list)


class Org(BaseModel):
    """Org metadata (name, slug, repository, author, license)."""

    name: str
    slug: str
    package_name: str
    domain: str = ''
    description: str = ''
    repository: str = ''
    author_name: str = ''
    author_email: str = ''
    visibility: Literal['public', 'private'] = 'private'
    license_year: int = 2026


class Deployment(BaseModel):
    """Cloud-deployment targets for the rendered org."""

    api: Literal['railway', 'none'] = 'none'
    frontend: Literal['vercel', 'none'] = 'none'
    auth: Literal['clerk', 'none'] = 'none'


class SetupStep(BaseModel):
    """One item on the post-install setup checklist."""

    id: str
    title: str
    vars: list[str] = Field(default_factory=list)
    command: str | None = None
    platform: str | None = None


class Setup(BaseModel):
    """Setup checklist shown after the user pip-installs the rendered org."""

    steps: list[SetupStep] = Field(default_factory=list)


def _default_agents() -> list[Any]:
    """Indirection to break a circular import: platform_agents imports back from here."""
    from agentorg.core.schema.platform_agents import PLATFORM_AGENTS  # noqa: PLC0415

    return list(PLATFORM_AGENTS)


def _default_documents() -> dict[str, list[DocumentType]]:
    return {'types': []}


class Spec(BaseModel):
    """The whole org spec — a single Python value the user constructs in `spec.py`.

    Agents/teams/workflows are agno-native objects. Everything else accepts dicts that Pydantic coerces into the
    matching model, so the user side reads as one dict literal per section.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # platform / architecture
    agentorg_version: str = '0.1.0'
    agent_architecture: Literal['default'] = 'default'
    workflow_architecture: Literal['pipeline', 'router', 'agentic'] = 'pipeline'
    team_architecture: Literal['coordinate', 'route', 'collaborate', 'broadcast'] | None = None
    infra: Literal['local', 'docker'] = 'local'

    # org metadata
    org: Org
    deployment: Deployment = Field(default_factory=Deployment)

    # agno-native runtime objects (typed `Any` so Pydantic does not introspect agno's complex annotations)
    agents: list[Any] = Field(default_factory=_default_agents)
    teams: list[Any] = Field(default_factory=list)
    workflows: list[Any] = Field(default_factory=list)

    # org content
    charter: Charter = Field(default_factory=Charter)
    state: StateSchema = Field(default_factory=StateSchema)
    documents: dict[str, list[DocumentType]] = Field(default_factory=_default_documents)
    agent_groups: list[GroupRef] = Field(default_factory=list)
    workflow_groups: list[GroupRef] = Field(default_factory=list)
    ui: UI | None = None
    env_vars: EnvVars = Field(default_factory=EnvVars)
    setup: Setup = Field(default_factory=Setup)

    @model_validator(mode='after')
    def _validate_platform_agents_present(self) -> 'Spec':
        from agentorg.core.schema.platform_agents import PLATFORM_AGENT_IDS  # noqa: PLC0415

        present = {a.id for a in self.agents if a.id}
        missing = PLATFORM_AGENT_IDS - present
        if missing:
            msg = (
                f'Spec is missing required platform agents: {sorted(missing)}. '
                'Platform agents are the default behaviour for every agentorg-generated org; '
                'they ship pre-built — start from `PLATFORM_AGENTS` and extend.'
            )
            raise ValueError(msg)
        return self
