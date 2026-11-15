# CLAUDE.md

Context for Claude Code working on the `agentorg` library.

## Introduction

A metaagent library that produces a runnable multi-agent organisation from a single Python `spec.py`. End-state vision:

1. The user runs the `agentorg` master agent.
2. It interviews them across five stages to fill in the spec: org metadata, budget and lifecycle, infra, the unit tree of
   Claude agents with their triggers, knowledge and governance, and the dashboard UI.
3. The interview output is written to `spec.py`.
4. `agentorg render <spec.py>` materialises a complete project: an `AgentField` agent node (FastAPI) running the operations
   runtime, a React/Vite dashboard, docs, and (for docker packaging) a compose file wiring node + control plane + db +
   RabbitMQ + ui.

`agentorg` is not a single product. It's a factory for org-shaped products, and the master agent is the front door.

## Architecture

The layers live under `src/agentorg/core/`:

- **`spec/`** — the Pydantic models a user constructs in `spec.py`. `Spec` is six domain models: `org`, `runtime`, `ai`,
  `operations`, `knowledge`, `ui`. `ai` holds typed `Agent` definitions (persona, Claude model tier, autonomy, built-in
  tools, custom tool functions, MCP servers, skills, limits, output) and a tree of `Unit`s, each governed by one of five
  models: `solo`, `pipeline`, `hub`, `pool`, `council`. `operations` holds triggers, run policy, governance, budget,
  notifications and lifecycle.
- **`render/`** — `render(spec_path, output_dir)` loads the user's `spec.py` and materialises the project tree under
  `render/templates/` against it (Jinja). Writes are idempotent — unchanged files are not touched, so the live preview's
  Vite watcher doesn't fire on no-op rerenders.
- **`adapters/claude/`** — maps an `Agent` onto Claude Agent SDK options (prompt, tools, MCP servers, skills, limits) and
  registers agents and units as tagged AgentField reasoners. agentorg runs agents only on the Claude Agent SDK.
- **`operations/`** — the runtime every rendered org starts with `start_operations`: the run store (org database), the
  RabbitMQ broker (queued runs, retries, dead letters, events), the dispatcher, the agent runner, the unit engines,
  communication tools (delegate, handoff, publish, escalate), the scheduler, webhooks, external queue consumers,
  approvals, lifecycle and notifications. Every tool call goes through `_policy.decide`.
- **`agents/tools/`** — the knowledge, parameter and setup tools agents call, declared with `@tool(side_effect)`.

The rendered runtime delegates identity, memory and audit to `AgentField`:

- One `AgentField.agent` node per org: agents register as reasoners tagged `agent`, units as `unit` plus their model,
  all with the org slug.
- Knowledge → `app.memory.global_scope`; per-user state → `app.memory.actor(user_id)`.
- DID/VC identity + execution-DAG audit are automatic when a control plane is present.

Two services are required next to the node: the AgentField control plane (`agentfield/control-plane:latest`) for
memory/audit/policies, and RabbitMQ at `AMQP_URL`. `ANTHROPIC_API_KEY` is always required. The docker-compose template
wires all of them in. In preview mode the node runs without a broker and with a local sqlite store.

## Master agent

The master agent is one Claude agent per stage, each with only its stage's tools served as an in-process MCP server and no
built-in tools:

1. **Discover** — what the group does, who it serves, principles. Tools: `record_discovery_summary`, principle tools, advance.
2. **Configure** — identity, budget, lifecycle, approvers, infra. Tools: `set_org_identity`, `set_budget`, `set_lifecycle`,
   `set_approvers`, `set_runtime_infra`, env vars, setup steps, advance.
3. **Build** — units, agents, custom tools/skills, triggers. Tools: `add_or_update_unit`, `set_pipeline_step`,
   `add_or_update_agent`, `emit_custom_tool` / `emit_custom_skill`, `add_or_update_trigger`, `sandbox_agent`, advance. The
   interview keeps agent and unit drafts and assembles them into the spec after every change. The crucial stage; the
   user smoke-tests in the live preview between commits.
4. **Refine** — knowledge types, parameters, governance, notifications, run policy, dashboard polish.
5. **Handoff** — finalize spec, run/deploy walkthrough. Terminal.

Cross-stage drift is impossible at the runtime layer: Discover's agent literally lacks `set_org_identity`. The stage transitions
via the agent's `advance_to_next_stage` tool on explicit user confirmation, or the user's `/next` command.

LibreChat is the one chat surface. `agentorg ui` starts a local LibreChat stack (`master/ui/librechat/compose.yaml`, needs
Docker) whose `AgentOrg` endpoint is the master server's OpenAI-compatible `/v1` (`ui/_chat.py`, model `agentorg`, with
`/stage`, `/next`, `/spec`, `/preview`, `/reset confirm`), and whose `Preview` endpoint is the preview node's chat API.
Rendered orgs ship LibreChat the same way, over `core/operations/_chat_api.py` + `_chat_org.py`, with operations
commands such as `/approve` and `/status`; their dashboard is the operations console and has no chat.

The master page hosts a **live preview iframe** of the rendered org. `ui/_preview.py` boots uvicorn + Vite as subprocesses on the
user's machine; every chat turn rewrites `spec.py` and uvicorn `--reload` picks it up. The React app polls `/api/v1/config` and
related endpoints on a 2s heartbeat so spec mutations propagate to the iframe without manual reload. In preview mode
(`AGENTORG_PREVIEW_MODE=true` on the rendered process), knowledge writes are no-ops, login is auto-completed, and the
parameter-setup modal is skipped.

## Development

Standard flow when working on this repo:

- `uv run nox -s formatting` — auto-format code and docstrings.
- `uv run nox -s checks` — run all checks (quality, types, security, deps).
- `uv run nox -s tests` — run the test suite.
- `uv run nox -s docs` — only when documentation or project dependencies changed.

When you touch the renderer's template tree under `src/agentorg/core/render/templates/{full,frontend,backend,ai}/`,
`tests/core/render/test_base.py::test_each_shipped_template_renders` is the cheap end-to-end check that each shipped template
still produces its signature files for a minimal spec. There is no longer a byte-identical fixture test — the renderer's output
is shaped by the spec at render time.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full task reference and commit message convention.

## Package discipline

Two conventions every package and its tests follow:

1. **Public vs private — decide by test-worthiness.** A name imported across modules within a package is either
   (a) public — no underscore, listed in the package's `__init__.__all__`, and deserves dedicated tests; or
   (b) private — leading underscore, not in `__init__`, internal plumbing not worth its own test.
   The decision is *should this be tested?*, not *is it tested right now*. If yes → keep public and add the test if it's
   missing. If no → underscore it.
2. **Tests import via the public surface; test file structure mirrors the source tree.** A test reaches
   `from agentorg.X import Y`, not `from agentorg.X._private import Y` — anything tests need is part of the public surface, by
   definition of rule 1. Underscored helpers (genuinely private internals) are still imported via the underscore path. And the
   test file layout maps 1:1 onto the source: `src/X/_engine.py` has its tests in `tests/X/test_engine.py`.

   One intentional exception: an internal module whose only export is a base class subclassed by other modules (e.g.
   `core/spec/_config.py::SpecModel`) is exercised transitively and doesn't need a dedicated test file. Such exceptions
   are declared in `[tool.agentorg.test-layout] exempt`; `nox -s checks -- layout` (`agentorg check-layout`) enforces
   the mirror for the library and for rendered projects.

## Module structure

Every `.py` file in `src/` and `tests/` follows this order, with no other shape mixed in:

1. **One-sentence module docstring** at the top (`"""Verb-phrase summary."""`). No paragraph; no multi-line essay.
2. **Imports**, with in-project imports written as relative imports (`from .X import Y` / `from ..X import Y`), not
   `from agentorg.X import Y`. The exception is test files, which sit outside the package and use absolute imports
   against the package's public surface.
3. **Module-level constants** (`UPPER_CASE`, no leading underscore) — but only when shared by 2+ call sites in the module.
   A constant used in one place gets inlined into that function or class. A leading underscore on an `UPPER_CASE`
   module-level value is a smell: the underscore signals "private", the uppercase signals "shared and stable" — those
   contradict. Mutable module-level cache state (e.g. `_STAGE_AGENTS = None` that gets reassigned) is a different beast
   and stays underscored.
4. **Functions / classes** — the actual code.

No block-comment dividers (`# ---- section ----`, `# ====`, `# ##`). If a module needs section markers, it's probably
doing too much — split it. The headers on `__init__.py` files re-exporting from multiple submodules are the natural
TOC; nothing else needs one.

## Code style

Match the codebase. Read a couple of nearby files before writing. Stop fighting the existing voice.

- **Module docstrings**: one short sentence, no period needed. `"""Organization metadata."""`. Not a paragraph.
- **Class docstrings**: one short sentence. Skip if the class name + fields are self-evident.
- **Function docstrings**: short summary line. Add an `Arguments:` / `Returns:` block only when the parameters / return value
  are non-obvious and the function is part of a public surface. Internal helpers and tool implementations usually need just
  the summary line — and often nothing at all.
- **No dash-as-separator in docstrings.** A docstring is one sentence. Don't write `"""Foo is X - bar is Y."""`; just write
  `"""Foo is X."""`. If the second clause matters, it belongs in test assertions / code, not the docstring.
- **No multi-paragraph comments explaining decisions.** If something genuinely needs explaining (a hidden invariant, a
  workaround for a specific bug, a constraint that would surprise the next reader), one terse line is enough. Don't write
  essays; don't include "why this matters" prose; don't include before/after examples in docstrings.
- **No "for future readers" annotations.** No `# This used to be X but now Y because Z`. No `# TODO: refactor`. The git blame
  and the PR are the audit trail.
- **No defensive try/except for scenarios that can't happen.** Trust internal code and framework guarantees. Validate at
  system boundaries (user input, external APIs); don't wrap every framework call in a guard.
- **Don't introduce abstractions a bug fix doesn't need.** Three similar lines is fine. A helper that's used once is noise.
- **Single-purpose functions, minimal nesting.** If a function is doing two things, split it; if a nested conditional is
  three levels deep, refactor.

When in doubt: look at `src/agentorg/core/spec/` and `src/agentorg/core/agents/tools/` for the target voice. New code that's
wordier than what's already there should be tightened before landing.
