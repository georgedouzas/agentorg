"""Static configuration shared by the six built-in platform agents."""

PLATFORM_DEFAULT_MODEL = 'google:gemini-2.5-flash'

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
