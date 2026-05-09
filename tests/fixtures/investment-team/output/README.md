# Agentic Investment Team

Multi-agent system simulating a professional investment team managing a configurable equity portfolio.

## Agents

### Analysts

| Agent | Role |
| --- | --- |
| Stock Screener | Generate a shortlist of high-conviction tickers that match the fund mandate — not deep analysis of each. |
| Market Analyst | Provide the macro context — what the broader market is doing — for individual investment decisions. |
| Financial Analyst | Determine whether a stock is fundamentally sound and reasonably valued. |
| Technical Analyst | Determine optimal entry and exit points using price-action and momentum. |
| Risk Officer | Quantify downside and recommend position sizing within mandate limits. |
| Research Analyst | Build the team's long-form research library — company profiles and sector analyses other agents and humans can reference. |

### Support

| Agent | Role |
| --- | --- |
| Knowledge Agent | Be the team's librarian — answer 'what do we know about X?' by searching memos, reports, and the research library. |
| Memo Writer | Turn the analyst team's reports into a single, decision-ready investment memo. |
| Portfolio Agent | Be the source of truth for what we own, in what size, and how it has performed. |

### Leadership

| Agent | Role |
| --- | --- |
| Committee Chair | Read the team's full analysis and issue a final BUY / HOLD / PASS decision with allocation. |

### Platform

| Agent | Role |
| --- | --- |
| Platform Engineer | Help the user complete setup, manage deployments, and answer infra questions. |
| Policy Officer | Maintain the org's charter — mandate, policies, process — and answer policy questions. |

## Workflows

### Automated

#### Investment Pipeline

Deterministic pipeline: screen → research → analyse (parallel) → memo → decide → allocate

| Step | Name | Agents | HITL |
| --- | --- | --- | --- |
| 1 | Screen Stocks | Stock Screener | Yes |
| 2 | Select Tickers | Stock Screener | Yes |
| 3 | Bootstrap Research | Research Analyst | No |
| 4 | Full Analysis | Market Analyst, Financial Analyst, Technical Analyst, Risk Officer (parallel) | No |
| 5 | Write Memos | Memo Writer | Yes |
| 6 | Committee Decision | Committee Chair | Yes |
| 7 | Portfolio Update | Portfolio Agent | No |

## Running Locally

Prerequisites:

- Docker Desktop installed
- `GOOGLE_API_KEY` set in `.env`
- `EXA_API_KEY` set in `.env`

```sh
git clone https://github.com/georgedouzas/investment-team.git
cd investment-team
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
| `EXA_API_KEY` | Exa web search (Market Analyst) |

### Optional

| Variable | When | Description |
| --- | --- | --- |
| `DB_HOST/PORT/USER/PASS/DATABASE` | Override | PostgreSQL connection (Docker defaults work out of the box) |
| `PARALLEL_API_KEY` | Optional | ParallelTools web search |
| `RUNTIME_ENV` | No | Set to `dev` to enable uvicorn auto-reload |
| `API_BASE_URL` | Cloud only | Railway domain for cross-origin dashboard calls |
| `ALLOWED_ORIGINS` | Cloud only | Comma-separated CORS origins (default: `*`) |
| `CLERK_PUBLISHABLE_KEY` | Optional | Enables SSO login on the dashboard |
| `CLERK_SECRET_KEY` | Optional | Server-side Clerk token verification |

## Learn More

- [Agno Documentation](https://docs.agno.com)
- [AgentOS Documentation](https://docs.agno.com/agent-os/introduction)
