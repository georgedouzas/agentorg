# Proposal

## Why

agentorg has two hand-built chat surfaces: the master interview's chat and the generated dashboard's chat panel. Both
are basic, and making either as good as a dedicated chat app would take a lot of frontend work. LibreChat is a mature,
MIT-licensed chat app with conversation history, search, per-user login and a polished streaming UI. It talks to any
OpenAI-compatible API, so it can front both the master and every rendered org without being forked. Making it the one
chat surface removes both hand-built chats. What LibreChat cannot do, such as approvals, run status, lifecycle and
interview stages, moves into our chat API as commands. The dashboard keeps the operations views.

## What Changes

- **LibreChat is the chat app of every rendered org.** There is no option. The renderer always writes a
  `librechat.yaml` generated from the spec:
  - one custom endpoint for the org's chat API;
  - one model spec per agent and unit;
  - branding from the spec;
  - LibreChat's own agents, presets, model switching, file search, code execution, web search and MCP turned off.

  With docker packaging, `compose.yaml` adds LibreChat, MongoDB and Meilisearch, using the official LibreChat image
  pinned by version. Railway orgs get a setup step that deploys LibreChat.
- **An OpenAI-compatible chat API on every rendered node**: `GET /v1/models` and `POST /v1/chat/completions`,
  authenticated with the always-required `CHAT_API_KEY`.
  - Every message runs through the operations runtime.
  - Tool activity, delegations and approval holds stream as text.
- **Chat commands for what LibreChat lacks.** A message starting with `/` is a command, answered by the node without
  starting a run:
  - `/approve` and `/reject`, checked against the governance approvers;
  - `/runs`, `/run <id>` and `/inbox`;
  - `/status`, `/pause` and `/resume`;
  - `/help`.
- **The master interview runs in LibreChat.**
  - The master server exposes the same kind of chat API with one model, `agentorg`. It routes each message to the
    current stage's agent and streams its tool activity and stage progress.
  - Interview commands: `/stage`, `/next` to advance after the blockers clear, `/spec`, `/preview` and `/help`.
  - The `agentorg` command starts a local LibreChat stack beside the master. Its configuration offers the interview
    and, as a second endpoint, the live preview's agents.
- **The live preview's agents are chatted with in LibreChat.** The preview node serves the chat API, and LibreChat
  reads its model list from the node, so new agents appear as the interview adds them.
- **The hand-built chats are removed**: the dashboard's chat panel and agent chat views, its stream route, and the
  master UI's chat. The dashboard becomes the operations console, linking to LibreChat. The master UI becomes the live
  preview page.

### Out of scope

- Forking or patching LibreChat. Only configuration and the official image are used.
- LibreChat's agents, MCP, RAG and file search. They would run a model loop outside our runtime and its governance.
- Running LibreChat on Railway automatically. Railway orgs get a setup step instead.
- Running the master without Docker. LibreChat needs MongoDB and Meilisearch, so the master requires Docker.
- Agno's AgentOS as a UI.

## Capabilities

### New Capabilities

- `ui/chat-api`: the OpenAI-compatible chat API of rendered nodes: models, runs, streaming, sessions, authentication
  and chat commands.
- `ui/chat-app`: LibreChat as every org's chat app: its generated configuration and services, and the dashboard as the
  operations console.
- `master/chat-interview`: the master interview served through the chat API and LibreChat, including interview
  commands and the live preview's agents.

### Modified Capabilities

None. `master/interview-authoring` belongs to the unarchived `claude-agents-and-org-operations` change, so the
interview's new surface is specified in `master/chat-interview`.

## Impact

- **Spec**: `Runtime` always requires `CHAT_API_KEY` and, on Railway, adds a LibreChat setup step.
- **Operations**: a new chat router with commands; the runner forks agent sessions on resume.
- **Renderer**: `librechat.yaml`, LibreChat services in `compose.yaml`, `example.env` and README changes. The dashboard
  loses its chat panel, agent chat views and stream route.
- **Master**: a chat API on the master server, a bundled LibreChat compose stack started by `agentorg`, the preview
  node started with a chat key, and the master UI reduced to the preview page.
- **Tests**: unit tests for the routers and commands; render tests; a later e2e scenario on `local-docker`.
- **Operational dependencies**: Docker with MongoDB and Meilisearch for the master and for docker-packaged orgs.
