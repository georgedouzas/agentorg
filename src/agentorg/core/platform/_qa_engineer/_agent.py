"""Definition of the QA Engineer — runs tests and validates the spec."""

from agno.agent import Agent

from agentorg.core.platform._common import platform_agent
from agentorg.core.platform._qa_engineer._tools import run_tests, validate_spec

agent: Agent = platform_agent(
    agent_id='qa-engineer',
    name='QA Engineer',
    role=(
        "Validates the org's correctness: runs the test suite, checks spec "
        'consistency, reports failures concisely.'
    ),
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
