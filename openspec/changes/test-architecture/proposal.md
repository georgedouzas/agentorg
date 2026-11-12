# Proposal

## Why

The test tree mostly mirrors `src/` already, but nothing enforces it. The rendered projects break the rule: their
`tests/test_routes.py` tests `app/routes.py`.

More importantly, no test proves that a generated org actually runs. Current tests stop at "the template renders". The
product's promise is "describe an org, get a running org", so it must be tested end to end:

- render;
- install;
- boot locally, under docker and in the cloud;
- drive real work through triggers, approvals and the dashboard;
- tear down.

The constitution forbids tests that reach the network, so this tier needs an explicit, separate home.

## What Changes

- **A test-layout check in the merge gate.** Every source module maps to exactly one test file at the mirrored path, and
  every unit test file maps to a source module. Exemptions are declared, not implicit.
- **The same rule for rendered projects.** The rendered templates move their tests to mirrored paths, and the rendered
  project's own gate runs the same check.
- **A new end-to-end suite** under `tests/e2e/`. It is excluded from the mirror rule and from the `tests` merge gate, and it
  runs through a new `nox -s e2e` session with one of these targets:
  - `local-process`: the rendered org runs as plain processes, with RabbitMQ and the control plane in containers;
  - `local-docker`: the rendered `compose.yaml`;
  - `cloud`: Railway for the API and Vercel for the frontend, in an ephemeral project torn down afterwards.
- **Two model modes for e2e:**
  - `replay`, the default: a local mock of the Anthropic Messages API serves recorded responses. It is deterministic,
    free and makes no model calls.
  - `live`: the real API with a hard USD cap per scenario.

  A `record` mode refreshes the replay recordings.
- **E2e scenarios** are the archetype specs from `claude-agents-and-org-operations` plus a master-interview golden path. The
  golden path scripts an interview, writes `spec.py`, renders it and boots it.
- **CI:**
  - `replay` × `local-process` runs on every PR;
  - `replay` × `local-docker` runs on every PR touching `render/` or `core/operations/`;
  - `live` × `local-docker` and `replay` × `cloud` run nightly and on manual dispatch, using repository secrets.
- **Constitution amendment**: the no-network rule applies to the gated suite. End-to-end tests live in their own suite
  outside the merge gate. The Project Profile names the e2e session and targets.

### Out of scope

- Load and soak testing (thousands of concurrent runs), which belongs to a later performance change.
- Visual regression testing of the dashboard. E2e UI checks are functional (Playwright smoke), not pixel diffs.
- Cloud targets other than Railway and Vercel. The target interface allows adding them later.
- Running `live` mode on PRs, because of cost and secret exposure to forks.

## Capabilities

### New Capabilities

- `quality/test-layout`: the mirror rule between source and tests, its exemptions, and its enforcement in the library and
  rendered projects.
- `quality/e2e-testing`: the end-to-end suite: targets, model modes, scenarios, lifecycle (provision, exercise, tear
  down), artifacts and CI cadence.

### Modified Capabilities

None. No baseline specs exist.

## Impact

- **Code**:
  - New: `agentorg.core.quality` and the `agentorg check-layout` command, wired into `nox -s checks`;
  - New: `tests/e2e/`, holding the harness, targets, mock API and scenarios;
  - New: the `nox -s e2e` session;
  - `noxfile.py.jinja` in the full and backend templates;
  - Moved: the rendered test templates (`tests/test_routes.py` → `tests/app/test_routes.py`, and similar).
- **Dependencies (dev)**: `playwright` (UI smoke), `testcontainers[rabbitmq]` (shared with the operations change), and the
  Railway CLI and Vercel CLI in the cloud CI job only.
- **CI**: a new `e2e.yml` workflow (PR plus nightly plus `workflow_dispatch`), and secrets `ANTHROPIC_API_KEY`,
  `RAILWAY_TOKEN` and `VERCEL_TOKEN`.
- **Docs**: the constitution's Tests & Gates rule and its Project Profile; `CONTRIBUTING.md` gains an e2e section.
- **Ordering**:
  - The layout check can land immediately.
  - The e2e scenarios exercise the runtime introduced by `claude-agents-and-org-operations`. Each scenario lands with or
    after the capability it exercises.
