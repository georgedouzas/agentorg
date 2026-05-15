"""The six built-in platform agents shipped with every org."""

from agentorg.core.platform._backend_engineer import agent as backend_engineer
from agentorg.core.platform._frontend_engineer import agent as frontend_engineer
from agentorg.core.platform._knowledge_engineer import agent as knowledge_engineer
from agentorg.core.platform._platform_engineer import agent as platform_engineer
from agentorg.core.platform._qa_engineer import agent as qa_engineer
from agentorg.core.platform._security_engineer import agent as security_engineer

PLATFORM_AGENTS = (
    platform_engineer,
    security_engineer,
    backend_engineer,
    frontend_engineer,
    knowledge_engineer,
    qa_engineer,
)
PLATFORM_AGENT_IDS: frozenset[str] = frozenset(a.id for a in PLATFORM_AGENTS if a.id)

# Default sidebar icons for the built-in platform agents; `spec.ui.agent_icons` overrides on a per-id basis.
PLATFORM_AGENT_ICONS: dict[str, str] = {
    'platform-engineer': '⚙️',
    'security-engineer': '🛡️',
    'backend-engineer': '🐍',
    'frontend-engineer': '🎨',
    'knowledge-engineer': '🗂️',
    'qa-engineer': '✅',
}

# Grouping for the dashboard's `Platform` tab — the rendered org renders these as card sections.
PLATFORM_AGENT_GROUPS: tuple[dict[str, object], ...] = (
    {'label': 'Operations', 'ids': ('platform-engineer', 'security-engineer')},
    {'label': 'Engineering', 'ids': ('backend-engineer', 'frontend-engineer')},
    {'label': 'Quality & Knowledge', 'ids': ('qa-engineer', 'knowledge-engineer')},
)

__all__ = ['PLATFORM_AGENTS', 'PLATFORM_AGENT_GROUPS', 'PLATFORM_AGENT_ICONS', 'PLATFORM_AGENT_IDS']
