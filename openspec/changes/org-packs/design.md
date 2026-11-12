# Design

## Context

See proposal.md for the motivation and the monetization analysis. This design builds on two other changes:

- **`claude-agents-and-org-operations`**: the org is a tree of units with five governance models. Agents, units, triggers,
  knowledge types, parameters and env vars are all typed spec models with cross-reference validation in `Spec`.
- **`test-architecture`**: a harness that renders an org, boots it on a target, and replays or calls the model.

## Goals / Non-Goals

**Goals:**

- A pack drops into any org without editing the pack, and the org stays valid by construction.
- One validation path. A pack is validated by the same models as a hand-written spec.

**Non-Goals:**

- Sandboxing pack code. A pack's custom tools run with the org's permissions, the same as a user's own tools. Trust comes
  from the tier, the licence and review, plus the autonomy and governance policy that still gates every tool call.

## Decisions

### D1. Python distributions with entry points, not a custom registry format

Packs contain Python (custom tools), so Python packaging already supplies the essentials:

- versioning and dependency resolution;
- hosting on PyPI;
- provenance through trusted publishing.

The `agentorg.packs` entry point returns a `Pack` model.

- *Alternative*: git repositories with a YAML manifest. Rejected because tools would need a second install mechanism and
  there would be no dependency resolution.
- *Alternative*: an agentorg-hosted registry server. Rejected for now because it is operational cost before there is
  demand; the JSON index suffices.

### D2. Reference, don't copy

The spec stores `PackRef(id, version, mount_into, overrides, license_accepted)`. At load time `Spec` resolves each
reference through the entry point, namespaces its ids, applies the overrides, and merges the result into the in-memory
tree before cross-reference validation. The renderer adds the pinned distribution to the rendered `pyproject.toml`.

- *Why*: upgrades become one-line diffs, and catalog fixes reach every org.
- *Trade-off*: the org depends on the distribution being installable. `eject` is the escape hatch, and the
  version pin protects reproducibility.

### D3. Namespacing at mount time

Ids become `<pack_id>.<local_id>`, and pack internals reference local ids. Shared names merge as follows:
- knowledge types and parameters merge by exact name; equal definitions are deduplicated and different ones are a
  conflict;
- env vars merge by name.

The dot is reserved: user-defined ids cannot contain it, so packs can never collide with user ids.

### D4. Closed overrides

The override keys (see the `pack-installation` spec) are the parameters users actually tune: tone and instructions, cost
through the model tier, safety through autonomy, scale through replicas, and timing through triggers. Structural edits
would invalidate the pack's evals, so they require `eject`, which makes the user the owner.

### D5. The catalog as a static index plus a CI repository

`agentorg-catalog` holds `packs/<id>.toml` submissions. Each submission names the distribution and the versions to list.

CI does the following:
1. installs each listed version;
2. validates it against the minimal org;
3. runs `agentorg pack verify --model-mode live` with a per-pack budget of $2;
4. writes the results into `index.json`;
5. publishes `index.json` with GitHub Pages.

Re-verification runs weekly, so model drift shows up as failures.

### D6. Business sequencing

The order is chosen to maximise adoption before monetizing, and to monetize what cannot be copied:

1. **Now (this change)**: the pack format, the catalog and three seed packs, all `community` or `verified`. Adoption grows
   through "start from a working support desk".
2. **Next**: a hosted cloud with one-click deployment of a spec, managed RabbitMQ, control plane and database, a
   cross-org approvals inbox, and usage-based pricing on runs. The customer brings their own Anthropic key, so there is
   no reselling of tokens.
3. **Then**:
   - `commercial` packs: vertical units with maintained integrations and SLAs, sold through the cloud with revenue share
     for third-party authors;
   - enterprise add-ons: SSO, RBAC, audit export, and compliance governance presets.

The cloud is the primary revenue line because the runtime now legitimately needs four services, a burden users will pay to
remove. Packs make the cloud stickier (verified updates flow to managed orgs) and give third parties a reason to build on
agentorg.

## Risks / Trade-offs

- [A malicious or low-quality community pack] → Tiers are visible, and commercial packs need licence acknowledgement.
  Every pack tool is still subject to autonomy and governance, and there is the review in catalog submission. True
  sandboxing is deferred.
- [Live eval cost in catalog CI grows with the number of packs] → $2 per pack per run, weekly cadence, and replay mode for
  PR checks on submissions.
- [Dependency conflicts between packs] → uv resolution fails at `pack add` with the conflicting requirement, so nothing
  silently breaks at runtime.
- [The business model depends on AgentField's licence for a hosted control plane] → Confirm before starting the cloud
  initiative. This does not affect this change.

## Migration Plan

1. Land `core/spec/_packs.py` and reference resolution in `Spec`, the mount, namespacing and overrides.
2. Land the CLI commands and the master tools.
3. Land `pack verify` on the e2e harness.
4. Create `agentorg-catalog` with CI and the three seed packs extracted from the e2e archetypes.

## Open Questions

- Whether commercial pack authors are paid through the cloud only, or also through direct licences. This does not affect
  this change.
