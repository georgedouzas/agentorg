"""Turn a `Spec` into a Jinja-ready data dict.

`spec.ai.{agents,teams,workflows}` hold agno-native runtime objects (not Pydantic).
`make_agent(in_scope=[...], workflow=[...], style=[...])` assembles its structured
kwargs into a single `instructions` string at construction time - those structured
fields are not recoverable from the agent afterwards. We extract only what IS
introspectable: id, name, role, model, tools (as names), skills (as refs), and the
final assembled `instructions`. Templates that need the structured pieces should
parse `instructions` markdown or read the user's spec.py directly.
"""

from datetime import UTC, datetime
from typing import Any

from agentorg.core.spec import Spec


def _runnable_name(obj: object) -> str:
    """Best-effort stable name: `.id`, then `.name`, then `.__name__`."""
    return str(getattr(obj, 'id', None) or getattr(obj, 'name', None) or getattr(obj, '__name__', None) or '')


def _tool_name(tool: object) -> str:
    """The callable name of a tool (function `__name__`, or class `__name__` for agno toolkits)."""
    return str(getattr(tool, '__name__', None) or type(tool).__name__)


def _skill_ref(skill: object) -> str:
    """A best-effort string ref for a skill - the agno SkillLoader's `path` or class name."""
    return str(getattr(skill, 'path', None) or getattr(skill, 'url', None) or type(skill).__name__)


def _model_id(model: object) -> str:
    """The model identifier - agno wraps strings into objects with `.id`; bare strings fall through."""
    return str(getattr(model, 'id', None) or getattr(model, 'name', None) or model or '')


def _agent_summary(agent: object) -> dict[str, Any]:
    name = _runnable_name(agent)
    return {
        'id': name,
        'name': getattr(agent, 'name', None) or name,
        'role': getattr(agent, 'role', '') or '',
        'model': _model_id(getattr(agent, 'model', None)),
        'instructions': getattr(agent, 'instructions', '') or '',
        'tools': [_tool_name(t) for t in (getattr(agent, 'tools', None) or [])],
        'skills': [_skill_ref(s) for s in (getattr(agent, 'skills', None) or [])],
    }


def _team_summary(team: object) -> dict[str, Any]:
    name = _runnable_name(team)
    return {
        'id': name,
        'name': getattr(team, 'name', None) or name,
        'role': getattr(team, 'role', '') or '',
        'mode': getattr(team, 'mode', None) or 'route',
        'model': _model_id(getattr(team, 'model', None)),
        'instructions': getattr(team, 'instructions', '') or '',
        'tools': [_tool_name(t) for t in (getattr(team, 'tools', None) or [])],
        'skills': [_skill_ref(s) for s in (getattr(team, 'skills', None) or [])],
        'members': [_runnable_name(m) for m in (getattr(team, 'members', None) or []) if _runnable_name(m)],
    }


def _step_summary(step: object) -> dict[str, Any]:
    parallel = getattr(step, 'steps', None) if type(step).__name__ == 'Parallel' else None
    if parallel is not None:
        return {'name': getattr(step, 'name', '') or 'Parallel', 'parallel': [_step_summary(s) for s in parallel]}
    agent = getattr(step, 'agent', None)
    hitl = bool(
        getattr(step, 'requires_output_review', False)
        or getattr(step, 'requires_confirmation', False)
        or getattr(step, 'requires_user_input', False),
    )
    return {
        'name': getattr(step, 'name', '') or '',
        'agent': _runnable_name(agent) if agent is not None else None,
        'hitl': hitl,
    }


def _workflow_summary(workflow: object) -> dict[str, Any]:
    name = _runnable_name(workflow)
    return {
        'id': name,
        'name': getattr(workflow, 'name', None) or name,
        'description': getattr(workflow, 'description', '') or '',
        'steps': [_step_summary(s) for s in (getattr(workflow, 'steps', None) or [])],
    }


def jinja_context(spec: Spec) -> dict[str, Any]:
    """Convert the Spec to a plain dict for Jinja templates.

    Pydantic fields (org / runtime / parameters / knowledge / ui) round-trip through `model_dump`. The `ai` slot is
    agno-native so we hand-shim it via the summary helpers above. Templates access fields directly: `{{ org.name }}`,
    `{{ ui.app.icon }}`, `{{ ai.agents }}`, etc.
    """
    base = spec.model_dump(mode='json', exclude={'ai'})
    base['year'] = datetime.now(tz=UTC).year
    base['ai'] = {
        'agents': [_agent_summary(a) for a in spec.ai.agents],
        'teams': [_team_summary(t) for t in spec.ai.teams],
        'workflows': [_workflow_summary(w) for w in spec.ai.workflows],
    }
    return base
