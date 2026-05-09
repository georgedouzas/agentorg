"""Committee Chair — final decision-maker and capital allocator (Gemini 3.1 Pro)."""

from agno.agent import Agent
from agno.guardrails.prompt_injection import PromptInjectionGuardrail
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.google import Gemini

from investment_team.ai.agents.settings import get_instructions, get_tools, team_knowledge, team_learnings
from investment_team.db import get_postgres_db

agent_db = get_postgres_db()

instructions = get_instructions("committee-chair")

committee_chair = Agent(
    id="committee-chair",
    name="Committee Chair",
    model=Gemini(id="gemini-3.1-pro-preview"),
    db=agent_db,
    instructions=instructions,
    tools=get_tools("committee-chair"),
    knowledge=team_knowledge,
    search_knowledge=True,
    learning=LearningMachine(
        knowledge=team_learnings,
        learned_knowledge=LearnedKnowledgeConfig(
            mode=LearningMode.AGENTIC,
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
    committee_chair.print_response("Should we invest in NVIDIA? Give me a final decision.", stream=True)
