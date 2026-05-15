"""Everything the React dashboard needs to render the org."""

from pydantic import BaseModel


class AppUI(BaseModel):
    """App-level UI metadata shown in the dashboard chrome."""

    name: str
    icon: str
    description: str


class EmptyState(BaseModel):
    """Copy shown when the user lands without selecting an agent or workflow."""

    icon: str
    title: str
    body: str




class AgentConfigUI(BaseModel):
    """Per-agent display config for the sidebar and agent picker."""

    model: str
    description: str
    tools: list[str]
    features: list[str]


class GroupRef(BaseModel):
    """A sidebar group with a label and the agent or workflow ids it contains."""

    label: str
    ids: list[str]


class OverviewBlock(BaseModel):
    """A custom markdown card rendered on the Overview tab below the defaults."""

    title: str
    body: str


class UI(BaseModel):
    """All UI customisation, consumed by the React frontend."""

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
