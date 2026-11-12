"""Tests for the models module."""

import pytest
from pydantic import ValidationError

from agentorg.master import CustomSkill, CustomTool, UnitDraft


def test_unit_draft_defaults_to_an_empty_root() -> None:
    """A unit draft starts as a root with no members and no lead."""
    draft = UnitDraft(id='research', name='Research', model='hub')
    assert (draft.parent_id, draft.lead, draft.members, draft.routing) == (None, None, [], 'least_loaded')


def test_unit_draft_rejects_unknown_model() -> None:
    """The governance model is a closed set."""
    with pytest.raises(ValidationError):
        UnitDraft(id='u', name='U', model='democracy')  # type: ignore[arg-type]


def test_custom_artefacts_hold_their_sources() -> None:
    """Custom tools and skills keep their name and source."""
    assert CustomTool(name='t', source='src').source == 'src'
    assert CustomSkill(name='s', skill_md='# S').skill_md == '# S'
