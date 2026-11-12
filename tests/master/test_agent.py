"""Tests for the agent module."""

from typing import Any

from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock

from agentorg.master import (
    MASTER_INSTRUCTIONS,
    MASTER_INTRODUCTION,
    MASTER_TOOLS,
    STAGE_TOOLS,
    StageAgent,
    add_or_update_agent,
    add_or_update_trigger,
    agent_for_current_stage,
    finalize_spec,
    get_state,
    set_budget,
    set_org_identity,
    stage_instructions,
    turn_context,
)

from .conftest import ScriptedClient, result_message


def _agent(stage: str, *messages: object) -> StageAgent:
    ScriptedClient.calls = []
    return StageAgent(stage, STAGE_TOOLS[stage], client_factory=lambda options: ScriptedClient(options, list(messages)))


def test_stage_agent_has_only_its_stage_tools() -> None:
    """A stage agent exposes its stage tools through the `stage` server and no built-in tools."""
    options = _agent('build').options()
    assert options.tools == []
    assert 'mcp__stage__add_or_update_agent' in options.allowed_tools
    assert 'mcp__stage__set_budget' not in options.allowed_tools
    assert list(options.mcp_servers) == ['stage']  # type: ignore[arg-type]
    assert options.setting_sources == []


def test_discover_lacks_agent_and_trigger_tools() -> None:
    """Discover cannot add agents or triggers, and only Configure sets the budget."""
    assert add_or_update_agent not in STAGE_TOOLS['discover']
    assert add_or_update_trigger not in STAGE_TOOLS['discover']
    assert [stage for stage, tools in STAGE_TOOLS.items() if set_budget in tools] == ['configure']
    assert set_org_identity in STAGE_TOOLS['configure']
    assert STAGE_TOOLS['handoff'] == [STAGE_TOOLS['handoff'][0], finalize_spec]


async def test_stage_agent_collects_text_and_tool_calls_and_resumes() -> None:
    """A turn returns the assistant text and the tools called, and the next turn resumes the session."""
    turn = [
        AssistantMessage(content=[ToolUseBlock('t1', 'mcp__stage__set_budget', {'monthly_usd': 50})], model='sonnet'),
        AssistantMessage(content=[TextBlock('Budget set.')], model='sonnet'),
        result_message(session_id='sdk-7'),
    ]
    agent = _agent('configure', *turn)
    reply = await agent.arun('Set the budget to 50.')
    assert (reply.content, reply.tool_calls) == ('Budget set.', ['set_budget'])
    assert ScriptedClient.calls[0].prompt.startswith('## Live context')
    assert ScriptedClient.calls[0].prompt.endswith('Set the budget to 50.')
    await agent.arun('Thanks.')
    assert ScriptedClient.calls[1].options.resume == 'sdk-7'


async def test_stage_agent_falls_back_to_next_question_without_text() -> None:
    """A turn that ends without text answers with the next interview question."""
    reply = await _agent('configure', result_message()).arun('Hi')
    assert reply.content.endswith('?')


def test_turn_context_carries_stage_blockers_and_spec_source() -> None:
    """The live context names the stage, its blockers and the working spec source."""
    context = turn_context()
    assert '- stage: discover' in context
    assert 'record_discovery_summary' in context
    assert '"""Spec for Untitled org."""' in context


def test_stage_instructions_describe_units_and_claude_agents() -> None:
    """The Build prompt teaches units, autonomy, MCP servers and sandboxing."""
    build = stage_instructions('build')
    for phrase in ('`pool`', '`council`', 'autonomy', 'MCP servers', 'sandbox_agent'):
        assert phrase in build
    assert 'units' in MASTER_INSTRUCTIONS
    assert 'Build' in MASTER_INTRODUCTION


def test_master_tools_cover_every_stage_tool_once() -> None:
    """MASTER_TOOLS is the union of the stage tools without duplicates."""
    names = [fn.__name__ for fn in MASTER_TOOLS]
    assert len(names) == len(set(names))
    assert {fn.__name__ for tools in STAGE_TOOLS.values() for fn in tools} == set(names)


def test_agent_for_current_stage_follows_the_stage_cursor() -> None:
    """The cached workflow hands out the agent of the current stage."""
    get_state().stage = 'refine'
    agent: Any = agent_for_current_stage()
    assert agent.stage == 'refine'
