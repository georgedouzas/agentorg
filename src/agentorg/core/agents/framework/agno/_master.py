"""Production master registration on the AgentField node."""

from agentfield.agent import Agent as AgentFieldNode

from .....master._agent import build_production_master
from ....adapters.agno import append_principles, register_reasoner


def register_master(node: AgentFieldNode, principles_text: str = '') -> str:
    """Register the master agent as the only platform-level reasoner on the node.

    Replaces the legacy `register_platform_agents` - the master subsumes the work of
    Platform/Security/Backend/Frontend/Knowledge/QA Engineer by carrying the full
    interview toolbelt (set_org_identity, agent/team/workflow patches, knowledge tools,
    UI tweaks, request_redeploy).
    """
    agent = build_production_master()
    append_principles(agent, principles_text)
    return register_reasoner(node, agent, tags=['agent', 'master'])
