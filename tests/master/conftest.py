"""Shared fixtures - reset the master agent's state before each test so order doesn't matter."""

from collections.abc import AsyncIterator
from typing import Any, ClassVar

import pytest
from claude_agent_sdk import ResultMessage

from agentorg.master import Discovery, get_state, reset_state


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Reset the singleton interview state at the start of every test."""
    reset_state()


def advance_to_configure_stage() -> None:
    """Bypass Stage 1's identity gate for tests by jumping the cursor to 'configure'.

    Most pre-existing `set_org_identity` tests are unit tests of the underlying tool; they predate the staged interview
    machinery and treat the tool as stage-agnostic. Calling this in the test body lets them keep doing so without
    dragging the rest of the conftest through a fake interview.
    """
    get_state().stage = 'configure'


def seed_discovery() -> None:
    """Pre-fill `state.discovery` so tests can call principle / budget tools directly.

    Bypasses the full Stage-1 Phase-A interview gate. Use this in tests that need to drive
    `add_or_update_principle_section` or `set_org_identity(budget=...)` without conducting a fake interview first. Field
    values are deliberately long enough to pass the per- field minimum-length validation enforced by
    `record_discovery_summary`.
    """
    get_state().discovery = Discovery(
        what_the_group_does=(
            'Test fixture: this group designs and operates X end-to-end, covering both '
            'the upstream research and downstream delivery to internal stakeholders.'
        ),
        who_serves=(
            'Test fixture: internal product teams and external researchers who need '
            'curated digests of recent work on a target topic.'
        ),
        concrete_tasks_owned=(
            'Test fixture: literature review; source curation; weekly brief drafting; '
            'review-with-stakeholder; publish + archive in knowledge store.'
        ),
        typical_flow=(
            'Test fixture: topic arrives -> agents search literature -> shortlist sources '
            "-> distil findings -> draft brief -> review with the requester -> publish."
        ),
        business_context=(
            'Test fixture: internal research-ops team inside a model-evaluation org, '
            'serving 4 product squads on a weekly cadence.'
        ),
        current_pain_or_alternative=(
            'Test fixture: today a single PhD spends a week per brief; the group lets us '
            'survey 5x more topics per quarter without hiring more researchers.'
        ),
    )


ECHO_TOOL_SOURCE = '\n'.join(
    [
        '"""Echo tool for master tests."""',
        '',
        'async def echo_tool(message: str) -> str:',
        '    """Return the message unchanged."""',
        '    return message',
    ],
)


def build_hub_org() -> None:
    """Build a valid org through the tools: a hub `research` led by `lead` with member `researcher`."""
    from agentorg.master import add_or_update_agent, add_or_update_unit  # noqa: PLC0415 - fixture helper

    add_or_update_unit(unit_id='research', name='Research', model='hub')
    add_or_update_agent(agent_id='lead', name='Lead', role='Leads the research.', unit_id='research', as_lead=True)
    add_or_update_agent(agent_id='researcher', name='Researcher', role='Gathers sources.', unit_id='research')


class ScriptedClient:
    """A fake SDK client that replays scripted messages and records what it was asked."""

    calls: ClassVar[list['ScriptedClient']] = []

    def __init__(self, options: Any, messages: list[object]) -> None:  # noqa: ANN401
        """Keep the options and the messages to replay."""
        self.options = options
        self.messages = messages
        self.prompt = ''
        ScriptedClient.calls.append(self)

    async def __aenter__(self) -> 'ScriptedClient':
        """Open the fake session."""
        return self

    async def __aexit__(self, *_: object) -> None:
        """Close the fake session."""

    async def query(self, prompt: str) -> None:
        """Record the prompt."""
        self.prompt = prompt

    async def receive_response(self) -> AsyncIterator[object]:
        """Replay the scripted messages."""
        for message in self.messages:
            yield message


def result_message(result: str = 'Done.', session_id: str = 'sdk-1', **fields: Any) -> ResultMessage:  # noqa: ANN401
    """Return an SDK result message with test defaults for the timing fields."""
    defaults = {'duration_ms': 1, 'duration_api_ms': 1, 'is_error': False, 'num_turns': 1}
    return ResultMessage(subtype='success', result=result, session_id=session_id, **{**defaults, **fields})
