"""Tests for extract module."""

from typing import Any

from agentorg.core.render import jinja_context
from agentorg.core.spec import Spec


def test_pydantic_fields_round_trip(spec_dict_normal: dict[str, Any]) -> None:
    """Org, runtime, parameters, knowledge, ui round-trip through model_dump as plain dicts."""
    spec = Spec.model_validate(spec_dict_normal)
    data = jinja_context(spec)
    assert data['org']['name'] == 'Acme Organization'
    assert data['runtime']['infra']['packaging'] == 'docker'
    assert data['knowledge']['types'][0]['id'] == 'report'
    assert data['ui']['app']['icon'] == '🔬'


def test_year_is_attached(spec_dict_minimal: dict[str, Any]) -> None:
    """`year` is set from the current UTC year and exposed for copyright lines."""
    data = jinja_context(Spec.model_validate(spec_dict_minimal))
    assert isinstance(data['year'], int)
    assert data['year'] >= 2026


def test_ai_namespace_replaces_pydantic_dump(spec_dict_normal: dict[str, Any]) -> None:
    """`ai` is the hand-shimmed namespace; `model_dump` does not produce it because agno objects are not Pydantic."""
    data = jinja_context(Spec.model_validate(spec_dict_normal))
    assert set(data['ai']) == {'agents', 'teams', 'workflows'}
    assert len(data['ai']['agents']) == 1
    assert len(data['ai']['teams']) == 1
    assert len(data['ai']['workflows']) == 1


def test_agent_summary_extracts_id_name_role_model(spec_dict_normal: dict[str, Any]) -> None:
    """An agno Agent surfaces as {id, name, role, model, instructions, tools, skills}."""
    data = jinja_context(Spec.model_validate(spec_dict_normal))
    agent = data['ai']['agents'][0]
    assert agent['id'] == 'researcher'
    assert agent['name'] == 'Researcher'
    assert set(agent) == {'id', 'name', 'role', 'model', 'instructions', 'tools', 'skills'}
    assert isinstance(agent['tools'], list)
    assert isinstance(agent['skills'], list)


def test_team_summary_carries_members(spec_dict_normal: dict[str, Any]) -> None:
    """A team's members are flattened to a list of member ids."""
    data = jinja_context(Spec.model_validate(spec_dict_normal))
    team = data['ai']['teams'][0]
    assert team['id'] == 'research-team'
    assert team['members'] == ['researcher']


def test_workflow_summary_carries_steps(spec_dict_normal: dict[str, Any]) -> None:
    """A workflow's steps are summarised as `{name, agent, hitl}` dicts."""
    data = jinja_context(Spec.model_validate(spec_dict_normal))
    workflow = data['ai']['workflows'][0]
    assert workflow['id'] == 'pipeline'
    assert workflow['steps'][0] == {'name': 'Gather', 'agent': 'researcher', 'hitl': False}


def test_empty_ai_lists_render_as_empty(spec_dict_minimal: dict[str, Any]) -> None:
    """A spec with no agents/teams/workflows produces empty lists, not missing keys."""
    data = jinja_context(Spec.model_validate(spec_dict_minimal))
    assert data['ai'] == {'agents': [], 'teams': [], 'workflows': []}
