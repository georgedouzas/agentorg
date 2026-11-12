# Spec Delta

## Purpose

Lets users plug packs into an org, keep them upgradable, adjust them within safe bounds, and take full ownership when they
need to. This works through the CLI and through the master agent's interview.

## ADDED Requirements

### Requirement: Adding a pack mounts it by reference
`agentorg pack add <id>[==<version>] --into <unit_id>` SHALL do three things:
- install the distribution;
- add a pinned `PackRef` to the spec;
- mount the pack's agent or root unit as a member of the target unit.

The spec SHALL store the reference, not a copy of the pack's content.

#### Scenario: Add a support pool to a hub
- **WHEN** a user runs `agentorg pack add support-desk --into root`, where `root` is a hub with 3 members
- **THEN** `spec.py` contains a `PackRef('support-desk', '<resolved version>')` mounted under `root`, and the rendered org
  routes work to the pack's pool

#### Scenario: Span limit respected
- **WHEN** the target hub already has 12 members
- **THEN** the add fails with the span-limit error, and the spec is unchanged

### Requirement: Pack ids are namespaced
Every agent and unit id from a pack SHALL be exposed as `<pack_id>.<local_id>`. Knowledge types, parameters and env vars
from a pack SHALL merge into the org. A conflicting definition of the same name SHALL fail the add.

#### Scenario: Namespaced agent
- **WHEN** pack `support-desk` provides agent `triage`
- **THEN** the org addresses it as `support-desk.triage`

#### Scenario: Conflicting knowledge type
- **WHEN** the org defines knowledge type `ticket` with a field `priority: int` and the pack defines `priority: string`
- **THEN** the add fails naming the type and field

### Requirement: Trigger templates arrive disabled
A pack's trigger templates SHALL be added to the spec disabled. The user SHALL enable each trigger explicitly.

#### Scenario: Pack schedule not firing
- **WHEN** a pack with a daily schedule template is added
- **THEN** no scheduled run occurs until the user enables that trigger

### Requirement: Overrides are a closed set
`PackRef.overrides` SHALL accept only these keys:
- per-agent `instructions`, appended to the persona;
- `model`;
- `autonomy`, equal or stricter only;
- `replicas`;
- parameter values;
- trigger `enabled` flags and cron expressions.

Any other override SHALL be rejected, with a message pointing to `pack eject`.

#### Scenario: Loosening autonomy rejected
- **WHEN** an override sets an agent whose pack autonomy is `propose` to `autonomous`
- **THEN** spec validation fails

#### Scenario: Unsupported override
- **WHEN** an override tries to add a tool to a pack agent
- **THEN** validation fails, suggesting `pack eject`

### Requirement: Upgrade keeps overrides
`agentorg pack upgrade <id>[==<version>]` SHALL move the pin and re-apply the overrides. When the new version removes an
overridden agent or trigger, or changes its type, the upgrade SHALL fail and the spec SHALL be left on the old version.

#### Scenario: Clean upgrade
- **WHEN** a pack is upgraded from 1.2.0 to 1.3.0 and every override still applies
- **THEN** the pin is 1.3.0, and the overrides are unchanged in `spec.py`

### Requirement: Eject transfers ownership
`agentorg pack eject <id>` SHALL replace the `PackRef` with the pack's content written into the spec and the project's tool
and skill directories, keeping the namespaced ids. The org SHALL then no longer depend on the distribution.

#### Scenario: Ejected pack is editable
- **WHEN** a user ejects `support-desk`
- **THEN** its agents appear as ordinary agent definitions in `spec.py`, and the distribution is removed from the rendered
  dependencies

### Requirement: Removal is safe
`agentorg pack remove <id>` SHALL fail while anything outside the pack references one of its ids. Such references include
referrals, triggers, step agents and escalation paths. The failure SHALL list each reference.

#### Scenario: Referenced pack
- **WHEN** an org trigger targets `support-desk.triage` and the user removes `support-desk`
- **THEN** the removal fails, naming the trigger

### Requirement: The master agent can install packs
The Build stage SHALL own three tools: `search_packs`, `add_pack` and `remove_pack`. They SHALL behave as the CLI commands
and return validation errors as text.

#### Scenario: Interview suggests a pack
- **WHEN** during Build the user describes needing customer support
- **THEN** the Build agent can search the catalog and, after confirmation, add the support pack into the chosen unit

### Requirement: Commercial packs need licence acknowledgement
Adding a `commercial` pack SHALL require an explicit acknowledgement of its licence: the `--accept-license` flag, or a user
confirmation in the interview. The acknowledgement SHALL be recorded in the `PackRef`.

#### Scenario: Missing acknowledgement
- **WHEN** a user adds a `commercial` pack without `--accept-license`
- **THEN** the add fails, showing the licence identifier and URL
