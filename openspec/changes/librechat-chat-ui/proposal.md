# Proposal

## Why

Chat is where users of a rendered org spend most of their time. Our generated React chat panel is basic, and making it
as good as a dedicated chat app would take a lot of frontend work. LibreChat is a mature, MIT-licensed chat app that
already has conversation history, search, auth and a polished streaming UI. It can talk to any OpenAI-compatible API, so
it can sit in front of an org without being forked. Meanwhile the operations views (runs, approvals, lifecycle,
knowledge) are specific to agentorg, and we should keep building them ourselves.

## What Changes

- **A new `runtime.infra.chat_ui` choice**: `dashboard` (the default and current behaviour) or `librechat`.
- **An OpenAI-compatible chat API on every rendered node**:
  - `GET /v1/models` lists the org's agents and units;
  - `POST /v1/chat/completions` starts a run through the operations runtime and streams it back.

  Every chat still goes through the runtime, so policy, budget, lifecycle and run history apply as before. Approval holds
  and tool activity appear in the stream as text, with a link to the matching Inbox item.
- **With `chat_ui='librechat'`, the renderer adds:**
  - a `librechat.yaml` generated from the spec: the custom endpoint, one model spec per agent and unit, branding, a link
    to the operations console, and LibreChat's own agents, presets, model switching, file search and MCP turned off;
  - LibreChat, MongoDB and Meilisearch services in `compose.yaml`, with the official LibreChat image pinned by version.
- **With `chat_ui='librechat'`, the generated dashboard becomes an operations console**: it keeps runs, Inbox, lifecycle,
  knowledge, parameters and units, and drops its chat panel.
- **The master interview** offers the choice in the Configure stage through `set_runtime_infra`.
- **The master agent and its live preview keep the built-in chat panel.** Preview mode never starts LibreChat or MongoDB.

### Out of scope

- Forking or patching LibreChat. Only configuration and the official image are used.
- LibreChat's agents, MCP, RAG and file search. They would run a model loop outside our runtime and its governance, so
  they are turned off.
- Deciding approvals inside LibreChat. Approvals stay in the operations console.
- Cloud deployment of LibreChat. `chat_ui='librechat'` requires docker packaging for now; Railway support can follow.
- Combining LibreChat with Clerk auth. LibreChat uses its own login.
- Agno's AgentOS as a UI.

## Capabilities

### New Capabilities

- `ui/chat-api`: the OpenAI-compatible chat API that rendered nodes expose, and how it maps onto runs, sessions and
  users.
- `ui/librechat-frontend`: choosing LibreChat as the chat UI, the rendered LibreChat configuration and services, and
  the operations-console form of the dashboard.

### Modified Capabilities

None. The interview's new Configure choice is covered in `ui/librechat-frontend`, because `master/interview-authoring`
belongs to the unarchived `claude-agents-and-org-operations` change.

## Impact

- **Spec**: `core/spec/_runtime.py` (`Infra.chat_ui` and its validation).
- **Renderer**: new templates for `librechat.yaml` and the compose services; the dashboard template becomes conditional
  on `chat_ui`; `example.env` gains LibreChat variables.
- **Rendered node**: a new OpenAI-compatible router, authenticated with a shared key.
- **Master**: the `set_runtime_infra` tool and the Configure prompt.
- **Tests**: unit tests for the router and the spec; render tests for both `chat_ui` values; a later e2e scenario on
  `local-docker`.
- **Operational dependencies**: MongoDB and Meilisearch, only when `chat_ui='librechat'`.
