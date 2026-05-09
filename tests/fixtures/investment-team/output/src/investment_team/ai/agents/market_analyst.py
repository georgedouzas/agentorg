"""Market Analyst — macro environment, sector trends, and breaking news (Exa MCP + YFinance)."""

from os import getenv

from agno.agent import Agent
from agno.guardrails.prompt_injection import PromptInjectionGuardrail
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.google import Gemini
from agno.tools.mcp import MCPTools
from agno.tools.yfinance import YFinanceTools

from investment_team.ai.agents.settings import EXA_MCP_URL, get_instructions, get_tools, team_knowledge, team_learnings
from investment_team.db import get_postgres_db

agent_db = get_postgres_db()

instructions = get_instructions("market-analyst")

tools: list = [MCPTools(url=EXA_MCP_URL), YFinanceTools(), *get_tools("market-analyst")]

if getenv("PARALLEL_API_KEY"):
    try:
        from agno.tools.parallel import ParallelTools

        tools.append(ParallelTools())
    except ImportError:
        pass

market_analyst = Agent(
    id="market-analyst",
    name="Market Analyst",
    model=Gemini(id="gemini-3-flash-preview"),
    db=agent_db,
    instructions=instructions,
    tools=tools,
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

if __name__ == "__main__":
    market_analyst.print_response("What's the current market environment for tech stocks?", stream=True)
