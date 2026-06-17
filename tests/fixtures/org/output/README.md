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

## Getting Started

There are three common ways to land here. Pick the one that matches how you got the
source, then continue from **Step 2: Configure**.

### Step 1: Get the source

#### A. You downloaded a zip from AgentOrg
Extract it anywhere; the folder is your project root.

```sh
unzip org.zip
cd org
```

#### B. You cloned an existing repository
```sh
git clone https://github.com/example/org
cd org
```

#### C. You want to push the zip contents to a new GitHub repository
After extracting the zip, initialize a repo and push:

```sh
cd org
git init && git add . && git commit -m "Initial commit"
gh repo create org --private --source=. --remote=origin --push   # or use the GitHub UI
```

### Step 2: Configure

Copy the example environment file and fill in real values. The required variables
are listed in [Environment Variables](#environment-variables); the longer-form setup
walkthroughs for credentialed services (one per external integration) are in
[Setup Tasks](#setup-tasks).

```sh
cp example.env .env
${EDITOR:-vi} .env
```

After the org boots, you can also see the setup tasks rendered as a checklist at
`GET /api/v1/setup` or in the dashboard's setup view.

### Step 3: Install and run
The project uses [uv](https://docs.astral.sh/uv/) for dependency management and is
run directly on your machine.

Prerequisites: Python 3.11+ and `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```sh
uv sync                                          # install dependencies into a venv
uv run nox -s tests                              # smoke-test the rendered package
uv run python -m org          # run the API node
```

In a separate terminal, start the dashboard:

```sh
cd src/frontend && npm install && npm run dev
```

### Endpoints

- Dashboard: `http://localhost:5173`
- API (the AgentField node): `http://localhost:8000` — agents are exposed at `/reasoners/{name}`
- AgentField control plane (optional): `http://localhost:8080` — discovery, execution DAG, audit
- Setup checklist (live): `http://localhost:8000/api/v1/setup`
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
## Setup Tasks

Long-form setup walkthroughs for the credentialed services the agents need. The org
boots without these completed, but the affected tools will only run once the listed
variables are set.

### Set GOOGLE_API_KEY in .env

Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) and add it to your `.env`:

```sh
GOOGLE_API_KEY=your-key-here
```

**Variables:** `GOOGLE_API_KEY`
## Learn More

- [AgentField Documentation](https://www.agentfield.ai/docs) — the runtime, control plane, and reasoner model
- [Agno Documentation](https://docs.agno.com) — for agents that use agno as their backend
