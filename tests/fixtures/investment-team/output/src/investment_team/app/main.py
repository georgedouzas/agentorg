"""AgentOS entry point — registers agents, teams, workflows, and mounts the API router."""

import os
from pathlib import Path

from agno.os import AgentOS
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from investment_team.ai.agents.factory import build_agents
from investment_team.ai.refresh import start_scheduler
from investment_team.ai.teams.factory import build_teams
from investment_team.ai.tools.providers import import_universal_providers
from investment_team.ai.workflows.factory import build_workflows
from investment_team.app.routes import router
from investment_team.db import create_app_tables, get_postgres_db, truncate_user_data
from investment_team.org import bootstrap_overview_feeds, seed_policy_documents
from investment_team.org.platform_kb import seed_platform_kb

# Ensure tables exist
create_app_tables()

# Dev convenience: wipe all user-created data on every restart so the app boots fresh.
# Set RESET_ON_STARTUP=1 in compose.yaml; do NOT enable in production.
if os.getenv("RESET_ON_STARTUP", "").strip() == "1":
    truncate_user_data()

# Seed reference docs (platform + policies + overview feeds) — idempotent
seed_platform_kb()
seed_policy_documents()
bootstrap_overview_feeds()

# Register universal refresh providers (yfinance, state, knowledge)
import_universal_providers()

# ---------------------------------------------------------------------------
# Create AgentOS
# ---------------------------------------------------------------------------
agents = list(build_agents().values())
teams = build_teams()
workflows = build_workflows()

agent_os = AgentOS(
    name="Agentic Investment Team",
    tracing=True,
    scheduler=True,
    db=get_postgres_db(),
    agents=agents,
    teams=teams,
    workflows=workflows,
    config=str(Path(__file__).parent / "config.yaml"),
)

app = agent_os.get_app()

# Allow the Vercel-hosted dashboard to call this API cross-origin.
# Set ALLOWED_ORIGINS to a comma-separated list of allowed origins in production.
_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def _start_knowledge_scheduler() -> None:
    """Boot the refresh scheduler once the FastAPI event loop is running."""
    start_scheduler()


# Serve Vite-built static assets (JS/CSS bundles) if the public/assets dir exists.
_assets_dir = Path(__file__).parent.parent.parent.parent / "public" / "assets"
if _assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RUNTIME_ENV", "") == "dev"
    agent_os.serve(app="app.main:app", port=port, reload=reload)
