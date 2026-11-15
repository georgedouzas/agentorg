"""Tests for the chat module."""

from typing import Any

import pytest

from agentorg.core.operations import ChatUser
from agentorg.master import MasterReply, get_state, reset_state, set_budget, set_org_identity
from agentorg.master.ui import MasterChat

from ..conftest import seed_discovery

USER = ChatUser('u1', 'dana@acme.com', 'c1')


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_state()


class Interview:
    """Records the hooks MasterChat calls and answers turns with a scripted reply."""

    def __init__(self, reply: MasterReply | Exception, *, advance: bool = False) -> None:
        """Answer with `reply`, moving to the next stage first when `advance` is set."""
        self.reply = reply
        self.advance = advance
        self.messages: list[str] = []
        self.saved = 0

    async def run(self, message: str) -> MasterReply:
        """Answer a message."""
        self.messages.append(message)
        if isinstance(self.reply, Exception):
            raise self.reply
        if self.advance:
            get_state().stage = 'configure'
        return self.reply

    async def after(self) -> None:
        """Count draft saves."""
        self.saved += 1


def _chat(interview: Interview, preview: dict[str, Any] | None = None) -> MasterChat:
    return MasterChat(interview.run, interview.after, lambda: preview or {'status': 'disabled', 'detail': 'off'})


async def _answer(chat: MasterChat, text: str) -> str:
    reply = await chat.turn('agentorg', [{'role': 'user', 'content': text}], USER)
    parts = [part async for part in reply.deltas(0.01, 0.01) if part is not None]
    await reply.finish()
    return ''.join(parts)


async def test_models_offer_the_interview() -> None:
    """The master lists exactly the agentorg model."""
    assert await _chat(Interview(MasterReply('x'))).models() == {'agentorg': 'AgentOrg'}


async def test_turn_streams_tools_reply_and_saves() -> None:
    """A turn shows the tool lines and reply of the stage agent, then saves the draft."""
    interview = Interview(MasterReply('Noted.', ['record_discovery_summary']))
    text = await _answer(_chat(interview), 'We run a help desk.')
    assert text == '> record_discovery_summary\n\nNoted.'
    assert (interview.messages, interview.saved) == (['We run a help desk.'], 1)


async def test_turn_names_a_stage_change() -> None:
    """When the agent advances the interview, the reply ends with the new stage."""
    text = await _answer(_chat(Interview(MasterReply('Moving on.'), advance=True)), 'Yes, continue.')
    assert text.endswith('Now in **Configure**.')


async def test_failed_turn_is_reported() -> None:
    """An agent failure becomes reply text."""
    text = await _answer(_chat(Interview(RuntimeError('model down'))), 'Hello')
    assert 'The interviewer failed: model down' in text


async def test_stage_reports_progress_and_blockers() -> None:
    """The stage command marks done and current stages and lists what blocks the next one."""
    seed_discovery()
    get_state().stage = 'configure'
    text = await _chat(Interview(MasterReply('x'))).command('agentorg', '/stage', USER)
    assert '✓ Discover' in text
    assert '▶ Configure' in text
    assert 'budget' in text


async def test_next_is_refused_while_blocked() -> None:
    """Next lists the blockers and leaves the stage unchanged."""
    interview = Interview(MasterReply('x'))
    text = await _chat(interview).command('agentorg', '/next', USER)
    assert text.startswith('Still in **Discover**')
    assert (get_state().stage, interview.saved) == ('discover', 0)


async def test_next_advances_when_clear() -> None:
    """Next moves on once nothing blocks it, and saves the draft."""
    seed_discovery()
    get_state().stage = 'configure'
    set_org_identity(
        name='Acme Help',
        slug='acme-help',
        package_name='acme_help',
        description=(
            'Acme Help answers questions from freelancers about invoicing, expenses and tax exports in our accounting '
            'app, explains features step by step, and hands billing disputes to a human on the support team.'
        ),
        admin_name='Dana',
        admin_email='dana@acme.com',
    )
    set_budget(monthly_usd=20)
    interview = Interview(MasterReply('x'))
    text = await _chat(interview).command('agentorg', '/next', USER)
    assert 'Now in **Build**' in text
    assert (get_state().stage, interview.saved) == ('build', 1)


async def test_spec_preview_reset_and_help() -> None:
    """The read commands answer from state; reset needs confirmation; unknown commands list them all."""
    interview = Interview(MasterReply('x'))
    ready = {'status': 'ready', 'slug': 'acme', 'frontend_url': 'http://127.0.0.1:5173'}
    chat = _chat(interview, ready)
    get_state().stage = 'configure'
    set_org_identity(name='Acme Help')
    spec = await chat.command('agentorg', '/spec', USER)
    preview = await chat.command('agentorg', '/preview', USER)
    unconfirmed = await chat.command('agentorg', '/reset', USER)
    still = get_state().spec.org.name
    confirmed = await chat.command('agentorg', '/reset confirm', USER)
    unknown = await chat.command('agentorg', '/what', USER)
    assert spec.startswith('```python\n')
    assert "name='Acme Help'" in spec
    assert 'http://127.0.0.1:5173' in preview
    assert ('/reset confirm' in unconfirmed, still) == (True, 'Acme Help')
    assert 'starts again' in confirmed
    assert get_state().stage == 'discover'
    assert '/stage' in unknown


async def test_preview_not_ready() -> None:
    """The preview command reports a preview that is not running."""
    text = await _chat(Interview(MasterReply('x'))).command('agentorg', '/preview', USER)
    assert text == 'The preview is disabled: off.'
