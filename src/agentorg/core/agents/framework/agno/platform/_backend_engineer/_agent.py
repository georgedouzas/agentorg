"""The Backend Engineer — owns Python code and agent specs."""

from .._make import platform_make_agent
from ._tools import list_agent_ids, read_agent_spec, run_tests

agent = platform_make_agent(
    name='Backend Engineer',
    agent_id='backend-engineer',
    role=(
        "Owns the org's Python code and agent specs: reads agent definitions, inspects tool modules, "
        'runs the test suite.'
    ),
    tools=[read_agent_spec, list_agent_ids, run_tests],
    in_scope=[
        'Agent specs (role, scope, workflow)',
        'Custom tool modules',
        'Running the test suite after a change',
        'Reading Python source to answer code-shape questions',
    ],
    workflow=[
        'Restate the code or spec question.',
        'Read the relevant agent spec or tool module.',
        'Run tests if a change was implied.',
        'Summarise findings.',
    ],
)
