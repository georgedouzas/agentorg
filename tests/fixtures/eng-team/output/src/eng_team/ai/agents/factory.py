"""Agent factory — builds every agent declaratively from config.yaml.

This is the `default` agent architecture: a single `agno.Agent` per
spec entry, with instructions composed from structured fields, tools resolved through
the binding registry, and shared knowledge + (optional) learning wired in.
"""

from agno.agent import Agent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.google import Gemini

from eng_team.ai.agents.settings import (
    AGENT_CONFIGS,
    get_instructions,
    get_tools,
    team_knowledge,
    team_learnings,
)
from eng_team.db import get_postgres_db


def _build_learning(cfg: dict) -> LearningMachine | None:
    if not cfg.get("learning"):
        return None
    return LearningMachine(
        knowledge=team_learnings,
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC, namespace="global"),
    )


def build_agents() -> dict[str, Agent]:
    """Return ``{agent_id: Agent}`` for every agent declared in config.yaml."""
    db = get_postgres_db()
    agents: dict[str, Agent] = {}
    for agent_id, cfg in AGENT_CONFIGS.items():
        agents[agent_id] = Agent(
            id=agent_id,
            name=cfg.get("name", agent_id),
            model=Gemini(id=cfg.get("model", "gemini-3-flash-preview")),
            db=db,
            instructions=get_instructions(agent_id),
            tools=get_tools(agent_id),
            knowledge=team_knowledge,
            search_knowledge=True,
            learning=_build_learning(cfg),
            add_datetime_to_context=True,
            add_history_to_context=True,
            num_history_runs=5,
            markdown=True,
            enable_agentic_memory=True,
        )
    return agents
