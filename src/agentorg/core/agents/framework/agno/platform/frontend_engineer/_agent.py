"""The Frontend Engineer — owns the dashboard's UI configuration."""

from .._make import platform_make_agent
from ._tools import list_overview_widgets, read_ui_config

agent = platform_make_agent(
    name='Frontend Engineer',
    agent_id='frontend-engineer',
    role=("Owns the dashboard's UI configuration: sidebar groups, agent icons, overview widgets, chat quick prompts."),
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
