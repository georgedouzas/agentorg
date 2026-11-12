"""Tests for the prompts module."""

from datetime import UTC, datetime

from agentorg.core.operations import render_prompt


def test_render_prompt_fills_trigger_context_and_parameters() -> None:
    """Every documented variable is filled, with payloads rendered as JSON."""
    template = '{trigger_id} at {now}: event={event} body={body} message={message} focus={focus}'
    prompt = render_prompt(
        template,
        trigger_id='crm',
        parameters={'focus': 'Billing'},
        event={'type': 'report'},
        body={'ticket': 42},
        message={'order': 'A-1'},
        now=datetime(2026, 11, 12, 8, 0, tzinfo=UTC),
    )
    assert prompt == (
        'crm at 2026-11-12T08:00+00:00: event={"type": "report"} body={"ticket": 42} '
        'message={"order": "A-1"} focus=Billing'
    )


def test_render_prompt_renders_missing_payloads_as_null() -> None:
    """A payload the trigger kind does not carry renders as JSON null."""
    assert render_prompt('{event}', trigger_id='t', parameters={}) == 'null'
