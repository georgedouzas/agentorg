"""Execute one agent run on the Claude Agent SDK and record its outcome."""

import asyncio
import shutil
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Any, Protocol

import jsonschema
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResult,
    ResultMessage,
    TextBlock,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from ..adapters.claude import build_agent_options, resolve_workspace
from ..spec import Agent, Spec
from ._store import Run, RunStatus, Store

FAILURE_REASONS = {
    'error_max_turns': 'max_turns',
    'error_max_budget_usd': 'max_run_usd',
    'error_during_execution': 'error',
}


class SdkClient(Protocol):
    """The part of `ClaudeSDKClient` the runner uses."""

    async def query(self, prompt: str) -> None:
        """Send the run's prompt."""
        ...

    def receive_response(self) -> Any:  # noqa: ANN401
        """Yield messages until the result message."""
        ...


class PermissionGate(Protocol):
    """Decide a tool call of `agent` within `run`."""

    async def check(self, agent: Agent, run: Run, tool_name: str, tool_input: dict[str, Any]) -> PermissionResult:
        """Return the SDK permission result for one tool call."""
        ...


ClientFactory = Callable[[ClaudeAgentOptions], AbstractAsyncContextManager[SdkClient]]
OrgTools = Callable[[Agent, Run], list[Callable[..., Any]]]
OutputFiler = Callable[[Agent, Run, str], Awaitable[None]]


def _content_text(content: object) -> str:
    """Return the text of a tool result content."""
    if isinstance(content, list):
        return ''.join(str(item.get('text', '')) for item in content if isinstance(item, dict))
    return '' if content is None else str(content)


def _events(message: object) -> list[dict[str, Any]]:
    """Return the stream events carried by one SDK message."""
    if isinstance(message, AssistantMessage):
        events: list[dict[str, Any]] = []
        for block in message.content:
            if isinstance(block, TextBlock):
                events.append({'type': 'text', 'text': block.text})
            elif isinstance(block, ToolUseBlock):
                events.append({'type': 'tool_call', 'id': block.id, 'name': block.name, 'input': block.input})
        return events
    if isinstance(message, UserMessage) and isinstance(message.content, list):
        return [
            {
                'type': 'tool_result',
                'id': block.tool_use_id,
                'is_error': bool(block.is_error),
                'text': _content_text(block.content),
            }
            for block in message.content
            if isinstance(block, ToolResultBlock)
        ]
    return []


class Runner:
    """Run agents on the SDK with their options, permissions, limits and output contract.

    Arguments:
        spec: The org spec.
        store: The operations store.
        workspace_root: The directory under which run workspaces are created.
        skills_dir: The directory of the org's skills.
        gate: The permission gate consulted before every tool call.
        org_tools: Returns the org tools an agent may use within a run.
        file_output: Files a successful output under the agent's knowledge type.
        client_factory: Opens an SDK client for the given options.
        parameter_values: Current parameter values for principle placeholders.
    """

    def __init__(
        self,
        spec: Spec,
        store: Store,
        *,
        workspace_root: Path,
        skills_dir: Path,
        gate: PermissionGate,
        org_tools: OrgTools,
        file_output: OutputFiler | None = None,
        client_factory: ClientFactory = ClaudeSDKClient,
        parameter_values: Mapping[str, object] | None = None,
    ) -> None:
        self.spec = spec
        self.store = store
        self.workspace_root = workspace_root
        self.skills_dir = skills_dir
        self.gate = gate
        self.org_tools = org_tools
        self.file_output = file_output
        self.client_factory = client_factory
        self.parameter_values = parameter_values or {}
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._deadlines: dict[str, asyncio.Timeout] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        """Return a queue that receives the stream events of run `run_id` until its `end` event."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.setdefault(run_id, []).append(queue)
        return queue

    def emit(self, run_id: str, event: dict[str, Any]) -> None:
        """Send one stream event to every subscriber of run `run_id`."""
        for queue in self._subscribers.get(run_id, []):
            queue.put_nowait(event)
        if event['type'] == 'end':
            self._subscribers.pop(run_id, None)

    @asynccontextmanager
    async def _clock_stopped(self, run_id: str) -> AsyncIterator[None]:
        """Stop the run's `timeout_s` clock while a tool call waits at the gate, such as for a human approval."""
        deadline = self._deadlines.get(run_id)
        when = deadline.when() if deadline is not None else None
        if deadline is None or when is None:
            yield
            return
        loop = asyncio.get_running_loop()
        stopped = loop.time()
        deadline.reschedule(None)
        try:
            yield
        finally:
            deadline.reschedule(when + loop.time() - stopped)

    async def _options(self, agent: Agent, run: Run, workspace: Path) -> ClaudeAgentOptions:
        """Return the SDK options of one run, resuming the agent's session when it keeps memory."""
        resume = None
        if run.session_id and agent.memory != 'none':
            resume = await self.store.get_value('sdk_session', f'{agent.id}:{run.session_id}')

        async def can_use_tool(name: str, tool_input: dict[str, Any], _: ToolPermissionContext) -> PermissionResult:
            async with self._clock_stopped(run.id):
                return await self.gate.check(agent, run, name, tool_input)

        return build_agent_options(
            agent,
            self.spec,
            workspace=workspace,
            skills_dir=self.skills_dir,
            org_tools=self.org_tools(agent, run),
            can_use_tool=can_use_tool,
            parameter_values=self.parameter_values,
            resume=resume if isinstance(resume, str) else None,
        )

    async def _converse(self, run: Run, options: ClaudeAgentOptions) -> ResultMessage | None:
        """Send the prompt and stream the reply into the transcript and to subscribers."""
        result = None
        async with self.client_factory(options) as client:
            await client.query(run.prompt)
            async for message in client.receive_response():
                events = _events(message)
                for event in events:
                    self.emit(run.id, event)
                await self.store.append_transcript(run.id, events) if events else None
                if isinstance(message, ResultMessage):
                    result = message
        return result

    def _outcome(self, agent: Agent, result: ResultMessage | None) -> tuple[object, str | None]:
        """Return the run output and the failure reason, which is `None` on success."""
        if result is None:
            return None, 'error'
        if result.subtype != 'success' or result.is_error:
            return result.result, FAILURE_REASONS.get(result.subtype, 'error')
        if agent.output.format != 'json':
            return result.result, None
        try:
            jsonschema.validate(result.structured_output, agent.output.json_schema or {})
        except jsonschema.ValidationError:
            return result.structured_output, 'invalid_output'
        return result.structured_output, None

    async def execute(self, run: Run) -> None:
        """Run a claimed agent run to completion and record its output, cost and status.

        Arguments:
            run: A run in `running` status whose target is an agent.
        """
        agent = self.spec.ai.agent(run.target)
        workspace = resolve_workspace(agent, self.spec, self.workspace_root, run.id)
        self.emit(run.id, {'type': 'status', 'status': 'running'})
        result: ResultMessage | None = None
        reason: str | None
        try:
            async with asyncio.timeout(agent.limits.timeout_s) as deadline:
                self._deadlines[run.id] = deadline
                result = await self._converse(run, await self._options(agent, run, workspace))
            output, reason = self._outcome(agent, result)
        except TimeoutError:
            output, reason = None, 'timeout'
        finally:
            self._deadlines.pop(run.id, None)
            if agent.workspace == 'ephemeral':
                shutil.rmtree(workspace, ignore_errors=True)
        await self._record(agent, run, result, output, reason)

    async def _record(
        self,
        agent: Agent,
        run: Run,
        result: ResultMessage | None,
        output: object,
        reason: str | None,
    ) -> None:
        """Store the run's outcome, cost and session, and file its output as knowledge."""
        usage = (result.usage if result else None) or {}
        cost = {
            'cost_usd': (result.total_cost_usd if result else None) or 0.0,
            'input_tokens': int(usage.get('input_tokens', 0)),
            'output_tokens': int(usage.get('output_tokens', 0)),
        }
        if result and result.session_id and run.session_id and agent.memory != 'none':
            await self.store.set_value('sdk_session', f'{agent.id}:{run.session_id}', result.session_id)
        status: RunStatus = 'failed' if reason else 'succeeded'
        await self.store.transition(run.id, status, output=output, failure_reason=reason, **cost)
        if not reason and self.file_output and agent.output.knowledge_type:
            await self.file_output(agent, run, output if isinstance(output, str) else str(output))
        self.emit(run.id, {'type': 'end', 'status': status, 'output': output, 'failure_reason': reason, **cost})
