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
    '''

       ,
).strip()
VALID_CASES = [{'input': {'message': 'pong'}, 'expected_contains': 'pong'}]


def test_validate_tool_source_accepts_a_well_formed_async_function():
    """A clean `async def <name>(...): ...` with a passing test case is accepted."""
    validate_tool_source('echo_tool', VALID_TOOL_SOURCE, test_cases=VALID_CASES)


def test_validate_tool_source_rejects_syntax_error():
    """An obvious syntax error is caught by ast.parse before any further check."""
    with pytest.raises(ToolValidationError, match='syntax error'):
        validate_tool_source('broken', 'async def broken(:', test_cases=VALID_CASES)


def test_validate_tool_source_rejects_missing_target_function():
    """A file without the expected `async def <name>` is rejected before the subprocess runs."""
    source = 'async def other(): return "x"'
    with pytest.raises(ToolValidationError, match='no top-level'):
        validate_tool_source('expected', source, test_cases=VALID_CASES)


def test_validate_tool_source_rejects_sync_function_with_the_target_name():
    """A sync `def <name>` is rejected because tools must be coroutine functions."""
    source = 'def echo_tool(): return "x"'
    with pytest.raises(ToolValidationError, match='no top-level'):
        validate_tool_source('echo_tool', source, test_cases=VALID_CASES)


def test_validate_tool_source_rejects_import_time_exceptions():
    """An import-time exception surfaces as a sandbox failure."""
    source = 'raise RuntimeError("boom")\n\nasync def echo_tool(): return "x"'
    with pytest.raises(ToolValidationError, match='sandbox check failed'):
        validate_tool_source('echo_tool', source, test_cases=VALID_CASES)


def test_validate_tool_source_runs_supplied_smoke_test_cases():
    """A passing smoke case (expected substring is present) accepts the tool."""
    validate_tool_source(
        'echo_tool',
        VALID_TOOL_SOURCE,
        test_cases=[{'input': {'message': 'pong'}, 'expected_contains': 'pong'}],
    )


def test_validate_tool_source_rejects_tool_that_fails_a_smoke_case():
    """A test case whose expected substring is missing fails the sandbox."""
    with pytest.raises(ToolValidationError, match='sandbox check failed'):
        validate_tool_source(
            'echo_tool',
            VALID_TOOL_SOURCE,
            test_cases=[{'input': {'message': 'hello'}, 'expected_equals': 'pong'}],
        )


# ---------- Layer A: placeholder rejection ----------


def test_validate_tool_source_rejects_empty_body():
    """A body of just `pass` is rejected before the subprocess runs."""
    source = 'async def stub_tool():\n    pass\n'
    with pytest.raises(ToolValidationError, match='empty/pass-only'):
        validate_tool_source('stub_tool', source, test_cases=VALID_CASES)


def test_validate_tool_source_rejects_docstring_only_body():
    """A body that is only a docstring is rejected - the function does nothing."""
    source = 'async def stub_tool():\n    """Does something eventually."""\n'
    with pytest.raises(ToolValidationError, match='empty/pass-only'):
        validate_tool_source('stub_tool', source, test_cases=VALID_CASES)


def test_validate_tool_source_rejects_ellipsis_body():
    """A body of `...` is structurally an empty placeholder and rejected."""
    source = 'async def stub_tool():\n    ...\n'
    with pytest.raises(ToolValidationError, match='empty/pass-only'):
        validate_tool_source('stub_tool', source, test_cases=VALID_CASES)


def test_validate_tool_source_rejects_raise_not_implemented_error():
    """`raise NotImplementedError(...)` is the classic stub escape - banned outright."""
    source = textwrap.dedent(
        '''
        async def stub_tool() -> str:
            """Will be filled in later."""
            raise NotImplementedError("configure foo")
        '''
           ,
    ).strip()
    with pytest.raises(ToolValidationError, match='NotImplementedError'):
        validate_tool_source('stub_tool', source, test_cases=VALID_CASES)


def test_validate_tool_source_rejects_todo_string_literal():
    """A return value containing `TODO` is detected by the placeholder scanner."""
    source = 'async def stub_tool() -> str:\n    return "TODO: integrate stripe"\n'
    with pytest.raises(ToolValidationError, match='placeholder marker'):
        validate_tool_source('stub_tool', source, test_cases=VALID_CASES)


def test_validate_tool_source_rejects_in_a_real_scenario_comment_as_return():
    """A return value containing the common 'in a real scenario' lie is rejected."""
    source = 'async def stub_tool() -> str:\n    return "In a real scenario this would call the API."\n'
    with pytest.raises(ToolValidationError, match='placeholder marker'):
        validate_tool_source('stub_tool', source, test_cases=VALID_CASES)


# ---------- Layer B: test_cases requirement + expected_raises ----------


def test_validate_tool_source_rejects_missing_test_cases():
    """`test_cases` is required and non-empty - the prompt may not skip it."""
    with pytest.raises(ToolValidationError, match='requires at least one test case'):
        validate_tool_source('echo_tool', VALID_TOOL_SOURCE)


def test_validate_tool_source_rejects_empty_test_cases_list():
    """An empty list of test cases is also rejected."""
    with pytest.raises(ToolValidationError, match='requires at least one test case'):
        validate_tool_source('echo_tool', VALID_TOOL_SOURCE, test_cases=[])


def test_validate_tool_source_expected_raises_passes_when_env_var_missing():
    """A real env-var-reading body + expected_raises with drop_env asserts the read happens."""
    source = textwrap.dedent(
        '''
        import os

        async def stripe_charge(amount: int) -> str:
            """Charge a Stripe customer; raises KeyError if the secret is not configured."""
            key = os.environ["STRIPE_SECRET_KEY"]
            return f"would charge {amount} with key prefix {key[:4]}"
        ''',
    ).strip()
    validate_tool_source(
        'stripe_charge',
        source,
        test_cases=[
            {
                'input': {'amount': 100},
                'drop_env': ['STRIPE_SECRET_KEY'],
                'expected_raises': 'STRIPE_SECRET_KEY',
            },
        ],
    )


def test_validate_tool_source_expected_raises_fails_when_function_does_not_raise():
    """If the function returns normally with the env var dropped, the test case fails (stub guard)."""
    source = 'async def stub_tool() -> str:\n    return "ok"\n'
    with pytest.raises(ToolValidationError, match='sandbox check failed'):
        validate_tool_source(
            'stub_tool',
            source,
            test_cases=[
                {
                    'input': {},
                    'drop_env': ['STRIPE_SECRET_KEY'],
                    'expected_raises': 'STRIPE_SECRET_KEY',
                },
            ],
        )


def test_validate_tool_source_env_override_lets_a_real_call_succeed():
    """Setting `env={...}` on a test case lets a tool that reads env vars actually return."""
    source = textwrap.dedent(
        '''
        import os

        async def env_echo() -> str:
            """Return the configured echo prefix."""
            return os.environ.get("ECHO_PREFIX", "missing") + ":ok"
        '''
           ,
    ).strip()
    validate_tool_source(
        'env_echo',
        source,
        test_cases=[
            {
                'input': {},
                'env': {'ECHO_PREFIX': 'hello'},
                'expected_equals': 'hello:ok',
            },
        ],
    )
