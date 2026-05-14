"""Team factory — registers the spec's teams as reasoners on the AgentField node.

A team is "anything runnable" — typically an agno `Team` (which exposes `.arun()` and orchestrates its members), or
a plain callable that fans out to member reasoners via `app.call`. `register_teams` adapts each into a reasoner.
"""

from typing import Any

from agentorg.core.spec import Spec
from agentorg.core.tools.runtime import register_runnable


def register_teams(app: Any, spec: Spec) -> list[str]:
    """Register every team in the spec as a reasoner; return the registered reasoner names."""
    return [register_runnable(app, team) for team in spec.ai.teams]
