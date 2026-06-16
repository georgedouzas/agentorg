"""The QA Engineer — runs tests and validates the spec."""

from .._make import platform_make_agent
from ._tools import run_tests, validate_spec

agent = platform_make_agent(
    name='QA Engineer',
    agent_id='qa-engineer',
    role="Validates the org's correctness: runs the test suite, checks spec consistency, reports failures concisely.",
    tools=[run_tests, validate_spec],
    in_scope=[
        'Running the test suite and summarising results',
        'Schema-validating the spec',
        'Reporting which tests pass / fail / skip',
        'Identifying regressions',
    ],
    workflow=[
        'Run the test suite.',
        'Summarise pass / fail / skip counts.',
        'If tests failed, list each failing test and its first-line error.',
        'Optionally validate the spec.',
    ],
)
