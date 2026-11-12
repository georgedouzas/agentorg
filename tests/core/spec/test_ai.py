"""Tests for ai module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import AI


def _agents(*ids: str, **fields: object) -> list[dict[str, Any]]:
    return [{'id': id_, 'name': id_, 'role': 'Works.', **fields} for id_ in ids]


def test_ai_validates_solo_org(ai_dict_minimal: dict[str, Any]) -> None:
    """A single agent in a solo root unit is a valid org."""
    ai = AI.model_validate(ai_dict_minimal)
    assert ai.root.model == 'solo'
    assert ai.agent('assistant').name == 'Assistant'


def test_ai_validates_nested_org(ai_dict_normal: dict[str, Any]) -> None:
    """A hub over an agent and a nested pipeline validates and resolves paths."""
    ai = AI.model_validate(ai_dict_normal)
    assert [unit.id for unit in ai.path_to('editor')] == ['research', 'reporting']
    assert [unit.id for unit in ai.path_to('analyst')] == ['research']
    assert ai.unit('reporting').model == 'pipeline'


def test_ai_rejects_orphan_agent(ai_dict_minimal: dict[str, Any]) -> None:
    """An agent that is neither a member nor a lead is rejected."""
    ai_dict_minimal['agents'] += _agents('orphan')
    with pytest.raises(ValidationError, match='orphan'):
        AI.model_validate(ai_dict_minimal)


def test_ai_rejects_agent_in_two_units() -> None:
    """The same agent placed twice is rejected."""
    root = {
        'id': 'root',
        'name': 'Root',
        'model': 'hub',
        'lead': 'lead',
        'members': ['a', {'id': 'inner', 'name': 'Inner', 'model': 'solo', 'members': ['a']}],
    }
    with pytest.raises(ValidationError, match='exactly one unit'):
        AI.model_validate({'agents': _agents('lead', 'a'), 'root': root})


def test_ai_rejects_undeclared_member(ai_dict_minimal: dict[str, Any]) -> None:
    """A unit referencing an undeclared agent is rejected."""
    ai_dict_minimal['root']['members'] = ['ghost']
    with pytest.raises(ValidationError, match='ghost'):
        AI.model_validate(ai_dict_minimal)


def test_ai_rejects_agent_unit_id_clash(ai_dict_minimal: dict[str, Any]) -> None:
    """An agent and a unit cannot share an id."""
    ai_dict_minimal['root']['id'] = 'assistant'
    with pytest.raises(ValidationError, match='unique'):
        AI.model_validate(ai_dict_minimal)


def test_ai_rejects_referral_to_unknown_target(ai_dict_minimal: dict[str, Any]) -> None:
    """An out-of-scope referral must name a declared agent or unit."""
    ai_dict_minimal['agents'][0]['persona'] = {'out_of_scope': [{'topic': 'billing', 'refer_to': 'finance'}]}
    with pytest.raises(ValidationError, match='finance'):
        AI.model_validate(ai_dict_minimal)


def test_ai_rejects_majority_council_without_choice_output() -> None:
    """Majority council members must return json with a `choice` field."""
    root = {'id': 'board', 'name': 'Board', 'model': 'council', 'decision': 'majority', 'members': ['a', 'b', 'c']}
    with pytest.raises(ValidationError, match='choice'):
        AI.model_validate({'agents': _agents('a', 'b', 'c'), 'root': root})


def test_ai_accepts_majority_council_with_choice_output() -> None:
    """Members with a `choice` json output satisfy a majority council."""
    output = {'format': 'json', 'json_schema': {'type': 'object', 'properties': {'choice': {'type': 'string'}}}}
    root = {'id': 'board', 'name': 'Board', 'model': 'council', 'decision': 'majority', 'members': ['a', 'b', 'c']}
    assert (
        AI.model_validate({'agents': _agents('a', 'b', 'c', output=output), 'root': root}).root.decision == 'majority'
    )


def test_ai_rejects_unit_budget_above_parent() -> None:
    """A nested unit's budget cannot exceed its parent's."""
    inner = {'id': 'inner', 'name': 'Inner', 'model': 'solo', 'members': ['a'], 'monthly_usd': 200}
    root = {'id': 'root', 'name': 'Root', 'model': 'hub', 'lead': 'lead', 'members': [inner], 'monthly_usd': 100}
    with pytest.raises(ValidationError, match='above its parent'):
        AI.model_validate({'agents': _agents('lead', 'a'), 'root': root})


def test_ai_rejects_tree_deeper_than_six_levels() -> None:
    """Seven levels of nesting exceed the depth limit."""
    unit: dict[str, Any] = {'id': 'u7', 'name': 'U', 'model': 'solo', 'members': ['a']}
    for level in range(6, 0, -1):
        unit = {'id': f'u{level}', 'name': 'U', 'model': 'pipeline', 'members': [unit]}
    with pytest.raises(ValidationError, match='levels deep'):
        AI.model_validate({'agents': _agents('a'), 'root': unit})


def test_ai_validates_four_million_instance_org() -> None:
    """A tree of hubs over 576 pools of 100 agents with 70 replicas each describes over 4 million instances."""
    agents: list[dict[str, Any]] = []

    def build(level: int, prefix: str) -> dict[str, Any]:
        if level == 4:
            members = [f'{prefix}-w{i}' for i in range(100)]
            agents.extend(_agents(*members, replicas=70))
            return {'id': prefix, 'name': prefix, 'model': 'pool', 'members': members}
        lead = f'{prefix}-lead'
        agents.extend(_agents(lead))
        children = [build(level + 1, f'{prefix}-{i}') for i in range(12 if level < 2 else 2)]
        return {'id': prefix, 'name': prefix, 'model': 'hub', 'lead': lead, 'members': children}

    ai = AI.model_validate({'agents': agents, 'root': build(0, 'org')})
    assert ai.root.depth() == 5
    assert sum(agent.replicas for agent in ai.agents) > 4_000_000
    assert max(len(unit.members) for unit in ai.root.iter_units() if unit.model == 'hub') == 12
