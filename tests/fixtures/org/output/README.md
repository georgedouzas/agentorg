# Research Organisation

Small research team that gathers source material, synthesises findings, and publishes structured analysis reports.

## Agents

### Research Team

| Agent | Role |
| --- | --- |
| Researcher | Gather source material on a topic and write a structured research document. |
| Analyst | Synthesise existing research docs into a structured analysis report with implications and open questions. |

## Workflows

### Pipelines

#### Research Pipeline

Sequential pipeline: researcher gathers material, then analyst publishes a report.

| Step | Name | Agents | HITL |
| --- | --- | --- | --- |
| 1 | Gather |  (parallel) | No |
| 2 | Analyse |  (parallel) | No |

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
- API: `http://localhost:8000`
- AgentOS UI (optional): connect `http://localhost:8000` at [os.agno.com](https://os.agno.com)

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

- [Agno Documentation](https://docs.agno.com)
- [AgentOS Documentation](https://docs.agno.com/agent-os/introduction)
