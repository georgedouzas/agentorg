"""Tests for the sandbox module."""

import pytest

from agentorg.master import (
    SkillValidationError,
    ToolValidationError,
    compile_tool,
    validate_skill_source,
    validate_tool_source,
)

VALID_TOOL_SOURCE = '\n'.join(
    [
        '"""A simple custom tool that echoes its input."""',
        '',
        'async def echo_tool(message: str) -> str:',
        '    """Return the message unchanged - used as a smoke test for the sandbox."""',
        '    return message',
    ],
)
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
    source = '\n'.join(
        [
            'async def stub_tool() -> str:',
            '    """Will be filled in later."""',
            '    raise NotImplementedError("configure foo")',
        ],
    )
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
    source = '\n'.join(
        [
            'import os',
            '',
            'async def stripe_charge(amount: int) -> str:',
            '    """Charge a Stripe customer; raises KeyError if the secret is not configured."""',
            '    key = os.environ["STRIPE_SECRET_KEY"]',
            '    return f"would charge {amount} with key prefix {key[:4]}"',
        ],
    )
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
    source = '\n'.join(
        [
            'import os',
            '',
            'async def env_echo() -> str:',
            '    """Return the configured echo prefix."""',
            '    return os.environ.get("ECHO_PREFIX", "missing") + ":ok"',
        ],
    )
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


VALID_SKILL_MD = '\n'.join(
    [
        '---',
        'name: negotiation-playbook',
        'description: Steps for negotiating with a counterparty.',
        '---',
        '',
        '# Negotiation playbook',
        '',
        '1. Open with the high anchor.',
    ],
)


def test_validate_skill_source_accepts_a_well_formed_skill():
    """A clean SKILL.md with frontmatter and body passes validation."""
    validate_skill_source('negotiation-playbook', VALID_SKILL_MD)


def test_validate_skill_source_rejects_bad_name_shape():
    """The name must be lowercase-with-hyphens (the folder-name shape)."""
    with pytest.raises(SkillValidationError, match='lowercase-with-hyphens'):
        validate_skill_source('NegotiationPlaybook', VALID_SKILL_MD)


def test_validate_skill_source_rejects_missing_frontmatter():
    """Source without an opening `---` is rejected before YAML parsing."""
    body = '# A skill\n\nNo frontmatter here.'
    with pytest.raises(SkillValidationError, match='YAML frontmatter'):
        validate_skill_source('some-skill', body)


def test_validate_skill_source_rejects_unclosed_frontmatter():
    """An opening `---` without a closing `---` is rejected."""
    body = '---\nname: x\ndescription: y\n\n# Body\n'
    with pytest.raises(SkillValidationError, match='not closed'):
        validate_skill_source('some-skill', body)


def test_validate_skill_source_rejects_missing_name_field():
    """The frontmatter must declare a `name:` field."""
    body = '---\ndescription: Only a description.\n---\n\n# Body\n'
    with pytest.raises(SkillValidationError, match='name:'):
        validate_skill_source('some-skill', body)


def test_validate_skill_source_rejects_missing_description_field():
    """The frontmatter must declare a `description:` field."""
    body = '---\nname: x\n---\n\n# Body\n'
    with pytest.raises(SkillValidationError, match='description:'):
        validate_skill_source('some-skill', body)


def test_validate_skill_source_rejects_empty_body():
    """A SKILL.md with frontmatter but no body content is rejected."""
    body = '---\nname: x\ndescription: y\n---\n\n   \n\n'
    with pytest.raises(SkillValidationError, match='at least one non-empty line'):
        validate_skill_source('some-skill', body)


async def test_compile_tool_returns_the_named_function() -> None:
    """A validated tool source compiles into its callable async function."""
    source = 'async def shout(text: str) -> str:\n    """Shout."""\n    return text.upper()\n'
    shout = compile_tool('shout', source)
    assert shout.__name__ == 'shout'
    assert await shout('hi') == 'HI'
