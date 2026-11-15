"""Execute runs addressed to units with the engine of each governance model."""

import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from ..spec import Spec, Step, Unit
from ._store import InboxItem, Run, RunStatus, Store

CallTarget = Callable[[str, str, Run], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ReviewDecision:
    """A reviewer's verdict on a pipeline step's output."""

    approved: bool
    comment: str = ''
    output: Any = None


class HumanReview(Protocol):
    """Hold a pipeline run until a human reviews a step's output."""

    async def review(self, run: Run, step: str, output: object) -> ReviewDecision:
        """Return the reviewer's decision on `output` of `step` within `run`."""
        ...


def _member_id(member: str | Unit) -> str:
    """Return the id of an agent or unit member."""
    return member if isinstance(member, str) else member.id


def _reason(result: dict[str, Any]) -> str:
    """Return why a member's run failed, so the unit run fails, retries and escalates for the same reason."""
    return str(result.get('failure_reason') or 'error')


class UnitEngine:
    """Run a unit's work by its model: solo, hub, pool, council or pipeline.

    Arguments:
        spec: The org spec.
        store: The operations store.
        call_target: Runs a member on a task as a child of a run and returns its result.
        human: Holds a pipeline step for human review.
    """

    def __init__(self, spec: Spec, store: Store, call_target: CallTarget, human: HumanReview) -> None:
        self.spec = spec
        self.store = store
        self.call_target = call_target
        self.human = human

    async def _finish(self, run: Run, output: object, reason: str | None = None) -> None:
        """Record a unit run as succeeded, or failed with `reason`."""
        status: RunStatus = 'failed' if reason else 'succeeded'
        await self.store.transition(run.id, status, output=output, failure_reason=reason)

    async def _delegate_whole(self, run: Run, target: str) -> None:
        """Run one member on the whole task and record its outcome."""
        result = await self.call_target(target, run.prompt, run)
        await self._finish(run, result.get('output'), None if result.get('status') == 'succeeded' else _reason(result))

    async def _pick(self, unit: Unit, run: Run) -> str | None:
        """Return the pool member the routing rule selects, or None."""
        members = [_member_id(member) for member in unit.member_refs]
        if unit.routing == 'round_robin':
            turn = await self.store.get_value('round_robin', unit.id)
            index = turn if isinstance(turn, int) else 0
            await self.store.set_value('round_robin', unit.id, (index + 1) % len(members))
            return members[index % len(members)]
        if unit.routing == 'skill_match':
            agents = {agent.id: agent for agent in self.spec.ai.agents}
            matching = [m for m in members if m in agents and set(agents[m].tags) & set(run.tags)]
            members = matching
        if not members:
            return None
        loads = [await self.store.count_active(member) for member in members]
        return members[loads.index(min(loads))]

    async def _pool(self, unit: Unit, run: Run) -> None:
        """Route the work to one pool member, its lead, or the inbox."""
        member = await self._pick(unit, run)
        if member is None and unit.lead:
            member = unit.lead
        if member is None:
            reason = f"No member of pool '{unit.id}' matches the work's tags {run.tags}."
            await self.store.add(InboxItem(kind='escalation', run_id=run.id, reason=reason))
            await self._finish(run, None, 'no_match')
            return
        await self._delegate_whole(run, member)

    async def _council(self, unit: Unit, run: Run) -> None:
        """Ask every member independently and combine the answers by the decision rule."""
        members = [_member_id(member) for member in unit.member_refs]
        results = await asyncio.gather(*(self.call_target(member, run.prompt, run) for member in members))
        answers = {member: result.get('output') for member, result in zip(members, results, strict=True)}
        if unit.decision == 'judge' and unit.lead:
            briefing = '\n\n'.join(f'### {member}\n{answer}' for member, answer in answers.items())
            verdict = await self.call_target(
                unit.lead,
                f'{run.prompt}\n\nDecide from these answers:\n\n{briefing}',
                run,
            )
            await self._finish(run, {'decision': verdict.get('output'), 'answers': answers})
            return
        choices = Counter(
            str(answer.get('choice')) if isinstance(answer, dict) else str(answer) for answer in answers.values()
        )
        top, votes = choices.most_common(1)[0]
        if unit.decision == 'unanimous' and votes < len(members):
            reason = f"Council '{unit.id}' disagreed: {dict(choices)}."
            await self.store.add(
                InboxItem(kind='escalation', run_id=run.id, reason=reason, context={'answers': answers}),
            )
            await self._finish(run, {'answers': answers}, 'no_consensus')
            return
        await self._finish(run, {'decision': top, 'answers': answers})

    async def _review(self, unit: Unit, run: Run, step: Step, label: str, output: object) -> ReviewDecision:
        """Return the review decision on a pipeline step's output."""
        if step.review == 'human':
            return await self.human.review(run, label, output)
        lead = next((u.lead for u in reversed(self.spec.ai.path_to(unit.id)) if u.lead), None)
        if step.review == 'none' or lead is None:
            return ReviewDecision(approved=True, output=output)
        prompt = f'Review the output of step {label}. Reply APPROVE, or REJECT followed by your comment.\n\n{output}'
        verdict = str((await self.call_target(lead, prompt, run)).get('output', ''))
        approved = verdict.strip().upper().startswith('APPROVE')
        return ReviewDecision(approved, '' if approved else verdict.strip()[len('REJECT') :].strip(), output)

    async def _pipeline(self, unit: Unit, run: Run) -> None:
        """Run the pipeline steps in order with their review gates."""
        current: object = run.prompt
        previous: str | None = None
        for index, member in enumerate(unit.members):
            step = member if isinstance(member, Step) else Step(member=member)
            target, label = _member_id(step.member), f'{index + 1}:{_member_id(step.member)}'
            # Every step sees the original request; later steps also get the output they build on.
            work = str(current) if previous is None else f'{run.prompt}\n\nOutput of step {previous}:\n\n{current}'
            task = f'{step.instruction}\n\n{work}' if step.instruction else work
            decision = ReviewDecision(approved=False)
            for attempt in range(2):
                result = await self.call_target(target, task, run)
                if result.get('status') != 'succeeded':
                    await self._finish(run, result.get('output'), _reason(result))
                    return
                decision = await self._review(unit, run, step, label, result.get('output'))
                if decision.approved:
                    break
                task = f'{task}\n\nReviewer comment on your previous attempt ({attempt + 1}): {decision.comment}'
            if not decision.approved:
                await self._finish(run, {'step': label, 'comment': decision.comment}, 'review_rejected')
                return
            current, previous = decision.output, label
        await self._finish(run, current)

    async def execute(self, run: Run) -> None:
        """Run a claimed unit run with its unit's model and record the outcome.

        Arguments:
            run: A run in `running` status whose target is a unit.
        """
        unit = self.spec.ai.unit(run.target)
        if unit.model == 'solo':
            await self._delegate_whole(run, _member_id(unit.member_refs[0]))
        elif unit.model == 'hub':
            await self._delegate_whole(run, unit.lead or '')
        elif unit.model == 'pool':
            await self._pool(unit, run)
        elif unit.model == 'council':
            await self._council(unit, run)
        else:
            await self._pipeline(unit, run)
