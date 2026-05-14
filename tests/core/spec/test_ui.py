"""Tests for `agentorg.core.spec._ui` — UI and its sub-models."""

import pytest
from pydantic import ValidationError

from agentorg.core.spec import UI, AgentConfigUI, AppUI, EmptyState, GroupRef, KnowledgeEmpty

APP = {'name': 'Org', 'icon': '🔬', 'description': 'A research org.'}
EMPTY_STATE = {'icon': '🔬', 'title': 'Pick an agent', 'body': 'Try the pipeline.'}
KNOWLEDGE_EMPTY = {'documents': 'No documents yet.', 'learnings': 'No learnings yet.'}
GROUP = {'label': 'Research Team', 'ids': ['researcher', 'analyst']}
AGENT_CONFIG = {
    'model': 'google:gemini-2.0-flash',
    'description': 'Gathers sources.',
    'tools': ['search'],
    'features': [],
}
UI_FIELDS = {
    'app': APP,
    'empty_state': EMPTY_STATE,
    'knowledge_empty': KNOWLEDGE_EMPTY,
    'agent_groups': [GROUP],
    'workflow_groups': [],
    'featured_agents': ['analyst'],
    'agent_icons': {'researcher': '📚'},
    'overview': {},
    'agent_configs': {'researcher': AGENT_CONFIG},
    'chat_quick_prompts': {'researcher': ['Summarise the topic']},
}


# ── Sub-models ───────────────────────────────────────────────────────────────


def test_app_ui_fields() -> None:
    """`AppUI` is name + icon + description."""
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


@pytest.mark.parametrize(
    ('model', 'sample'),
    [(AppUI, APP), (EmptyState, EMPTY_STATE), (KnowledgeEmpty, KNOWLEDGE_EMPTY), (GroupRef, GROUP)],
)
def test_sub_model_fields_required(model: type, sample: dict[str, object]) -> None:
    """Every field on the UI sub-models is required."""
    for missing in sample:
        with pytest.raises(ValidationError):
            model(**{k: v for k, v in sample.items() if k != missing})


# ── UI ───────────────────────────────────────────────────────────────────────


def test_ui_construction() -> None:
    """`UI` coerces nested dicts into AppUI / EmptyState / GroupRef / AgentConfigUI."""
    ui = UI.model_validate(UI_FIELDS)
    assert ui.app.name == 'Org'
    assert ui.agent_groups[0].label == 'Research Team'
    assert ui.agent_configs['researcher'].model == 'google:gemini-2.0-flash'
    assert ui.chat_quick_prompts['researcher'] == ['Summarise the topic']


@pytest.mark.parametrize('missing', list(UI_FIELDS))
def test_ui_fields_required(missing: str) -> None:
    """Every `UI` field is required — empty collections are allowed, omission is not."""
    with pytest.raises(ValidationError):
        UI.model_validate({k: v for k, v in UI_FIELDS.items() if k != missing})
