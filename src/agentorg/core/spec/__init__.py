"""Pydantic models describing the agentorg spec.

A `spec.py` constructs a `Spec` from five domain models — `org`, `runtime`, `ai`, `knowledge`, `ui`. Agents, teams, and
workflows are agno-native (`agno.agent.Agent`, `agno.team.Team`, `agno.workflow.Workflow`/`Step`); everything else
accepts plain dict literals that Pydantic validates. The user-facing surface is `Spec`, the five domain models, and
`PLATFORM_AGENTS`.
"""

from agentorg.core.spec._ai import AI
from agentorg.core.spec._knowledge import (
    Charter,
    CharterParameter,
    CharterSection,
    DocumentType,
    DocumentTypeMetadataField,
    Knowledge,
)
from agentorg.core.spec._org import Org
from agentorg.core.spec._runtime import EnvVar, EnvVars, Infra, Runtime, SetupStep
from agentorg.core.spec._ui import UI, AgentConfigUI, AppUI, EmptyState, GroupRef, KnowledgeEmpty
from agentorg.core.spec.models import Spec
from agentorg.core.spec.platform_agents import PLATFORM_AGENT_IDS, PLATFORM_AGENTS

__all__ = [
    'PLATFORM_AGENTS',
    'PLATFORM_AGENT_IDS',
    'AI',
    'UI',
    'AgentConfigUI',
    'AppUI',
    'Charter',
    'CharterParameter',
    'CharterSection',
    'DocumentType',
    'DocumentTypeMetadataField',
    'EmptyState',
    'EnvVar',
    'EnvVars',
    'GroupRef',
    'Infra',
    'Knowledge',
    'KnowledgeEmpty',
    'Org',
    'Runtime',
    'SetupStep',
    'Spec',
]
