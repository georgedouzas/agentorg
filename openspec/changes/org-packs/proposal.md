# Proposal

## Why

agentorg needs a sustainable business model that does not cripple the open-source core. The options considered:

| Model | Revenue potential | Fit for agentorg | Verdict |
|---|---|---|---|
| Hosted cloud (managed node, control plane, RabbitMQ, DB, approvals inbox; usage-based) | High, recurring | Strong. The runtime now needs four services, which is real operational pain to remove | **Primary revenue**, a separate initiative |
| Packs: plug-and-play agents, units and whole orgs; community, verified and commercial tiers | Low to medium alone | Strong. Packs map 1:1 onto units, so they drop into any org | **Adoption engine and secondary revenue**, this change |
| Enterprise add-ons (SSO, RBAC, audit export, compliance policy packs, support) | High per deal | Later. Needs adoption first | Later |
| Services (custom org builds) | Immediate, does not scale | Useful to seed verified packs | Opportunistic |

Code is copyable; what people pay for is outcomes that keep working. The value of a pack is that it is evaluated,
maintained against changing APIs and models, and supported. That is also the value of a hosted cloud. Packs come first
because they grow adoption and they give the cloud something to sell: one-click install of verified packs into a managed
org. Without a pack format, every org starts from zero and nothing is reusable across orgs.

## What Changes

- **A pack is a pip-installable Python distribution.** It registers one pack under the `agentorg.packs` entry point. The
  pack declares:
  - its kind: `agent`, `unit` or `org`;
  - its agents and units, custom tools, skills and MCP servers;
  - the knowledge types, parameters and env vars it requires;
  - trigger templates;
  - eval cases;
  - an SPDX license and a tier: `community`, `verified` or `commercial`.
- **`spec.py` references packs by name and pinned version** (`PackRef`). It does not copy their content, so upgrades are
  one command. A pack is mounted as a member of a chosen unit, with ids namespaced under the pack id.
- **Closed customisation through `overrides`**: persona instructions, model tier, autonomy (tightening only), replicas,
  parameters and trigger enablement. Anything else requires `pack eject`, which copies the pack into the spec and drops
  the reference.
- **CLI**: `agentorg pack search|add|upgrade|remove|eject|verify`.
- **Master Build-stage tools**: `search_packs`, `add_pack`, `remove_pack`.
- **A catalog**: a JSON index at a configurable URL (default: the agentorg catalog repository), listing name, kind, tags,
  tier, versions, agentorg compatibility and the latest eval result.
- **Verification**: every pack ships eval cases. `agentorg pack verify` runs them with the e2e harness in replay or live
  mode. The `verified` tier means the catalog CI passes the pack's evals in live mode for each listed version.

### Out of scope

- The hosted cloud product, billing and payments.
- Licence entitlement enforcement for `commercial` packs. The catalog shows the tier and licence, and installing requires
  an explicit licence acknowledgement; enforcement belongs to the cloud.
- A web storefront. The catalog is a JSON index plus a generated docs page.
- Publishing tooling beyond standard Python packaging (`uv build` plus PyPI trusted publishing).

## Capabilities

### New Capabilities

- `packs/pack-format`: what a pack is, its manifest fields, kinds, tiers and compatibility rules.
- `packs/pack-installation`: adding, upgrading, overriding, ejecting and removing packs in an org spec, through the CLI and
  the master agent.
- `packs/pack-catalog`: discovery through the catalog index, and the verification that backs the `verified` tier.

### Modified Capabilities

None. No baseline specs exist.

## Impact

- **Code**:
  - New: `core/spec/_packs.py` with `PackRef` and `Pack`;
  - New: a `core/packs/` package for loading, mounting, the catalog client and verification;
  - New: `cli/_pack.py`;
  - Modified: the master Build-stage tools and the writer, the renderer (installed packs become dependencies of the
    rendered `pyproject.toml`), and the render of pack env vars into the setup checklist.
- **Dependencies**: none new. Packs install through `uv`, and the catalog is fetched with `httpx`.
- **New repository**: `agentorg-catalog`, holding `index.json`, the CI that runs the evals of submitted packs, and three
  seed packs. The seed packs are a support-desk pool unit, a research hub unit and a content pipeline unit.
- **Ordering**: depends on `claude-agents-and-org-operations` (units and agent definitions) and on `test-architecture`
  (the e2e harness used by `pack verify`).
