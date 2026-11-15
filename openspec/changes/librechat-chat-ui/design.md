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

- One chat surface, LibreChat, for the master interview, the live preview and every rendered org.
- One chat API that any OpenAI-compatible client can use, with no LibreChat-specific behaviour in the node.
- LibreChat set up entirely through generated configuration, so upgrading it means changing one pinned version.

**Non-Goals:**

- Mirroring LibreChat's conversation history into the run store, or the reverse.
- Supporting the OpenAI tools, function-calling or vision parameters. The org's agents own their tools.

## Decisions

### D1. The chat API lives in `core/operations`, not in the templates

`core/operations/_chat_api.py` builds an `APIRouter` from the spec, the store and the runtime's `start_run`, like the
webhook router. `start_operations` mounts it at `/v1` only when `CHAT_API_KEY` is set, which every deployed org has. Any
OpenAI client can use it, not only LibreChat.

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

### D3. Every turn is a fork of the turn it follows

The runner forks the SDK session whenever it resumes one (`fork_session`), so each run leaves the session it resumed
unchanged. Every finished turn is therefore an immutable snapshot.

- **Lookup**: a conversation at a given point is keyed by the user, the target, the conversation id header (or an empty
  string) and the SHA-256 of its user and assistant messages. After each run, the node stores the key of the conversation
  including the streamed reply, mapped to that turn's session key. When the client also sends a conversation id, the
  latest turn is stored under it as a fallback for histories the client re-renders.
- **New turn**: every chat-API turn gets a new session key, seeded with the previous turn's SDK sessions and handoff
  owner. Regenerate and edit in LibreChat resend an older prefix, find the older snapshot and branch from it, so the
  discarded answer never reaches the agent's context.
- **Dashboard chats** keep one session key per chat; forking only changes the SDK session id stored after each turn.
- The mappings are kept in the operations store's key-value table with a 30-day TTL.

### D4. LibreChat passes identity through endpoint headers

The pinned image is `ghcr.io/danny-avila/librechat:v0.8.7`, the newest non-prerelease tag on ghcr; its configuration
version is `1.3.13`. Its custom endpoints resolve `{{LIBRECHAT_USER_ID}}` and `{{LIBRECHAT_BODY_CONVERSATIONID}}` in
`headers` (checked in `packages/api/src/utils/env.ts` at that tag). The endpoint sets
`Authorization: Bearer ${CHAT_API_KEY}`, `X-Agentorg-User-Id: {{LIBRECHAT_USER_ID}}` and
`X-Agentorg-Conversation-Id: {{LIBRECHAT_BODY_CONVERSATIONID}}`.

### D5. LibreChat always; the dashboard reads no flag

There is no chat-UI option. `Runtime` adds `CHAT_API_KEY` to the always-required variables, like `ANTHROPIC_API_KEY`
and `AMQP_URL`, and on Railway adds a `librechat` setup step next to `rabbitmq`. The renderer always writes
`librechat.yaml`, and `compose.yaml` always carries the LibreChat services. The dashboard has no chat code: the chat
panel, agent panel, chat-event parsing, the stale Master view and the `/api/v1/reasoners/{name}/stream` route are
deleted. Selecting an agent opens `chat_url` from `/api/v1/config`, and the Inbox reads `approval` from the query
string and scrolls to that card.

### D6. `librechat.yaml` is generated, and LibreChat's extra features are turned off

- The `interface` section turns off the model selector outside model specs, presets, agents, MCP servers, file search,
  code interpreter, web search and parameters.
- `modelSpecs.enforce: true` and `prioritize: true` list one spec per agent and unit. Their labels, icons and
  descriptions come from `ui.agent_configs` and `ui.agent_icons`, and the default is the first of `ui.featured_agents`.
- `.env` sets `ENDPOINTS=custom`, so the built-in OpenAI, Anthropic and other endpoints are hidden.
- The image tag and configuration version live in one template, so an upgrade is a one-line change.

### D7. One OpenAI layer, two chat backends

`core/operations/_chat_api.py` owns the OpenAI protocol: authentication, the models list, request validation, command
dispatch, streaming chunks, keep-alives and usage. What a message does comes from a `ChatBackend` protocol:

- `models()`: the ids and names to list;
- `command(text, user)`: the reply to a `/` command;
- `turn(model, messages, user)`: a `ChatTurn` that yields text deltas and reports usage and a run id.

`OrgChat` is the rendered node's backend over the store and the operations runtime (D2, D3). `MasterChat`, in
`master/ui`, is the master's backend over the interview state and the stage agents. The user is a dataclass carrying
the id, email and conversation id from the headers.

### D8. Commands answer from state, never from a model

`OrgChat.command` parses `/name args` and answers from the store, the approvals service and the lifecycle:

- **Decisions**: `/approve` and `/reject` go through the same `Approvals.decide` call as the console, with the user's
  email as the actor. They are allowed when the email is in the approval's approvers, or when the approval lists none
  and the email is the admin's.
- **Lifecycle**: `/pause` and `/resume` use `Lifecycle.transition`.
- **Reads**: `/status`, `/runs`, `/run` and `/inbox` read the store.

`MasterChat.command` answers `/stage`, `/next`, `/spec`, `/preview`, `/reset confirm` and `/help` from the interview
state and the stage machine. Command replies are plain Markdown and never start a run or touch a session.

### D9. The master runs LibreChat from a shipped compose file

`agentorg ui` checks Docker first, then:

- **Secrets**: it writes `~/.agentorg/librechat/.env` on first use, with a random `CHAT_API_KEY` and LibreChat
  secrets, and reuses it after that.
- **Configuration**: it writes `librechat.yaml` there with two custom endpoints:
  - `AgentOrg`: the master at `http://host.docker.internal:<port>/v1`, model `agentorg`;
  - `Preview`: the preview node at `http://host.docker.internal:<port + 1>/v1`, with `models.fetch: true`.
- **Stack**: it runs `docker compose -p agentorg-master up -d` on the shipped `master/ui/librechat/compose.yaml`, and
  `down` on exit.

The preview node is pinned to the master port plus one and is started with the same `CHAT_API_KEY`. The stack enables registration so the first local user can sign up. LibreChat requires at least one default model per
endpoint, so the preview endpoint lists a `preview` placeholder that the fetched list replaces once the preview runs.
Both configurations were checked by booting LibreChat v0.8.7, which loads them without validation errors, and a
`/help` sent through LibreChat's chat API reached the master and came back. The master page
keeps the preview iframe and the stage progress, and links to LibreChat on port 3080.

- *Streaming*: stage agents return a whole reply, so `MasterChat` streams the tool-call lines as soon as they are known,
  sends keep-alives while the agent works, then sends the text.

## Risks / Trade-offs

- [LibreChat's configuration schema changes between versions] → The version is pinned. A render test checks the
  generated YAML against the keys the pinned version documents, and the `local-docker` e2e scenario boots it.
- [MongoDB and Meilisearch add weight to every org and to the master] → One LibreChat stack serves the master and its
  preview. Rendered orgs share it with nothing, which keeps each deployment self-contained.
- [The master now needs Docker] → The command checks for it first and says so. The preview already needed RabbitMQ.
- [On Linux, `host.docker.internal` does not reach services bound to 127.0.0.1] → Docker Desktop on macOS and Windows
  forwards it; Linux users bind the master with `--host` to the docker bridge address.
- [Approval holds keep a stream open for a long time] → Keep-alive comments are sent. If the client disconnects, the run
  continues; the reply is in the run and in the console, and the next message in that conversation resumes the session.
- [Two places hold conversation history] → LibreChat's copy is for display. The agent session in the runtime is the
  source of truth for context.
- [Header placeholder support may differ in the pinned version] → D3's prefix key works without it.
