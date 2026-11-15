"""Answer chat messages and commands for a rendered org through its operations runtime."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import timedelta
from typing import Any

from ..spec import Spec
from ._approvals import Approvals
from ._chat_api import ChatUser, conversation_key, message_text
from ._lifecycle import Lifecycle
from ._store import TERMINAL, Run, Store

CONVERSATION_TTL = timedelta(days=30)
StartRun = Callable[[str, str, str | None, str], Awaitable[dict[str, Any]]]
HELP = """**Commands**

- `/approve <id> [comment]`, `/reject <id> <comment>`: decide a held action, if you are one of its approvers.
- `/runs`: the latest runs. `/run <id>`: one run with its output.
- `/inbox`: escalations and failures waiting for a human.
- `/status`: lifecycle, broker and pending approvals.
- `/pause <reason>`, `/resume`: stop and restart new work, for approvers.
- `/help`: this list."""


class ChatSessions:
    """Map client conversations onto the sessions of `agents`, one forkable session key per turn."""

    def __init__(self, store: Store, agents: list[str]) -> None:
        self.store = store
        self.agents = agents

    async def _previous(self, user: ChatUser, target: str, history: list[dict[str, Any]]) -> object:
        key = conversation_key(user.id, target, user.conversation, history)
        found = await self.store.get_value('chat_conversation', key)
        if found is None and user.conversation:
            latest = conversation_key(user.id, target, user.conversation, [])
            found = await self.store.get_value('chat_latest', latest)
        return found

    async def start(self, user: ChatUser, target: str, history: list[dict[str, Any]]) -> str:
        """Return a new session key seeded with the agent sessions and handoff owner of the turn before."""
        session = uuid.uuid4().hex
        previous = await self._previous(user, target, history)
        if not isinstance(previous, str):
            return session
        for agent in self.agents:
            sdk = await self.store.get_value('sdk_session', f'{agent}:{previous}')
            if sdk is not None:
                await self.store.set_value('sdk_session', f'{agent}:{session}', sdk, ttl=CONVERSATION_TTL)
        owner = await self.store.get_value('session_owner', previous)
        if owner is not None:
            await self.store.set_value('session_owner', session, owner, ttl=CONVERSATION_TTL)
        return session

    async def remember(self, user: ChatUser, target: str, messages: list[dict[str, Any]], session: str) -> None:
        """Record that the conversation ending with `messages` continues from `session`."""
        key = conversation_key(user.id, target, user.conversation, messages)
        await self.store.set_value('chat_conversation', key, session, ttl=CONVERSATION_TTL)
        if user.conversation:
            latest = conversation_key(user.id, target, user.conversation, [])
            await self.store.set_value('chat_latest', latest, session, ttl=CONVERSATION_TTL)


class RunReply:
    """Translate the run `run_id` into chat text, linking approvals to `console_url`, and remember its session."""

    def __init__(self, store: Store, run_id: str, console_url: str, finish: Callable[[str], Awaitable[None]]) -> None:
        self.store = store
        self.run_id: str | None = run_id
        self.console_url = console_url.rstrip('/')
        self._finish = finish
        self.seen = 0
        self.children: set[str] = set()
        self.approvals: set[str] = set()
        self.content = ''
        self.run: Run | None = None

    async def _lines(self, run: Run) -> list[str]:
        lines = []
        for event in run.transcript[self.seen :]:
            if event['type'] == 'text':
                lines.append(event['text'])
            elif event['type'] == 'tool_call':
                lines.append(f"\n> {event['name']} {json.dumps(event.get('input', {}))[:120]}\n")
        self.seen = len(run.transcript)
        for child in await self.store.list_runs(parent_id=run.id, limit=1000):
            if child.id not in self.children:
                self.children.add(child.id)
                lines.append(f'\n> delegated to {child.target}\n')
        if run.status == 'awaiting_approval':
            for approval in await self.store.list_approvals(status='pending'):
                if approval.run_id == run.id and approval.id not in self.approvals:
                    self.approvals.add(approval.id)
                    link = f'{self.console_url}/?tab=inbox&approval={approval.id}'
                    lines.append(
                        f'\n⏸ `{approval.tool_name}` is waiting for approval: {link}\n'
                        f'Approvers can reply `/approve {approval.id}` or `/reject {approval.id} <comment>`.\n',
                    )
        if run.status in TERMINAL and run.status != 'succeeded':
            lines.append(f'\n✖ The run {run.status}: {run.failure_reason or "no reason given"}.')
        return lines

    async def deltas(self, poll: float, keepalive: float) -> AsyncIterator[str | None]:
        """Yield text deltas as the run progresses, and `None` when nothing changed for `keepalive` seconds."""
        quiet = 0.0
        while self.run_id is not None:
            run = await self.store.get_run(self.run_id)
            if run is None:
                return
            self.run = run
            lines = await self._lines(run)
            for line in lines:
                self.content += line
                yield line
            if run.status in TERMINAL:
                return
            quiet = 0.0 if lines else quiet + poll
            if quiet >= keepalive:
                quiet = 0.0
                yield None
            await asyncio.sleep(poll)

    def usage(self) -> dict[str, int]:
        """Return the run's token usage."""
        prompt, completion = (self.run.input_tokens or 0, self.run.output_tokens or 0) if self.run else (0, 0)
        return {'prompt_tokens': prompt, 'completion_tokens': completion, 'total_tokens': prompt + completion}

    async def finish(self) -> None:
        """Remember the conversation including this reply."""
        await self._finish(self.content)


class OrgChat:
    """The chat backend of a rendered org: its agents and units as models, and the operations commands."""

    def __init__(
        self,
        spec: Spec,
        store: Store,
        start_run: StartRun,
        approvals: Approvals,
        *,
        lifecycle: Lifecycle,
        broker_status: Callable[[], str],
        console_url: str,
    ) -> None:
        self.spec = spec
        self.store = store
        self.start_run = start_run
        self.approvals = approvals
        self.lifecycle = lifecycle
        self.broker_status = broker_status
        self.console_url = console_url
        self.sessions = ChatSessions(store, [agent.id for agent in spec.ai.agents])
        self.org_approvers = list(spec.operations.governance.approvers) or [spec.org.admin_email]
        self.targets = {unit.id: unit.name for unit in spec.ai.units} | {a.id: a.name for a in spec.ai.agents}

    async def models(self) -> dict[str, str]:
        """Return the enabled agents and units."""
        return {id_: name for id_, name in self.targets.items() if not await self.store.get_value('disabled', id_)}

    async def turn(self, model: str, messages: list[dict[str, Any]], user: ChatUser) -> RunReply | str:
        """Start a manual run of `model` on the last message, resuming the conversation's session."""
        session = await self.sessions.start(user, model, messages[:-1])
        started = await self.start_run(model, message_text(messages[-1].get('content')), session, user.id)
        if started['status'] == 'refused':
            return str(started['output'])

        async def finish(content: str) -> None:
            reply = {'role': 'assistant', 'content': content}
            await self.sessions.remember(user, model, [*messages, reply], session)

        return RunReply(self.store, started['run_id'], self.console_url, finish)

    def _may_govern(self, email: str, approvers: list[str]) -> bool:
        allowed = {address.lower() for address in approvers or [self.spec.org.admin_email]}
        return bool(email) and email.lower() in allowed

    async def command(self, model: str, text: str, user: ChatUser) -> str:
        """Answer a `/` command from the store, the approvals and the lifecycle."""
        name, _, rest = text[1:].partition(' ')
        handlers = {
            'approve': self._approve,
            'reject': self._reject,
            'runs': self._runs,
            'run': self._run,
            'inbox': self._inbox,
            'status': self._status,
            'pause': self._pause,
            'resume': self._resume,
        }
        handler = handlers.get(name.lower())
        del model
        return HELP if handler is None else await handler(rest.strip(), user)

    async def _decide(self, args: str, user: ChatUser, *, approved: bool) -> str:
        approval_id, _, comment = args.partition(' ')
        approval = await self.store.get_approval(approval_id) if approval_id else None
        if approval is None or approval.status != 'pending':
            return f'There is no pending approval `{approval_id}`.'
        if not self._may_govern(user.email, approval.approvers):
            return f'You are not an approver of `{approval_id}`; ask {", ".join(approval.approvers)}.'
        if not approved and not comment.strip():
            return f'A rejection needs a comment for the agent: `/reject {approval_id} <comment>`.'
        await self.approvals.decide(approval_id, approved=approved, actor=user.email, comment=comment.strip())
        return f'`{approval.tool_name}` {"approved" if approved else "rejected"}; run `{approval.run_id}` continues.'

    async def _approve(self, args: str, user: ChatUser) -> str:
        return await self._decide(args, user, approved=True)

    async def _reject(self, args: str, user: ChatUser) -> str:
        return await self._decide(args, user, approved=False)

    async def _runs(self, args: str, user: ChatUser) -> str:
        del args, user
        runs = await self.store.list_runs(limit=10)
        rows = [f'| `{r.id}` | {r.target} | {r.trigger_kind} | {r.status} |' for r in runs]
        return (
            '\n'.join(['| Run | Target | Trigger | Status |', '| --- | --- | --- | --- |', *rows])
            if runs
            else 'No runs yet.'
        )

    async def _run(self, args: str, user: ChatUser) -> str:
        del user
        run = await self.store.get_run(args) if args else None
        if run is None:
            return f'There is no run `{args}`.'
        reason = f'\n\nFailure: {run.failure_reason}' if run.failure_reason else ''
        return f'**{run.target}** · {run.trigger_kind} · {run.status}\n\n{run.output or "(no output yet)"}{reason}'

    async def _inbox(self, args: str, user: ChatUser) -> str:
        del args, user
        items = await self.store.list_inbox()
        return '\n'.join(f'- {item.kind}: {item.reason}' for item in items) if items else 'The inbox is empty.'

    async def _status(self, args: str, user: ChatUser) -> str:
        del args, user
        pending = await self.store.list_approvals(status='pending')
        held = ''.join(f'\n- `{a.id}`: `{a.tool_name}` in run `{a.run_id}`' for a in pending)
        return (
            f'Lifecycle: **{await self.lifecycle.state()}** · broker: **{self.broker_status()}** · '
            f'pending approvals: **{len(pending)}**{held}'
        )

    async def _pause(self, args: str, user: ChatUser) -> str:
        if not self._may_govern(user.email, self.org_approvers):
            return 'Only the org approvers can pause it.'
        if not await self.lifecycle.transition('paused', user.email, args or 'Paused from chat.'):
            return f'The org cannot be paused from {await self.lifecycle.state()}.'
        return 'The org is paused; new work waits until `/resume`.'

    async def _resume(self, args: str, user: ChatUser) -> str:
        del args
        if not self._may_govern(user.email, self.org_approvers):
            return 'Only the org approvers can resume it.'
        if not await self.lifecycle.transition('active', user.email, 'Resumed from chat.'):
            return f'The org cannot be resumed from {await self.lifecycle.state()}.'
        return 'The org is active again.'
