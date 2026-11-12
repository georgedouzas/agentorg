"""Tests for the structure module."""

import pytest

from agentorg.core.spec import Agent
from agentorg.master import UnitDraft, assemble_ai


def _agents(*ids: str) -> list[Agent]:
    return [Agent(id=agent_id, name=agent_id, role='Works.') for agent_id in ids]


def test_assemble_ai_without_units_has_no_root() -> None:
    """Before any unit exists the org has no tree."""
    assert assemble_ai([], []).root is None


def test_assemble_ai_nests_children_by_parent() -> None:
    """Child units join their parent's members through `parent_id`."""
    units = [
        UnitDraft(id='org', name='Org', model='hub', lead='lead'),
        UnitDraft(id='desk', name='Desk', model='pool', parent_id='org', members=['a', 'b']),
    ]
    ai = assemble_ai(_agents('lead', 'a', 'b'), units)
    assert [unit.id for unit in ai.units] == ['org', 'desk']
    assert ai.path_to('a')[-1].id == 'desk'


def test_assemble_ai_builds_pipeline_steps() -> None:
    """Pipeline members with a review or instruction become steps."""
    unit = UnitDraft(
        id='content',
        name='C',
        model='pipeline',
        members=['draft', 'publish'],
        step_reviews={'draft': 'human'},
    )
    root = assemble_ai(_agents('draft', 'publish'), [unit]).root
    assert root is not None
    assert root.members[0].review == 'human'  # type: ignore[union-attr]
    assert root.members[1] == 'publish'


@pytest.mark.parametrize(
    ('units', 'match'),
    [
        ([UnitDraft(id='a', name='A', model='solo'), UnitDraft(id='b', name='B', model='solo')], 'exactly one root'),
        ([UnitDraft(id='a', name='A', model='solo', parent_id='ghost')], 'exactly one root'),
        (
            [UnitDraft(id='a', name='A', model='hub'), UnitDraft(id='b', name='B', model='solo', parent_id='ghost')],
            'do not exist',
        ),
        (
            [
                UnitDraft(id='root', name='R', model='hub', lead='x'),
                UnitDraft(id='c1', name='C1', model='solo', parent_id='c2'),
                UnitDraft(id='c2', name='C2', model='solo', parent_id='c1'),
            ],
            'cycle',
        ),
    ],
)
def test_assemble_ai_rejects_broken_trees(units: list[UnitDraft], match: str) -> None:
    """Missing or duplicated roots, unknown parents and parent cycles are named."""
    with pytest.raises(ValueError, match=match):
        assemble_ai(_agents('x'), units)


def test_assemble_ai_reports_incomplete_unit() -> None:
    """A hub without its lead fails with the spec's own message."""
    with pytest.raises(ValueError, match='needs a `lead`'):
        assemble_ai(_agents('a'), [UnitDraft(id='hub', name='Hub', model='hub', members=['a'])])
