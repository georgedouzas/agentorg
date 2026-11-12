# Tasks

## 1. Test layout check

- [x] 1.1 Add `agentorg.core.quality.find_layout_violations` and the `agentorg check-layout` command covering the mapping, AST detection of re-export-only inits, the default exemptions, `[tool.agentorg.test-layout] exempt` with a stale-entry check, the ambiguous-twin check, and orphan detection. Verify with `tests/core/quality/test_layout.py` and `tests/cli/test_check_layout.py` on temporary trees covering each scenario in `specs/quality/test-layout`.
- [x] 1.2 Add `exempt = ["src/agentorg/core/spec/_config.py"]` to `pyproject.toml` and wire `agentorg check-layout` into `nox -s checks` as the `layout` subcommand, also included in `all`. Verify that `uv run nox -s checks -- layout` passes on the current tree, or lists only the agno module that the operations change deletes.
- [x] 1.3 Move the rendered test templates to mirrored paths: `tests/test_routes.py` → `tests/app/test_routes.py` in full and backend, and map `test_factories` and `test_knowledge` to their source modules or fold them in. Declare each template's exemptions in its rendered `pyproject.toml` and add `layout` (running `agentorg check-layout`) to the rendered `noxfile.py`. Verify that `test_each_shipped_template_renders` passes and that `nox -s checks -- layout` passes inside a rendered minimal project.

## 2. Constitution and docs

- [x] 2.1 Amend the constitution's Tests & Gates no-network rule into the gated-suite and e2e-suite rules, extend the Project Profile with the ecosystem contract and the `e2e` session and targets, and bump the version to 1.1.0. Verify by reading the diff: the body has only MUST / MUST NOT rules and the profile names all three targets.
- [ ] 2.2 Add an "End-to-end tests" section to `CONTRIBUTING.md` covering targets, model modes, recording cassettes, and the artifacts location. Verify that the documented `nox -s e2e -- --target local-process --scenario master-golden-path` command runs as written once group 4 lands.

## 3. E2e harness

- [ ] 3.1 Add the `nox -s e2e` session, excluded from `tests`, with the `--target`, `--model-mode` and `--scenario` options. It checks for Docker and validates the target before provisioning. Verify that `nox -s tests` collects zero tests from `tests/e2e/`, and that `nox -s e2e -- --target bogus` fails before provisioning.
- [ ] 3.2 Implement `harness/mock_anthropic.py` with request canonicalisation and hashing, streaming and non-streaming replay, record-mode proxying, and a missing-recording error. Verify with self-tests in `tests/e2e/harness/` (run by `nox -s e2e -- --self-test`) covering hash stability and SSE replay.
- [ ] 3.3 Implement the `Target` protocol, `local_process.py` and the conftest teardown guarantee and artifact capture. Verify that a deliberately failing smoke scenario leaves `.e2e-artifacts/<run-id>/` populated and no running containers.
- [ ] 3.4 Implement `harness/client.py`, a typed client for the runs, approvals, inbox, lifecycle, hooks and chat stream endpoints, and the Playwright smoke helpers. Verify with the golden-path scenario in 4.1.

## 4. Scenarios

- [ ] 4.1 Add `test_master_golden_path.py`: a scripted interview, then the spec validates, renders, boots on the target and answers chat. Record its cassettes. Verify that it passes in `replay` × `local-process` twice with identical outputs.
- [ ] 4.2 Add `test_support_desk.py`: signed webhook, approval held, approved through both the API and the Inbox UI, run succeeded. Verify that it passes in `replay` × `local-process`.
- [ ] 4.3 Add `test_research_reporting.py`: a schedule fires via the clock offset, the `hub` lead delegates, a report knowledge unit is written, and an event triggers the summariser. Verify that it passes in `replay` × `local-process`.
- [ ] 4.4 Add `test_ops_monitoring.py` with a stub metrics MCP server, `custom.incident` publish, the responder run, and escalation to the inbox on forced failure. Verify that it passes in `replay` × `local-process`.
- [ ] 4.4a Add `test_credit_decisions.py`: a 3-member `council` returns a majority decision with all three answers recorded on the run, and a governed write is held for approval. Verify that it passes in `replay` × `local-process`.
- [ ] 4.5 Add `test_content_pipeline.py`: the review gate is held, rejected once with a comment, re-run, approved, and published through a stub CMS MCP. Verify that it passes in `replay` × `local-process`.

## 5. Additional targets

- [ ] 5.1 Implement `local_docker.py` on the rendered `compose.yaml`, with health waits on the node, broker and control plane. Verify that all scenarios pass in `replay` × `local-docker`.
- [ ] 5.2 Implement `cloud.py`: Railway API service plus the mock service, Vercel frontend, run-id naming, teardown and the orphan sweeper. Verify with a manual `workflow_dispatch` that the support-desk scenario passes in `replay` × `cloud` and that no `agentorg-e2e-*` projects remain afterwards.

## 6. CI

- [ ] 6.1 Add `.github/workflows/e2e.yml` with the D5 matrix, fork guards on secret-using jobs, and artifact upload on failure. Verify that a PR run shows only the replay jobs, and that a fork PR shows no secret-using jobs.

## 7. Integration verification

- [ ] 7.1 Run `uv run nox -s e2e -- --target local-docker --model-mode live --scenario support-desk` once and verify that it passes within its `max_usd`.
- [ ] 7.2 Run `uv run pytest tests/core/render/test_base.py::test_each_shipped_template_renders` and verify that it passes.
- [ ] 7.3 Run `uv run nox -s formatting` and verify that it leaves no diff on a second run.
- [ ] 7.4 Run `uv run nox -s checks` and verify that it passes, including `layout`.
- [ ] 7.5 Run `uv run nox -s tests` and verify that it passes.
