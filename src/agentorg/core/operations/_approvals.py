"""Hold consequential tool calls and pipeline steps for human approval."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from claude_agent_sdk import PermissionResult, PermissionResultAllow, PermissionResultDeny

from ..spec import ActionClass, Agent, Spec
from ._policy import LifecycleState, approvers_for, decide, effective_autonomy, effective_governed
from ._store import Approval, Run, Store
from ._units import ReviewDecision

POLL_S = 1.0

Publish = Callable[[str, dict[str, Any]], Awaitable[None]]
Notify = Callable[[str, dict[str, Any]], Awaitable[None]]
LifecycleProvider = Callable[[], Awaitable[LifecycleState]]


class Approvals:
    """Create approval requests, wait for their decisions and apply timeouts.

    Arguments:
        spec: The org spec, which sets approvers and the timeout policy.
        store: The operations store.
        publish: Publishes an org event such as `approval.decided`.
        notify: Sends a notification of a kind with a payload.
    """

    def __init__(self, spec: Spec, store: Store, publish: Publish, notify: Notify) -> None:
        self.spec = spec
        self.store = store
        self.publish = publish
        self.notify = notify
        self._waiting: dict[str, asyncio.Future[None]] = {}

    async def _request(self, run: Run, action_class: str, tool_name: str, arguments: dict[str, Any]) -> Approval:
        """Store an approval request, hold the run and notify the approvers."""
        approval = Approval(
            run_id=run.id,
            action_class=action_class,
            tool_name=tool_name,
            arguments=arguments,
            approvers=approvers_for(self.spec, run.target),
        )
        # Hold the run first, so anyone who sees the pending approval also sees the run waiting on it.
        await self.store.transition(run.id, 'awaiting_approval')
        await self.store.add(approval)
        await self.store.append_transcript(
            run.id,
            [{'type': 'approval_requested', 'approval_id': approval.id, 'tool': tool_name}],
        )
        await self.notify('approval_requested', {'approval_id': approval.id, 'run_id': run.id, 'tool': tool_name})
        return approval

    async def _wait(self, approval_id: str) -> Approval:
        """Wait for a decision on the approval, applying the timeout."""
        future = asyncio.get_running_loop().create_future()
        self._waiting[approval_id] = future
        timeout_s = self.spec.operations.governance.approval_timeout_h * 3600
        deadline = asyncio.get_running_loop().time() + timeout_s
        try:
            while (stored := await self.store.get_approval(approval_id)) and stored.status == 'pending':
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    await self._time_out(approval_id)
                    continue
                await asyncio.wait({future}, timeout=min(POLL_S, remaining))
        finally:
            self._waiting.pop(approval_id, None)
        return stored  # type: ignore[return-value]

    async def _time_out(self, approval_id: str) -> None:
        """Decide an approval that nobody decided in time."""
        status = 'approved' if self.spec.operations.governance.on_timeout == 'approve' else 'timed_out'
        if await self.store.decide_approval(approval_id, status=status, decided_by='timeout'):
            await self.publish('approval.decided', {'approval_id': approval_id, 'status': status})

    async def _resume(self, run: Run, approval: Approval) -> None:
        """Return a held run to running and record the decision in its transcript."""
        await self.store.transition(run.id, 'running')
        event = {
            'type': 'approval_decided',
            'approval_id': approval.id,
            'status': approval.status,
            'by': approval.decided_by,
        }
        await self.store.append_transcript(run.id, [{**event, 'comment': approval.comment}])

    async def hold(
        self,
        run: Run,
        action_class: ActionClass | None,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> PermissionResult:
        """Hold a tool call until it is decided and return the SDK permission result.

        Arguments:
            run: The run making the call.
            action_class: The governed class of the call.
            tool_name: The SDK tool name.
            arguments: The tool arguments shown to the approver.

        Returns:
            permission: Allow, with edited arguments when the approver changed them, or deny with the reason.
        """
        approval = await self._wait(
            (await self._request(run, action_class or 'external_write', tool_name, arguments)).id,
        )
        await self._resume(run, approval)
        if approval.status == 'approved':
            return PermissionResultAllow(updated_input=approval.edited_arguments)
        reason = 'timed out' if approval.status == 'timed_out' else f'was rejected: {approval.comment or "no comment"}'
        return PermissionResultDeny(message=f'The approval for {tool_name} {reason}. Do not retry it.')

    async def review(self, run: Run, step: str, output: object) -> ReviewDecision:
        """Hold a pipeline step's output for human review and return the decision.

        Arguments:
            run: The pipeline run.
            step: The step label.
            output: The step output shown to the reviewer.

        Returns:
            decision: Approved with the possibly edited output, or rejected with the comment.
        """
        approval = await self._wait((await self._request(run, 'review', f'review:{step}', {'output': output})).id)
        await self._resume(run, approval)
        edited = (approval.edited_arguments or {}).get('output', output)
        return ReviewDecision(approval.status == 'approved', approval.comment or '', edited)

    async def decide(
        self,
        approval_id: str,
        *,
        approved: bool,
        actor: str,
        comment: str = '',
        edited_arguments: dict[str, Any] | None = None,
    ) -> bool:
        """Record a human decision on a pending approval and release the waiting run.

        Arguments:
            approval_id: The approval to decide.
            approved: Whether to approve.
            actor: The approver's email.
            comment: The reason, shown to the agent on rejection.
            edited_arguments: Replacement arguments for an approval with edits.

        Returns:
            decided: Whether the approval was still pending.
        """
        status = 'approved' if approved else 'rejected'
        fields = {'status': status, 'decided_by': actor, 'comment': comment, 'edited_arguments': edited_arguments}
        if not await self.store.decide_approval(approval_id, **fields):
            return False
        await self.publish('approval.decided', {'approval_id': approval_id, 'status': status, 'by': actor})
        future = self._waiting.get(approval_id)
        if future is not None and not future.done():
            future.set_result(None)
        return True


class ApprovalGate:
    """The runner's permission gate: policy decisions, with held calls routed to approvals.

    Arguments:
        spec: The org spec.
        approvals: Holds calls for approval.
        lifecycle: Returns the org's current lifecycle state.
        preview: Whether the node runs as the master's live preview.
    """

    def __init__(self, spec: Spec, approvals: Approvals, lifecycle: LifecycleProvider, *, preview: bool) -> None:
        self.spec = spec
        self.approvals = approvals
        self.lifecycle = lifecycle
        self.preview = preview

    async def check(self, agent: Agent, run: Run, tool_name: str, tool_input: dict[str, Any]) -> PermissionResult:
        """Return the permission result of one tool call of `agent` within `run`."""
        decision = decide(
            agent,
            tool_name,
            autonomy=effective_autonomy(self.spec, agent.id),
            governed=effective_governed(self.spec, agent.id),
            lifecycle=await self.lifecycle(),
            preview=self.preview,
        )
        if decision.verdict == 'allow':
            return PermissionResultAllow()
        if decision.verdict == 'deny':
            await self.approvals.store.append_transcript(
                run.id,
                [{'type': 'denied', 'tool': tool_name, 'reason': decision.reason}],
            )
            return PermissionResultDeny(message=decision.reason)
        return await self.approvals.hold(run, decision.action_class, tool_name, tool_input)
