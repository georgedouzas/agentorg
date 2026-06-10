"""The built-in platform agents."""

from ._base import PLATFORM_AGENT_IDS, PLATFORM_AGENTS
from ._defaults import (
    PLATFORM_AGENT_GROUPS,
    PLATFORM_AGENT_ICONS,
    PLATFORM_DEFAULT_MODEL,
)
from ._register import register_platform_agents

__all__ = [
    'PLATFORM_AGENTS',
    'PLATFORM_AGENT_GROUPS',
    'PLATFORM_AGENT_ICONS',
    'PLATFORM_AGENT_IDS',
    'PLATFORM_DEFAULT_MODEL',
    'register_platform_agents',
]
