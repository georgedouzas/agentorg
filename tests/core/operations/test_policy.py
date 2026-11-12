"""Tests for the policy module."""

import copy
from typing import Any

import pytest

from agentorg.core.agents.tools import tool
from agentorg.core.operations import approvers_for, classify_tool, decide, effective_autonomy, effective_governed
from agentorg.core.spec import Agent, Spec


@tool('read')
def lookup(order_id: int) -> str:
    """Look up an order."""
    return str(order_id)


@tool(outbound=True)
def send_email(to: str, body: str) -> str:
    """Send an email."""
    return to + body


def update_crm(deal: str) -> str:
    """Update a deal."""
    return deal


def _agent(autonomy: str = 'act') -> Agent:
    server = {
        'name': 'crm',
        'transport': 'http',
        'url': 'https://crm.example',
        'allowed_tools': ['search', 'update', 'reply'],
        'read_tools': ['search'],
        'outbound_tools': ['reply'],
    }
    return Agent.model_validate(
        {
            'id': 'a',
            'name': 'A',
            'role': 'Works.',
            'autonomy': autonomy,
            'tools': [lookup, send_email, update_crm],
            'mcp_servers': [server],
        },
    )


@pytest.mark.parametrize(
    ('tool_name', 'kind', 'action_class'),
    [
        ('Read', 'read', None),
        ('WebFetch', 'read', None),
        ('Write', 'workspace_write', None),
        ('Bash', 'action', 'code_execution'),
        ('mcp__custom__lookup', 'read', None),
        ('mcp__custom__send_email', 'action', 'outbound_message'),
        ('mcp__custom__update_crm', 'action', 'external_write'),
        ('mcp__crm__search', 'read', None),
        ('mcp__crm__update', 'action', 'external_write'),
        ('mcp__crm__reply', 'action', 'outbound_message'),
        ('mcp__crm__delete_everything', 'unknown', None),
        ('mcp__org__delegate', 'org', None),
        ('mcp__org__write_knowledge', 'action', 'knowledge_publish'),
        ('mcp__ghost__x', 'unknown', None),
        ('Task', 'unknown', None),
    ],
)
def test_classify_tool(tool_name: str, kind: str, action_class: str | None) -> None:
    """Built-ins, custom tools, org tools and MCP tools are classified by their declared side effects."""
    tool_class = classify_tool(_agent(), tool_name)
    assert (tool_class.kind, tool_class.action_class) == (kind, action_class)


GOVERNED = ['external_write', 'outbound_message']


@pytest.mark.parametrize(
    ('autonomy', 'tool_name', 'lifecycle', 'verdict'),
    [
        ('read_only', 'Read', 'active', 'allow'),
        ('read_only', 'Write', 'active', 'deny'),
        ('read_only', 'Bash', 'active', 'deny'),
        ('read_only', 'mcp__crm__update', 'active', 'deny'),
        ('propose', 'Write', 'active', 'allow'),
        ('propose', 'Bash', 'active', 'hold'),
        ('propose', 'mcp__crm__update', 'active', 'hold'),
        ('act', 'Bash', 'active', 'allow'),
        ('act', 'mcp__crm__update', 'active', 'hold'),
        ('act', 'mcp__org__write_knowledge', 'active', 'allow'),
        ('autonomous', 'mcp__crm__reply', 'active', 'hold'),
        ('autonomous', 'Bash', 'active', 'allow'),
        ('autonomous', 'Bash', 'trial', 'hold'),
        ('autonomous', 'mcp__org__write_knowledge', 'trial', 'hold'),
        ('autonomous', 'Write', 'trial', 'allow'),
        ('autonomous', 'Write', 'draft', 'deny'),
        ('autonomous', 'Read', 'draft', 'allow'),
        ('act', 'mcp__org__delegate', 'trial', 'allow'),
        ('act', 'mcp__crm__delete_everything', 'active', 'deny'),
    ],
)
def test_decide_combines_autonomy_governance_and_lifecycle(
    autonomy: str,
    tool_name: str,
    lifecycle: str,
    verdict: str,
) -> None:
    """Every autonomy level against reads, writes, actions and lifecycle states."""
    decision = decide(
        _agent(autonomy),
        tool_name,
        autonomy=autonomy,  # type: ignore[arg-type]
        governed=GOVERNED,  # type: ignore[arg-type]
        lifecycle=lifecycle,  # type: ignore[arg-type]
        preview=False,
    )
    assert decision.verdict == verdict


def test_decide_hold_names_the_action_class() -> None:
    """A held call carries the action class the approver decides on."""
    decision = decide(_agent(), 'mcp__crm__reply', autonomy='act', governed=GOVERNED, lifecycle='active', preview=False)  # type: ignore[arg-type]
    assert (decision.verdict, decision.action_class) == ('hold', 'outbound_message')


def test_decide_denies_actions_in_preview_with_a_reason() -> None:
    """In preview, consequential actions are denied with a message stating preview mode."""
    decision = decide(
        _agent('autonomous'),
        'Bash',
        autonomy='autonomous',
        governed=[],
        lifecycle='active',
        preview=True,
    )
    assert decision.verdict == 'deny'
    assert 'preview mode' in decision.reason


def test_decide_denies_unknown_tool_with_a_reason() -> None:
    """A tool the agent does not have is denied with a message the agent can read."""
    decision = decide(_agent(), 'Task', autonomy='act', governed=[], lifecycle='active', preview=False)
    assert (decision.verdict, decision.reason) == ('deny', 'Task is not one of your tools.')


def _scoped_spec(spec_dict_minimal: dict[str, Any], inner: dict[str, Any]) -> Spec:
    spec_dict_minimal['ai'] = {
        'agents': [
            {'id': 'lead', 'name': 'Lead', 'role': 'Leads.'},
            {'id': 'trader', 'name': 'Trader', 'role': 'Trades.', 'autonomy': 'autonomous'},
        ],
        'root': {
            'id': 'org',
            'name': 'Org',
            'model': 'hub',
            'lead': 'lead',
            'owners': ['ceo@acme.com'],
            'approval_required': ['spend'],
            'members': [{'id': 'desk', 'name': 'Desk', 'model': 'solo', 'members': ['trader'], **inner}],
        },
    }
    return Spec.model_validate(spec_dict_minimal)


def test_effective_autonomy_is_capped_by_unit(spec_dict_minimal: dict[str, Any]) -> None:
    """An autonomous agent in a unit capped at propose runs as propose."""
    spec = _scoped_spec(spec_dict_minimal, {'max_autonomy': 'propose'})
    assert effective_autonomy(spec, 'trader') == 'propose'
    assert effective_autonomy(_scoped_spec(spec_dict_minimal, {}), 'trader') == 'autonomous'


def test_effective_governed_only_adds_classes(spec_dict_minimal: dict[str, Any]) -> None:
    """A nested unit that omits a parent's class still governs it, and its own additions apply too."""
    spec = _scoped_spec(spec_dict_minimal, {'approval_required': ['code_execution']})
    assert effective_governed(spec, 'trader') == {'external_write', 'outbound_message', 'spend', 'code_execution'}


def test_approvers_for_prefers_nearest_unit_owners(spec_dict_minimal: dict[str, Any]) -> None:
    """Approvals go to the nearest owners up the tree, then the org approvers, then the admin."""
    plain = Spec.model_validate(copy.deepcopy(spec_dict_minimal))
    assert approvers_for(_scoped_spec(spec_dict_minimal, {'owners': ['desk@acme.com']}), 'trader') == ['desk@acme.com']
    assert approvers_for(_scoped_spec(spec_dict_minimal, {}), 'trader') == ['ceo@acme.com']
    assert approvers_for(plain, 'assistant') == ['']
