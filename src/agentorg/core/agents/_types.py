"""Type aliases for the agentorg agents module."""

from typing import TypeAlias

from agno.agent import Agent as _AgnoAgent
from agno.team import Team as _AgnoTeam
from agno.workflow import Workflow as _AgnoWorkflow

AgnoAgent: TypeAlias = _AgnoAgent | _AgnoTeam | _AgnoWorkflow
Agent: TypeAlias = AgnoAgent
