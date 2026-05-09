"""Policy Officer — maintains the org's policy documents (rules, guardrails, procedures)."""

from agno.agent import Agent
from agno.models.google import Gemini

from eng_team.ai.agents.settings import get_instructions, get_tools
from eng_team.db import get_postgres_db

agent_db = get_postgres_db()

instructions = get_instructions("policy-officer")

policy_officer = Agent(
    id="policy-officer",
    name="Policy Officer",
    model=Gemini(id="gemini-3-flash-preview"),
    db=agent_db,
    instructions=instructions,
    tools=get_tools("policy-officer"),
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
    enable_agentic_memory=True,
)
