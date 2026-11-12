"""Turn a Spec into a Jinja-ready data dict."""

from datetime import UTC, datetime
from typing import Any

from ..spec import Agent, Spec, Step, Unit


def _agent_summary(agent: Agent) -> dict[str, Any]:
    """Return the template fields of an agent."""
    return {
        'id': agent.id,
        'name': agent.name,
        'role': agent.role,
        'model': agent.model,
        'autonomy': agent.autonomy,
        'tools': list(agent.builtin_tools or []) + [fn.__name__ for fn in agent.tools],
        'mcp_servers': [server.name for server in agent.mcp_servers],
        'skills': agent.skills,
    }


def _unit_summary(unit: Unit) -> dict[str, Any]:
    """Return the template fields of a unit."""
    steps = [member if isinstance(member, Step) else Step(member=member) for member in unit.members]
    return {
        'id': unit.id,
        'name': unit.name,
        'model': unit.model,
        'lead': unit.lead,
        'members': [member if isinstance(member, str) else member.id for member in unit.member_refs],
        'steps': (
            [
                {'member': step.member if isinstance(step.member, str) else step.member.id, 'review': step.review}
                for step in steps
            ]
            if unit.model == 'pipeline'
            else []
        ),
    }


def jinja_context(spec: Spec) -> dict[str, Any]:
    """Convert the Spec to a plain dict for Jinja templates.

    Every domain except `ai` round-trips through `model_dump`. The `ai` slot holds agent and unit summaries, because
    agents carry Python callables as tools. Templates access fields directly: `{{ org.name }}`, `{{ ai.units }}`.
    """
    base = spec.model_dump(mode='json', exclude={'ai'})
    base['year'] = datetime.now(tz=UTC).year
    base['ai'] = {
        'root': spec.ai.root.id if spec.ai.root else None,
        'agents': [_agent_summary(agent) for agent in spec.ai.agents],
        'units': [_unit_summary(unit) for unit in spec.ai.units],
    }
    return base
