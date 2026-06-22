"""Tests for ui module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import UI, AgentConfigUI, AppUI, EmptyState, GroupRef, OverviewBlock


def test_app_ui_fields(ui_dict_normal: dict[str, Any]) -> None:
    """AppUI is name + icon + description."""
    assert AppUI(**ui_dict_normal['app']).name == 'Org'


def test_group_ref_fields(ui_dict_normal: dict[str, Any]) -> None:
    """GroupRef is a label + the ids it groups."""
    group = GroupRef(**ui_dict_normal['agent_groups'][0])
    assert group.label == 'Research Team'
    assert group.ids == ['researcher', 'analyst']


def test_agent_config_ui_fields(ui_dict_normal: dict[str, Any]) -> None:
    """AgentConfigUI carries model, description, tools, and features."""
    config = AgentConfigUI(**ui_dict_normal['agent_configs']['researcher'])
    assert config.tools == ['search']
    assert config.features == []


def test_overview_block_fields(ui_dict_normal: dict[str, Any]) -> None:
    """OverviewBlock is a markdown card with title + body."""
    block = OverviewBlock(**ui_dict_normal['overview'][0])
    assert block.title == 'Mission'
    assert '**publish**' in block.body


def test_sub_model_fields_required(ui_dict_normal: dict[str, Any]) -> None:
    """Every field on the UI sub-models is required."""
    samples: list[tuple[type, dict[str, Any]]] = [
        (AppUI, ui_dict_normal['app']),
        (EmptyState, ui_dict_normal['empty_state']),
        (GroupRef, ui_dict_normal['agent_groups'][0]),
        (OverviewBlock, ui_dict_normal['overview'][0]),
    ]
    for model, sample in samples:
        for missing in sample:
            with pytest.raises(ValidationError):
                model(**{k: v for k, v in sample.items() if k != missing})


def test_ui_construction(ui_dict_normal: dict[str, Any]) -> None:
    """UI coerces nested dicts into AppUI, EmptyState, GroupRef, OverviewBlock, AgentConfigUI."""
    ui = UI.model_validate(ui_dict_normal)
    assert ui.app.name == 'Org'
    assert ui.agent_groups[0].label == 'Research Team'
    assert ui.overview[0].title == 'Mission'
    assert ui.agent_configs['researcher'].model == 'google:gemini-2.5-flash'
    assert ui.chat_quick_prompts['researcher'] == ['Summarise the topic']


def test_ui_accepts_empty_overview(ui_dict_minimal: dict[str, Any]) -> None:
    """An empty overview list is the common case."""
    assert UI.model_validate(ui_dict_minimal).overview == []


@pytest.mark.parametrize(
    'missing',
    [
        'app',
        'empty_state',
        'knowledge_empty',
        'agent_groups',
        'workflow_groups',
        'featured_agents',
        'agent_icons',
        'overview',
        'agent_configs',
        'chat_quick_prompts',
    ],
)
def test_ui_fields_required(ui_dict_minimal: dict[str, Any], missing: str) -> None:
    """Every UI field is required."""
    del ui_dict_minimal[missing]
    with pytest.raises(ValidationError):
        UI.model_validate(ui_dict_minimal)
