"""Tests for the comms module."""

from typing import Any

import pytest

from agentorg.core.operations import OrgTools, Run, Store
from agentorg.core.spec import Spec


class Recording:
    """Records delegated calls and published events."""

    def __init__(self) -> None:
        """Start with nothing recorded."""
        self.calls: list[tuple[str, str, str]] = []
        self.events: list[tuple[str, dict[str, Any], list[str] | None]] = []

    async def call_target(self, target: str, task: str, parent: Run) -> dict[str, Any]:
        """Record a delegated call and answer it."""
        self.calls.append((target, task, parent.id))
        return {'output': f'{target} did it'}

    async def publish(self, name: str, payload: dict[str, Any], chain: list[str] | None = None) -> None:
        """Record a published event."""
        self.events.append((name, payload, chain))


@pytest.fixture
def spec(archetype_specs: dict[str, dict[str, Any]]) -> Spec:
    """The support desk: a hub led by desk-lead over a frontline pool led by triage with billing and tech."""
    return Spec.model_validate(archetype_specs['support-desk'])


async def _tools(spec: Spec, store: Store, agent_id: str, **run: Any) -> tuple[dict[str, Any], Recording, Run]:
    recording = Recording()
    org = OrgTools(spec, store, recording, recording.call_target)
    parent = await store.create_run(target=agent_id, trigger_kind='manual', prompt='Help.', **run)
    tools = org.tools_for(spec.ai.agent(agent_id), parent)
    return {fn.__name__: fn for fn in tools}, recording, parent


@pytest.mark.parametrize(
    ('agent_id', 'delegate', 'handoff'),
    [('desk-lead', True, False), ('triage', False, True), ('billing', False, True)],
)
async def test_tools_for_follows_position(
    spec: Spec,
    store: Store,
    agent_id: str,
    delegate: bool,
    handoff: bool,
) -> None:
    """Only hub leads delegate, pool members and pool leads hand off, and everyone publishes and escalates."""
    tools, _, _ = await _tools(spec, store, agent_id)
    assert ('delegate' in tools, 'handoff' in tools) == (delegate, handoff)
    assert {'publish', 'escalate', 'read_knowledge', 'search_knowledge'} <= set(tools)


async def test_delegate_runs_member_and_returns_output(spec: Spec, store: Store) -> None:
    """A hub lead's delegation runs the member as a child of the current run."""
    tools, recording, parent = await _tools(spec, store, 'desk-lead')
    assert await tools['delegate']('frontline', 'Answer ticket 42') == 'frontline did it'
    assert recording.calls == [('frontline', 'Answer ticket 42', parent.id)]


async def test_delegate_outside_hub_is_denied_with_event_hint(spec: Spec, store: Store) -> None:
    """Delegating past the hub's members is denied and suggests publishing an event."""
    tools, recording, _ = await _tools(spec, store, 'desk-lead')
    message = await tools['delegate']('billing', 'Refund')
    assert "you may delegate to ['frontline']" in message
    assert 'publish an event' in message
    assert recording.calls == []


async def test_delegate_back_into_chain_is_denied(spec: Spec, store: Store) -> None:
    """A delegation to a target already in the run's delegation chain is denied."""
    root = await store.create_run(target='frontline', trigger_kind='manual', prompt='x')
    tools, recording, _ = await _tools(spec, store, 'desk-lead', parent_id=root.id)
    assert 'loop back' in await tools['delegate']('frontline', 'again')
    assert recording.calls == []


async def test_hub_lead_delegates_from_within_its_unit_run(
    archetype_specs: dict[str, dict[str, Any]],
    store: Store,
) -> None:
    """A one-level hub's lead, run as the child of its unit's run, may delegate to its members."""
    research = Spec.model_validate(archetype_specs['research-reporting'])
    unit_run = await store.create_run(target='research', trigger_kind='schedule', prompt='Weekly.')
    tools, recording, _ = await _tools(research, store, 'lead-analyst', parent_id=unit_run.id)
    assert await tools['delegate']('analyst-markets', 'One finding.') == 'analyst-markets did it'
    assert recording.calls[0][0] == 'analyst-markets'


async def test_delegate_beyond_the_org_depth_is_denied(
    archetype_specs: dict[str, dict[str, Any]],
    store: Store,
) -> None:
    """A chain that already holds as many agents as the tree has levels cannot go deeper."""
    research = Spec.model_validate(archetype_specs['research-reporting'])
    above = await store.create_run(target='summariser', trigger_kind='manual', prompt='Hi.')
    tools, recording, _ = await _tools(research, store, 'lead-analyst', parent_id=above.id)
    assert "delegation depth of 1" in await tools['delegate']('analyst-markets', 'One finding.')
    assert recording.calls == []


async def test_handoff_sets_session_owner(spec: Spec, store: Store) -> None:
    """A pool member's handoff to a peer routes the session to that peer with the note."""
    tools, _, _ = await _tools(spec, store, 'billing', session_id='chat-1')
    assert (await tools['handoff']('tech', 'Printer is broken')).startswith('Handed off to tech.')
    assert await store.get_value('session_owner', 'chat-1') == {'agent': 'tech', 'note': 'Printer is broken'}


async def test_handoff_to_unrelated_agent_is_denied(spec: Spec, store: Store) -> None:
    """A pool member cannot hand off outside its pool and lead."""
    tools, _, _ = await _tools(spec, store, 'billing', session_id='chat-1')
    assert 'cannot hand off to desk-lead' in await tools['handoff']('desk-lead', 'x')
    assert await store.get_value('session_owner', 'chat-1') is None


async def test_publish_requires_custom_prefix_and_carries_chain(spec: Spec, store: Store) -> None:
    """Agents publish only `custom.*` events, carrying the run's trigger chain."""
    tools, recording, _ = await _tools(spec, store, 'tech', chain=['helpdesk'])
    assert await tools['publish']('run.failed', {}) == "Event names must start with 'custom.'."
    assert await tools['publish']('custom.outage', {'region': 'eu'}) == 'Published custom.outage.'
    assert recording.events == [('custom.outage', {'region': 'eu'}, ['helpdesk'])]


@pytest.mark.parametrize(('agent_id', 'lead'), [('billing', 'triage'), ('triage', 'desk-lead')])
async def test_escalate_climbs_to_nearest_lead(spec: Spec, store: Store, agent_id: str, lead: str) -> None:
    """An escalation goes to the agent's unit lead, or to the parent unit's lead for a lead."""
    tools, recording, _ = await _tools(spec, store, agent_id)
    assert (await tools['escalate']('Customer threatens to churn')).startswith(f'Escalated to {lead}.')
    assert recording.calls[0][0] == lead


async def test_escalate_from_root_lead_reaches_inbox(spec: Spec, store: Store) -> None:
    """The root lead's escalation creates a human inbox item with the escalation path."""
    tools, _, parent = await _tools(spec, store, 'desk-lead')
    assert 'human was notified' in await tools['escalate']('Legal threat', 'Ticket 42')
    item = (await store.list_inbox())[0]
    assert (item.kind, item.run_id, item.reason, item.context['path']) == (
        'escalation',
        parent.id,
        'Legal threat',
        ['support', 'desk-lead'],
    )
