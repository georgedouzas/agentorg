"""Serve the master interview as the `agentorg` chat model."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from typing import Any

from ...core.operations import ChatUser, message_text
from .._agent import MasterReply, _reset_workflow_cache
from .._stages import STAGE_LABELS, STAGES, advance, next_blockers
from .._state import get_state, reset_state
from .._tools import get_current_spec

MODEL = 'agentorg'
HELP = """**Interview commands**

- `/stage`: where the interview is and what blocks the next stage.
- `/next`: move to the next stage once nothing blocks it.
- `/spec`: the current `spec.py`.
- `/preview`: the live preview and its operations console.
- `/reset confirm`: throw the draft away and start over.
- `/help`: this list.

Anything else goes to the interviewer."""
Run = Callable[[str], Coroutine[Any, Any, MasterReply]]
Hook = Callable[[], Awaitable[None]]
PreviewStatus = Callable[[], dict[str, Any]]


class InterviewReply:
    """One interview turn, streamed as keep-alives until the stage agent answers."""

    def __init__(self, task: asyncio.Task[MasterReply], stage: str, after: Hook) -> None:
        self.task = task
        self.stage = stage
        self.after = after
        self.content = ''
        self.run_id: str | None = None

    def _text(self) -> str:
        try:
            reply = self.task.result()
        except Exception as error:  # noqa: BLE001 - the user sees the failure instead of a dropped stream
            return f'✖ The interviewer failed: {error}. Send the message again.'
        tools = ''.join(f'> {name}\n' for name in reply.tool_calls)
        text = f'{tools}\n{reply.content}' if tools else reply.content
        stage = get_state().stage
        if stage != self.stage:
            text += f'\n\n→ Now in **{STAGE_LABELS[stage]}**.'
        return text

    async def deltas(self, poll: float, keepalive: float) -> AsyncIterator[str | None]:
        """Yield `None` every `keepalive` seconds while the agent works, then its whole reply."""
        del poll
        while not self.task.done():
            done, _ = await asyncio.wait({self.task}, timeout=keepalive)
            if not done:
                yield None
        self.content = self._text()
        yield self.content

    def usage(self) -> dict[str, int]:
        """Return zero usage; the interview's cost is not metered per message."""
        return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

    async def finish(self) -> None:
        """Save the draft and refresh the preview."""
        await self.after()


class MasterChat:
    """The chat backend of the master: the interview as one model, and the interview commands.

    Arguments:
        run: Answers a message with the current stage's agent.
        after_turn: Saves the draft and refreshes the preview after a change.
        preview_status: Returns the live preview's status and addresses.
    """

    def __init__(self, run: Run, after_turn: Hook, preview_status: PreviewStatus) -> None:
        self.run = run
        self.after_turn = after_turn
        self.preview_status = preview_status

    async def models(self) -> dict[str, str]:
        """Return the interview model."""
        return {MODEL: 'AgentOrg'}

    async def turn(self, model: str, messages: list[dict[str, Any]], user: ChatUser) -> InterviewReply:
        """Send the last message to the current stage's agent."""
        del model, user
        stage = get_state().stage
        task = asyncio.get_running_loop().create_task(self.run(message_text(messages[-1].get('content'))))
        return InterviewReply(task, stage, self.after_turn)

    async def command(self, model: str, text: str, user: ChatUser) -> str:
        """Answer an interview command from the draft."""
        del model, user
        name, _, rest = text[1:].partition(' ')
        handlers: dict[str, Callable[[str], Awaitable[str]]] = {
            'stage': self._stage,
            'next': self._next,
            'spec': self._spec,
            'preview': self._preview,
            'reset': self._reset,
        }
        handler = handlers.get(name.lower())
        return HELP if handler is None else await handler(rest.strip())

    async def _stage(self, args: str) -> str:
        del args
        state = get_state()
        current = STAGES.index(state.stage)
        symbols = ['✓'] * current + ['▶'] + ['·'] * (len(STAGES) - current - 1)
        marks = [f'{symbol} {STAGE_LABELS[stage]}' for symbol, stage in zip(symbols, STAGES, strict=True)]
        blockers = next_blockers(state)
        todo = ''.join(f'\n- {blocker}' for blocker in blockers) if blockers else '\nNothing blocks `/next`.'
        return '\n'.join(marks) + f'\n\n**To finish {STAGE_LABELS[state.stage]}:**{todo}'

    async def _next(self, args: str) -> str:
        del args
        ok, stage, blockers = advance(get_state())
        if not ok:
            return f'Still in **{STAGE_LABELS[stage]}**:' + ''.join(f'\n- {blocker}' for blocker in blockers)
        await self.after_turn()
        return f'→ Now in **{STAGE_LABELS[stage]}**. Tell the interviewer when you are ready to start.'

    async def _spec(self, args: str) -> str:
        del args
        return f'```python\n{get_current_spec()}```'

    async def _preview(self, args: str) -> str:
        del args
        status = self.preview_status()
        if status.get('status') != 'ready':
            return f'The preview is {status.get("status")}: {status.get("detail") or "starting"}.'
        return (
            f'The preview of **{status.get("slug")}** is running. Operations console: {status.get("frontend_url")}. '
            "Chat with its agents under the **Preview** endpoint."
        )

    async def _reset(self, args: str) -> str:
        if args.lower() != 'confirm':
            return 'This throws the whole draft away. Send `/reset confirm` to do it.'
        reset_state()
        _reset_workflow_cache()
        await self.after_turn()
        return 'The draft is empty; the interview starts again at **Discover**.'
