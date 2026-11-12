"""Assemble the interview's agent and unit drafts into the org's unit tree."""

from ..core.spec import AI, Agent, Step, Unit
from ._models import UnitDraft


def _build_unit(draft: UnitDraft, drafts: dict[str, UnitDraft], seen: set[str]) -> Unit:
    """Build a unit and its nested units from their drafts."""
    if draft.id in seen:
        msg = f"Unit '{draft.id}' is its own ancestor; fix the parent of one of its units."
        raise ValueError(msg)
    seen = seen | {draft.id}
    children = [unit.id for unit in drafts.values() if unit.parent_id == draft.id and unit.id not in draft.members]
    misplaced = [m for m in draft.members if m in drafts and drafts[m].parent_id != draft.id]
    if misplaced:
        msg = f"Unit '{draft.id}' lists units {misplaced} whose parent is another unit."
        raise ValueError(msg)
    members: list[str | Unit | Step] = []
    for member_id in [*draft.members, *children]:
        member: str | Unit = _build_unit(drafts[member_id], drafts, seen) if member_id in drafts else member_id
        if draft.model == 'pipeline' and (member_id in draft.step_reviews or member_id in draft.step_instructions):
            review = draft.step_reviews.get(member_id, 'none')
            members.append(Step(member=member, instruction=draft.step_instructions.get(member_id, ''), review=review))
        else:
            members.append(member)
    return Unit(
        id=draft.id,
        name=draft.name,
        model=draft.model,
        members=members,
        lead=draft.lead,
        routing=draft.routing,
        decision=draft.decision,
        review=draft.review,
        owners=draft.owners,
        max_autonomy=draft.max_autonomy,
        monthly_usd=draft.monthly_usd,
        approval_required=draft.approval_required,
    )


def assemble_ai(agents: list[Agent], units: list[UnitDraft]) -> AI:
    """Build and validate the org's agents and unit tree from flat unit drafts.

    Arguments:
        agents: The agent definitions.
        units: The unit drafts; exactly one has no parent once any unit exists.

    Returns:
        ai: The validated agents and root unit.

    Raises:
        ValueError: The drafts do not form a single valid tree; the message says what to fix.
    """
    if not units:
        return AI(agents=agents)
    roots = [unit for unit in units if unit.parent_id is None]
    if len(roots) != 1:
        msg = f'The org needs exactly one root unit (a unit without a parent); found {[u.id for u in roots] or "none"}.'
        raise ValueError(msg)
    drafts = {unit.id: unit for unit in units}
    unknown_parents = sorted({u.parent_id for u in units if u.parent_id and u.parent_id not in drafts})
    if unknown_parents:
        msg = f'Units name parents that do not exist: {unknown_parents}.'
        raise ValueError(msg)
    root = _build_unit(roots[0], drafts, set())
    unreachable = sorted(set(drafts) - {unit.id for unit in root.iter_units()})
    if unreachable:
        msg = f'Units {unreachable} are not under the root unit; their parents form a cycle.'
        raise ValueError(msg)
    return AI(agents=agents, root=root)
