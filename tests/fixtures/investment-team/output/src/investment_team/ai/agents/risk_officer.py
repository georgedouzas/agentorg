"""Risk Officer — downside scenarios, position sizing, and mandate compliance (YFinance)."""

from agno.agent import Agent
from agno.guardrails.prompt_injection import PromptInjectionGuardrail
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.google import Gemini
from agno.tools.yfinance import YFinanceTools

from investment_team.ai.agents.settings import get_instructions, get_tools, team_knowledge, team_learnings
from investment_team.db import get_postgres_db

agent_db = get_postgres_db()

instructions = get_instructions("risk-officer")

risk_officer = Agent(
    id="risk-officer",
    name="Risk Officer",
    model=Gemini(id="gemini-3-flash-preview"),
    db=agent_db,
    instructions=instructions,
    tools=[YFinanceTools(), *get_tools("risk-officer")],
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
    risk_officer.print_response("What's the risk profile of NVDA at a $2M position?", stream=True)
