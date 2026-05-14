"""AgentOS entry point — boots the FastAPI app from the spec."""

import os
from pathlib import Path

from agno.os import AgentOS
from fastapi.middleware.cors import CORSMiddleware

from agentorg.core.tools._engine import get_postgres_db
from agentorg.core.tools.tables import create_app_tables, truncate_user_data

from org.ai.agents.factory import build_agents
from org.ai.teams.factory import build_teams
from org.ai.workflows.factory import build_workflows
from org.app.routes import build_router
from org.spec import spec

os.environ.setdefault('AGENTORG_INFRA', 'docker' if spec.runtime.infra.database == 'postgres' else 'local')
os.environ.setdefault('AGENTORG_ORG_SLUG', spec.org.slug)

create_app_tables()

if os.getenv('RESET_ON_STARTUP', '').strip() == '1':
    truncate_user_data()

# Spec already holds agno-native agents/teams/workflows — factories just return them.
_agents = build_agents(spec)
_teams = build_teams(spec)
_workflows = build_workflows(spec)

agent_os = AgentOS(
    name=spec.org.name,
    tracing=True,
    scheduler=True,
    db=get_postgres_db(),
    agents=list(_agents.values()),
    teams=_teams,
    workflows=_workflows,
)

app = agent_os.get_app()

_origins = [o.strip() for o in os.getenv('ALLOWED_ORIGINS', '*').split(',') if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(build_router(spec, _agents, _workflows))


if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    reload = os.getenv('RUNTIME_ENV', '') == 'dev'
    agent_os.serve(app='app.main:app', port=port, reload=reload)
