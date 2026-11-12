"""Tests for the agent sandbox module."""

from typing import Any

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, ToolUseBlock

from agentorg.master import get_state, sandbox_agent, sandbox_run

from .conftest import ScriptedClient, build_hub_org, result_message


def _factory(options: ClaudeAgentOptions) -> ScriptedClient:
    turn = [
        AssistantMessage(content=[ToolUseBlock('t1', 'WebSearch', {'q': 'x'}), TextBlock('Found it.')], model='sonnet'),
        result_message(result='Found it.', total_cost_usd=0.02),
    ]
    return ScriptedClient(options, turn)


async def test_sandbox_run_reports_output_tools_and_cost() -> None:
    """Each prompt's status, tool calls, cost and output are reported."""
    build_hub_org()
    report = await sandbox_run(
        get_state().spec,
        'researcher',
        ['Find sources', 'Out of scope?'],
        client_factory=_factory,
    )
    assert report.count('### Prompt') == 2
    assert '**Status:** succeeded · **Cost:** 0.0200 USD' in report
    assert '**Tools called:** WebSearch' in report
    assert 'Found it.' in report


async def test_sandbox_run_runs_in_preview_mode() -> None:
    """The sandboxed agent runs without a broker, with consequential actions denied by preview mode."""
    build_hub_org()
    seen: list[Any] = []

    def factory(options: ClaudeAgentOptions) -> ScriptedClient:
        seen.append(options)
        return _factory(options)

    await sandbox_run(get_state().spec, 'researcher', ['Go'], client_factory=factory)
    assert seen[0].model == 'sonnet'


async def test_sandbox_agent_explains_missing_agent_and_prompts() -> None:
    """The tool answers with guidance for an unknown agent, missing prompts or an incomplete structure."""
    assert 'Finish the org structure' not in await sandbox_agent(agent_id='ghost', test_prompts=['x'])
    assert "No agent named 'ghost'" in await sandbox_agent(agent_id='ghost', test_prompts=['x'])
    build_hub_org()
    assert 'at least one test prompt' in await sandbox_agent(agent_id='researcher', test_prompts=[])
    get_state().structure_error = 'hub needs a lead'
    assert 'Finish the org structure' in await sandbox_agent(agent_id='researcher', test_prompts=['x'])
