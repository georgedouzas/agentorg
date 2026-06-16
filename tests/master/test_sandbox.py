"""Tests for the sandbox module."""

import textwrap

import pytest

from agentorg.master import ToolValidationError, validate_tool_source

VALID_TOOL_SOURCE = textwrap.dedent(
    '''
    """A simple custom tool that echoes its input."""

    async def echo_tool(message: str) -> str:
        """Return the message unchanged - used as a smoke test for the sandbox."""
        return message
    ''',
).strip()


def test_validate_tool_source_accepts_a_well_formed_async_function():
    """A clean `async def <name>(...): ...` passes validation."""
    validate_tool_source('echo_tool', VALID_TOOL_SOURCE)


def test_validate_tool_source_rejects_syntax_error():
    """An obvious syntax error is caught by ast.parse before the subprocess runs."""
    with pytest.raises(ToolValidationError, match='syntax error'):
        validate_tool_source('broken', 'async def broken(:')


def test_validate_tool_source_rejects_missing_target_function():
    """A file without the expected `async def <name>` is rejected before the subprocess runs."""
    source = 'async def other(): return "x"'
    with pytest.raises(ToolValidationError, match='no top-level'):
        validate_tool_source('expected', source)


def test_validate_tool_source_rejects_sync_function_with_the_target_name():
    """A sync `def <name>` is rejected because tools must be coroutine functions."""
    source = 'def echo_tool(): return "x"'
    with pytest.raises(ToolValidationError, match='no top-level'):
        validate_tool_source('echo_tool', source)


def test_validate_tool_source_rejects_import_time_exceptions():
    """An import-time exception surfaces as a sandbox failure."""
    source = 'raise RuntimeError("boom")\n\nasync def echo_tool(): return "x"'
    with pytest.raises(ToolValidationError, match='sandbox import failed'):
        validate_tool_source('echo_tool', source)
