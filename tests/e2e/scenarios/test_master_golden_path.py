"""Golden path: interview the master through its chat API, then render, boot and chat with the org it wrote."""

import runpy
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from agentorg.core.spec import Spec
from agentorg.master import finalize_spec, get_state, reset_state
from agentorg.master.ui import build_app

from ..conftest import Deployment
from ..harness.mock_anthropic import MockAnthropic

SCRIPT: dict[str, list[str]] = {
    'discover': [
        (
            'We are Acme Help, a small team answering customer questions about our accounting app for freelancers. '
            'We value accurate, friendly answers and we never promise refunds.'
        ),
        'That covers it. Record the summary and move on to the next stage.',
    ],
    'configure': [
        (
            'Call it Acme Help, slug acme-help, package acme_help. The admin is Dana Admin, dana@acme.example. '
            'The description: Acme Help answers questions from freelancers about invoicing, expenses and tax exports '
            'in our accounting app, explains features step by step, and hands anything about billing disputes to a '
            'human. Budget 20 USD a month. Keep the default infrastructure.'
        ),
        'Yes, all correct. Advance to the next stage.',
    ],
    'build': [
        (
            'Create one solo unit called Desk with a single agent, Helper, who answers customer questions about the '
            'app in a friendly tone. No custom tools and no triggers.'
        ),
        'Looks good. Advance to the next stage.',
    ],
    'refine': ['Nothing to add for now. Advance to the next stage.'],
}


@pytest.mark.max_usd(1.0)
async def test_master_golden_path(
    deploy: Callable[..., Deployment],
    model_api: MockAnthropic,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A scripted interview writes a spec that validates, renders, boots and answers a chat message."""
    monkeypatch.setenv('ANTHROPIC_BASE_URL', model_api.url)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'e2e-mock')
    monkeypatch.setenv('CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC', '1')
    reset_state()
    master = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=build_app(chat_api_key='master-key')),
        base_url='http://master',
        headers={'Authorization': 'Bearer master-key'},
        timeout=600,
    )
    async with master:
        for stage, messages in SCRIPT.items():
            assert get_state().stage == stage, f'the interview did not reach {stage}'
            for message in messages:
                body = {'model': 'agentorg', 'messages': [{'role': 'user', 'content': message}]}
                (await master.post('/v1/chat/completions', json=body)).raise_for_status()
    assert get_state().stage == 'handoff'
    spec_path = tmp_path / 'written' / 'spec.py'
    finalize_spec(spec_path)
    spec = runpy.run_path(str(spec_path))['spec']
    assert isinstance(spec, Spec)
    org = deploy(spec_path)
    reply = org.client.chat(spec.ai.agents[0].id, 'How do I export my expenses for my tax return?')
    assert reply['choices'][0]['message']['content']
    assert org.client.runs()[0]['status'] == 'succeeded'
