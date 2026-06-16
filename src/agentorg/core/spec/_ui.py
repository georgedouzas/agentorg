"""Everything the UI dashboard needs to render the org."""

from ._config import SpecModel


class AppUI(SpecModel):
    """App-level UI metadata shown in the dashboard chrome."""

    name: str
    icon: str
    description: str


class EmptyState(SpecModel):
    """Copy shown when the user lands without selecting an agent or workflow."""

    icon: str
    title: str
    body: str


class AgentConfigUI(SpecModel):
    """Per-agent display config for the sidebar and agent picker."""

    model: str
    description: str
    tools: list[str]
    features: list[str]


class GroupRef(SpecModel):
    """A sidebar group with a label and the agent or workflow ids it contains."""

    label: str
    ids: list[str]


class OverviewBlock(SpecModel):
    """A custom markdown card rendered on the Overview tab below the defaults."""

    title: str
    body: str


class UI(SpecModel):
    """All UI customisation, consumed by the frontend."""

    app: AppUI
    empty_state: EmptyState
    knowledge_empty: str
    agent_groups: list[GroupRef]
    workflow_groups: list[GroupRef]
    featured_agents: list[str]
    agent_icons: dict[str, str]
    overview: list[OverviewBlock]
    agent_configs: dict[str, AgentConfigUI]
    chat_quick_prompts: dict[str, list[str]]
