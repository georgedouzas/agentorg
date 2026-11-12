# Spec Delta

## Purpose

Makes packs discoverable and trustworthy. A public index lists packs with their tier and evaluation results, and an eval
mechanism backs the `verified` tier with evidence instead of a label.

## ADDED Requirements

### Requirement: The catalog is a JSON index at a configurable URL
agentorg SHALL read the pack catalog from `AGENTORG_PACK_INDEX`, defaulting to the agentorg catalog repository's
`index.json`. Each entry SHALL list:
- `id`, `name`, `description`, `kind`, `tags` and `tier`;
- the license;
- the distribution name and versions, with each version's `agentorg` range;
- the latest eval result, which is pass/fail, cost and date, per version.

#### Scenario: Private catalog
- **WHEN** `AGENTORG_PACK_INDEX` points to a company-internal URL
- **THEN** search and add use only that catalog

#### Scenario: Catalog unreachable
- **WHEN** the index cannot be fetched
- **THEN** `pack search` fails with a network error, and installed packs keep working

### Requirement: Search filters by need
`agentorg pack search [query] [--kind] [--tier] [--tag]` SHALL return the entries that are compatible with the running
agentorg version, ranked by text match. Each result SHALL show tier, kind and the latest eval status.

#### Scenario: Search support units
- **WHEN** a user runs `agentorg pack search support --kind unit --tier verified`
- **THEN** only verified unit packs matching "support" and compatible with the running version are listed

### Requirement: Packs ship evaluation cases
A pack SHALL declare at least one eval case. Each case has:
- a target id;
- an input;
- assertions, each one of: output contains, output matches a JSON schema, tool called, tool not called, run status, or
  cost at most a given USD amount.

#### Scenario: Pack without evals rejected from the catalog
- **WHEN** a pack with no eval cases is submitted to the catalog
- **THEN** catalog CI rejects it

### Requirement: Verification runs evals on the real harness
`agentorg pack verify <id> [--model-mode replay|live]` SHALL mount the pack into a minimal generated org. It SHALL run every
eval case through the e2e harness on the `local-process` target, and report each assertion with total cost. Any failed
assertion SHALL make the command exit non-zero.

#### Scenario: Local verification
- **WHEN** a pack author runs `agentorg pack verify support-desk --model-mode live`
- **THEN** each eval case runs against the pack's agents on the real harness, and a pass/fail table with costs is printed

### Requirement: The verified tier is earned per version
A version SHALL be listed as `verified` only when the catalog CI has passed its evals in `live` mode for that exact
version. A verified pack whose latest version fails SHALL keep its last verified version marked, and SHALL show the failure.

#### Scenario: Regression on new release
- **WHEN** version 1.3.0 of a verified pack fails its live evals in catalog CI
- **THEN** the index marks 1.3.0 as failed, keeps 1.2.0 as verified, and `pack add` without a version resolves to 1.2.0
