# Spec Delta

## Purpose

Defines a pack: a versioned, installable bundle of agents, units or a whole org that drops into any agentorg org. Packs are
reusable and shareable, and they are what the project's monetization builds on.

## ADDED Requirements

### Requirement: A pack is an installable distribution with one entry point
A pack SHALL be a Python distribution. It SHALL register exactly one object in the `agentorg.packs` entry-point group.
Loading the entry point SHALL yield a valid pack definition. A distribution with zero or several entries SHALL be rejected.

#### Scenario: Load installed pack
- **WHEN** a distribution `agentorg-pack-support-desk` is installed and registers entry point `support-desk`
- **THEN** agentorg can load the pack by the name `support-desk`

### Requirement: Pack manifest fields
A pack SHALL declare identity and compatibility fields:
- `id` (kebab-case), `name`, `version` (SemVer) and `description`;
- `agentorg`: the compatible version range;
- `kind`: `agent`, `unit` or `org`;
- `license` (SPDX) and `tier`: `community`, `verified` or `commercial`.

#### Scenario: Missing licence rejected
- **WHEN** a pack omits `license`
- **THEN** loading the pack fails naming the field

### Requirement: Pack content uses the org spec models
A pack SHALL declare its content with the same agentorg spec models as a hand-written org:
- `requires`: env vars, parameters and knowledge types;
- `provides`: agents and one root unit;
- custom tools, skills, MCP servers and trigger templates;
- eval cases.

#### Scenario: Invalid pack rejected
- **WHEN** a pack's provided unit violates an org-structure rule, such as a hub with 15 members
- **THEN** loading the pack fails with the same validation error a spec would get

### Requirement: Pack kinds define where a pack can be mounted
The pack's kind SHALL determine where it can go:
- an `agent` pack provides a single agent;
- a `unit` pack provides a unit and is mounted as a member of an existing unit;
- an `org` pack provides a full root unit, plus operations defaults, and can only start a new org.

#### Scenario: Org pack as starting point
- **WHEN** a user starts a new org from org pack `agency-starter`
- **THEN** the new spec's root is the pack's root unit, and the pack's operations defaults are applied

#### Scenario: Org pack not mountable
- **WHEN** a user tries to add an `org` pack into an existing unit
- **THEN** the command fails, suggesting that the user start a new org from the pack instead

### Requirement: Compatibility is checked before use
A pack whose `agentorg` range excludes the running agentorg version SHALL be refused, with a message naming both versions.

#### Scenario: Incompatible pack
- **WHEN** a pack declares `agentorg>=2,<3` and agentorg 1.4 is running
- **THEN** installation is refused

### Requirement: Packs never carry secrets
A pack SHALL reference credentials only by env var name in `requires`. A pack whose manifest contains a literal value for a
declared secret env var SHALL be rejected.

#### Scenario: Required env var surfaced
- **WHEN** a pack requires `ZENDESK_TOKEN`
- **THEN** after installation, `ZENDESK_TOKEN` appears in the org's required env vars and setup checklist
