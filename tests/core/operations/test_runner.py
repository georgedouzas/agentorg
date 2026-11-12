"""Tests for the runner module."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    TextBlock,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from agentorg.core.operations import Run, Runner, Store
from agentorg.core.spec import Agent, Spec

from .conftest import FakeClient, Script, result_message, scripted


class FakeGate:
    """Allows everything except the tool names it was told to deny."""

    def __init__(self, deny: tuple[str, ...] = ()) -> None:
        """Keep the tool names to deny."""
        self.deny = deny
        self.calls: list[str] = []

    async def check(self, agent: Agent, run: Run, tool_name: str, tool_input: dict[str, Any]) -> PermissionResult:
        """Deny the configured tools and allow the rest."""
        self.calls.append(tool_name)
        if tool_name in self.deny:
            return PermissionResultDeny(message=f'{tool_name} denied')
        return PermissionResultAllow()


@pytest.fixture
def spec(spec_dict_minimal: dict[str, Any]) -> Spec:
    """A solo org whose agent files its output as a report."""
    spec_dict_minimal['knowledge']['types'] = [{'id': 'report', 'label': 'Reports', 'metadata_fields': []}]
    spec_dict_minimal['ai']['agents'][0]['output'] = {'knowledge_type': 'report'}
    return Spec.model_validate(spec_dict_minimal)


def _runner(
    spec: Spec,
    store: Store,
    tmp_path: Path,
    script: Script,
    gate: FakeGate | None = None,
    **kwargs: Any,
) -> Runner:
    FakeClient.opened = []
    return Runner(
        spec,
        store,
        workspace_root=tmp_path / 'ws',
        skills_dir=tmp_path / 'skills',
        gate=gate or FakeGate(),
        org_tools=lambda agent, run: [],
        client_factory=lambda options: FakeClient(options, script),
        **kwargs,
    )


async def _claimed(store: Store, **fields: Any) -> Run:
    run = await store.create_run(target='assistant', trigger_kind='manual', prompt='Write the report.', **fields)
    await store.claim(run.id, 'w1')
    return run


async def test_runner_records_success_cost_and_stream(spec: Spec, store: Store, tmp_path: Path) -> None:
    """A successful run stores its output, cost and transcript, streams events and files its output."""
    filed: list[str] = []

    async def file_output(agent: Agent, run: Run, output: str) -> None:
        filed.append(output)

    script = scripted(
        AssistantMessage(content=[TextBlock('Working'), ToolUseBlock('t1', 'WebSearch', {'q': 'x'})], model='sonnet'),
        UserMessage(content=[ToolResultBlock('t1', [{'type': 'text', 'text': 'results'}], False)]),
        result_message(total_cost_usd=0.03, usage={'input_tokens': 120, 'output_tokens': 45}),
    )
    runner = _runner(spec, store, tmp_path, script, file_output=file_output)
    run = await _claimed(store)
    events = runner.subscribe(run.id)
    await runner.execute(run)
    stored = await store.get_run(run.id)
    assert stored is not None
    assert (stored.status, stored.output, stored.cost_usd, stored.input_tokens, stored.output_tokens) == (
        'succeeded',
        'Done.',
        0.03,
        120,
        45,
    )
    streamed = [events.get_nowait()['type'] for _ in range(events.qsize())]
    assert streamed == ['status', 'text', 'tool_call', 'tool_result', 'end']
    assert [event['type'] for event in stored.transcript] == ['text', 'tool_call', 'tool_result']
    assert filed == ['Done.']
    assert FakeClient.opened[0].prompt == 'Write the report.'


@pytest.mark.parametrize(
    ('subtype', 'reason'),
    [('error_max_turns', 'max_turns'), ('error_max_budget_usd', 'max_run_usd'), ('error_during_execution', 'error')],
)
async def test_runner_names_the_limit_hit(spec: Spec, store: Store, tmp_path: Path, subtype: str, reason: str) -> None:
    """An SDK error result fails the run with the matching reason and files nothing."""
    run = await _claimed(store)
    await _runner(spec, store, tmp_path, scripted(result_message(subtype, is_error=True))).execute(run)
    stored = await store.get_run(run.id)
    assert (stored.status, stored.failure_reason) == ('failed', reason)  # type: ignore[union-attr]


async def test_runner_fails_on_timeout(spec_dict_minimal: dict[str, Any], store: Store, tmp_path: Path) -> None:
    """A run exceeding `timeout_s` fails with reason `timeout`."""
    spec_dict_minimal['ai']['agents'][0]['limits'] = {'timeout_s': 1}
    spec = Spec.model_validate(spec_dict_minimal)

    async def slow(_: ClaudeAgentOptions) -> AsyncIterator[object]:
        await asyncio.sleep(5)
        yield result_message()

    run = await _claimed(store)
    await _runner(spec, store, tmp_path, slow).execute(run)
    assert (await store.get_run(run.id)).failure_reason == 'timeout'  # type: ignore[union-attr]


async def test_runner_returns_denial_to_agent_as_toolresult_message(spec: Spec, store: Store, tmp_path: Path) -> None:
    """A denied tool call reaches the agent as an error tool result and the run continues to success."""

    async def tries_bash(options: ClaudeAgentOptions) -> AsyncIterator[object]:
        assert options.can_use_tool is not None
        permission = await options.can_use_tool('Bash', {'command': 'ls'}, ToolPermissionContext())
        yield AssistantMessage(content=[ToolUseBlock('t1', 'Bash', {'command': 'ls'})], model='sonnet')
        message = permission.message if isinstance(permission, PermissionResultDeny) else ''
        yield UserMessage(content=[ToolResultBlock('t1', message, True)])
        yield result_message()

    gate = FakeGate(deny=('Bash',))
    run = await _claimed(store)
    await _runner(spec, store, tmp_path, tries_bash, gate).execute(run)
    stored = await store.get_run(run.id)
    assert stored.status == 'succeeded'  # type: ignore[union-attr]
    assert gate.calls == ['Bash']
    assert stored.transcript[-1] == {'type': 'tool_result', 'id': 't1', 'is_error': True, 'text': 'Bash denied'}  # type: ignore[union-attr]


@pytest.mark.parametrize(('structured', 'status'), [({'choice': 'approve'}, 'succeeded'), ({'choice': 7}, 'failed')])
async def test_runner_validates_json_output(
    spec_dict_minimal: dict[str, Any],
    store: Store,
    tmp_path: Path,
    structured: dict[str, object],
    status: str,
) -> None:
    """JSON output is checked against the agent's schema."""
    schema = {'type': 'object', 'properties': {'choice': {'type': 'string'}}, 'required': ['choice']}
    spec_dict_minimal['ai']['agents'][0]['output'] = {'format': 'json', 'json_schema': schema}
    spec = Spec.model_validate(spec_dict_minimal)
    run = await _claimed(store)
    await _runner(spec, store, tmp_path, scripted(result_message(structured_output=structured))).execute(run)
    stored = await store.get_run(run.id)
    assert (stored.status, stored.output) == (status, structured)  # type: ignore[union-attr]


async def test_runner_resumes_session(spec: Spec, store: Store, tmp_path: Path) -> None:
    """A second run in the same session resumes the SDK session of the first."""
    runner = _runner(spec, store, tmp_path, scripted(result_message(session_id='sdk-42')))
    await runner.execute(await _claimed(store, session_id='chat-1'))
    await runner.execute(await _claimed(store, session_id='chat-1'))
    assert [client.options.resume for client in FakeClient.opened] == [None, 'sdk-42']


async def test_runner_removes_ephemeral_workspace(spec: Spec, store: Store, tmp_path: Path) -> None:
    """The ephemeral workspace exists during the run and is removed afterwards."""
    seen: list[bool] = []

    async def script(options: ClaudeAgentOptions) -> AsyncIterator[object]:
        seen.append(Path(str(options.cwd)).is_dir())
        yield result_message()

    run = await _claimed(store)
    await _runner(spec, store, tmp_path, script).execute(run)
    assert seen == [True]
    assert not (tmp_path / 'ws' / 'runs' / run.id).exists()
