"""In-memory state holding the current Spec, custom tools, the interview stage, and discovery."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from ..core.spec import Agent, Spec
from ._models import CustomSkill, CustomTool, UnitDraft
from ._seed import default_spec

Stage = Literal['discover', 'configure', 'build', 'refine', 'handoff']


@dataclass
class Discovery:
    """The master agent's recorded understanding of the business, set during Stage 1.

    Six structured fields, each with a per-field length minimum, forcing the agent to ask enough follow-up questions to
    fill them with substance. Gates `add_or_update_principle_section` and `set_org_identity(description=...)` during
    Stage 1, so the master can't race past discovery into fluffy principles.
    """

    what_the_group_does: str
    who_serves: str
    concrete_tasks_owned: str
    typical_flow: str
    business_context: str
    current_pain_or_alternative: str


@dataclass
class State:
    """The working state of an interview: spec, agent and unit drafts, custom artefacts, stage cursor, discovery."""

    spec: Spec = field(default_factory=default_spec)
    agents: list[Agent] = field(default_factory=list)
    units: list[UnitDraft] = field(default_factory=list)
    custom_tools: list[CustomTool] = field(default_factory=list)
    custom_skills: list[CustomSkill] = field(default_factory=list)
    functions: dict[str, Callable[..., Any]] = field(default_factory=dict)
    stage: Stage = 'discover'
    discovery: Discovery | None = None
    structure_error: str | None = None

    def reset(self) -> None:
        """Reset every field back to its seed value, in place."""
        self.spec = default_spec()
        self.agents = []
        self.units = []
        self.functions = {}
        self.structure_error = None
        self.custom_tools = []
        self.custom_skills = []
        self.stage = 'discover'
        self.discovery = None


STATE = State()


def get_state() -> State:
    """Return the singleton interview state.

    Returns:
        state: The current `State`.
    """
    return STATE


def reset_state() -> None:
    """Reset the interview state back to a fresh placeholder-seeded `Spec`."""
    STATE.reset()
