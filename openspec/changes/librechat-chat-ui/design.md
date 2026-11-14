# Design

## Context

- **Dashboard chat today**: the dashboard calls `POST /api/v1/reasoners/{name}/stream` on the rendered node. That route
  calls `OrgRuntime.start_run(target, message, session_id, user_id)` and then polls the run's transcript. Transcript
  events have the types `text`, `tool_call`, `tool_result`, `status` and `end`. A run held for approval sits in
  `awaiting_approval`, which is not terminal, so the stream simply waits.
- **Sessions**: `start_run` passes the `session_id` to the runner. The runner resumes the agent's Claude Agent SDK
  session, and handoffs re-route a session to its new owner. The SDK also supports `fork_session` and
  `resume_session_at`.
- **Webhooks as a model**: `core/operations/_webhooks.py` builds its router from the spec and runtime callables, and
  `start_operations` mounts it. The chat API follows the same shape.
- **LibreChat**: it reaches OpenAI-compatible backends through custom endpoints in `librechat.yaml`. It always resends the
  whole conversation and keeps its own history in MongoDB.

## Goals / Non-Goals

**Goals:**

- One chat API that any OpenAI-compatible client can use, with no LibreChat-specific behaviour in the node.
- LibreChat set up entirely through rendered configuration, so upgrading it means changing one pinned version.

**Non-Goals:**

- Mirroring LibreChat's conversation history into the run store, or the reverse.
- Supporting the OpenAI tools, function-calling or vision parameters. The org's agents own their tools.

## Decisions

### D1. The chat API lives in `core/operations`, not in the templates

`core/operations/_chat_api.py` builds an `APIRouter` from the spec, the store and the runtime's `start_run`, like the
webhook router. `start_operations` mounts it at `/v1` only when `CHAT_API_KEY` is set. It works with either `chat_ui`
value, so other OpenAI clients can use it too.

- *Why not in `routes.py.jinja`*: the library can unit-test it, and every rendered org gets fixes by upgrading agentorg.

### D2. Streaming translates the run transcript

The stream polls the run like the dashboard route and translates each transcript event:

| Event | Sent as |
|---|---|
| `text` | a content delta |
| `tool_call` | a line `› <tool> <short arguments>` |
| `tool_result` | nothing, to keep the chat readable |
| `status` = `awaiting_approval` | a message naming the action, with the console link `<CONSOLE_URL>/?tab=inbox&approval=<id>` |
| child run started | a line `› delegated to <target>` |
| `end` | a final chunk with `finish_reason` `stop`, or the failure reason as a last delta |

While a run waits for approval, the stream sends SSE comment lines every 15 seconds so proxies don't close it.
`CONSOLE_URL` defaults to the compose UI address.

### D3. Session keys come from the conversation prefix

A conversation is keyed by the user, the target, the conversation id header (or an empty string) and the SHA-256 of
every message before the new one. After each run, the node stores the key of the conversation including the new reply,
mapped to the run's session id. The next request finds its session by its own prefix.

- **Regenerate and edit in LibreChat**: these resend an older prefix. When the session found for that prefix has
  already moved on, the run resumes it with `fork_session`, so the discarded branch doesn't leak into the agent's
  context.
- **Clients that send no conversation id**: they still work, because the prefix alone identifies the conversation.
- The mapping is kept in the operations store's key-value table, with the same 30-day TTL as other chat state.

### D4. LibreChat passes identity through endpoint headers

The custom endpoint sets `Authorization: Bearer ${CHAT_API_KEY}`. It also sets `X-Agentorg-User-Id` and
`X-Agentorg-Conversation-Id` from LibreChat's header placeholders for the user id and conversation id. Which placeholders
the pinned version supports is checked once, during implementation (task 3.1). Without a conversation id placeholder, D3
still works from the prefix.

### D5. The spec chooses; the renderer adds files and the dashboard reads a flag

- **Spec**: `Infra.chat_ui: Literal['dashboard', 'librechat'] = 'dashboard'`, validated against `packaging` and
  `auth`.
- **Renderer**: adds `librechat.yaml` and the compose services under `{% if runtime.infra.chat_ui == 'librechat' %}`
  conditions, following the existing file-name conditional pattern.
- **Dashboard**: one bundle, not two. `/api/v1/config` gains `chat_ui` and `chat_url`, and `App.tsx` hides the chat
  panel and agent chat views and shows a "Chat" link when `chat_ui` is `librechat`. The Inbox reads `approval` from the
  query string and scrolls to that card.
- **Preview**: the master's preview forces `chat_ui` to `dashboard` in the config it serves, so the panel always shows.

### D6. `librechat.yaml` is generated, and LibreChat's extra features are turned off

- The `interface` section turns off the model selector outside model specs, presets, agents, MCP servers, file search,
  code interpreter, web search and parameters.
- `modelSpecs.enforce: true` and `prioritize: true` list one spec per agent and unit. Their labels, icons and
  descriptions come from `ui.agent_configs` and `ui.agent_icons`, and the default is the first of `ui.featured_agents`.
- `.env` sets `ENDPOINTS=custom`, so the built-in OpenAI, Anthropic and other endpoints are hidden.
- The image is `ghcr.io/danny-avila/librechat:<pinned>`, pinned in one template variable.

## Risks / Trade-offs

- [LibreChat's configuration schema changes between versions] → The version is pinned. A render test checks the
  generated YAML against the keys the pinned version documents, and the `local-docker` e2e scenario boots it.
- [MongoDB and Meilisearch add weight] → They only exist with `chat_ui='librechat'`, and preview never starts them.
- [Approval holds keep a stream open for a long time] → Keep-alive comments are sent. If the client disconnects, the run
  continues; the reply is in the run and in the console, and the next message in that conversation resumes the session.
- [Two places hold conversation history] → LibreChat's copy is for display. The agent session in the runtime is the
  source of truth for context.
- [Header placeholder support may differ in the pinned version] → D3's prefix key works without it.
