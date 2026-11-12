# Design

## Context

See proposal.md for the motivation. These parts of the current state shape the approach:

- **`Spec.ai`** holds `list[Any]` of agno objects that `spec.py` builds itself through `make_agent` / `make_team` /
  `make_workflow`. The renderer, the master writer and `render/_extract.py` all introspect agno attributes (`.tools`,
  `.model.id`, skill loaders).
- **`core/adapters/agno/_runtime.py`** wraps each runnable's `.arun()` in an AgentField reasoner and registers its tools as
  skills. The rendered `app/main.py` calls `register_master`, `register_agents`, `register_teams` and `register_workflows`.
- **The master agent** (`master/_agent.py`) is a set of agno stage agents with per-stage tool lists from `master/_tools.py`.
  The production master is also registered inside every rendered org.
- **AgentField** owns knowledge (`app.memory.global_scope`), per-user state (`app.memory.actor`), DID/VC identity, the
  execution DAG and tag-targeted policies. This change keeps all of that.
- **Persistence**: the rendered org has a database (`runtime.infra.database`: sqlite or postgres). Today only the control
  plane uses it.

## Goals / Non-Goals

**Goals:**

- One place, `core/operations/_policy.py`, decides allow, deny or hold for every tool call. It combines autonomy, side-effect
  class, governance and lifecycle.
- Spec models stay pure Pydantic with no runtime imports. All cross-references are validated at load time, so the master
  agent gets errors immediately.
- Every default is concrete and justified by a real org archetype (see D10), so a minimal spec yields a safe org.

**Non-Goals:**

- Durable execution across restarts for in-flight runs. Queued runs are durable on the broker. A run interrupted mid-execution
  fails with reason `interrupted` and follows the retry policy.
- A generic workflow DSL (branches, loops, parallel steps). Pipelines stay linear; branching is done by a hub lead that
  delegates.

## Decisions

### D1. Claude Agent SDK, one `ClaudeSDKClient` per run

Each run opens a `ClaudeSDKClient` with options built from the agent definition, sends the rendered prompt, streams messages,
and closes the client. Session continuity uses the SDK's `resume`. A table in the run store maps an agentorg
`(agent_id, session_id)` pair to the last SDK session id.

- *Alternative*: the one-shot `query()` function. Rejected because in-process SDK MCP servers and `can_use_tool` need
  streaming-input mode.
- *Alternative*: a long-lived client per agent. Rejected because concurrent runs would share conversation state.

### D2. Option mapping (`core/adapters/claude/_options.py`)

| Spec field | SDK option |
|---|---|
| `model` (`opus`/`sonnet`/`haiku`) | `model` alias |
| persona + principles + output contract | `system_prompt`: a compiled string, not the `claude_code` preset |
| `builtin_tools` | `tools`: a subset of `Read Write Edit Glob Grep Bash WebSearch WebFetch TodoWrite`, so no other built-in exists |
| custom tools | one in-process server `create_sdk_mcp_server('custom', …)`; exposed as `mcp__custom__<name>` |
| org tools | in-process server `org` (`delegate`, `handoff`, `publish`, `escalate`, the knowledge tools) |
| `mcp_servers` | `mcp_servers={name: stdio/http/sse config}`; a stdio server gets its `env` names as process env, an http or sse server sends the first one as a bearer token; exposed as `mcp__<name>__<tool>` |
| `skills` | copied into `<workspace>/.claude/skills/<name>/`; `skills=[names]`, which enables exactly those skills and loads only project settings |
| `workspace` | `cwd` |
| `max_turns` | `max_turns` |
| `max_run_usd` | `max_budget_usd`; an exceeded budget ends the query with an `error_max_budget_usd` result |
| `timeout_s` | `asyncio.timeout` around the stream, then `interrupt()` |
| `output` (`json`) | `output_format={'type': 'json_schema', 'schema': …}` |
| permissions | `permission_mode='default'`, `allowed_tools=[]` and `can_use_tool` → `_policy.decide` |
| isolation | `setting_sources=[]` when the agent has no skills |

`disallowed_tools` always contains `Task` and `NotebookEdit`. The workspace never contains a `settings.json`, so the
project settings that `skills` loads hold nothing but the copied skills.

- *Why `allowed_tools` stays empty*: the SDK auto-approves every tool listed there without calling `can_use_tool`, which
  would bypass `_policy`. `tools` limits which built-ins exist, and every call still reaches the policy.
- *SDK version*: confirmed against `claude-agent-sdk` 0.2.180, which provides `max_budget_usd`, `tools`, `skills` and
  `output_format` natively.

- *Why not the `claude_code` preset prompt*: org agents are not coding assistants, and the preset's identity text conflicts
  with personas. The tools carry their own usage descriptions.
- *Why not `bypassPermissions` for `autonomous`*: governance must still be able to hold governed classes. Autonomy changes
  the policy outcome; it never turns the hook off.

### D3. Spec layout

- **`core/spec/_agents.py`**:
  - `Agent`, `Persona`, `Referral`, `McpServer`, `Limits`, `Output`;
  - `Unit`, `Step` (pipeline review), the `Model`, `Routing` and `Decision` literals;
  - the `BuiltinTool` and `Autonomy` literals.
- **`core/spec/_ai.py`**: `AI(agents, root)`, which validates unique ids, references, unit membership, the per-model rules,
  span and depth limits and
  the derived default tools.
- **`core/spec/_operations.py`**:
  - `Operations(triggers, runs, communication, governance, budget, notifications, lifecycle)`;
  - triggers as a `kind`-discriminated union: `ScheduleTrigger`, `EventTrigger` and `WebhookTrigger`. Manual triggering is
    implicit, so it has no model.
- **`core/spec/_base.py`**: `Spec` gains `operations`. Its `model_validator` runs the checks that span domains, since they
  need sibling models:
  - triggers target existing ids;
  - env var references are declared;
  - output knowledge types exist;
  - prompt variables are known parameters.
- **Custom tools** stay callables. A public `agentorg.tool(side_effect='read'|'write', outbound=False)` decorator attaches
  metadata. It extends the existing `core/agents/tools/_tags.py` `tags` decorator and replaces it.

Pydantic validation errors already contain the field path, so master tools return `str(exc)` directly.

### D4. Operations runtime (`core/operations/`)

| Module | Responsibility |
|---|---|
| `_store.py` | run, approval, inbox, lifecycle, idempotency, session-map, worker-heartbeat and scheduler-lease tables on the org DB (SQLAlchemy async; `aiosqlite` / `asyncpg`) |
| `_broker.py` | the `aio-pika` robust connection, the D11 topology declaration, publish helpers and a health probe |
| `_queue.py` | per-agent run consumers with prefetch, the per-worker semaphore, retry publishing and the dead-letter consumer |
| `_runner.py` | executes one run: SDK client, streaming to subscribers, cost capture, retries, failure policy |
| `_policy.py` | `decide(agent, tool, ctx) -> allow \| deny(reason) \| hold(action_class)` |
| `_approvals.py` | creates approval records, awaits a `Future` per held action, handles timeouts |
| `_scheduler.py` | `croniter` loop on the worker holding the scheduler lease; persists the last fire per trigger for `catch_up`; honours `overlap` |
| `_bus.py` | publish to and subscribe on the `events` topic exchange; carries the causal chain depth; existing knowledge memory events are bridged in |
| `_webhooks.py` | `/hooks/{id}` route, HMAC verification, idempotency, 503 when the broker is down |
| `_consumers.py` | external `queue` trigger consumers |
| `_comms.py` | the org MCP tools; `delegate` and `escalate` create child runs through the dispatcher, linked by `parent_id`, which is the audit trail of delegation |
| `_units.py` | the model engines: pipeline steps with review holds, hub entry, the pool dispatcher, council fan-out and decision |
| `_lifecycle.py` | the state machine, the circuit breaker and the budget watcher |
| `_notify.py` | dashboard inbox, email (SMTP env vars), webhook and AMQP channels |

`start_operations(app, spec)` wires all of these on node startup and is the single call the template adds. It also
supplies the `run_target` callable that `register_org` gives every agent and unit reasoner, so the adapter never
imports the operations runtime.

- *Run store on the org DB, not AgentField memory*: run history needs filtered queries and atomic status transitions, and
  AgentField memory is a key-value scope. Knowledge and per-user state remain in AgentField; identity, audit and policies are
  untouched.
- *croniter, not APScheduler*: the scheduler is about 60 lines over a persisted last-fire time, while APScheduler brings its
  own job store that would duplicate `_store`.

### D11. RabbitMQ is mandatory and the only queue and bus

There is one implementation. The DB holds the run records; messages carry only `run_id`.

The topology is declared idempotently on startup, under the org slug prefix `<slug>.`:

| Object | Kind | Purpose |
|---|---|---|
| `runs` | direct exchange | routing key = target id |
| `runs.<target_id>` | classic durable queue, `x-max-priority=4`, DLX → `dead` | one per agent and unit; competing consumers on every worker; classic because quorum queues do not support `x-max-priority` |
| `runs.retry.<n>` | fanout exchange and queue with message TTL = 30s·2ⁿ, DLX → `runs` | delayed redelivery without a plugin; messages are published with the target as routing key, which the dead-lettering keeps, so they return to the right run queue |
| `runs.dead` | queue | consumed by the `on_failure` handler |
| `events` | topic exchange | routing key = event name; one durable queue per event trigger, bound by name |

Consuming a run works as follows:
1. Atomically move the DB row from `queued` to `running`, recording the worker id.
2. If the row was not `queued`, the message is a duplicate: ack it and drop it.
3. Otherwise ack it and execute the run.

Acknowledging on start rather than on finish avoids re-executing a run the SDK has already partly carried out. Workers write
a heartbeat. On startup, a worker fails any `running` rows whose owner's heartbeat is stale with reason `interrupted`.

Other behaviour:
- **The per-agent `replicas` cap across workers** is enforced at claim time. `claim` succeeds only while the agent's
  `running` count is below `replicas`, in the same DB transaction. A refused claim republishes the message to
  `runs.retry.0`. Workers compete on every queue, so a pool with thousands of replicas spreads across all workers.
- **The per-worker cap** comes from a semaphore sized `max_concurrent`.
- **Scheduling** happens on exactly one worker, which holds a DB lease row renewed every 15s.
- **Pausing** cancels the run, event and queue consumers, so messages wait on the broker. Resuming re-attaches them.
- **Preview mode** skips `_broker` entirely. `_runner` executes manual runs inline, and automatic triggers are already off.

Alternatives considered:
- *In-process queue plus the DB*: single worker only, no external queue ingress, and retry and dead-letter logic would be
  hand-written.
- *Optional broker*: two implementations with drifting semantics.
- *Redis Streams*: no native priorities or dead-letter queues, and a weaker fit for enterprise event sources.

### D5. Holding for approval keeps the run alive in-process

`can_use_tool` awaits the approval `Future` while the run sits in `awaiting_approval`. The SDK client stays open.

- *Alternative*: end the run and resume the SDK session on approval. That is more robust across restarts but needs replaying
  the pending tool call. It is deferred; the restart case falls under the `interrupted` non-goal.

### D6. Handoff is session routing

A `session_owner` row maps `session_id` to `agent_id`. The chat stream endpoint resolves the owner before starting a run.
`handoff` updates the row and injects the note as the first context line of the new owner's next run.

### D7. Rendered project

- **`app/main.py.jinja`** imports `register_org` from `agentorg.core.adapters.claude`, which registers agents, units and
  the master, and calls `start_operations`.
- **`app/routes.py.jinja`** gains these routes:
  - `/runs`, `/runs/{id}`, `/runs/{id}/cancel`;
  - `/approvals`, `/approvals/{id}`;
  - `/inbox`;
  - `/lifecycle`;
  - `/agents/{id}/enabled`.

  `/agents` summaries read from the spec models instead of introspecting agno.
- **`_extract.py`** shrinks to plain field access.
- **Frontend**: a Runs view (list and transcript), an Inbox view (approvals with edit-and-approve, plus escalations), and a
  lifecycle banner with transition controls. AgentPanel shows persona, autonomy, tools and triggers.
- **`ANTHROPIC_API_KEY` and `AMQP_URL`** are injected into the rendered `example.env` and the required env vars. The
  Dockerfile installs `claude-agent-sdk`, which bundles the CLI.
- **`compose.yaml`** always includes a `rabbitmq:3.13-management` service with a health check and a volume. The node
  `depends_on` it being healthy.
- **Railway**: the rendered setup checklist gains a "Provision RabbitMQ" step that sets `AMQP_URL`.
- **`packaging='none'`**: `AMQP_URL` is documented as required in the README, just as the control plane is.

### D8. Master agent on the SDK

Each stage becomes an `Agent`-like configuration with these settings:
- `autonomy='autonomous'`;
- `builtin_tools=[]`;
- the stage tool functions served as the `stage` in-process MCP server;
- `can_use_tool` allowing only `mcp__stage__*`.

`core/adapters/claude/_tools.py::as_sdk_tool(fn)` derives the JSON schema from the signature with Pydantic `TypeAdapter`.
The same helper serves custom tools, org tools and master tools. `_stages.py` gains blockers:
- Configure requires the budget;
- Build requires at least one agent.

The tool-slice tables in `_agent.py` are extended per the `master/interview-authoring` spec.

### D9. Defaults

| Field | Default | Reason |
|---|---|---|
| `autonomy` | `propose` | Safe until trust is earned; trial forces approvals anyway |
| `model` | `sonnet` | Cost/capability balance; `haiku` for triage, `opus` for leads |
| `workspace` | `ephemeral` | No leaked state between runs |
| `memory` | `session` | Chat continuity without cross-user persistence |
| `max_turns`, `timeout_s` | 30, 600 | Bounded runaway cost |
| `per_run_usd` | 2.0 | Typical research run cost with headroom |
| root model | by size: 1 agent → `solo`; 2–12 → `hub`; more → `hub` of nested units | The master proposes it; see D12 |
| pool `routing` | `least_loaded` | Even load without tags |
| `replicas` | 1 | One instance until the user scales a role |
| `max_delegation_depth` / `max_chain_depth` | 3 / 5 | Stops loops while allowing lead → specialist → helper |
| governed classes | `external_write`, `outbound_message` | Irreversible or customer-visible actions |
| lifecycle initial | `trial`, 50 runs | Shadow period before full autonomy |

### D10. Archetype coverage check

The parameter set must express these four common orgs without extensions:

1. **Support desk** (a root `hub` with a `pool` of support agents):
   - a `webhook` trigger from the helpdesk, or a `queue` trigger fed by the CRM, targets `triage` (`haiku`, `read_only`);
   - `triage` hands off to `billing` and `tech`;
   - `outbound_message` is governed;
   - `escalate` reaches humans.
2. **Research and reporting** (a `hub`):
   - a weekly `schedule` targets `hub` unit `research`, whose lead delegates to analysts;
   - the output goes to knowledge type `report`;
   - a `knowledge.created` event triggers a `summariser` that publishes to a webhook channel.
3. **Ops monitoring** (`solo` units under a root `hub`):
   - an hourly `schedule` with `overlap='skip'` runs `monitor`, which has a metrics MCP server marked `read`;
   - on anomaly, `monitor` calls `publish('custom.incident')`, which triggers `responder`;
   - `on_failure='escalate'`, with an `amqp` notification channel feeding the on-call system.
4. **Content pipeline** (a `pipeline`), plus a fifth archetype, **Credit decisions**: a `council` of 3 underwriters with
   `decision='majority'` and governed `external_write`:
   - a `pipeline` unit runs `research` → `draft` (`review='human'`) → `publish`;
   - the publish step's CMS MCP write tool is governed.

The spec unit tests encode each archetype as a fixture spec that must validate.

### D12. Governance models: a closed set, composed by nesting

Every org, from 1 agent to millions of instances, is one tree of units, and every unit uses one of five models. The set
covers the coordination patterns that keep reappearing in practice, and each has semantics the runtime can enforce
mechanically:

| Model | Real-world analogue | Entry point | Who decides | Typical use |
|---|---|---|---|---|
| `solo` | a single professional | the agent | the agent | personal assistant, monitor |
| `pipeline` | an assembly line, editorial flow | first step | each step plus review gates | content, ETL-like flows, approvals chains |
| `hub` | a manager and their team | the lead | the lead | research, projects, departments |
| `pool` | a call centre, a dispatch desk | the deterministic dispatcher | the routing rule | support, triage, high-volume work |
| `council` | a committee, an expert panel | all members | the decision rule | credit, hiring, risk calls |

Hierarchy is not a model; it is what nested hubs produce. Matrix structures are expressed as a hub whose members are pools,
for example a shared specialist pool.

**Why a closed set.** Every model maps to a fixed engine in `_units.py` with known failure modes. A user-defined model
could not be validated before runtime, which is the failure this project exists to avoid.

**Rejected alternatives:**
- *`mesh` (any agent to any agent)*: unbounded conversations, cycles and cost. Peers collaborate through a `council` or
  through events instead.
- *Free-form graphs*: they cannot be validated for termination or ownership.
- *Market or auction models*: the cost and benefit of bidding are unclear for LLM agents. A `pool` with `skill_match`
  covers routing by capability.

**Why the limits.** A span of 12 bounds a lead's context and delegation fan-out; LLM leads degrade on long member lists.
Pools allow 100 because their dispatcher is code. A depth of 6 bounds escalation latency and delegation chains. At these
limits, 12⁵ hubs × 100 pool members × replicas comfortably exceeds any realistic org, so size is never the constraint;
structure is.

**Information hiding is the scaling rule.** A unit is a black box with one entry point. Agents only reach downward (lead
to members), upward (escalate) and sideways inside a pool (handoff). Sibling units only interact through events. So adding
a unit never changes the prompts or tools of agents outside it, and per-agent context stays constant as the org grows.

**Decision rights** are layered and only ever tighten going down the tree:
- Org level: governed action classes, approvers and budget.
- Unit level: `owners`, `max_autonomy`, `monthly_usd`, and additional governed classes.
- Agent level: `autonomy`.

The effective autonomy is the minimum along the path, and the governed classes are the union along the path.

**Runtime mapping:**
- every unit is a reasoner tagged `unit` and its model, with its own `runs.<unit_id>` queue;
- the `pool` dispatcher and the `council` aggregation run in the worker, not in an agent;
- `pipeline` steps are child runs linked to the pipeline run.

## Risks / Trade-offs

- [Approval waits hold an SDK subprocess for up to 24h] → Runs in `awaiting_approval` count toward `max_concurrent`. Operators can shorten `approval_timeout_h`; a restart fails held runs explicitly.
- [The SDK spawns the Claude Code CLI per run, so start-up latency is about 1s] → Acceptable for org workloads. The
  concurrency default of 4 bounds process count.
- [SDK option names drift between versions] → Pin `claude-agent-sdk` with a lower bound. All option construction is isolated
  in `_options.py` with one unit test per spec field.
- [Hard USD cap may be unavailable in the pinned SDK] → The fallback enforcement from streamed usage may overshoot by one
  turn; this is documented.
- [Breaking spec format] → No users depend on the agno format outside this repo. The master agent regenerates specs.
- [RabbitMQ is one more service to run, and its outage stops new work] → Webhooks return 503 so senders retry.
  - Missed schedule fires follow `catch_up`.
  - The health endpoint reports the broker.
  - `aio-pika`'s robust connection reconnects and re-declares the topology.
- [Several workers could each run the scheduler] → A DB lease guarantees a single scheduler. The lease expires after 45s, so
  a dead worker's schedules resume on another.
- [A parent waiting on a delegated child holds a worker slot, so delegation chains longer than `max_concurrent` on one
  worker can deadlock] → Chains are bounded by the tree depth (at most 6) and children usually land on other workers.
  Raise `max_concurrent` above the deepest chain, and revisit with slot release while waiting if it shows up in practice.
- [Refused claims cause requeue churn when an agent is saturated] → Refused messages go through the 30s retry queue, not
  an immediate requeue. Saturation is visible as queue depth on the dashboard.
- [Testing needs a broker] → Unit tests use an in-memory fake implementing the small `_broker` surface. Integration tests use
  `testcontainers[rabbitmq]` and are skipped when Docker is unavailable.
- [Sixth domain model] → `CLAUDE.md` is updated to describe `operations` and the Claude runtime.

## Migration Plan

1. Land the spec models and validation behind the new `Spec` shape. Update the seed and the master models.
2. Land `core/adapters/claude` and `core/operations` (broker first), then swap the templates and add `rabbitmq` to compose.
   Run `test_each_shipped_template_renders`.
3. Port the master stages, then remove the agno packages, the agno tests and the `agno` dependency.
4. Update `CLAUDE.md`, `openspec/config.yaml`, the README and the docs.

Rollback is a git revert. There is no persisted data migration, because run-store tables and broker topology are created on
first boot.

## Open Questions

- The email transport for notifications: plain SMTP env vars, or a provider API. This does not affect the specs: `email` is
  a channel either way.
