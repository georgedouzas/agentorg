# CLAUDE.md

Context for Claude Code working on the **agentorg** library itself (not on a generated org).

## What agentorg is

A **metaagent library** that produces a runnable multi-agent organisation from a single
spec file (`agentorg.json`). The end-state vision is:

1. A user runs the agentorg master agent.
2. The master agent **interviews the user** to determine: org name, mission, team
   composition, agent roles/scopes/workflows, state schema, deployment, env vars.
3. The interview output is written to `agentorg.json`.
4. `agentorg-render <agentorg.json>` materialises a complete project — backend (FastAPI +
   AgentOS), frontend (React/Vite), DB schema, Docker compose, docs, CI — ready to
   `docker compose up`.

So agentorg is *not* a single product: it's a **factory for org-shaped products**, and
the master agent is the front door.

## Layers

| Layer | Lives in | Status today | Source of truth |
| --- | --- | --- | --- |
| **Templates (fixed infra)** | `project/` | implemented | this repo |
| **Renderer** | `src/agentorg/render.py` | implemented (`agentorg-render` CLI) | this repo |
| **Spec** | `agentorg.json` per fixture | hand-written for fixtures | this repo |
| **Master agent** (interview → spec) | not yet built | future | future |
| **Generated org layer** (per-agent `.py`, per-workflow `.py`, org-specific tools, `CLAUDE.md` for the generated repo) | not yet templated | future — written by master agent | future |

The renderer covers the *infra* layer. Per-agent and per-workflow files are deliberately
NOT in `project/` — they belong to the master agent's output.

## Templating contract

`project/` is walked recursively. Each file is handled by suffix:

- **`*.jinja`** — rendered through Jinja2 with vars from `agentorg.json`. Suffix is
  stripped on output.
- **everything else** — copied verbatim (so frontend JSX `{{ ... }}` literals survive).

Path segments support `{% if ... %}name{% endif %}` for conditional generation
(e.g. `{% if org_visibility == 'public' %}LICENSE{% endif %}.jinja`). When the
condition is false the file is skipped.

The vars passed to Jinja are flattened from `agentorg.json` by `_extract_vars` —
key names are: `org_name`, `org_slug`, `package_name` (slug with `-`→`_`),
`org_repository`, `author_name`, `author_email`, `org_visibility`, `license_year`,
`api_deployment`, `frontend_deployment`, plus the nested `org`, `generated`,
`deployment`, `setup` objects.

## Fixtures

`tests/fixtures/<id>/` contains `agentorg.json` + `output/` (the rendered snapshot).
The test `tests/test_project_templates.py` renders each fixture and asserts every
file the renderer produces matches the snapshot byte-for-byte.

Files in `output/` that the renderer does NOT produce (per-agent `.py`, per-workflow
`.py`, org-specific tools, `uv.lock`, `node_modules/`, runtime `.env`) are out of
scope today and live alongside as placeholder content for end-to-end smoke testing.

To run a fixture locally see [tests/fixtures/README.md](tests/fixtures/README.md).

## Adding or changing a template

1. Edit (or add) the file under `project/`. Use the `.jinja` suffix if it contains any
   Jinja tags.
2. Re-render the fixtures:
   ```sh
   agentorg-render tests/fixtures/investment-team/agentorg.json --out tests/fixtures/investment-team/output
   agentorg-render tests/fixtures/eng-team/agentorg.json     --out tests/fixtures/eng-team/output
   ```
3. Run `pytest tests/test_project_templates.py` — both fixtures must stay byte-identical.
4. Commit `project/` + `tests/fixtures/*/output/` together.

If a change affects only one fixture, the spec (`agentorg.json`) is wrong, not the
template — fix the spec.

## What NOT to put in `project/`

- Per-agent or per-workflow `.py` files — those belong to the master agent.
- Org-specific business logic (e.g. portfolio providers, codebase tools) — same.
- A `CLAUDE.md` describing a particular generated org — same.
- Anything that would force a downstream `if org_slug == "investment-team"` switch.
