"""Product Manager — owns the roadmap, writes specs, prioritizes the backlog."""

from agno.agent import Agent
from agno.guardrails.prompt_injection import PromptInjectionGuardrail
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.google import Gemini

from eng_team.ai.agents.settings import get_instructions, get_tools, team_knowledge, team_learnings
from eng_team.db import get_postgres_db

agent_db = get_postgres_db()

instructions = get_instructions("product-manager")

product_manager = Agent(
    id="product-manager",
    name="Product Manager",
    model=Gemini(id="gemini-3-flash-preview"),
    db=agent_db,
    instructions=instructions,
    tools=get_tools("product-manager"),
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
