"""Give each agent the communication tools its position in the unit tree permits."""

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from ..agents.tools import list_knowledge, read_knowledge, search_knowledge, write_knowledge
from ..spec import Agent, Spec, Unit
from ._store import InboxItem, Run, Store

CallTarget = Callable[[str, str, Run], Awaitable[dict[str, Any]]]


class EventPublisher(Protocol):
    """Publish an org event."""

    async def publish(self, name: str, payload: dict[str, Any], chain: list[str] | None = None) -> None:
        """Publish event `name` with `payload` and the chain of triggers that led to it."""
        ...


def _member_ids(unit: Unit) -> list[str]:
    """Return the ids of a unit's members."""
    return [member if isinstance(member, str) else member.id for member in unit.member_refs]


class OrgTools:
    """Build the delegate, handoff, publish, escalate and knowledge tools for one agent within one run.

    Arguments:
        spec: The org spec.
        store: The operations store, which keeps session owners and the inbox.
        bus: Publishes `custom.*` events.
        call_target: Runs a target on a task as a child of a run and returns its result.
    """

    def __init__(self, spec: Spec, store: Store, bus: EventPublisher, call_target: CallTarget) -> None:
        self.spec = spec
        self.store = store
        self.bus = bus
        self.call_target = call_target
        self.agent_ids = {agent.id for agent in spec.ai.agents}

    def _unit_of(self, agent_id: str) -> Unit:
        """Return the unit that holds an agent."""
        return self.spec.ai.path_to(agent_id)[-1]

    def delegates(self, agent: Agent) -> list[str]:
        """Return the members `agent` may delegate to: those of the hub it leads, else none."""
        unit = self._unit_of(agent.id)
        return _member_ids(unit) if unit.model == 'hub' and unit.lead == agent.id else []

    def handoff_targets(self, agent: Agent) -> list[str]:
        """Return the agents `agent` may hand a conversation to: its unit's lead and its pool peers."""
        unit = self._unit_of(agent.id)
        targets = [unit.lead] if unit.lead and unit.lead != agent.id else []
        if unit.model == 'pool':
            targets += [member for member in _member_ids(unit) if member != agent.id]
        return targets

    def escalation_target(self, agent: Agent) -> str | None:
        """Return the lead an escalation from `agent` goes to, or `None` when it reaches the human inbox."""
        for unit in reversed(self.spec.ai.path_to(agent.id)):
            if unit.lead and unit.lead != agent.id:
                return unit.lead
        return None

    async def _chain_targets(self, run: Run) -> list[str]:
        """Return the targets of a run and of every run above it in its delegation chain."""
        targets, current = [run.target], run
        while current.parent_id and (parent := await self.store.get_run(current.parent_id)):
            targets.append(parent.target)
            current = parent
        return targets

    def tools_for(self, agent: Agent, run: Run) -> list[Callable[..., Any]]:  # noqa: C901 - one closure per tool
        """Return the org tools `agent` may call within `run`.

        Arguments:
            agent: The agent.
            run: The run the tools act within.

        Returns:
            tools: The knowledge tools, `publish` and `escalate`, plus `delegate` and `handoff` where permitted.
        """
        allowed_delegates = self.delegates(agent)
        allowed_handoffs = self.handoff_targets(agent)

        async def delegate(target: str, task: str) -> str:
            """Ask a member of your unit to do a task and return its answer."""
            if target not in allowed_delegates:
                allowed = allowed_delegates or 'nobody'
                hint = 'To reach other units, publish an event.'
                return f'You cannot delegate to {target}; you may delegate to {allowed}. {hint}'
            chain = await self._chain_targets(run)
            if target in chain:
                return f'Delegating to {target} would loop back through {" -> ".join(reversed(chain))}.'
            # Each agent in the chain delegated one level down; the runs of units only wrap their lead.
            hops = sum(1 for link in chain if link in self.agent_ids)
            if hops > self.spec.ai.depth:
                return f'Delegating to {target} would exceed the org\'s delegation depth of {self.spec.ai.depth}.'
            result = await self.call_target(target, task, run)
            return str(result.get('output', ''))

        async def handoff(target: str, note: str) -> str:
            """Hand this conversation to another agent and end your turn."""
            if target not in allowed_handoffs:
                return f'You cannot hand off to {target}; you may hand off to: {allowed_handoffs or "nobody"}.'
            if run.session_id:
                await self.store.set_value('session_owner', run.session_id, {'agent': target, 'note': note})
            return f'Handed off to {target}. Tell the user that {target} takes over, then end your turn.'

        async def publish(event: str, payload: dict[str, Any]) -> str:
            """Publish a custom event that other units can react to."""
            if not event.startswith('custom.'):
                return "Event names must start with 'custom.'."
            await self.bus.publish(event, payload, run.chain)
            return f'Published {event}.'

        async def escalate(reason: str, context: str = '') -> str:
            """Escalate a problem you cannot resolve to your lead or to a human, and end your turn."""
            lead = self.escalation_target(agent)
            if lead is not None:
                await self.call_target(lead, f'Escalation from {agent.id}: {reason}\n\n{context}', run)
                return f'Escalated to {lead}. Tell the user it was escalated, then end your turn.'
            path = [unit.id for unit in self.spec.ai.path_to(agent.id)]
            await self.store.add(
                InboxItem(
                    kind='escalation',
                    run_id=run.id,
                    reason=reason,
                    context={'context': context, 'path': [*path, agent.id]},
                ),
            )
            return 'A human was notified. Tell the user a person will follow up, then end your turn.'

        tools: list[Callable[..., Any]] = [
            read_knowledge,
            list_knowledge,
            search_knowledge,
            write_knowledge,
            publish,
            escalate,
        ]
        if allowed_delegates:
            tools.append(delegate)
        if allowed_handoffs:
            tools.append(handoff)
        return tools
