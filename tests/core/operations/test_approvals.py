"""Tests for the approvals module."""

import asyncio
from typing import Any

import pytest
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from agentorg.core.operations import ApprovalGate, Approvals, LifecycleState, Run, Store
from agentorg.core.spec import Spec


class Sink:
    """Records published events and notifications."""

    def __init__(self) -> None:
        """Start empty."""
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.notes: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, name: str, payload: dict[str, Any]) -> None:
        """Record an event."""
        self.events.append((name, payload))

    async def notify(self, kind: str, payload: dict[str, Any]) -> None:
        """Record a notification."""
        self.notes.append((kind, payload))


def _spec(spec_dict_minimal: dict[str, Any], **governance: Any) -> Spec:
    spec_dict_minimal['org']['admin_email'] = 'admin@acme.com'
    spec_dict_minimal['operations'] = {'governance': governance}
    return Spec.model_validate(spec_dict_minimal)


async def _running(store: Store) -> Run:
    run = await store.create_run(target='assistant', trigger_kind='manual', prompt='Email the customer.')
    await store.claim(run.id, 'w1')
    return run


async def _pending_id(store: Store) -> str:
    while not (pending := await store.list_approvals()):
        await asyncio.sleep(0.01)
    return pending[0].id


async def test_hold_waits_and_applies_edited_arguments(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """A held call parks the run until approval, then runs with the approver's edited arguments."""
    sink = Sink()
    approvals = Approvals(_spec(spec_dict_minimal), store, sink.publish, sink.notify)
    run = await _running(store)
    held = asyncio.create_task(approvals.hold(run, 'outbound_message', 'mcp__mail__send', {'body': 'Hi'}))
    approval_id = await _pending_id(store)
    assert (await store.get_run(run.id)).status == 'awaiting_approval'  # type: ignore[union-attr]
    assert (await store.get_approval(approval_id)).approvers == ['admin@acme.com']  # type: ignore[union-attr]
    assert await approvals.decide(
        approval_id,
        approved=True,
        actor='admin@acme.com',
        edited_arguments={'body': 'Hello'},
    )
    permission = await held
    assert isinstance(permission, PermissionResultAllow)
    assert permission.updated_input == {'body': 'Hello'}
    assert (await store.get_run(run.id)).status == 'running'  # type: ignore[union-attr]
    assert sink.events == [
        ('approval.decided', {'approval_id': approval_id, 'status': 'approved', 'by': 'admin@acme.com'}),
    ]
    assert sink.notes[0][0] == 'approval_requested'


async def test_rejection_reaches_agent_and_transcript(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """A rejection denies the call with the comment and is recorded with the approver in the transcript."""
    approvals = Approvals(_spec(spec_dict_minimal), store, Sink().publish, Sink().notify)
    run = await _running(store)
    held = asyncio.create_task(approvals.hold(run, 'outbound_message', 'mcp__mail__send', {}))
    approval_id = await _pending_id(store)
    await approvals.decide(approval_id, approved=False, actor='admin@acme.com', comment='Wrong customer')
    permission = await held
    assert isinstance(permission, PermissionResultDeny)
    assert 'Wrong customer' in permission.message
    transcript = (await store.get_run(run.id)).transcript  # type: ignore[union-attr]
    assert transcript[-1] == {
        'type': 'approval_decided',
        'approval_id': approval_id,
        'status': 'rejected',
        'by': 'admin@acme.com',
        'comment': 'Wrong customer',
    }


async def test_timeout_rejects_and_publishes(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """An undecided approval times out, denies the call and publishes `approval.decided`."""
    sink = Sink()
    approvals = Approvals(_spec(spec_dict_minimal, approval_timeout_h=0.0002), store, sink.publish, sink.notify)
    permission = await approvals.hold(await _running(store), 'external_write', 'mcp__crm__update', {})
    assert isinstance(permission, PermissionResultDeny)
    assert 'timed out' in permission.message
    assert sink.events[0][1]['status'] == 'timed_out'


async def test_decision_from_another_worker_releases_hold(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """A decision recorded through a different Approvals instance is picked up by polling the store."""
    spec = _spec(spec_dict_minimal)
    holder = Approvals(spec, store, Sink().publish, Sink().notify)
    other = Approvals(spec, store, Sink().publish, Sink().notify)
    held = asyncio.create_task(holder.hold(await _running(store), 'external_write', 'mcp__crm__update', {}))
    await other.decide(await _pending_id(store), approved=True, actor='admin@acme.com')
    assert isinstance(await asyncio.wait_for(held, 5), PermissionResultAllow)


async def test_review_returns_edited_output(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """A pipeline review approved with edits returns the edited output."""
    approvals = Approvals(_spec(spec_dict_minimal), store, Sink().publish, Sink().notify)
    reviewed = asyncio.create_task(approvals.review(await _running(store), '2:draft', 'Draft v1'))
    await approvals.decide(
        await _pending_id(store),
        approved=True,
        actor='editor',
        edited_arguments={'output': 'Draft v2'},
    )
    decision = await reviewed
    assert (decision.approved, decision.output) == (True, 'Draft v2')


@pytest.mark.parametrize(('tool_name', 'expected'), [('Read', 'allow'), ('Task', 'deny'), ('Bash', 'hold')])
async def test_gate_routes_policy_decisions(
    spec_dict_minimal: dict[str, Any],
    store: Store,
    tool_name: str,
    expected: str,
) -> None:
    """The gate allows reads, denies unknown tools with a reason, and holds governed actions."""
    spec_dict_minimal['ai']['agents'][0]['autonomy'] = 'autonomous'
    spec = _spec(spec_dict_minimal, approval_required=['code_execution'])
    approvals = Approvals(spec, store, Sink().publish, Sink().notify)

    async def active() -> LifecycleState:
        return 'active'

    gate = ApprovalGate(spec, approvals, active, preview=False)
    run = await _running(store)
    task = asyncio.create_task(gate.check(spec.ai.agent('assistant'), run, tool_name, {}))
    if expected == 'hold':
        await approvals.decide(await _pending_id(store), approved=True, actor='admin@acme.com')
    permission = await task
    assert isinstance(permission, PermissionResultAllow if expected != 'deny' else PermissionResultDeny)
    assert bool(await store.list_approvals(status=None)) == (expected == 'hold')
