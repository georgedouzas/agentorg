# Proposal

## Why

Rendered orgs currently run agno `Agent`/`Team`/`Workflow` objects with a large set of agno-specific defaults (`AGENT_DEFAULTS`
in `core/agents/framework/agno/_base.py`). Agents assembled this way do not reliably carry out real multi-step work. They lack
a working harness: file workspace, shell, web access, MCP, skills, context compaction and permission control. The Claude Agent
SDK ships that harness ready-made. agentorg's job then becomes *configuring* agents (persona, tools, MCP, skills, autonomy)
rather than assembling them.

The org concept is also unconstrained today. Every agent is a chat endpoint triggered by a human. There is no notion of
scheduled work, events, inter-agent protocol, approvals, budgets or org lifecycle. Practical orgs need all of these: a
support desk reacting to webhooks, a research team producing a weekly report, an ops team escalating incidents. This change
makes them explicit, typed spec parameters in two groups: **(1) individual agent behaviour** and **(2) organization
operations**.

## What Changes

- **BREAKING**: `Spec.ai` stops accepting arbitrary runnables (`list[Any]` of agno objects). It becomes typed declarations:
  - `Agent`: persona, model, autonomy level, built-in tools, custom tools, MCP servers, skills, workspace, memory, limits and
    output contract.
  - `Unit`: the org is a tree of units. Each unit is governed by one of five fixed models: `solo`, `pipeline`, `hub`,
    `pool` or `council`. One agent is a one-unit org; hundreds of thousands of agents are nested units under hard span and
    depth limits.
- **BREAKING**: agno is removed as a dependency.
  - Deleted: `core/agents/framework/agno/`, `core/adapters/agno/`, the agno skill loaders and the `AgnoAgent` type.
  - Replaced by a Claude Agent SDK adapter that turns each `Agent` into `ClaudeAgentOptions` and registers it as an
    AgentField reasoner.
- New `Spec.operations` domain model (the sixth domain next to `org`, `runtime`, `ai`, `knowledge` and `ui`) with concrete,
  closed choices:
  - **Triggers**: `manual`, `schedule` (cron), `event` (org bus), `webhook` (external HTTP) and `queue` (an external AMQP
    queue). Each has explicit overlap and catch-up policies.
  - **Runs**: a single unit of work with a fixed status machine, a concurrency cap, retries and a failure policy.
  - **Communication**: four primitives only (`delegate`, `handoff`, `publish`, `escalate`). Who may call whom follows
    the unit tree, and sibling units interact only through events.
  - **Governance**: action classes that require human approval, and a USD budget (monthly cap, per-run cap, alert threshold,
    exhaustion behaviour).
  - **Lifecycle**: org states `draft → trial → active ⇄ paused → retired`, with defined effects on triggers, approvals and
    writes.
- **BREAKING**: `Org.budget: Literal['low','medium','high']` is replaced by `operations.budget` in USD.
- **BREAKING**: RabbitMQ becomes a mandatory dependency of every rendered org.
  - It carries queued runs (with native priorities), retries (delayed redelivery), permanently failed runs (a dead-letter
    queue) and the org event bus. There is no in-process queue or bus.
  - The database remains the record of every run.
  - `AMQP_URL` is a required env var. Docker packaging always ships a `rabbitmq` service; Railway deployments need a hosted
    RabbitMQ.
  - Preview mode is the one exception: manual chat runs execute directly, so the live preview needs no broker.
- The rendered node gains:
  - a scheduler, broker-backed run queue and event bus, webhook routes, external queue consumers and a run store;
  - an approvals inbox and lifecycle endpoints;
  - dashboard views for runs, approvals and lifecycle.
- The master agent moves to the Claude Agent SDK. Each stage is a Claude agent whose tool slice is served by an in-process
  MCP server. Build gains trigger/communication tools; Configure gains budget/lifecycle tools; Refine gains approval and
  notification tools.

### Out of scope

- Multi-provider model support. Agents run on Claude models only; the existing `provider:model` strings for agents are
  dropped. The embedder setting is unaffected.
- Claude Agent SDK in-process subagents (`agents=` / `Task`). All agent-to-agent work goes through the org's `delegate` and
  `handoff` primitives so AgentField audits it.
- Multi-node / multi-org federation. One org is one AgentField node.
- A migration tool for existing agno-based `spec.py` files. Existing specs must be re-authored through the master agent.
- Org-to-org messaging, marketplaces for skills or MCP servers, and per-tenant billing.
- Brokers other than RabbitMQ (Redis Streams, SQS, Kafka).
- Surviving a restart mid-run. A run executing when its worker dies fails with reason `interrupted` and follows the retry
  policy; the broker does not resume it.

## Capabilities

### New Capabilities

- `agents/agent-definition`: the typed spec of one agent's behaviour: persona, model, autonomy, tools, MCP servers, skills,
  workspace, memory, limits, output contract.
- `agents/agent-runtime`: running an agent definition on the Claude Agent SDK as an AgentField reasoner, including
  principles injection, streaming, cost capture and permission enforcement.
- `operations/work-intake`: how work enters the org: manual, schedule, event, webhook and queue triggers and their
  policies.
- `operations/run-management`: the run record, status machine, broker-backed queueing, concurrency, retries, failure
  handling and run history.
- `operations/org-structure`: the unit tree, the five governance models and their semantics, span and depth limits,
  replicas, and per-unit owners, autonomy ceilings and budgets.
- `operations/agent-communication`: delegate, handoff, publish and escalate, and how the unit tree permits them.
- `operations/governance`: human approvals by action class, and USD budgets with alerting and exhaustion behaviour.
- `operations/org-lifecycle`: org states, the transitions between them, and what each state permits.
- `master/interview-authoring`: the master agent's per-stage tools for authoring agent definitions and operations, running
  on the Claude Agent SDK.

### Modified Capabilities

None. No baseline specs exist yet under `openspec/specs/`.

## Impact

- **Spec**:
  - `core/spec/_ai.py` is rewritten.
  - New `core/spec/_agents.py` and `core/spec/_operations.py`.
  - `Org.budget` is removed and `Spec` gains `operations`.
  - `master/_seed.py` and `master/_models.py` are updated.
- **Runtime**:
  - Removed: `core/adapters/agno/` and `core/agents/framework/agno/`.
  - New: `core/adapters/claude/` and a `core/operations/` package (broker, scheduler, runs, approvals, lifecycle,
    communication tools).
  - `core/adapters/mcp/` is unchanged.
- **Render**:
  - Every template that imports agno: backend/full `app/main.py`, `app/routes.py`, `pyproject.toml`, `Dockerfile`,
    `compose.yaml`, `README.md`, the ai `sandbox.py` and the tests.
  - The frontend `AgentPanel`, `ChatBar` and `useIdentity`.
  - New dashboard views.
  - `core/render/_extract.py` shims.
- **Master**: `_agent.py`, `_agent_sandbox.py`, `_sandbox.py`, `_tools.py`, `_writer.py`, `_stages.py`, `ui/_server.py` and
  `ui/_preview.py`.
- **Dependencies**:
  - Removed: `agno`.
  - Added: `claude-agent-sdk`, `croniter` and `aio-pika`; `testcontainers[rabbitmq]` for development.
  - The Claude Code CLI is required at runtime; it is bundled by `claude-agent-sdk`.
  - RabbitMQ 3.13 or newer is required at runtime. `compose.yaml` always includes it, and the Railway setup checklist gains
    a hosted-broker step.
  - `ANTHROPIC_API_KEY` and `AMQP_URL` become required env vars of every rendered org.
- **Docs**: `CLAUDE.md` and `openspec/config.yaml` currently describe agno-compatible runnables and five domain models; both
  are updated.
- **Tests**: `tests/core/adapters/agno/`, `tests/core/agents/framework/agno/` and the agno fixtures in the `conftest.py`
  files are replaced.
