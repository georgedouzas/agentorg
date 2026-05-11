"""Agent factory — builds every agent declaratively from config.yaml.

This is the `default` agent architecture: a single `agno.Agent` per
spec entry, with instructions composed from structured fields, tools resolved by
import path, and shared knowledge + (optional) learning wired in.

Tool import paths use the form ``tools.<module>.<symbol>`` and resolve to
``eng_team.ai.tools.<module>.<symbol>`` at runtime. Use full dotted
paths for external libraries (e.g. ``agno.tools.yfinance.YFinanceTools``).
"""

import importlib
from collections.abc import Callable

from agno.agent import Agent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.google import Gemini

from eng_team.ai.agents.settings import (
    AGENT_CONFIGS,
    get_instructions,
    team_knowledge,
    team_learnings,
)
from eng_team.db import get_postgres_db

_TOOL_PREFIX = "tools."
_PACKAGE_TOOL_ROOT = "eng_team.ai.tools."


def _resolve_tool(import_path: str) -> Callable:
    """Import ``import_path`` and return the callable. ``tools.`` prefix maps to the org package."""
    if import_path.startswith(_TOOL_PREFIX):
        import_path = _PACKAGE_TOOL_ROOT + import_path[len(_TOOL_PREFIX):]
    module_path, _, symbol = import_path.rpartition(".")
    obj = getattr(importlib.import_module(module_path), symbol)
    # Class? Instantiate with no args (agno tool classes follow this convention).
    return obj() if isinstance(obj, type) else obj


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
        tools = [_resolve_tool(p) for p in cfg.get("tools", [])]
        agents[agent_id] = Agent(
            id=agent_id,
            name=cfg.get("name", agent_id),
            model=Gemini(id=cfg.get("model", "gemini-3-flash-preview")),
            db=db,
            instructions=get_instructions(agent_id),
            tools=tools,
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
