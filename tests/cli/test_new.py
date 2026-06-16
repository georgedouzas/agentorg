"""Tests for the new module."""

from pathlib import Path

import pytest
from agno.agent import Agent
from click.testing import CliRunner

from agentorg.cli import new
from agentorg.master import add_or_update_agent, get_state, reset_state, save_draft, set_org_identity


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_state()


@pytest.fixture
def _skip_cli_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace `agno.Agent.acli_app` with a no-op so the chat REPL doesn't try to read from stdin."""

    async def _noop_cli_app(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(Agent, 'acli_app', _noop_cli_app)


def test_new_help_documents_the_command():
    """`agentorg new --help` exits 0 and mentions the interview."""
    result = CliRunner().invoke(new, ['--help'])
    assert result.exit_code == 0
    assert 'interview' in result.output.lower() or 'spec.py' in result.output


@pytest.mark.usefixtures('_skip_cli_app')
def test_new_without_resume_starts_from_a_fresh_seed(tmp_path: Path):
    """Without `--resume`, the working spec is reset to the placeholder seed before the chat starts."""
    set_org_identity(name='Previous Session Org', description='leftover')
    assert get_state().spec.org.name == 'Previous Session Org'

    result = CliRunner().invoke(new, ['--draft', str(tmp_path / 'draft.json')])
    assert result.exit_code == 0
    assert get_state().spec.org.name == 'My Org'  # back to seed


@pytest.mark.usefixtures('_skip_cli_app')
def test_new_resume_loads_an_existing_draft(tmp_path: Path):
    """`--resume` reads the draft file before the chat loop starts."""
    set_org_identity(name='Resumed Org', description='From draft.')
    add_or_update_agent(
        agent_id='researcher',
        name='Researcher',
        role='Gather sources.',
        in_scope=['Sources'],
        workflow=['Step.'],
    )
    draft = tmp_path / 'draft.json'
    save_draft(draft)
    reset_state()
    assert get_state().spec.org.name == 'My Org'  # confirm fresh

    result = CliRunner().invoke(new, ['--resume', '--draft', str(draft)])
    assert result.exit_code == 0
    assert 'Resumed draft from' in result.output
    assert get_state().spec.org.name == 'Resumed Org'
