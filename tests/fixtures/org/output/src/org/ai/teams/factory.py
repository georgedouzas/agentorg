"""Team factory — builds teams from the spec.

Architecture: `coordinate`.
"""

from agno.agent import Agent as AgnoAgent
from agno.team import Team

from agentorg.core.schema import Spec

_MODE = 'coordinate'


def build_teams(spec: Spec, agents: dict[str, AgnoAgent]) -> list[Team]:
    """Return one `Team` per spec entry, in `coordinate` mode."""
    teams: list[Team] = []
    for team_spec in spec.generated.teams:
        leader = agents[team_spec.leader]
        members = [agents[m] for m in team_spec.members]
        teams.append(
            Team(
                id=team_spec.id,
                name=team_spec.name,
                description=team_spec.description,
                mode=_MODE,
                model=leader.model,
                members=members,
            ),
        )
    return teams
