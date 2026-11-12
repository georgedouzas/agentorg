# Tasks

## 1. Pack model and resolution

- [ ] 1.1 Create `core/spec/_packs.py` with `Pack`, `PackRef`, `PackRequires`, `EvalCase`, `Assertion` and the `PackKind`/`PackTier` literals, exported from `core/spec/__init__.py`. Verify with `tests/core/spec/test_packs.py` covering manifest validation, the secret-literal rejection and the closed override keys.
- [ ] 1.2 Create `core/packs/_loader.py`, which loads a pack by id from the `agentorg.packs` entry points, checks the agentorg version range, and rejects distributions with zero or several entries. Verify with `tests/core/packs/test_loader.py` using a fixture distribution installed into a temporary venv.
- [ ] 1.3 Create `core/packs/_mount.py` for namespacing, merging knowledge types, parameters and env vars with conflict detection, applying overrides (tightening-only autonomy), disabling trigger templates by default, and recording licence acknowledgement. Verify with `tests/core/packs/test_mount.py` covering every scenario in `specs/packs/pack-installation` that does not involve the CLI.
- [ ] 1.4 Resolve `PackRef`s in `Spec` before cross-reference validation, and reserve `.` in user ids. Verify with `tests/core/spec/test_base.py` cases: a spec with a mounted pack validates, and a span violation from a mount fails.

## 2. CLI and master

- [ ] 2.1 Create `cli/_pack.py` with `search`, `add`, `upgrade`, `remove`, `eject` and `verify`, using uv for install, failing safe with the spec unchanged on any error, and requiring `--accept-license` for `commercial` packs. Verify with `tests/cli/test_pack.py` covering add into a hub, span-limit failure, clean and failing upgrade, eject and referenced removal.
- [ ] 2.2 Add the `search_packs`, `add_pack` and `remove_pack` tools to the master Build-stage slice, and teach `master/_writer.py` to emit `PackRef`s. Verify with `tests/master/test_tools.py`, which checks that the tools return errors as text and that Discover lacks them, and with `tests/master/test_writer.py`, which checks the `PackRef` round-trip.
- [ ] 2.3 Render the pinned pack distributions into the rendered `pyproject.toml`, and the pack env vars into the setup checklist. Verify that `test_each_shipped_template_renders` passes, plus a render test for a spec with one pack.

## 3. Catalog and verification

- [ ] 3.1 Create `core/packs/_catalog.py`, which fetches `AGENTORG_PACK_INDEX`, filters by compatibility, kind, tier and tag, ranks by text, and resolves the default version to the latest verified one. Verify with `tests/core/packs/test_catalog.py` against a locally served index fixture.
- [ ] 3.2 Create `core/packs/_verify.py`, which mounts the pack into a minimal org, runs the eval cases through the e2e harness on `local-process`, evaluates the assertions, and prints a pass/fail and cost table. Verify with `tests/core/packs/test_verify.py` in replay mode using the fixture pack and recorded cassettes.
- [ ] 3.3 Document pack authoring, from manifest to evals, `verify`, publishing and catalog submission, in `docs/packs.md`, and link it from `properdocs.yml`. Verify that `nox -s docs -- build` succeeds and that the documented `agentorg pack verify` command runs against the fixture pack.

## 4. Catalog repository and seed packs

- [ ] 4.1 Create the `agentorg-catalog` repository with `packs/*.toml` submissions, CI (install, validate, live verify at $2 per pack, write `index.json`, publish to Pages), weekly re-verification, and replay-mode PR checks. Verify that a test submission appears in the published `index.json` with its eval result.
- [ ] 4.2 Extract the support-desk, research and content-pipeline e2e archetypes into three seed packs with eval cases. Publish them and submit them to the catalog. Verify that `agentorg pack search` lists all three as `verified`, and that `agentorg pack add support-desk --into root` boots in an e2e `local-process` run.

## 5. Integration verification

- [ ] 5.1 Run `uv run pytest tests/core/render/test_base.py::test_each_shipped_template_renders` and verify that it passes.
- [ ] 5.2 Run `uv run nox -s formatting` and verify that it leaves no diff on a second run.
- [ ] 5.3 Run `uv run nox -s checks` and verify that it passes, including `layout`.
- [ ] 5.4 Run `uv run nox -s tests` and verify that it passes.
