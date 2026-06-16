"""In-memory state holding the current Spec and custom tool definitions."""

from dataclasses import dataclass, field

from agentorg.core.spec import Spec

from ._models import CustomSkill, CustomTool
from ._seed import default_spec


@dataclass
class State:
    """The whole working state of an interview - the spec being built and any custom artefacts."""

    spec: Spec = field(default_factory=default_spec)
    custom_tools: list[CustomTool] = field(default_factory=list)
    custom_skills: list[CustomSkill] = field(default_factory=list)

    def reset(self) -> None:
        """Reset every field back to its seed value, in place."""
        self.spec = default_spec()
        self.custom_tools = []
        self.custom_skills = []


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
