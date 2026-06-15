"""Tests for the defaults module."""

from agentorg.core.agents.framework.agno.platform import (
    PLATFORM_AGENT_GROUPS,
    PLATFORM_AGENT_ICONS,
    PLATFORM_AGENT_IDS,
    PLATFORM_DEFAULT_MODEL,
)


def test_default_model_is_a_provider_qualified_id():
    """`PLATFORM_DEFAULT_MODEL` is shaped `provider:model`, not bare model id."""
    provider, _, model = PLATFORM_DEFAULT_MODEL.partition(':')
    assert provider, f'no provider prefix in {PLATFORM_DEFAULT_MODEL!r}'
    assert model, f'no model id after provider in {PLATFORM_DEFAULT_MODEL!r}'


def test_every_icon_keys_match_a_platform_agent_id():
    """`PLATFORM_AGENT_ICONS` keys must all be valid platform agent ids — catches typos either side."""
    assert set(PLATFORM_AGENT_ICONS) == PLATFORM_AGENT_IDS


def test_every_group_id_is_a_platform_agent_id():
    """Every id under `PLATFORM_AGENT_GROUPS[i]['ids']` is a valid platform agent id."""
    grouped_ids = {agent_id for group in PLATFORM_AGENT_GROUPS for agent_id in group['ids']}
    assert grouped_ids <= PLATFORM_AGENT_IDS


def test_every_platform_agent_appears_in_a_group():
    """No platform agent is orphaned — each id appears in exactly one group on the dashboard's Platform tab."""
    grouped_ids = [agent_id for group in PLATFORM_AGENT_GROUPS for agent_id in group['ids']]
    assert set(grouped_ids) == PLATFORM_AGENT_IDS, 'every platform agent must be in exactly one group'
    assert len(grouped_ids) == len(set(grouped_ids)), 'no agent should appear in more than one group'


def test_each_group_carries_a_label_and_ids():
    """Each group dict has the `label` (str) and `ids` (tuple) keys the frontend expects."""
    for group in PLATFORM_AGENT_GROUPS:
        assert set(group) == {'label', 'ids'}
        assert isinstance(group['label'], str)
        assert isinstance(group['ids'], tuple)
