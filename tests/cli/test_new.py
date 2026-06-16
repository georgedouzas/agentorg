"""Tests for the new module."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from agentorg.cli import new
from agentorg.master import add_or_update_agent, get_state, reset_state, save_draft, set_org_identity


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_state()


def test_new_help_documents_the_command():
    """`agentorg new --help` exits 0 and mentions the interview."""
    result = CliRunner().invoke(new, ['--help'])
    assert result.exit_code == 0
    assert 'interview' in result.output.lower() or 'spec.py' in result.output


def test_new_with_no_input_exits_cleanly(tmp_path: Path):
    """Sending immediate EOF terminates the chat loop without finalising."""
    draft = tmp_path / 'draft.json'
    result = CliRunner().invoke(new, ['--draft', str(draft)], input='')
    assert result.exit_code == 0


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

    result = CliRunner().invoke(new, ['--resume', '--draft', str(draft)], input='')
    assert result.exit_code == 0
    assert 'Resumed draft from' in result.output
    assert get_state().spec.org.name == 'Resumed Org'
