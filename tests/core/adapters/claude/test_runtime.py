"""Tests for the runtime module."""

from typing import Any

from agentfield.agent import Agent as AgentFieldNode

from agentorg.core.adapters.claude import register_org
from agentorg.core.agents.tools import tool
from agentorg.core.spec import Spec


@tool('read', tags=('crm',))
def lookup_order(order_id: int) -> str:
    """Look up an order."""
    return str(order_id)


async def _master(message: str) -> dict[str, Any]:
    return {'output': message}


def _spec(spec_dict_normal: dict[str, Any]) -> Spec:
    for agent in spec_dict_normal['ai']['agents'][:2]:
        agent['tools'] = [lookup_order]
    return Spec.model_validate(spec_dict_normal)


def test_register_org_tags_agents_units_and_master(spec_dict_normal: dict[str, Any]) -> None:
    """Agents carry `agent`, units carry `unit` and their model, the master carries `master`, all with the org slug."""
    node = AgentFieldNode(node_id='acme-org')
    calls: list[tuple[str, str, str | None, str]] = []

    async def run_target(target_id: str, message: str, session_id: str | None, user_id: str) -> dict[str, Any]:
        calls.append((target_id, message, session_id, user_id))
        return {'output': 'ok'}

    names = register_org(node, _spec(spec_dict_normal), run_target, master=_master)
    tags = {reasoner['id']: reasoner['tags'] for reasoner in node.reasoners}
    assert names == ['analyst', 'researcher', 'writer', 'editor', 'research', 'reporting', 'master']
    assert tags['researcher'] == ['agent', 'acme-org']
    assert tags['reporting'] == ['unit', 'pipeline', 'acme-org']
    assert tags['master'] == ['agent', 'master', 'acme-org']


def test_register_org_registers_each_custom_tool_once(spec_dict_normal: dict[str, Any]) -> None:
    """A tool shared by two agents becomes one node skill with its tags."""
    node = AgentFieldNode(node_id='acme-org')

    async def run_target(*_: object) -> dict[str, Any]:
        return {}

    register_org(node, _spec(spec_dict_normal), run_target)
    assert [(skill['id'], skill['tags']) for skill in node.skills] == [('lookup_order', ['crm'])]


async def test_register_org_reasoner_forwards_to_run_target(spec_dict_normal: dict[str, Any]) -> None:
    """Calling a registered reasoner starts a run of that target through the operations entry point."""
    node = AgentFieldNode(node_id='acme-org')
    calls: list[tuple[str, str, str | None, str]] = []

    async def run_target(target_id: str, message: str, session_id: str | None, user_id: str) -> dict[str, Any]:
        calls.append((target_id, message, session_id, user_id))
        return {'output': 'done'}

    register_org(node, _spec(spec_dict_normal), run_target)
    reasoner = node._reasoner_registry['research']
    result = await reasoner.func('Plan the week', session_id='s-1', user_id='ana')
    assert result == {'output': 'done'}
    assert calls == [('research', 'Plan the week', 's-1', 'ana')]
