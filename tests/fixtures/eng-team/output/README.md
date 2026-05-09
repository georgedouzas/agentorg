# AI Software Engineering Team

Multi-agent system simulating a professional software engineering team that plans, builds, reviews, and ships production code.

## Agents

### Planning

| Agent | Role |
| --- | --- |
| Product Manager | Translate goals into a prioritized roadmap and unambiguous specs the team can build. |
| Architect | Decide how a feature should be built — interfaces, modules, data flow — and record the rationale. |

### Engineering

| Agent | Role |
| --- | --- |
| Backend Engineer | Turn specs into shipping backend code. |
| Frontend Engineer | Turn UI specs into accessible, polished frontend code. |
| QA Engineer | Verify shipped code with automated tests. |

### Leadership

| Agent | Role |
| --- | --- |
| Tech Lead | Approve major decisions and ship-blocking PRs. |

### Platform

| Agent | Role |
| --- | --- |
| Platform Engineer | Help the user complete setup, manage deployments, and answer infra questions. |
| Policy Officer | Maintain the engineering charter and answer policy questions. |

## Workflows

### Automated

#### Engineering Pipeline

Deterministic pipeline: plan → design → implement (parallel) → test → ship

| Step | Name | Agents | HITL |
| --- | --- | --- | --- |
| 1 | Plan | Product Manager | Yes |
| 2 | Design | Architect | No |
| 3 | Implement | Backend Engineer, Frontend Engineer (parallel) | No |
| 4 | Test | QA Engineer | Yes |
| 5 | Ship | Tech Lead | No |

## Running Locally

Prerequisites:

- Docker Desktop installed
- `GOOGLE_API_KEY` set in `.env`
- `GITHUB_TOKEN` set in `.env`

```sh
git clone https://github.com/georgedouzas/eng-team.git
cd eng-team
cp example.env .env
docker compose up -d --build
```

### Endpoints

- Dashboard: `http://localhost:5173`
- API: `http://localhost:8000`
- AgentOS UI (optional): connect `http://localhost:8000` at [os.agno.com](https://os.agno.com)

---

## Cloud Deployment (Railway)

```sh
railway login && nox -s deploy
```

## Environment Variables

### Required

| Variable | Description |
| --- | --- |
| `GOOGLE_API_KEY` | LLM models and embeddings |
| `GITHUB_TOKEN` | GitHub API access for code operations |

### Optional

| Variable | When | Description |
| --- | --- | --- |
| `DB_HOST/PORT/USER/PASS/DATABASE` | Override | PostgreSQL connection (Docker defaults work out of the box) |
| `RUNTIME_ENV` | No | Set to `dev` to enable uvicorn auto-reload |
| `API_BASE_URL` | Cloud only | Railway domain for cross-origin dashboard calls |
| `ALLOWED_ORIGINS` | Cloud only | Comma-separated CORS origins (default: `*`) |

## Learn More

- [Agno Documentation](https://docs.agno.com)
- [AgentOS Documentation](https://docs.agno.com/agent-os/introduction)
