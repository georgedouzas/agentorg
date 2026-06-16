"""Tests for the tools module."""

import json

from agentorg.core.agents.framework.agno.platform.frontend_engineer import (
    list_overview_widgets,
    read_ui_config,
)

_UI = {
    'app': {'name': 'Research Org', 'icon': '🔬'},
    'overview': {
        'widgets': [
            {'id': 'recent-reports', 'kind': 'knowledge-list'},
            {'id': 'workflow-status', 'kind': 'progress'},
        ],
    },
}


def test_read_ui_config_returns_pretty_printed_json():
    """The full UI dict round-trips through `json.loads` after pretty-printing."""
    result = read_ui_config(_UI)
    assert json.loads(result) == _UI
    assert '\n' in result, 'expected pretty-printed JSON, got compact'


def test_read_ui_config_returns_empty_object_when_no_ui():
    """Missing UI config returns `{}` rendered as JSON."""
    assert json.loads(read_ui_config()) == {}
    assert json.loads(read_ui_config(None)) == {}


def test_list_overview_widgets_returns_empty_message_when_none_configured():
    """`list_overview_widgets` reports the empty state across missing UI / missing overview / empty widgets."""
    assert list_overview_widgets() == 'No overview widgets configured.'
    assert list_overview_widgets({}) == 'No overview widgets configured.'
    assert list_overview_widgets({'overview': {}}) == 'No overview widgets configured.'
    assert list_overview_widgets({'overview': {'widgets': []}}) == 'No overview widgets configured.'


def test_list_overview_widgets_lists_each_widget_with_id_and_kind():
    """Each widget's id and kind appear in the formatted listing."""
    result = list_overview_widgets(_UI)
    assert 'Overview widgets:' in result
    assert 'recent-reports' in result
    assert 'kind=knowledge-list' in result
    assert 'workflow-status' in result
    assert 'kind=progress' in result
