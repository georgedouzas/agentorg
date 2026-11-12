"""Tests for the node module."""

import pytest
from agentfield import Agent

from agentorg.core.agents.tools import bind_node, current_node


def test_current_node_falls_back_to_bound_node() -> None:
    """Outside a reasoner execution, tools use the bound node."""
    node = Agent(node_id='acme')
    node._clear_current()
    bind_node(node)
    assert current_node() is node


def test_current_node_without_binding_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without an execution or a binding, the error says how to fix it."""
    monkeypatch.setattr('agentorg.core.agents.tools._node._bound', [])
    monkeypatch.setattr(Agent, 'get_current', classmethod(lambda cls: None))
    with pytest.raises(RuntimeError, match='bind_node'):
        current_node()
