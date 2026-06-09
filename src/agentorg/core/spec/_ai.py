"""The agents, teams, and workflows the org runs."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class AI(BaseModel):
    """The org's user-declared agents, teams, and workflows."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    framework: Literal['agno'] = 'agno'
    agents: list[Any]
    teams: list[Any]
    workflows: list[Any]
