"""The agents, teams, and workflows the org runs."""

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from agentorg.core.spec.platform_agents import PLATFORM_AGENT_IDS


class AI(BaseModel):
    """The org's agents, teams, and workflows."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agents: list[Any]
    teams: list[Any]
    workflows: list[Any]

    @model_validator(mode='after')
    def _validate_platform_agents_present(self) -> 'AI':
        present = {a.id for a in self.agents if a.id}
        missing = PLATFORM_AGENT_IDS - present
        if missing:
            msg = (
                f'AI is missing required platform agents: {sorted(missing)}. '
                'Platform agents ship pre-built — start from `PLATFORM_AGENTS` and extend.'
            )
            raise ValueError(msg)
        return self
