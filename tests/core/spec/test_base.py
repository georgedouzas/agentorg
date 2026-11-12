"""Tests for the base module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import Spec


def test_spec_round_trips_minimal(spec_dict_minimal: dict[str, Any]) -> None:
    """A Spec assembled from minimal dicts round-trips."""
    spec = Spec.model_validate(spec_dict_minimal)
    assert spec.org.slug == 'acme'
    assert spec.runtime.infra.packaging == 'none'
    assert spec.ai.root.model == 'solo'
    assert spec.operations.budget.monthly_usd is None
    assert spec.parameters == []
    assert spec.knowledge.principles.sections == []
    assert spec.ui.app.name == 'Acme'


def test_spec_round_trips_normal(spec_dict_normal: dict[str, Any]) -> None:
    """A Spec assembled from populated dicts round-trips."""
    spec = Spec.model_validate(spec_dict_normal)
    assert spec.org.slug == 'acme-org'
    assert spec.runtime.infra.packaging == 'docker'
    assert spec.parameters[0].name == 'min_sources'
    assert spec.knowledge.principles.sections[0].id == 'mission'
    assert spec.ui.featured_agents == ['analyst']


@pytest.mark.parametrize('missing', ['org', 'runtime', 'ai', 'operations', 'parameters', 'knowledge', 'ui'])
def test_top_level_fields_are_all_required(spec_dict_minimal: dict[str, Any], missing: str) -> None:
    """Every top-level field is required."""
    del spec_dict_minimal[missing]
    with pytest.raises(ValidationError):
        Spec.model_validate(spec_dict_minimal)


@pytest.mark.parametrize(
    'archetype',
    ['support-desk', 'research-reporting', 'ops-monitoring', 'content-pipeline', 'credit-decisions'],
)
def test_spec_validates_archetype(archetype_specs: dict[str, dict[str, Any]], archetype: str) -> None:
    """Each archetype org is expressible with the shipped models."""
    spec = Spec.model_validate(archetype_specs[archetype])
    assert spec.org.slug == archetype


def _with_trigger(spec_dict: dict[str, Any], **trigger: Any) -> dict[str, Any]:
    base = {'kind': 'schedule', 'id': 't', 'target': 'assistant', 'prompt': 'Go.', 'cron': '0 * * * *'}
    spec_dict['operations'] = {'triggers': [{**base, **trigger}]}
    return spec_dict


def test_spec_rejects_trigger_with_unknown_target(spec_dict_minimal: dict[str, Any]) -> None:
    """A trigger must target a declared agent or unit."""
    with pytest.raises(ValidationError, match='not declared agents or units'):
        Spec.model_validate(_with_trigger(spec_dict_minimal, target='ghost'))


def test_spec_rejects_prompt_with_unknown_variable(spec_dict_minimal: dict[str, Any]) -> None:
    """A trigger prompt may only use trigger variables and parameter names."""
    with pytest.raises(ValidationError, match='customer_name'):
        Spec.model_validate(_with_trigger(spec_dict_minimal, prompt='Hello {customer_name}'))


def test_spec_rejects_undeclared_webhook_secret(spec_dict_minimal: dict[str, Any]) -> None:
    """A webhook secret must be a declared env var."""
    trigger = {'kind': 'webhook', 'secret_env': 'HOOK_SECRET'}
    with pytest.raises(ValidationError, match='HOOK_SECRET'):
        Spec.model_validate(_with_trigger(spec_dict_minimal, **trigger))


def test_spec_rejects_undeclared_mcp_env(spec_dict_minimal: dict[str, Any]) -> None:
    """MCP server env names must be declared env vars."""
    server = {'name': 'crm', 'transport': 'http', 'url': 'https://crm.example', 'env': ['CRM_TOKEN']}
    spec_dict_minimal['ai']['agents'][0]['mcp_servers'] = [server]
    with pytest.raises(ValidationError, match='CRM_TOKEN'):
        Spec.model_validate(spec_dict_minimal)


def test_spec_rejects_unknown_output_knowledge_type(spec_dict_minimal: dict[str, Any]) -> None:
    """An agent's output knowledge type must be declared."""
    spec_dict_minimal['ai']['agents'][0]['output'] = {'knowledge_type': 'report'}
    with pytest.raises(ValidationError, match='knowledge types'):
        Spec.model_validate(spec_dict_minimal)


def test_spec_rejects_unknown_fallback_agent(spec_dict_minimal: dict[str, Any]) -> None:
    """The failure fallback agent must be declared."""
    spec_dict_minimal['operations'] = {'runs': {'on_failure': 'handoff', 'fallback_agent': 'ghost'}}
    with pytest.raises(ValidationError, match='fallback_agent'):
        Spec.model_validate(spec_dict_minimal)
