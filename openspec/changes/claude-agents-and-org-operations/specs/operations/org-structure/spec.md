# Spec Delta

## Purpose

Defines the shape of every organization, from one agent to hundreds of thousands. The org is a tree of units. Each unit is
governed by one model from a closed set with exact runtime semantics, so any structure the user picks is guaranteed to run.

## ADDED Requirements

### Requirement: The org is a tree of units
`Spec.ai.root` SHALL be a unit. A unit has these fields:
- a unique `id`;
- `name`;
- `model`;
- an ordered list of `members`, each an agent id or a nested unit.

Every declared agent SHALL appear in exactly one unit, either as a member or as its `lead`. Agent and unit ids SHALL share
one namespace.

#### Scenario: Single-agent org
- **WHEN** a spec declares one agent and a root unit with `model='solo'` containing it
- **THEN** the spec validates, and the org runs with that agent as its only entry point

#### Scenario: Orphan agent rejected
- **WHEN** an agent is declared but is neither a member nor a lead of any unit
- **THEN** spec validation fails naming the agent

#### Scenario: Agent in two units rejected
- **WHEN** the same agent id appears in two units
- **THEN** spec validation fails

### Requirement: Governance models are a closed set
A unit's `model` SHALL be exactly one of five values:
- `solo`: exactly one agent member;
- `pipeline`: members run in order, and each receives the previous output;
- `hub`: a `lead` agent receives work and delegates to members;
- `pool`: a deterministic dispatcher routes each piece of work to one member;
- `council`: members answer independently, and a decision rule combines the answers.

There SHALL be no user-defined models.

#### Scenario: Unknown model rejected
- **WHEN** a unit declares `model='democracy'`
- **THEN** spec validation fails, listing the five allowed models

### Requirement: Each model has a fixed entry point
Work addressed to a unit SHALL enter at the model's entry point:
- `solo`: its agent;
- `pipeline`: its first member;
- `hub`: its lead;
- `pool`: its dispatcher;
- `council`: all members in parallel.

Units SHALL be valid targets for triggers, chat and delegation.

#### Scenario: Message to a hub
- **WHEN** a user messages unit `research` whose model is `hub`
- **THEN** a run of the unit's lead is created

### Requirement: Pipeline semantics
A `pipeline` SHALL run its members in declared order, passing each output as the next input. Each step MAY declare
`review` as `none`, `lead` or `human`. A held review SHALL pause the pipeline in `awaiting_approval`. A rejection SHALL re-run
that step once with the comment, and a second rejection SHALL fail the pipeline run.

#### Scenario: Human review gate
- **WHEN** the `draft` step of a pipeline has `review='human'` and completes
- **THEN** the pipeline run is `awaiting_approval`, and the next step has not started

#### Scenario: Double rejection
- **WHEN** a reviewer rejects the same step twice
- **THEN** the pipeline run is `failed` with reason `review_rejected`

### Requirement: Hub semantics
A `hub` SHALL declare a `lead` agent. The lead SHALL NOT also be listed in `members`. Only the lead may delegate to the
unit's members. Members SHALL return results to the lead, and SHALL NOT delegate to each other. With `review='lead'`, the
lead SHALL review each member result before using it.

#### Scenario: Member-to-member delegation denied
- **WHEN** a hub member tries to delegate to another member of the same hub
- **THEN** the call is denied with a message naming the lead as the only delegator

### Requirement: Pool semantics
A `pool` SHALL declare `routing` as one of three values:
- `round_robin`;
- `least_loaded`, the default;
- `skill_match`, which routes by matching work tags to member `skills_tags`.

The dispatcher SHALL be deterministic code, not an agent. A pool MAY declare a `lead` that receives escalations and handoffs
from members.

#### Scenario: Least-loaded routing
- **WHEN** a pool has members `a` with 2 running runs and `b` with 0, and new work arrives
- **THEN** the work is routed to `b`

#### Scenario: No match escalates
- **WHEN** `routing='skill_match'` and no member's tags match the work's tags
- **THEN** the work goes to the pool's lead, or to an escalation inbox item when there is no lead

### Requirement: Council semantics
A `council` SHALL have between 3 and 9 members and a `decision` rule:
- `majority`: requires `json` output with a `choice` field, and an odd member count;
- `judge`: a declared `lead` synthesises the answers;
- `unanimous`: disagreement escalates.

Members SHALL NOT see each other's answers before deciding.

#### Scenario: Majority decision
- **WHEN** a 3-member majority council returns choices `approve`, `approve`, `reject`
- **THEN** the unit's output is `approve`, and all three answers are recorded on the run

#### Scenario: Even majority council rejected
- **WHEN** a council has `decision='majority'` and 4 members
- **THEN** spec validation fails

### Requirement: Span and depth limits bound every unit
A unit SHALL have at most 12 direct members, except `pool`, which allows 100. The unit tree SHALL be at most 6 levels deep.
Larger orgs SHALL be expressed by nesting units. Agents MAY declare `replicas`: the number of parallel instances of one
agent definition, default 1.

#### Scenario: Oversized hub rejected
- **WHEN** a hub declares 15 members
- **THEN** spec validation fails, suggesting splitting it into nested units

#### Scenario: Very large org
- **WHEN** a spec nests hubs of 12 units, 4 levels deep, over pools of 100 members with `replicas=2`
- **THEN** the spec validates, describing over 4 million agent instances without any unit exceeding its limits

### Requirement: Communication follows the tree
An agent SHALL be able to reach these targets:
- delegation, only when the agent is a hub lead: the members of its own hub, where a member unit is entered at its entry
  point;
- handoff: its own unit's lead, or the other members of its own pool;
- escalation: its unit's lead. A lead escalates to its parent unit's lead, and the root escalates to the human inbox.

All other communication, including between sibling units, SHALL go through `publish`ed events.

#### Scenario: Sibling unit reached by event only
- **WHEN** an agent in unit `sales` tries to delegate to an agent in sibling unit `support`
- **THEN** the call is denied, and the denial suggests publishing an event

#### Scenario: Escalation climbs the tree
- **WHEN** a member of a nested pool escalates and the pool has no lead
- **THEN** the escalation goes to the lead of the pool's parent unit

### Requirement: Units scope ownership, autonomy and budget
A unit MAY declare the following, and nested units inherit them:
- `owners`: approver emails;
- `max_autonomy`: a ceiling on member autonomy;
- `monthly_usd`: a budget cap no larger than its parent's cap;
- `approval_required`: action classes that add to, and never remove from, the parent's.

Approvals SHALL go to the nearest unit owners up the tree, then to the org approvers.

#### Scenario: Autonomy ceiling
- **WHEN** a unit has `max_autonomy='propose'` and contains an `autonomous` agent
- **THEN** the agent runs as `propose`

#### Scenario: Loosening governance rejected
- **WHEN** a nested unit omits a class that its parent requires approval for
- **THEN** that class is still governed in the nested unit

#### Scenario: Unit budget exhausted
- **WHEN** a unit's month-to-date spend reaches its `monthly_usd`
- **THEN** new runs in that unit are rejected with reason `unit_budget`, and the rest of the org keeps running
