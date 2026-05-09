"""Portfolio Agent — maintains portfolio state and generates performance reports (YFinance)."""

from agno.agent import Agent
from agno.guardrails.prompt_injection import PromptInjectionGuardrail
from agno.models.google import Gemini
from agno.tools.yfinance import YFinanceTools

from investment_team.ai.agents.settings import get_instructions, get_tools, team_knowledge
from investment_team.db import get_postgres_db

agent_db = get_postgres_db()

instructions = get_instructions("portfolio-agent")

portfolio_agent = Agent(
    id="portfolio-agent",
    name="Portfolio Agent",
    model=Gemini(id="gemini-3-flash-preview"),
    db=agent_db,
    instructions=instructions,
    tools=[YFinanceTools(), *get_tools("portfolio-agent")],
    knowledge=team_knowledge,
    search_knowledge=False,
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    pre_hooks=[PromptInjectionGuardrail()],
    markdown=True,
    enable_agentic_memory=True,
)
