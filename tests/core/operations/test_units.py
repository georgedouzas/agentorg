"""Tests for the units module."""

from collections.abc import Callable
from typing import Any

import pytest

from agentorg.core.operations import ReviewDecision, Run, Store, UnitEngine
from agentorg.core.spec import Spec

CHOICE = {'format': 'json', 'json_schema': {'type': 'object', 'properties': {'choice': {'type': 'string'}}}}


class Members:
    """Answers delegated calls from a per-target script and records them."""

    def __init__(self, answers: dict[str, Callable[[str], object]]) -> None:
        """Keep a function per target that maps the task to its output."""
        self.answers = answers
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, target: str, task: str, parent: Run) -> dict[str, Any]:
        """Record the call and return the scripted output as a succeeded run."""
        self.calls.append((target, task))
        return {'status': 'succeeded', 'output': self.answers[target](task)}


class Reviewer:
    """Returns scripted human review decisions in order."""

    def __init__(self, *decisions: ReviewDecision) -> None:
        """Keep the decisions to return."""
        self.decisions = list(decisions)
        self.reviewed: list[tuple[str, object]] = []

    async def review(self, run: Run, step: str, output: object) -> ReviewDecision:
        """Record what was reviewed and return the next decision, keeping the output when approved."""
        self.reviewed.append((step, output))
        decision = self.decisions.pop(0)
        return ReviewDecision(
            decision.approved,
            decision.comment,
            output if decision.output is None else decision.output,
        )


def _agent(agent_id: str, **fields: Any) -> dict[str, Any]:
    return {'id': agent_id, 'name': agent_id, 'role': 'Works.', **fields}


def _spec(spec_dict_minimal: dict[str, Any], agents: list[dict[str, Any]], root: dict[str, Any]) -> Spec:
    spec_dict_minimal['ai'] = {'agents': agents, 'root': root}
    return Spec.model_validate(spec_dict_minimal)


async def _run(engine: UnitEngine, store: Store, target: str, prompt: str = 'Task', **fields: Any) -> Run:
    run = await store.create_run(target=target, trigger_kind='manual', prompt=prompt, **fields)
    await store.claim(run.id, 'w1')
    await engine.execute(run)
    stored = await store.get_run(run.id)
    assert stored is not None
    return stored


async def test_hub_enters_at_lead(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """Work addressed to a hub runs its lead."""
    spec = _spec(
        spec_dict_minimal,
        [_agent('lead'), _agent('a')],
        {'id': 'hub', 'name': 'H', 'model': 'hub', 'lead': 'lead', 'members': ['a']},
    )
    members = Members({'lead': lambda task: f'lead handled {task}'})
    run = await _run(UnitEngine(spec, store, members, Reviewer()), store, 'hub', 'Plan')
    assert members.calls == [('lead', 'Plan')]
    assert (run.status, run.output) == ('succeeded', 'lead handled Plan')


async def test_solo_runs_its_agent(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """Work addressed to a solo unit runs its only agent."""
    members = Members({'assistant': lambda task: 'ok'})
    run = await _run(UnitEngine(Spec.model_validate(spec_dict_minimal), store, members, Reviewer()), store, 'org')
    assert (members.calls, run.output) == ([('assistant', 'Task')], 'ok')


@pytest.fixture
def pool_spec(spec_dict_minimal: dict[str, Any]) -> Callable[..., Spec]:
    """Build a pool of `a` (tag billing) and `b` (tag tech) with the given routing and optional lead."""

    def build(routing: str, lead: str | None = None) -> Spec:
        agents = [_agent('a', tags=['billing']), _agent('b', tags=['tech'])] + ([_agent(lead)] if lead else [])
        root = {'id': 'pool', 'name': 'P', 'model': 'pool', 'routing': routing, 'members': ['a', 'b'], 'lead': lead}
        return _spec(spec_dict_minimal, agents, root)

    return build


async def test_pool_routes_to_least_loaded(pool_spec: Callable[..., Spec], store: Store) -> None:
    """With `a` busy on two runs and `b` idle, new work goes to `b`."""
    for _ in range(2):
        busy = await store.create_run(target='a', trigger_kind='manual', prompt='x')
        await store.claim(busy.id, 'w')
    members = Members({'a': str, 'b': str})
    await _run(UnitEngine(pool_spec('least_loaded'), store, members, Reviewer()), store, 'pool')
    assert members.calls[0][0] == 'b'


async def test_pool_round_robin_alternates(pool_spec: Callable[..., Spec], store: Store) -> None:
    """Round robin hands consecutive work to consecutive members."""
    members = Members({'a': str, 'b': str})
    engine = UnitEngine(pool_spec('round_robin'), store, members, Reviewer())
    for _ in range(3):
        await _run(engine, store, 'pool')
    assert [target for target, _ in members.calls] == ['a', 'b', 'a']


async def test_pool_skill_match_routes_by_tags(pool_spec: Callable[..., Spec], store: Store) -> None:
    """Work tagged `tech` goes to the member tagged `tech`."""
    members = Members({'a': str, 'b': str})
    await _run(UnitEngine(pool_spec('skill_match'), store, members, Reviewer()), store, 'pool', tags=['tech'])
    assert members.calls[0][0] == 'b'


async def test_pool_without_match_goes_to_lead(pool_spec: Callable[..., Spec], store: Store) -> None:
    """Unmatched work goes to the pool's lead."""
    members = Members({'a': str, 'b': str, 'triage': str})
    await _run(
        UnitEngine(pool_spec('skill_match', lead='triage'), store, members, Reviewer()),
        store,
        'pool',
        tags=['legal'],
    )
    assert members.calls[0][0] == 'triage'


async def test_pool_without_match_or_lead_escalates(pool_spec: Callable[..., Spec], store: Store) -> None:
    """Unmatched work without a pool lead creates an inbox item and fails the run."""
    run = await _run(
        UnitEngine(pool_spec('skill_match'), store, Members({}), Reviewer()),
        store,
        'pool',
        tags=['legal'],
    )
    assert (run.status, run.failure_reason) == ('failed', 'no_match')
    assert (await store.list_inbox())[0].kind == 'escalation'


def _council(spec_dict_minimal: dict[str, Any], decision: str, lead: str | None = None) -> Spec:
    agents = [_agent(f'u{i}', output=CHOICE) for i in (1, 2, 3)] + ([_agent(lead)] if lead else [])
    root = {
        'id': 'board',
        'name': 'B',
        'model': 'council',
        'decision': decision,
        'members': ['u1', 'u2', 'u3'],
        'lead': lead,
    }
    return _spec(spec_dict_minimal, agents, root)


async def test_council_majority_decides_and_keeps_answers(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """Answers approve, approve, reject decide approve, and all three answers are recorded."""
    votes = {'u1': 'approve', 'u2': 'approve', 'u3': 'reject'}
    members = Members({member: (lambda task, v=vote: {'choice': v}) for member, vote in votes.items()})
    run = await _run(UnitEngine(_council(spec_dict_minimal, 'majority'), store, members, Reviewer()), store, 'board')
    assert run.output['decision'] == 'approve'
    assert run.output['answers'] == {member: {'choice': vote} for member, vote in votes.items()}
    assert sorted(target for target, _ in members.calls) == ['u1', 'u2', 'u3']


async def test_council_unanimous_disagreement_escalates(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """A unanimous council that disagrees fails with `no_consensus` and creates an inbox item."""
    members = Members(
        {
            'u1': lambda t: {'choice': 'approve'},
            'u2': lambda t: {'choice': 'approve'},
            'u3': lambda t: {'choice': 'reject'},
        },
    )
    run = await _run(UnitEngine(_council(spec_dict_minimal, 'unanimous'), store, members, Reviewer()), store, 'board')
    assert run.failure_reason == 'no_consensus'
    assert 'disagreed' in (await store.list_inbox())[0].reason


async def test_council_judge_synthesises_answers(spec_dict_minimal: dict[str, Any], store: Store) -> None:
    """A judge council passes every member answer to its lead."""
    members = Members(
        {
            'u1': lambda t: 'yes',
            'u2': lambda t: 'no',
            'u3': lambda t: 'maybe',
            'chair': lambda t: 'yes, with conditions',
        },
    )
    run = await _run(
        UnitEngine(_council(spec_dict_minimal, 'judge', 'chair'), store, members, Reviewer()),
        store,
        'board',
    )
    assert run.output['decision'] == 'yes, with conditions'
    assert '### u2\nno' in members.calls[-1][1]


@pytest.fixture
def pipeline(spec_dict_minimal: dict[str, Any]) -> Spec:
    """A research, draft (human review), publish pipeline."""
    root = {
        'id': 'content',
        'name': 'C',
        'model': 'pipeline',
        'members': ['research', {'member': 'draft', 'instruction': 'Write it up.', 'review': 'human'}, 'publish'],
    }
    return _spec(spec_dict_minimal, [_agent('research'), _agent('draft'), _agent('publish')], root)


def _content_members() -> Members:
    return Members(
        {'research': lambda t: 'notes', 'draft': lambda t: f'draft from [{t}]', 'publish': lambda t: f'published {t}'},
    )


async def test_pipeline_chains_outputs_through_review(pipeline: Spec, store: Store) -> None:
    """Each step gets the previous output, and the human review gates the next step."""
    members, reviewer = _content_members(), Reviewer(ReviewDecision(approved=True))
    run = await _run(UnitEngine(pipeline, store, members, reviewer), store, 'content', 'Topic')
    assert [target for target, _ in members.calls] == ['research', 'draft', 'publish']
    assert members.calls[1][1] == 'Write it up.\n\nnotes'
    assert reviewer.reviewed == [('2:draft', 'draft from [Write it up.\n\nnotes]')]
    assert (run.status, run.output) == ('succeeded', 'published draft from [Write it up.\n\nnotes]')


async def test_pipeline_reruns_step_once_after_rejection(pipeline: Spec, store: Store) -> None:
    """A rejected step re-runs once with the reviewer's comment, then continues when approved."""
    members = _content_members()
    reviewer = Reviewer(ReviewDecision(approved=False, comment='Too long'), ReviewDecision(approved=True))
    run = await _run(UnitEngine(pipeline, store, members, reviewer), store, 'content')
    assert [target for target, _ in members.calls] == ['research', 'draft', 'draft', 'publish']
    assert 'Reviewer comment on your previous attempt (1): Too long' in members.calls[2][1]
    assert run.status == 'succeeded'


async def test_pipeline_fails_after_second_rejection(pipeline: Spec, store: Store) -> None:
    """Two rejections of the same step fail the pipeline with `review_rejected` before the next step."""
    members = _content_members()
    reviewer = Reviewer(
        ReviewDecision(approved=False, comment='No'),
        ReviewDecision(approved=False, comment='Still no'),
    )
    run = await _run(UnitEngine(pipeline, store, members, reviewer), store, 'content')
    assert (run.status, run.failure_reason) == ('failed', 'review_rejected')
    assert 'publish' not in [target for target, _ in members.calls]
