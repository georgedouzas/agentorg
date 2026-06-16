"""Tests for the agent module."""

from agno.agent import Agent

from agentorg.master import MASTER_INSTRUCTIONS, MASTER_TOOLS, build_master_agent


def test_build_master_agent_returns_a_raw_agno_agent():
    """The master agent is a bare `agno.Agent` (no `make_agent` curation)."""
    agent = build_master_agent()
    assert isinstance(agent, Agent)
    assert agent.id == 'master'


def test_build_master_agent_carries_every_patch_tool():
    """Every entry in `MASTER_TOOLS` reaches the agent's `tools` list verbatim."""
    agent = build_master_agent()
    assert list(agent.tools) == MASTER_TOOLS


def test_master_instructions_reference_the_interview_workflow():
    """The persona instructions cite `list_placeholders` and the Spec-driven workflow."""
    assert 'list_placeholders' in MASTER_INSTRUCTIONS
    assert 'Workflow' in MASTER_INSTRUCTIONS
    assert 'finalize_spec' in MASTER_INSTRUCTIONS


def test_master_tools_include_finalize_and_emit_custom_tool():
    """The lifecycle tools (sandbox emitter + finalizer) are wired in."""
    tool_names = {getattr(t, '__name__', repr(t)) for t in MASTER_TOOLS}
    assert 'emit_custom_tool' in tool_names
    assert 'finalize_spec' in tool_names
    assert 'set_org_identity' in tool_names
