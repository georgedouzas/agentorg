"""Platform Engineer — manages infra/deployment, answers platform questions.

Has reference docs (RAG) for the platforms the org uses + web search for newer options.
"""

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.mcp import MCPTools

from investment_team.ai.agents.settings import EXA_MCP_URL, get_instructions, get_tools
from investment_team.db import get_postgres_db

agent_db = get_postgres_db()

instructions = get_instructions("platform-engineer")

platform_engineer = Agent(
    id="platform-engineer",
    name="Platform Engineer",
    model=Gemini(id="gemini-3-flash-preview"),
    db=agent_db,
    instructions=instructions,
    tools=[MCPTools(url=EXA_MCP_URL), *get_tools("platform-engineer")],
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
    enable_agentic_memory=True,
)
