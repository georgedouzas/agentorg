"""UI — everything the React dashboard needs to render the org.

App metadata, empty-state copy, sidebar groupings, agent icons, and per-agent display config. The renderer feeds this
into the frontend; nothing here affects agent behaviour.
"""

from typing import Any

from pydantic import BaseModel


class AppUI(BaseModel):
    """App-level UI metadata — name, icon, description shown in the dashboard chrome."""

    name: str
    icon: str
    description: str


class EmptyState(BaseModel):
    """Copy shown when the user lands without selecting an agent or workflow."""

    icon: str
    title: str
    body: str


class KnowledgeEmpty(BaseModel):
    """Empty-state copy for the Knowledge tab's documents and learnings panels."""

    documents: str
    learnings: str


class AgentConfigUI(BaseModel):
    """Per-agent display config for the sidebar / agent picker."""

    model: str
    description: str
    tools: list[str]
    features: list[str]


class GroupRef(BaseModel):
    """A sidebar group — a label and the agent/workflow ids it contains."""

    label: str
    ids: list[str]


class UI(BaseModel):
    """All UI customisation, consumed by the React frontend."""

    app: AppUI
    empty_state: EmptyState
    knowledge_empty: KnowledgeEmpty
    agent_groups: list[GroupRef]
    workflow_groups: list[GroupRef]
    featured_agents: list[str]
    agent_icons: dict[str, str]
    overview: dict[str, Any]
    agent_configs: dict[str, AgentConfigUI]
    chat_quick_prompts: dict[str, list[str]]
