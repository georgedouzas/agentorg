"""Tests for ui module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import UI, AgentConfigUI, AppUI, EmptyState, GroupRef, OverviewBlock

APP: dict[str, str] = {'name': 'Org', 'icon': '🔬', 'description': 'A research org.'}
EMPTY_STATE: dict[str, str] = {'icon': '🔬', 'title': 'Pick an agent', 'body': 'Try the pipeline.'}
GROUP: dict[str, Any] = {'label': 'Research Team', 'ids': ['researcher', 'analyst']}
AGENT_CONFIG: dict[str, Any] = {
    'model': 'google:gemini-2.5-flash',
    'description': 'Gathers sources.',
    'tools': ['search'],
    'features': [],
}
OVERVIEW_BLOCK: dict[str, str] = {'title': 'Mission', 'body': 'We **publish** structured analysis.'}
UI_FIELDS: dict[str, Any] = {
    'app': APP,
    'empty_state': EMPTY_STATE,
    'knowledge_empty': 'No knowledge yet.',
    'agent_groups': [GROUP],
    'workflow_groups': [],
    'featured_agents': ['analyst'],
    'agent_icons': {'researcher': '📚'},
    'overview': [OVERVIEW_BLOCK],
    'agent_configs': {'researcher': AGENT_CONFIG},
    'chat_quick_prompts': {'researcher': ['Summarise the topic']},
}


def test_app_ui_fields() -> None:
    """`AppUI` is name plus icon plus description."""
    assert AppUI(**APP).name == 'Org'


def test_group_ref_fields() -> None:
    """`GroupRef` is a label plus the ids it groups."""
    group = GroupRef(**GROUP)
    assert group.label == 'Research Team'
    assert group.ids == ['researcher', 'analyst']


def test_agent_config_ui_fields() -> None:
    """`AgentConfigUI` carries model, description, tools, and features."""
    config = AgentConfigUI(**AGENT_CONFIG)
    assert config.tools == ['search']
    assert config.features == []


def test_overview_block_fields() -> None:
    """`OverviewBlock` is a markdown card with a title and body."""
    block = OverviewBlock(**OVERVIEW_BLOCK)
    assert block.title == 'Mission'
    assert '**publish**' in block.body


@pytest.mark.parametrize(
    ('model', 'sample'),
    [
        (AppUI, APP),
        (EmptyState, EMPTY_STATE),
        (GroupRef, GROUP),
        (OverviewBlock, OVERVIEW_BLOCK),
    ],
)
def test_sub_model_fields_required(model: type, sample: dict[str, object]) -> None:
    """Every field on the UI sub-models is required."""
    for missing in sample:
        with pytest.raises(ValidationError):
            model(**{k: v for k, v in sample.items() if k != missing})


def test_ui_construction() -> None:
    """`UI` coerces nested dicts into AppUI, EmptyState, GroupRef, OverviewBlock, AgentConfigUI."""
    ui = UI.model_validate(UI_FIELDS)
    assert ui.app.name == 'Org'
    assert ui.knowledge_empty == 'No knowledge yet.'
    assert ui.agent_groups[0].label == 'Research Team'
    assert ui.overview[0].title == 'Mission'
    assert ui.agent_configs['researcher'].model == 'google:gemini-2.5-flash'
    assert ui.chat_quick_prompts['researcher'] == ['Summarise the topic']


def test_ui_accepts_empty_overview() -> None:
    """An empty `overview` list is the common case, the default panels still render."""
    ui = UI.model_validate({**UI_FIELDS, 'overview': []})
    assert ui.overview == []


@pytest.mark.parametrize('missing', list(UI_FIELDS))
def test_ui_fields_required(missing: str) -> None:
    """Every `UI` field is required, empty collections are allowed, omission is not."""
    with pytest.raises(ValidationError):
        UI.model_validate({k: v for k, v in UI_FIELDS.items() if k != missing})
