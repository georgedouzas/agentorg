"""Stock Screener — scans for investment candidates matching the fund mandate (Exa + YFinance)."""

from agno.agent import Agent
from agno.guardrails.prompt_injection import PromptInjectionGuardrail
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.google import Gemini
from agno.tools.mcp import MCPTools
from agno.tools.yfinance import YFinanceTools

from investment_team.ai.agents.settings import EXA_MCP_URL, get_instructions, get_tools, team_knowledge, team_learnings
from investment_team.db import get_postgres_db

agent_db = get_postgres_db()

instructions = get_instructions("stock-screener")

stock_screener = Agent(
    id="stock-screener",
    name="Stock Screener",
    model=Gemini(id="gemini-3-flash-preview"),
    db=agent_db,
    instructions=instructions,
    tools=[MCPTools(url=EXA_MCP_URL), YFinanceTools(), *get_tools("stock-screener")],
    knowledge=team_knowledge,
    search_knowledge=True,
    learning=LearningMachine(
        knowledge=team_learnings,
        learned_knowledge=LearnedKnowledgeConfig(
            mode=LearningMode.ALWAYS,
            namespace="global",
        ),
    ),
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    pre_hooks=[PromptInjectionGuardrail()],
    markdown=True,
    enable_agentic_memory=True,
)
