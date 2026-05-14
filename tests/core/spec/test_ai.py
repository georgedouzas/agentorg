"""Tests for `agentorg.core.spec._ai.AI`."""

import pytest
from agno.agent import Agent
from agno.team import Team
from agno.workflow import Step, Workflow
from pydantic import ValidationError

from agentorg.core.spec import AI, PLATFORM_AGENTS

_MODEL = 'google:gemini-2.0-flash'


def _custom_agent() -> Agent:
    return Agent(id='researcher', name='Researcher', model=_MODEL, instructions='Gather sources.')


def test_construction_with_platform_agents_and_extras() -> None:
    """`AI` holds the platform agents plus any custom agents, teams, and workflows."""
    researcher = _custom_agent()
    team = Team(id='research-team', name='Research Team', members=[researcher], model=_MODEL)
    workflow = Workflow(id='pipeline', name='Pipeline', steps=[Step(name='Gather', agent=researcher)])
    ai = AI(agents=[*PLATFORM_AGENTS, researcher], teams=[team], workflows=[workflow])
    assert {a.id for a in ai.agents} >= {a.id for a in PLATFORM_AGENTS}
    assert ai.teams[0].id == 'research-team'
    assert ai.workflows[0].id == 'pipeline'


def test_platform_agents_alone_validate() -> None:
    """The six platform agents with no extras is a valid `AI`."""
    ai = AI(agents=list(PLATFORM_AGENTS), teams=[], workflows=[])
    assert len(ai.agents) == len(PLATFORM_AGENTS)


def test_missing_platform_agents_raises() -> None:
    """Dropping a platform agent fails validation — they are required."""
    with pytest.raises(ValidationError, match='platform agents'):
        AI(agents=[_custom_agent()], teams=[], workflows=[])


def test_empty_agents_raises() -> None:
    """An empty agent list is missing every platform agent."""
    with pytest.raises(ValidationError, match='platform agents'):
        AI(agents=[], teams=[], workflows=[])


@pytest.mark.parametrize('missing', ['agents', 'teams', 'workflows'])
def test_all_fields_required(missing: str) -> None:
    """`agents`, `teams`, and `workflows` are all required keys (empty lists are fine, omission is not)."""
    fields: dict[str, list[object]] = {
        'agents': list(PLATFORM_AGENTS),
        'teams': [],
        'workflows': [],
    }
    del fields[missing]
    with pytest.raises(ValidationError):
        AI(**fields)
