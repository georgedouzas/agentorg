"""Memo Writer — synthesizes analyst inputs into formal investment memos stored in the DB."""

from agno.agent import Agent
from agno.guardrails.prompt_injection import PromptInjectionGuardrail
from agno.models.google import Gemini

from investment_team.ai.agents.settings import get_instructions, get_tools
from investment_team.db import get_postgres_db

agent_db = get_postgres_db()

instructions = get_instructions("memo-writer")

memo_writer = Agent(
    id="memo-writer",
    name="Memo Writer",
    model=Gemini(id="gemini-3-flash-preview"),
    db=agent_db,
    instructions=instructions,
    tools=get_tools("memo-writer"),
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    pre_hooks=[PromptInjectionGuardrail()],
    markdown=True,
    enable_agentic_memory=True,
)
