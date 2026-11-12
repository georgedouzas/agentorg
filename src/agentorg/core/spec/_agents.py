"""Agent definitions and the units that organise them."""

from collections.abc import Callable, Iterator
from typing import Any, Literal

from pydantic import Field, model_validator

from ._config import SpecModel

ID_PATTERN = r'^[a-z][a-z0-9-]*$'
READ_TOOLS = ('read', 'glob', 'grep', 'web_search', 'web_fetch', 'todo')
WRITE_TOOLS = ('write', 'edit')
MAX_SPAN = 12
MAX_POOL_SPAN = 100
COUNCIL_SIZE = range(3, 10)

Autonomy = Literal['read_only', 'propose', 'act', 'autonomous']
BuiltinTool = Literal['read', 'write', 'edit', 'glob', 'grep', 'bash', 'web_search', 'web_fetch', 'todo']
ActionClass = Literal['external_write', 'outbound_message', 'code_execution', 'knowledge_publish', 'spend']
Model = Literal['solo', 'pipeline', 'hub', 'pool', 'council']
Routing = Literal['round_robin', 'least_loaded', 'skill_match']
Decision = Literal['majority', 'judge', 'unanimous']
Review = Literal['none', 'lead', 'human']

DEFAULT_BUILTIN_TOOLS: dict[str, tuple[str, ...]] = {
    'read_only': READ_TOOLS,
    'propose': READ_TOOLS + WRITE_TOOLS,
    'act': READ_TOOLS + WRITE_TOOLS,
    'autonomous': (*READ_TOOLS, *WRITE_TOOLS, 'bash'),
}


class Referral(SpecModel):
    """A topic an agent declines and the agent or unit it refers the user to."""

    topic: str
    refer_to: str


class Persona(SpecModel):
    """How an agent speaks and which topics it owns."""

    tone: Literal['direct', 'warm', 'formal', 'playful'] = 'direct'
    verbosity: Literal['terse', 'balanced', 'thorough'] = 'balanced'
    instructions: str = ''
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[Referral] = Field(default_factory=list)


class McpServer(SpecModel):
    """An MCP server an agent connects to, with secrets referenced by env var name."""

    name: str = Field(pattern=r'^[a-z][a-z0-9_]*$')
    transport: Literal['stdio', 'http', 'sse']
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    env: list[str] = Field(default_factory=list)
    allowed_tools: list[str] | None = None
    read_tools: list[str] = Field(default_factory=list)
    outbound_tools: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def _validate_connection(self) -> 'McpServer':
        """Require a command for stdio servers and a url otherwise."""
        if self.transport == 'stdio' and not self.command:
            msg = f"MCP server '{self.name}' uses transport 'stdio' and needs a `command`."
            raise ValueError(msg)
        if self.transport != 'stdio' and not self.url:
            msg = f"MCP server '{self.name}' uses transport '{self.transport}' and needs a `url`."
            raise ValueError(msg)
        return self


class Limits(SpecModel):
    """Per-run limits; `max_run_usd` falls back to the org's per-run budget when unset."""

    max_turns: int = Field(default=30, ge=1)
    max_run_usd: float | None = Field(default=None, gt=0)
    timeout_s: int = Field(default=600, ge=1)


class Output(SpecModel):
    """The shape of an agent's final answer and where it is filed."""

    format: Literal['text', 'json'] = 'text'
    json_schema: dict[str, Any] | None = None
    knowledge_type: str | None = None

    @model_validator(mode='after')
    def _validate_schema(self) -> 'Output':
        """Require a JSON schema for json output."""
        if self.format == 'json' and not self.json_schema:
            msg = "Output format 'json' needs a `json_schema`."
            raise ValueError(msg)
        return self


class Agent(SpecModel):
    """One agent: its persona, model, autonomy, tools and limits."""

    id: str = Field(pattern=ID_PATTERN)
    name: str
    role: str
    persona: Persona = Field(default_factory=Persona)
    model: Literal['opus', 'sonnet', 'haiku'] = 'sonnet'
    autonomy: Autonomy = 'propose'
    builtin_tools: list[BuiltinTool] | None = None
    tools: list[Callable[..., Any]] = Field(default_factory=list)
    mcp_servers: list[McpServer] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    workspace: Literal['ephemeral', 'persistent', 'shared'] = 'ephemeral'
    memory: Literal['none', 'session', 'user'] = 'session'
    limits: Limits = Field(default_factory=Limits)
    output: Output = Field(default_factory=Output)
    replicas: int = Field(default=1, ge=1)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def _validate_tools(self) -> 'Agent':
        """Derive default built-in tools and reject write tools for read-only agents."""
        if self.builtin_tools is None:
            self.__dict__['builtin_tools'] = list(DEFAULT_BUILTIN_TOOLS[self.autonomy])
            return self
        granted = set(self.builtin_tools) & {'write', 'edit', 'bash'}
        if self.autonomy == 'read_only' and granted:
            msg = f"Agent '{self.id}' is read_only and cannot be granted {sorted(granted)}."
            raise ValueError(msg)
        return self


class Step(SpecModel):
    """One pipeline step: the member that runs it, its instruction and its review gate."""

    member: 'str | Unit'
    instruction: str = ''
    review: Review = 'none'


class Unit(SpecModel):
    """A group of agents or nested units governed by one model."""

    id: str = Field(pattern=ID_PATTERN)
    name: str
    model: Model
    members: list['str | Unit | Step']
    lead: str | None = None
    routing: Routing = 'least_loaded'
    decision: Decision | None = None
    review: Review = 'none'
    owners: list[str] = Field(default_factory=list)
    max_autonomy: Autonomy | None = None
    monthly_usd: float | None = Field(default=None, gt=0)
    approval_required: list[ActionClass] = Field(default_factory=list)

    @property
    def member_refs(self) -> list['str | Unit']:
        """The agent ids and nested units of this unit, unwrapping pipeline steps."""
        return [member.member if isinstance(member, Step) else member for member in self.members]

    def _validate_model_rules(self) -> None:
        """Enforce the structural rule of the unit's model."""
        if self.model != 'pipeline' and any(isinstance(member, Step) for member in self.members):
            msg = f"Unit '{self.id}': steps are only allowed in a pipeline."
            raise ValueError(msg)
        if self.model == 'solo' and (len(self.members) != 1 or not isinstance(self.members[0], str) or self.lead):
            msg = f"Unit '{self.id}': a solo unit has exactly one agent member and no lead."
            raise ValueError(msg)
        if self.model == 'hub' and not self.lead:
            msg = f"Unit '{self.id}': a hub needs a `lead`."
            raise ValueError(msg)
        if self.model == 'pipeline' and self.lead:
            msg = f"Unit '{self.id}': a pipeline has no lead."
            raise ValueError(msg)

    def _validate_council(self) -> None:
        """Enforce council size, decision rule and judge lead."""
        if self.model != 'council':
            return
        if len(self.members) not in COUNCIL_SIZE or self.decision is None:
            msg = f"Unit '{self.id}': a council needs 3 to 9 members and a `decision` rule."
            raise ValueError(msg)
        if self.decision == 'majority' and len(self.members) % 2 == 0:
            msg = f"Unit '{self.id}': a majority council needs an odd number of members, got {len(self.members)}."
            raise ValueError(msg)
        if self.decision == 'judge' and not self.lead:
            msg = f"Unit '{self.id}': a council with decision 'judge' needs a `lead`."
            raise ValueError(msg)

    @model_validator(mode='after')
    def _validate_unit(self) -> 'Unit':
        """Enforce the model rules, the span limit and the lead not being a member."""
        self._validate_model_rules()
        self._validate_council()
        span = MAX_POOL_SPAN if self.model == 'pool' else MAX_SPAN
        if len(self.members) > span:
            msg = f"Unit '{self.id}' has {len(self.members)} members; a {self.model} allows {span}. Nest units instead."
            raise ValueError(msg)
        if self.lead and self.lead in self.member_refs:
            msg = f"Unit '{self.id}': the lead '{self.lead}' must not also be a member."
            raise ValueError(msg)
        return self

    def iter_units(self) -> Iterator['Unit']:
        """Yield this unit and every unit nested in it, depth first."""
        yield self
        for member in self.member_refs:
            if isinstance(member, Unit):
                yield from member.iter_units()

    def depth(self) -> int:
        """Return the number of unit levels from this unit down to its deepest nested unit."""
        nested = [member.depth() for member in self.member_refs if isinstance(member, Unit)]
        return 1 + max(nested, default=0)


Step.model_rebuild()
Unit.model_rebuild()
