"""Tests for the tools module."""

import json

from agentorg.core.agents.framework.agno.platform._backend_engineer._tools import (
    list_agent_ids,
    read_agent_spec,
)

_RESEARCHER = {'id': 'researcher', 'name': 'Researcher', 'role': 'Gather sources.'}
_ANALYST = {'id': 'analyst', 'name': 'Analyst', 'role': 'Synthesise findings.'}


def test_list_agent_ids_returns_empty_message_when_no_agents():
    """Without a spec, `list_agent_ids` reports the empty state, not a blank string."""
    assert list_agent_ids() == 'No agents in spec.'
    assert list_agent_ids(None) == 'No agents in spec.'
    assert list_agent_ids([]) == 'No agents in spec.'


def test_list_agent_ids_lists_every_id_under_a_header():
    """Each spec agent's id appears on its own line, prefixed by `  - `."""
    listing = list_agent_ids([_RESEARCHER, _ANALYST])
    assert listing == 'Registered agents:\n  - researcher\n  - analyst'


def test_read_agent_spec_returns_not_found_when_id_is_unknown():
    """An unknown id returns the not-found message — quoted exactly as `{id!r}`."""
    assert read_agent_spec('missing', [_RESEARCHER]) == "No such agent: 'missing'."


def test_read_agent_spec_returns_pretty_printed_json_for_a_hit():
    """A found agent is serialised back with indent=2 — round-trips through `json.loads`."""
    result = read_agent_spec('researcher', [_RESEARCHER, _ANALYST])
    assert json.loads(result) == _RESEARCHER
    assert '\n' in result, 'expected pretty-printed JSON, got compact'


def test_read_agent_spec_returns_not_found_when_spec_is_empty():
    """A missing or empty spec list still surfaces the not-found message rather than crashing."""
    assert read_agent_spec('researcher') == "No such agent: 'researcher'."
    assert read_agent_spec('researcher', None) == "No such agent: 'researcher'."
    assert read_agent_spec('researcher', []) == "No such agent: 'researcher'."
