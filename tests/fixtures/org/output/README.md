# Research Organisation

Small research team that gathers sources and publishes structured analysis reports.

## Agents

### Research Team

| Agent | Role |
| --- | --- |
| Researcher | Gather source material on a topic and write a structured research document. |
| Analyst | Synthesise existing research docs into a structured analysis report. |

## Workflows

### Pipelines

#### Research Pipeline



| Step | Name | Agents | HITL |
| --- | --- | --- | --- |
| 1 | Gather | Researcher | No |
| 2 | Analyse | Analyst | Yes |

## Running Locally

Prerequisites:

- Docker Desktop installed
- `GOOGLE_API_KEY` set in `.env`

```sh
git clone https://github.com/example/org.git
cd org
cp example.env .env
docker compose up -d --build
```

### Endpoints

- Dashboard: `http://localhost:5173`
- API (the AgentField node): `http://localhost:8000` — agents are exposed at `/reasoners/{name}`
- AgentField control plane (optional): `http://localhost:8080` — discovery, execution DAG, audit

---
## Environment Variables

### Required

| Variable | Description |
| --- | --- |
| `GOOGLE_API_KEY` | Gemini API key. |

### Optional

| Variable | When | Description |
| --- | --- | --- |
| `DB_HOST/PORT/USER/PASS/DATABASE` | Override | PostgreSQL connection (Docker defaults work out of the box) |
| `RUNTIME_ENV` | Dev | Set to `dev` for uvicorn auto-reload. |

## Learn More

- [AgentField Documentation](https://www.agentfield.ai/docs) — the runtime, control plane, and reasoner model
- [Agno Documentation](https://docs.agno.com) — for agents that use agno as their backend
