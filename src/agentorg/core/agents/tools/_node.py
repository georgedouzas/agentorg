"""Resolve the AgentField node that tools read memory from."""

from agentfield import Agent

_bound: list[Agent] = []


def bind_node(node: Agent) -> None:
    """Make `node` the node tools use when no reasoner execution is current, as for scheduled or webhook runs."""
    _bound[:] = [node]


def current_node() -> Agent:
    """Return the node of the current reasoner execution, else the bound node.

    Returns:
        node: The AgentField node whose memory the tools use.

    Raises:
        RuntimeError: No reasoner is executing and no node was bound.
    """
    node = Agent.get_current() or (_bound[0] if _bound else None)
    if node is None:
        msg = 'Tools need an AgentField node; run them inside a reasoner or call bind_node(node) at startup.'
        raise RuntimeError(msg)
    return node
