"""Tests for ai module."""

from typing import Any

import pytest
from agno.agent import Agent
from agno.team import Team
from agno.workflow import Step, Workflow
from pydantic import ValidationError

from agentorg.core.spec import AI


def _custom_agent() -> Agent:
    return Agent(id='researcher', name='Researcher', instructions='Gather sources.')


def test_construction() -> None:
    """`AI` holds the user's agents, teams, and workflows."""
    researcher = _custom_agent()
    team = Team(id='research-team', name='Research Team', members=[researcher])
    workflow = Workflow(id='pipeline', name='Pipeline', steps=[Step(name='Gather', agent=researcher)])
    ai = AI(agents=[researcher], teams=[team], workflows=[workflow])
    assert ai.agents[0].id == 'researcher'
    assert ai.teams[0].id == 'research-team'
    assert ai.workflows[0].id == 'pipeline'


def test_empty_lists_validate() -> None:
    """All three fields accept empty lists."""
    ai = AI(agents=[], teams=[], workflows=[])
    assert ai.agents == [] == ai.teams == ai.workflows


def test_framework_defaults_to_agno() -> None:
    """`framework` defaults to `'agno'` — the only adapter that exists today."""
    ai = AI(agents=[], teams=[], workflows=[])
    assert ai.framework == 'agno'


def test_framework_rejects_unknown_value() -> None:
    """`framework` is a Literal — unknown frameworks fail validation."""
    with pytest.raises(ValidationError):
        AI(framework='claude_code', agents=[], teams=[], workflows=[])  # type: ignore[arg-type]


@pytest.mark.parametrize('missing', ['agents', 'teams', 'workflows'])
def test_all_fields_required(missing: str) -> None:
    """`agents`, `teams`, and `workflows` are all required keys (empty lists are fine, omission is not)."""
    fields: dict[str, Any] = {
        'agents': [],
        'teams': [],
        'workflows': [],
        'framework': 'agno',
    }
    del fields[missing]
    with pytest.raises(ValidationError):
        AI(**fields)
