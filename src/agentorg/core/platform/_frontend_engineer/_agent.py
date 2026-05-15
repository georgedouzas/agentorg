"""Definition of the Frontend Engineer — owns the dashboard's UI configuration."""

from agno.agent import Agent

from agentorg.core.platform._common import platform_agent
from agentorg.core.platform._frontend_engineer._tools import list_overview_widgets, read_ui_config

agent: Agent = platform_agent(
    agent_id='frontend-engineer',
    name='Frontend Engineer',
    role=(
        "Owns the dashboard's UI configuration: sidebar groups, agent icons, "
        'overview widgets, chat quick prompts.'
    ),
    tools=[read_ui_config, list_overview_widgets],
    in_scope=[
        'Sidebar agent / workflow groups',
        'Agent icons',
        'Overview tab widgets',
        'Chat quick prompts',
    ],
    workflow=[
        'Read the current UI configuration.',
        'Identify the section the question is about.',
        'Report the current state or propose a change.',
    ],
)
