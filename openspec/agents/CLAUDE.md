# CLAUDE.md

Context for Claude Code working on the `agentorg` library.

## Introduction

A metaagent library that produces a runnable multi-agent organisation from a single Python `spec.py`. End-state vision:

1. The user runs the `agentorg` master agent.
2. It interviews them across five stages to fill in the spec: org metadata + budget, infra, agents/teams/workflows, knowledge,
   and the dashboard UI.
3. The interview output is written to `spec.py`.
4. `agentorg render <spec.py>` materialises a complete project: an `AgentField` agent node (FastAPI), a React/Vite dashboard,
   docs, and (for docker packaging) a compose file wiring node + control plane + db + ui.

`agentorg` is not a single product. It's a factory for org-shaped products, and the master agent is the front door.

## Architecture

Three clean layers, each in its own module under `src/agentorg/core/`:

- **`spec/`** — the Pydantic models a user constructs in `spec.py`. `Spec` is five domain models: `org`, `runtime`, `ai`,
  `knowledge`, `ui`. Each lives in a `_*.py` module under `spec/`. Agents, teams, and workflows in `ai` are "anything runnable"
  (plain async callable, or an object with `.arun()` — agno objects fit cleanly but agentorg never imports agno).
- **`render/`** — `render(spec_path, output_dir)` loads the user's `spec.py` and materialises the project tree under
  `render/template/` against it (Jinja). Writes are idempotent — unchanged files are not touched, so the live preview's Vite
  watcher doesn't fire on no-op rerenders.
- **`tools/`** — runtime helpers shipped to every rendered org: `runtime.py` (`register_runnable` adapts a runnable into an
  `AgentField` reasoner with tags), `knowledge.py` / `state.py` (async tools over `app.memory`), `setup.py`, and the platform
  agents' tool modules under `tools/platform/`.

The rendered runtime delegates infrastructure to `AgentField`:

- One `AgentField.agent` node per org: agents/teams/workflows register as reasoners.
- Knowledge → `app.memory.global_scope`; per-user state → `app.memory.actor(user_id)`.
- DID/VC identity + execution-DAG audit are automatic when a control plane is present.
- Operator-managed policies on the control plane target reasoners by tag (`agent`/`platform`/`team`/`workflow` + the node-level
  org slug).

The control plane (`agentfield/control-plane:latest`, a Docker image) is required for memory/audit/policies. The rendered node
boots standalone, but memory-backed endpoints fail without one — the docker-compose template wires the control plane in.

## Master agent

The master agent is itself an agno-style workflow of per-stage agents, each with a narrow tool slice:

1. **Discover** — what the group does, who it serves, principles. Tools: `record_discovery_summary`, principle tools, advance.
2. **Configure** — identity, budget, infra. Tools: `set_org_identity`, `set_runtime_infra`, env vars, setup steps, advance.
3. **Build** — agents, teams, workflows, custom tools/skills. Tools: agent/team/workflow patches, `emit_custom_tool` /
   `emit_custom_skill`, `sandbox_agent`, advance. The crucial stage; user smoke-tests in the live preview between commits.
4. **Refine** — knowledge types, parameters, dashboard polish. Tools: knowledge types, parameters, UI tweaks, advance.
5. **Handoff** — finalize spec, run/deploy walkthrough. Terminal.

Cross-stage drift is impossible at the runtime layer: Discover's agent literally lacks `set_org_identity`. The stage transitions
via the agent's `advance_to_next_stage` tool on explicit user confirmation — there is no Next button.

The master UI hosts a **live preview iframe** of the rendered org. `ui/_preview.py` boots uvicorn + Vite as subprocesses on the
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
   `core/spec/_config.py::SpecModel`) is exercised transitively and doesn't need a dedicated test file.

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
