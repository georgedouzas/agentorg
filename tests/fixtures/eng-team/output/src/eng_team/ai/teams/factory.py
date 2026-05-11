"""Team factory — builds teams declaratively from config.yaml.

Architecture: `coordinate`.
"""

from pathlib import Path
from typing import Any

import yaml
from agno.team import Team

from eng_team.ai.agents.factory import build_agents

_CONFIG_PATH = Path(__file__).parent.parent.parent / "app" / "config.yaml"
_MODE = "coordinate"


def build_teams() -> list[Team]:
    """Return one `Team` per team spec, in `coordinate` mode."""
    agents = build_agents()
    specs: list[dict[str, Any]] = yaml.safe_load(_CONFIG_PATH.read_text()).get("teams", [])
    teams: list[Team] = []
    for spec in specs:
        leader_id = spec["leader"]
        member_agents = [agents[m] for m in spec.get("members", [])]
        teams.append(
            Team(
                id=spec["id"],
                name=spec.get("name", spec["id"]),
                description=spec.get("description", ""),
                mode=_MODE,
                model=agents[leader_id].model,
                members=member_agents,
            ),
        )
    return teams
