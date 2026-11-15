"""Tests for the tools module."""

import pytest
from pydantic import BaseModel

from agentorg.core.adapters.claude import as_sdk_server, as_sdk_tool, tool_error
from agentorg.core.agents.tools import tool


class Ticket(BaseModel):
    """A support ticket."""

    id: int
    subject: str


def lookup(ticket_id: int, verbose: bool = False) -> str:
    """Look up a ticket.

    Longer description that is not part of the tool summary.
    """
    return f'ticket {ticket_id} verbose={verbose}'


@tool('read')
async def summarise(ticket: Ticket) -> dict[str, object]:
    """Summarise a ticket."""
    return {'id': ticket.id, 'subject': ticket.subject.upper()}


def test_as_sdk_tool_derives_schema_and_description() -> None:
    """The schema comes from the signature and the description from the docstring summary."""
    sdk_tool = as_sdk_tool(lookup)
    assert (sdk_tool.name, sdk_tool.description) == ('lookup', 'Look up a ticket.')
    assert isinstance(sdk_tool.input_schema, dict)
    assert sdk_tool.input_schema['required'] == ['ticket_id']
    assert sdk_tool.input_schema['properties']['verbose']['default'] is False


def test_as_sdk_tool_marks_read_tools_read_only() -> None:
    """Read tools advertise a read-only hint and undecorated tools do not."""
    assert summarise.side_effect == 'read'  # type: ignore[attr-defined]
    assert as_sdk_tool(summarise).annotations.readOnlyHint is True  # type: ignore[union-attr]
    assert as_sdk_tool(lookup).annotations.readOnlyHint is False  # type: ignore[union-attr]


async def test_as_sdk_tool_calls_sync_function() -> None:
    """A sync function's string result is returned as text."""
    result = await as_sdk_tool(lookup).handler({'ticket_id': 7})
    assert result == {'content': [{'type': 'text', 'text': 'ticket 7 verbose=False'}]}


async def test_as_sdk_tool_validates_models_and_serialises_results() -> None:
    """Pydantic arguments are validated and non-string results are returned as JSON."""
    result = await as_sdk_tool(summarise).handler({'ticket': {'id': 1, 'subject': 'refund'}})
    assert result['content'][0]['text'] == '{"id": 1, "subject": "REFUND"}'


async def test_as_sdk_tool_reports_invalid_arguments_as_tool_error() -> None:
    """Invalid arguments come back to the agent as an error result."""
    result = await as_sdk_tool(lookup).handler({'ticket_id': 'seven'})
    assert result['is_error'] is True
    assert 'ticket_id' in result['content'][0]['text']


async def test_as_sdk_tool_reports_failures_without_a_traceback() -> None:
    """A raising tool returns its error type and first message line, never the traceback."""

    def broken() -> str:
        """Fail like a provider without a key."""
        msg = 'Missing API key.\nTraceback (most recent call last):\n  File "/usr/lib/x.py"'
        raise RuntimeError(msg)

    result = await as_sdk_tool(broken).handler({})
    assert result == {'content': [{'type': 'text', 'text': 'RuntimeError: Missing API key.'}], 'is_error': True}
    assert tool_error(ValueError()) == 'ValueError'


@pytest.mark.parametrize('functions', [[lookup], [lookup, summarise]])
def test_as_sdk_server_serves_every_function(functions: list[object]) -> None:
    """The server configuration names the server and carries an in-process instance."""
    server = as_sdk_server('custom', functions)  # type: ignore[arg-type]
    assert server['type'] == 'sdk'
    assert server['name'] == 'custom'
