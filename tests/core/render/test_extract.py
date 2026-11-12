"""Tests for the extract module."""

from typing import Any

from agentorg.core.render import jinja_context
from agentorg.core.spec import Spec


def test_pydantic_fields_round_trip(spec_dict_normal: dict[str, Any]) -> None:
    """Every domain except `ai` is a plain JSON dump of the spec."""
    data = jinja_context(Spec.model_validate(spec_dict_normal))
    assert data['org']['slug'] == 'acme-org'
    assert data['operations']['triggers'][0]['id'] == 'weekly-report'
    assert data['knowledge']['types'][0]['id'] == 'report'


def test_year_is_attached(spec_dict_minimal: dict[str, Any]) -> None:
    """The current year is available for licence headers."""
    assert isinstance(jinja_context(Spec.model_validate(spec_dict_minimal))['year'], int)


def test_ai_holds_agent_and_unit_summaries(spec_dict_normal: dict[str, Any]) -> None:
    """Agents and units are summarised as plain dicts, with the root unit named."""
    ai = jinja_context(Spec.model_validate(spec_dict_normal))['ai']
    assert ai['root'] == 'research'
    assert ai['agents'][1] == {
        'id': 'researcher',
        'name': 'Researcher',
        'role': 'Gathers sources.',
        'model': 'sonnet',
        'autonomy': 'read_only',
        'tools': ['read', 'glob', 'grep', 'web_search', 'web_fetch', 'todo'],
        'mcp_servers': [],
        'skills': [],
    }
    assert [unit['id'] for unit in ai['units']] == ['research', 'reporting']


def test_pipeline_units_list_steps_with_review(spec_dict_normal: dict[str, Any]) -> None:
    """Pipeline units list their steps and review gates, other models list none."""
    units = {unit['id']: unit for unit in jinja_context(Spec.model_validate(spec_dict_normal))['ai']['units']}
    steps = [{'member': 'writer', 'review': 'none'}, {'member': 'editor', 'review': 'human'}]
    assert units['reporting']['steps'] == steps
    assert units['research']['steps'] == []
    assert (units['research']['lead'], units['research']['members']) == ('analyst', ['researcher', 'reporting'])
