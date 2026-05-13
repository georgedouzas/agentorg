"""Pydantic models for the agentorg spec.

Every user-authored `spec.py` constructs a `Spec(...)` instance. Defaults are baked into the model so a minimal spec
(just `org=Org(...)`) still produces a valid org with the six platform agents already present.
"""

from collections.abc import Callable
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScopeRef(BaseModel):
    """Out-of-scope topic + agent to delegate it to."""

    topic: str
    refer_to: str


class CountRuleEntry(BaseModel):
    """One row in the count_rule decision table."""

    phrase: str
    count: int | str


class CountRule(BaseModel):
    """How an agent decides how many results to return."""

    default: int | str | None = None
    rules: list[CountRuleEntry] = Field(default_factory=list)


class OutputFormat(BaseModel):
    """Output shape an agent is expected to produce."""

    kind: Literal['markdown_table', 'structured_markdown']
    columns: list[str] | None = None
    sections: list[str] | None = None
    trailer: str | None = None


class SaveRule(BaseModel):
    """Auto-save instructions tacked onto the agent's prompt."""

    tool: str
    name_pattern: str
    title_pattern: str
    note: str | None = None


class Agent(BaseModel):
    """One agent.

    Tools are real callables — Python-as-spec wins over string import paths.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    name: str
    model: str = 'gemini-3-flash-preview'
    role: str
    tools: list[Callable[..., Any]] = Field(default_factory=list)
    learning: bool = False
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[ScopeRef] = Field(default_factory=list)
    workflow: list[str] = Field(default_factory=list)
    output_format: OutputFormat | None = None
    save_rule: SaveRule | None = None
    count_rule: CountRule | None = None


class StepRouteHitl(BaseModel):
    """Human-in-the-loop checkpoint inside a workflow step."""

    type: Literal['output_review']
    message: str
    on_reject: Literal['cancel', 'retry'] = 'cancel'


class Step(BaseModel):
    """One step in a workflow.

    Either runs a single agent, or runs several agents in parallel.
    """

    name: str
    agent: str | None = None
    parallel: list['Step'] | None = None
    hitl: StepRouteHitl | None = None

    @model_validator(mode='after')
    def _validate_agent_or_parallel(self) -> 'Step':
        if self.agent is None and not self.parallel:
            msg = f'Step {self.name!r} must specify either `agent` or `parallel`.'
            raise ValueError(msg)
        return self


class Workflow(BaseModel):
    """An ordered pipeline of steps."""

    id: str
    name: str
    description: str = ''
    steps: list[Step] = Field(default_factory=list)


class Team(BaseModel):
    """A team of agents under a leader."""

    id: str
    name: str
    description: str = ''
    leader: str
    members: list[str] = Field(default_factory=list)


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


def _import_platform_agents() -> list[Agent]:
    """Indirection to break a circular import: platform_agents imports Agent from this module."""
    from agentorg.core.schema.platform_agents import PLATFORM_AGENTS  # noqa: PLC0415

    return list(PLATFORM_AGENTS)


def _default_documents() -> dict[str, list[DocumentType]]:
    return {'types': []}


class Generated(BaseModel):
    """Everything an interview / scaffold produces under the user's authorship.

    The six platform agents are pre-populated via `default_factory` — the user gets them for free without having to
    spell them out. They can be replaced or extended, but cannot be removed entirely (see Spec.validate_platform).
    """

    agents: list[Agent] = Field(default_factory=_import_platform_agents)
    teams: list[Team] = Field(default_factory=list)
    workflows: list[Workflow] = Field(default_factory=list)
    charter: Charter = Field(default_factory=Charter)
    state: StateSchema = Field(default_factory=StateSchema)
    documents: dict[str, list[DocumentType]] = Field(default_factory=_default_documents)
    agent_groups: list[GroupRef] = Field(default_factory=list)
    workflow_groups: list[GroupRef] = Field(default_factory=list)
    ui: UI | None = None
    env_vars: EnvVars = Field(default_factory=EnvVars)


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


AgentArchitecture = Annotated[Literal['default'], 'default']
WorkflowArchitecture = Annotated[Literal['pipeline', 'router', 'agentic'], 'pipeline']
TeamArchitecture = Annotated[Literal['coordinate', 'route', 'collaborate', 'broadcast'] | None, None]
InfraMode = Annotated[Literal['local', 'docker'], 'local']


class Spec(BaseModel):
    """The whole org spec — a single Python value the user constructs in `spec.py`."""

    agentorg_version: str = '0.1.0'
    agent_architecture: Literal['default'] = 'default'
    workflow_architecture: Literal['pipeline', 'router', 'agentic'] = 'pipeline'
    team_architecture: Literal['coordinate', 'route', 'collaborate', 'broadcast'] | None = None
    infra: Literal['local', 'docker'] = 'local'
    org: Org
    deployment: Deployment = Field(default_factory=Deployment)
    generated: Generated = Field(default_factory=Generated)
    setup: Setup = Field(default_factory=Setup)

    @model_validator(mode='after')
    def _validate_platform_agents_present(self) -> 'Spec':
        from agentorg.core.schema.platform_agents import PLATFORM_AGENT_IDS  # noqa: PLC0415

        present = {a.id for a in self.generated.agents}
        missing = PLATFORM_AGENT_IDS - present
        if missing:
            msg = (
                f'Spec is missing required platform agents: {sorted(missing)}. '
                'Platform agents are the default behaviour for every agentorg-generated org; '
                'remove them only by overriding `Generated(agents=[...])` deliberately.'
            )
            raise ValueError(msg)
        return self


Step.model_rebuild()
