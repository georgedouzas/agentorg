# Design

## Context

See proposal.md for the motivation. These constraints shape the approach:

- **The constitution**: Tests & Gates requires the mirror layout and forbids network access in tests. Its Project Profile
  is the place for repo-specific instantiation.
- **Generated orgs depend on:**
  - the AgentField control plane, a container image;
  - RabbitMQ, which `claude-agents-and-org-operations` makes mandatory;
  - a database;
  - the Claude Agent SDK, which spawns the Claude Code CLI and honours `ANTHROPIC_BASE_URL`.
- **Deploy surfaces** come from `runtime.infra`: `packaging` (`none`/`docker`), `api` (`railway`) and `frontend`
  (`vercel`).

## Goals / Non-Goals

**Goals:**

- A PR-time e2e run that is deterministic and costs nothing in model spend.
- One harness shared by all targets. A scenario never contains target-specific code.

**Non-Goals:**

- Testing AgentField or RabbitMQ themselves. They are assumed correct, and the suite tests agentorg's use of them.

## Decisions

### D1. The layout check is a library command, not a pytest test

`agentorg.core.quality.find_layout_violations(project_root)` returns the violations, and `agentorg check-layout` prints
them and exits non-zero. `nox -s checks -- layout` runs the command. Rendered projects already depend on `agentorg`, so
they run the same command, and the check exists in exactly one place.

- *Why not a copied script*: the constitution forbids keeping the same logic in two places, and a copy in the templates
  would drift.

- *Why not a pytest test*: a meta-test would itself violate the mirror rule, and it would run inside the suite it polices.
- *Mapping*: strip leading underscores from the module name, then `tests/<rel dir>/test_<name>.py`. An `__init__.py`
  with logic maps to `tests/<rel dir>/test_init.py`. Re-export-only `__init__.py` files are detected by AST: they contain
  only a docstring, imports, `__all__` and `TypeAlias` declarations.
- *Template sources*: directories whose names are not Python identifiers, such as `{{ org.package_name }}`, are not
  importable and are skipped. This covers the render templates without naming them.
- *Roots*: `[tool.agentorg.test-layout] roots` maps source directories to tests directories, and defaults to
  `src/<package>` → `tests`.

### D2. E2e harness layout

```
tests/e2e/
  conftest.py          # --target / --model-mode / --scenario options, artifact dir, teardown guarantee
  harness/
    targets.py         # Target protocol: provision(project) -> Endpoints; health(); teardown()
    local_process.py
    local_docker.py
    cloud.py           # railway + vercel via their CLIs; name = f"agentorg-e2e-{run_id}"
    mock_anthropic.py  # ASGI app: POST /v1/messages (streaming + non-streaming), cassette store
    client.py          # typed client over the org's public HTTP API
  scenarios/
    test_support_desk.py
    test_research_reporting.py
    test_ops_monitoring.py
    test_content_pipeline.py
    test_credit_decisions.py
    test_master_golden_path.py
  cassettes/<scenario>/<hash>.json
```

`harness/` is test support code inside `tests/e2e/`, which is why `tests/e2e/` is exempt from the mirror rule.

### D3. The mock Messages API

- **Matching**: the request hash is SHA-256 over the canonical JSON of `model`, `system`, `messages`, the `tools` names and
  schemas, and `max_tokens`. Volatile fields are stripped: timestamps in prompts are replaced via the harness clock, and
  temp paths are normalised.
- **Streaming**: SSE replays the recorded event sequence.
- **Record mode**: the mock acts as a proxy to `api.anthropic.com` and writes cassettes.
- **Wiring**: the mock runs as a local process for `local-*` targets. For `cloud`, `replay` mode is served by deploying the
  mock alongside as a second Railway service. Recordings are therefore shared across targets.

- *Alternative*: stubbing at the SDK level. Rejected because it would skip the real harness, which is the point of e2e.
- *Alternative*: `live`-only e2e. Rejected because of cost, flakiness and secrets on every PR.

### D4. Deterministic time and external systems

- **Time**: scenarios that depend on schedules start the node with `AGENTORG_CLOCK_OFFSET`, a test-only env var honoured
  by `_scheduler`, or trigger the schedule through an admin endpoint that exists only in preview and e2e builds.
- **External systems**:
  - webhooks are sent by the harness;
  - external AMQP queues are the broker the target already runs;
  - MCP servers are small local stub servers shipped in `tests/e2e/harness/`.

### D5. CI workflow `e2e.yml`

| Trigger | Matrix |
|---|---|
| `pull_request` | `replay` × `local-process` (all scenarios) |
| `pull_request`, paths `src/agentorg/core/render/**`, `src/agentorg/core/operations/**` | plus `replay` × `local-docker` |
| `schedule` (nightly), `workflow_dispatch` | `live` × `local-docker` (`max_usd` 1.0 per scenario) and `replay` × `cloud` |

Secrets are referenced only in jobs guarded by `github.event.pull_request.head.repo.fork == false` or by non-PR triggers.
Artifacts are uploaded with `if: failure()`.

### D6. Constitution amendment

The Tests & Gates rule becomes two rules:
- A test in the gated suite MUST NOT reach the network.
- End-to-end tests MUST live in a separate suite outside the merge gate, and MUST tear down everything they provision.

The Project Profile gains:
- the `e2e` session and its targets;
- the ecosystem contract: the AgentField node plus the Claude Agent SDK.

The constitution version is bumped to 1.1.0.

## Risks / Trade-offs

- [Cassette drift: any prompt change invalidates recordings] → Hashes are per request, so only changed requests need
  re-recording. `record` mode can be run per scenario, and the failure message names the scenario.
- [Cloud e2e is slow, around 10 minutes, and can leak resources] → It runs nightly only, with a teardown guarantee and an
  orphan sweeper by name prefix.
- [The Railway and Vercel CLIs change] → They are isolated in `cloud.py`, and a nightly failure surfaces drift quickly.
- [Docker is needed for `local-process` because the broker and control plane are containers] → `nox -s e2e` checks for
  Docker first and fails with a clear message.

## Migration Plan

1. Land the layout check with the current tree. The only expected exemption is `core/spec/_config.py`; the agno
   `_master.py` is deleted by the operations change.
2. Move the rendered test templates to mirrored paths and add the check to the rendered noxfile.
3. Land the harness, the mock and the `local-process` target with the golden-path scenario.
4. Add the archetype scenarios as the operations change lands each runtime piece. Then add `local-docker`, then `cloud`.
