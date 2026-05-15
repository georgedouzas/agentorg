"""Definition of the Backend Engineer — owns Python code and agent specs."""

from agno.agent import Agent

from agentorg.core.platform._backend_engineer._tools import list_agent_ids, read_agent_spec, run_tests
from agentorg.core.platform._common import platform_agent

agent: Agent = platform_agent(
    agent_id='backend-engineer',
    name='Backend Engineer',
    role=(
        "Owns the org's Python code and agent specs: reads agent definitions, "
        'inspects tool modules, runs the test suite.'
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
