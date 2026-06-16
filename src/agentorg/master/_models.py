"""Interview-time representations of agents, teams, workflows, and custom tools."""

from typing import Literal

from pydantic import Field

from agentorg.core.spec import SpecModel


class AgentSpec(SpecModel):
    """Interview-time capture of a single user-defined agent's persona."""

    agent_id: str
    name: str
    role: str
    model: str = 'google:gemini-2.5-flash'
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    in_scope: list[str] = Field(default_factory=list)
    workflow: list[str] = Field(default_factory=list)
    when_to_act: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    style: list[str] = Field(default_factory=list)
    principles: list[str] = Field(default_factory=list)
    introduction: str = ''
    description: str = ''
    additional_context: str = ''


class StepSpec(SpecModel):
    """One step in a workflow - delegates to an agent identified by its id."""

    name: str
    agent_id: str
    requires_output_review: bool = False


class TeamSpec(SpecModel):
    """Interview-time capture of a team's persona and member references (by `agent_id`)."""

    team_id: str
    name: str
    role: str
    workflow: list[str]
    member_ids: list[str]
    mode: Literal['coordinate', 'route', 'broadcast', 'tasks'] = 'coordinate'
    model: str = 'google:gemini-2.5-flash'
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    when_to_act: list[str] = Field(default_factory=list)
    style: list[str] = Field(default_factory=list)
    principles: list[str] = Field(default_factory=list)
    introduction: str = ''
    description: str = ''
    additional_context: str = ''


class WorkflowSpec(SpecModel):
    """Interview-time capture of a workflow as an ordered sequence of steps."""

    workflow_id: str
    name: str
    steps: list[StepSpec]
    description: str = ''


class CustomTool(SpecModel):
    """A user-defined tool function emitted via `emit_custom_tool` and rendered into spec.py."""

    name: str
    source: str


class CustomSkill(SpecModel):
    """A user-defined skill emitted via `emit_custom_skill`.

    `skill_md` is the full SKILL.md markdown body. The writer materialises a folder of the form `skills/<name>/SKILL.md`
    next to the rendered `spec.py`, and the agents that reference this skill load it via `LocalSkills('skills/<name>')`.
    """

    name: str
    skill_md: str
