"""The agents, teams, and workflows the org runs."""

from typing import Any, Literal

from ._config import SpecModel


class AI(SpecModel):
    """The org's user-declared agents, teams, and workflows."""

    framework: Literal['agno'] = 'agno'
    agents: list[Any]
    teams: list[Any]
    workflows: list[Any]
