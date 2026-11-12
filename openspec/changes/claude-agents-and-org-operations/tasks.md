# Tasks

## 1. Dependencies

- [x] 1.1 Add `claude-agent-sdk`, `croniter`, `aio-pika`, `sqlalchemy[asyncio]`, `aiosqlite` and `asyncpg` to `pyproject.toml`, and add `testcontainers[rabbitmq]` to the dev group. Verify that `uv sync` succeeds and `uv run python -c "import claude_agent_sdk, croniter, aio_pika"` exits 0.
- [x] 1.2 Check whether the locked `claude-agent-sdk` exposes `max_budget_usd`, and record the result in design.md (Open Questions → resolved). Verify that design.md D2 names the branch that was chosen.

## 2. Agent definition spec models

- [x] 2.1 Create `core/spec/_agents.py` with `Agent`, `Persona`, `Referral`, `McpServer`, `Limits`, `Output`, `Unit` and `Step`, the `Model`/`Routing`/`Decision` literals, plus the `Autonomy`/`BuiltinTool` literals, and export them from `core/spec/__init__.py`. Verify with `tests/core/spec/test_agents.py`, which covers model tier rejection, autonomy-derived default tools, contradictory grants and MCP tool filtering fields.
- [x] 2.2 Rewrite `core/spec/_ai.py` as `AI(agents, root)` with these validations: unique ids across agents and units, every agent in exactly one unit, referral targets, the per-model rules (solo size, hub lead, council size and odd majority, pool routing), span and depth limits, and the inheritance of owners, autonomy ceilings, budgets and governed classes. Verify with `tests/core/spec/test_ai.py` covering each rejection scenario in `specs/agents/agent-definition` and `specs/operations/org-structure`, including the 4-million-instance spec validating.
- [x] 2.3 Replace `core/agents/tools/_tags.py` with the public `tool(side_effect=..., outbound=...)` decorator, and export it from `agentorg.core.agents.tools`. Verify with `tests/core/agents/tools/test_tags.py` that an unmarked tool reads as `write`.

## 3. Operations spec models

- [x] 3.1 Create `core/spec/_operations.py` with `Operations` and these models: the `kind`-discriminated triggers (`ScheduleTrigger`, `EventTrigger`, `WebhookTrigger`, `QueueTrigger`), `RunsPolicy`, `Communication`, `Governance`, `Budget`, `Notifications` (including the `amqp` channel with `exchange`) and `Lifecycle`, all with the D9 defaults. Verify with `tests/core/spec/test_operations.py` covering cron validation, the overlap/catch-up enums, the queue trigger fields and the default values.
- [x] 3.2 Add `operations` to `Spec`, remove `Org.budget`, and add the cross-domain checks to `Spec`'s validator: trigger targets, env var references for MCP servers, webhook secrets and queue `url_env`, output knowledge types, and prompt template variables. Verify with `tests/core/spec/test_base.py` covering each cross-domain rejection.
- [x] 3.3 Add the five D10 archetype fixture specs (support desk, research/reporting, ops monitoring, content pipeline, credit decisions) under `tests/core/spec/`. Verify that each validates in `test_base.py`.

## 4. Claude adapter

- [x] 4.1 Create `core/adapters/claude/_tools.py` with `as_sdk_tool(fn)`, which derives a schema from the signature and the description from the docstring. Verify with `tests/core/adapters/claude/test_tools.py` for sync, async and pydantic-typed callables.
- [x] 4.2 Create `core/adapters/claude/_prompt.py`, which compiles persona, principles (with parameter substitution), referrals and the output contract into a system prompt. Verify with `test_prompt.py` covering the referral and placeholder-substitution scenarios.
- [x] 4.3 Create `core/adapters/claude/_options.py`, which maps an `Agent` to `ClaudeAgentOptions` per the design.md D2 table: always disallow `Task`/`NotebookEdit`, copy skills into the workspace, resolve MCP env from the environment, and set the workspace `cwd` per mode. Verify with `test_options.py`, with one assertion per spec field and an isolation check that a host-level skill is absent.
- [x] 4.4 Create `core/adapters/claude/_runtime.py` with `register_org(node, spec, run_target, master=None)`. It registers agent, unit and master reasoners with the `agent`, `unit` plus model, and `master` tags and the org slug, and registers custom tools as node skills. Verify with `test_runtime.py` using a fake SDK client: the tags, the reasoner names, and the skills are registered once.

## 5. Operations runtime core

- [x] 5.1 Create `core/operations/_store.py` with the run, approval, inbox, lifecycle, idempotency, session-owner, trigger-last-fire, worker-heartbeat and scheduler-lease tables, created on startup for sqlite and postgres. Include an atomic `claim(run_id, worker_id)` for the `queued` → `running` transition. Verify with `tests/core/operations/test_store.py` on sqlite: a run survives store reopen, terminal states are immutable, and a second claim fails.
- [x] 5.1a Create `core/operations/_broker.py` with the robust connection, the idempotent D11 topology declaration under the org slug prefix, publish helpers with priority and persistence, and a health probe. Add the in-memory fake broker in `tests/core/operations/conftest.py`. Verify with `test_broker.py` against `testcontainers[rabbitmq]` (skipped without Docker) that the topology declares twice without error and that a `runs.retry.0` message reappears on `runs.<target>` after its TTL.
- [x] 5.2 Create `core/operations/_policy.py` with `decide(...)`, which combines autonomy, side-effect class, governed classes and lifecycle state. Verify with a table-driven `test_policy.py` covering every autonomy × class × lifecycle state, including the trial-forces-approval and autonomous-still-governed cases.
- [x] 5.3 Create `core/operations/_runner.py`, which runs one run through the SDK client. It streams events, records cost/tokens, enforces `max_turns`/`max_run_usd`/`timeout_s`, wires `can_use_tool` to `_policy`, resumes sessions per `memory`, writes output to the knowledge type, and validates JSON output. Verify with `test_runner.py` using a fake client for each limit failure reason and for denial-as-tool-result.
- [x] 5.4 Create `core/operations/_queue.py`, with these parts:
  - competing per-target consumers on every worker and the per-worker semaphore;
  - the `replicas` cap enforced in `claim`, with refused claims sent to `runs.retry.0`;
  - claim-then-ack with duplicate drop;
  - retries through `runs.retry.<n>`, with non-retryable reasons skipped;
  - the `runs.dead` consumer applying `on_failure`;
  - cascade cancel;
  - the startup sweep that fails stale-heartbeat `running` runs as `interrupted`.

  Verify with `test_queue.py` on the fake broker covering manual-before-schedule, no retry on `max_run_usd`, a duplicate delivery executing once, cascade cancel and the interrupted sweep.
- [x] 5.5 Make startup fail fast without `AMQP_URL` outside preview mode, and execute manual runs inline in preview mode with no broker connection. Report the broker in the node health endpoint. Verify with `test_queue.py` cases for the missing-URL error, a preview chat run with no broker, and health showing the broker as unavailable after a disconnect.

## 6. Work intake

- [x] 6.1 Create `core/operations/_bus.py` on the `events` topic exchange. It covers the built-in events, the `custom.*` names, one durable queue per event trigger, payload filters, the causal chain depth guard in message headers, and the bridge from knowledge memory events. Verify with `test_bus.py` on the fake broker covering the filter mismatch and the loop broken at `max_chain_depth`.
- [x] 6.2 Create `core/operations/_scheduler.py` with cron in a timezone, persisted last fire, `overlap`, `catch_up`, and the DB scheduler lease. Verify with `test_scheduler.py` using a frozen clock, covering skip-on-overlap, a single `run_once` after three missed fires, and two schedulers producing one fire.
- [x] 6.3 Create `core/operations/_webhooks.py` with `POST /hooks/{trigger_id}`, HMAC-SHA256 verification, a 24h `Idempotency-Key` window, a 202 response carrying the run id, and a 503 response when the broker is down. Verify with `test_webhooks.py` covering the valid, bad-signature, replay and broker-down cases.
- [x] 6.4 Create `core/operations/_consumers.py` for external `queue` triggers: consume from the named queue (on `url_env` or the org broker), apply the filter, create the run and then ack, and reject unparseable JSON without requeue. Verify with `test_consumers.py` on the fake broker, plus a testcontainers case for redelivery after a crash before the run exists.
- [x] 6.5 Add prompt template rendering for `{now}`, `{trigger_id}`, `{event}`, `{body}`, `{message}` and the parameters. Verify with a unit test that the rendered prompt contains the event payload and the queue message.

## 7. Communication, governance and lifecycle

- [x] 7.1 Create `core/operations/_comms.py`, the org MCP tools. Each agent gets only the primitives its position in the unit tree permits. `delegate` goes through `app.call` and enforces the tree and re-entrancy. `handoff` updates the session owner. `publish` emits `custom.*` events. `escalate` climbs the tree to the human inbox. Verify with `test_comms.py` covering the member-to-member denial, sibling-unit denial, re-entrant denial, escalation path and handoff routing scenarios.
- [x] 7.2 Create `core/operations/_units.py` with the five model engines:
  - pipeline steps with review holds and a single re-run on rejection;
  - hub entry at the lead;
  - the pool dispatcher (`round_robin`, `least_loaded`, `skill_match`, no-match escalation);
  - council fan-out with isolated members and the `majority`/`judge`/`unanimous` decisions.

  Verify with `test_units.py` covering every scenario in `specs/operations/org-structure`.
- [x] 7.2a Enforce unit scoping at runtime: effective autonomy as the minimum along the path, governed classes as the union, approvals routed to the nearest owners, and unit budget caps with reason `unit_budget`. Verify with `test_policy.py` and `test_lifecycle.py` cases for the autonomy ceiling, the loosening attempt and unit budget exhaustion.
- [x] 7.3 Create `core/operations/_approvals.py` with held-action futures, approve / reject / approve-with-edits, timeouts per `on_timeout`, and the `approval.decided` event. Verify with `test_approvals.py` covering the edited-arguments and timeout-reject cases.
- [x] 7.4 Create `core/operations/_lifecycle.py` with the state machine and allowed transitions, and the per-state permissions (pausing cancels the run, event and queue consumers; resuming re-attaches them). Add the failure-rate breaker, budget alert and exhaustion pause, per-agent enable/disable (cancels that target's consumer), and `lifecycle.changed`. Verify with `test_lifecycle.py` covering the illegal transition, paused-holds-queue, breaker trip and budget pause.
- [x] 7.5 Create `core/operations/_notify.py` with the dashboard, email, webhook and AMQP channels. Verify with `test_notify.py` that the webhook channel POSTs JSON for an escalation, and that the AMQP channel publishes a persistent message with routing key `run.failed`.
- [x] 7.6 Add `start_operations(app, spec)`, which wires the store, broker, consumers, scheduler, bus, webhooks and lifecycle on startup, and disables automatic triggers and write actions in preview mode. Verify with `tests/core/operations/test_runtime.py` that a due schedule creates no run when `AGENTORG_PREVIEW_MODE=true`.

## 8. Rendered project

- [x] 8.1 Rewrite `app/main.py.jinja` (backend and full) to use `register_org` and `start_operations`. Rewrite `app/routes.py.jinja` to add the runs, approvals, inbox, lifecycle and agent-enable endpoints, and to build `/agents` summaries from spec models. Verify that `test_each_shipped_template_renders` passes and that the rendered `tests/test_routes.py` covers the new endpoints.
- [x] 8.2 Simplify `core/render/_extract.py` to plain field access with no agno shims. Verify that `tests/core/render/test_extract.py` passes.
- [x] 8.3 Update `pyproject.toml.jinja` (ai/backend/full), `Dockerfile`, `example.env.jinja` and the README template: add `ANTHROPIC_API_KEY` and `AMQP_URL` as required, document the broker requirement for `packaging='none'`, and drop agno. Verify that `test_each_shipped_template_renders` passes and that `grep -ri agno` over a rendered minimal project returns nothing.
- [x] 8.3a Add a `rabbitmq:3.13-management` service to `compose.yaml.jinja` with a health check and a volume. Make the node `depends_on` it being healthy, and set `AMQP_URL` for the node. Verify that `docker compose config` validates on a rendered docker project and that `test_each_shipped_template_renders` passes.
- [x] 8.3b Add a "Provision RabbitMQ" setup step that sets `AMQP_URL` for Railway deployments, and inject `AMQP_URL` into the required env vars of every rendered org. Verify with a render test that a Railway spec's `/setup` checklist contains the step.
- [x] 8.4 Update the frontend: add the Runs view (list and transcript), the Inbox view (approve, edit and approve, reject, escalations) and the lifecycle banner and controls, and show persona/autonomy/tools/triggers in AgentPanel. Clean agno references from `AgentPanel`, `ChatBar` and `useIdentity` in both the `frontend` and `full` templates. Verify that `npm run build` succeeds in a rendered project.
- [x] 8.5 Rewrite the rendered `sandbox.py.jinja` and `tests/test_factories.py.jinja` for spec-model agents. Verify that the rendered project's own `pytest` passes.

## 9. Master agent

- [x] 9.1 Update `master/_models.py` and `master/_seed.py` to the new agent, unit and operations shapes, with the budget placeholder and no `Org.budget`. Verify that `tests/master` seed tests pass.
- [x] 9.2 Extend `master/_tools.py`:
  - Configure gets the budget, lifecycle and approvers tools.
  - Build gets the full agent fields, plus the unit tools (add, update, remove, move) and the trigger tools. The Build prompt proposes the root model by org size per design.md D12.
  - Refine gets the governance and notifications tools.

  Each tool returns validation errors as text. Verify with `tests/master/test_tools.py` that an invalid cron returns an error and leaves the spec unchanged.
- [x] 9.3 Port `master/_agent.py` stage agents to the SDK, serving each stage's slice as the `stage` MCP server with no built-in tools. Add the `_stages.py` blockers: Configure needs the budget, Build needs at least one agent. Verify with `tests/master/test_agent.py` that Discover has no agent/trigger tools and that the Build stage cannot call `bash`.
- [x] 9.4 Port `master/_agent_sandbox.py` and `master/_sandbox.py` to run agents through `_runner` in preview mode and report outputs, tool calls and cost. Verify with `tests/master/test_agent_sandbox.py` using a fake client.
- [x] 9.5 Rewrite `master/_writer.py` to emit `spec.py` with only `agentorg` spec-model and custom-tool imports. Verify with `tests/master/test_writer.py` that it round-trips each D10 archetype and that no framework import appears.
- [x] 9.6 Update `master/ui/_server.py` and `master/ui/_preview.py` for SDK message streaming. Verify that `tests/master/ui/test_server.py` passes.

## 10. Remove agno completely

- [x] 10.1 Delete `core/adapters/agno/`, `core/agents/framework/`, `core/agents/skills/` (agno loaders; keep pinned skill refs only if `_options.py` uses them, moved under `core/adapters/claude/`) and the `AgnoAgent`/`Agent` aliases in `core/agents/__init__.py`. Verify that the package imports cleanly with `uv run python -c "import agentorg"`.
- [x] 10.2 Delete `tests/core/adapters/agno/` and `tests/core/agents/framework/`, and remove the agno fixtures from `tests/conftest.py` files and `tests/cli/test_new.py`. Verify that `uv run nox -s tests` collects without import errors.
- [x] 10.3 Remove `agno` from `pyproject.toml` and regenerate `uv.lock`. Verify that `uv tree | grep -i agno` returns nothing.
- [x] 10.4 Update `CLAUDE.md` (Claude runtime, sixth `operations` domain, mandatory RabbitMQ next to the control plane), `openspec/config.yaml` context, `README.md` and `mkdocs.yml`. Verify that `grep -rni agno src tests docs README.md mkdocs.yml CLAUDE.md pyproject.toml openspec/config.yaml` returns nothing.

## 11. Integration verification

- [ ] 11.1 Render the support-desk archetype with docker packaging and boot the stack, including `rabbitmq`. Send a signed webhook and confirm that a run reaches `awaiting_approval` on an `outbound_message` tool and completes after approval in the Inbox.
- [ ] 11.1a On the same stack, publish a message to the CRM `queue` trigger's queue and confirm that a run is created. Then restart the `rabbitmq` container while a second run is `queued`, and confirm that it runs exactly once afterwards.
- [ ] 11.1b Scale the node to two workers and confirm that an hourly schedule fires once and that each enqueued run executes on exactly one worker.
- [x] 11.2 Run `uv run pytest tests/core/render/test_base.py::test_each_shipped_template_renders` and verify that it passes.
- [x] 11.3 Run `uv run nox -s formatting` and verify that it leaves no diff on a second run.
- [x] 11.4 Run `uv run nox -s checks` and verify that it passes.
- [x] 11.5 Run `uv run nox -s tests` and verify that it passes.

## Workflow follow-up

- Run `/opsx:verify` against this change, then `/opsx:archive` to promote the eight capability specs into `openspec/specs/`.
