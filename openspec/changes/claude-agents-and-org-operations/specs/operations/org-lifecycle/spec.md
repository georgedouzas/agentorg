# Spec Delta

## Purpose

Gives the organization an explicit lifecycle, so it can be introduced gradually, paused safely and retired without losing its
record. Each state defines what work is allowed.

## ADDED Requirements

### Requirement: Org lifecycle states
The org SHALL be in exactly one of these lifecycle states:
- `draft`
- `trial`
- `active`
- `paused`
- `retired`

A newly deployed org SHALL start in the state given by `operations.lifecycle.initial`, which defaults to `trial`. The
current state SHALL persist across restarts.

#### Scenario: Default initial state
- **WHEN** a freshly rendered org boots for the first time without `initial` set
- **THEN** its lifecycle state is `trial`

### Requirement: Draft, trial and active permit work with decreasing restriction
The three working states SHALL permit work as follows:
- `draft`: manual runs in preview only. Automatic triggers are off and all writes are denied.
- `trial`: all triggers are on. Every write-class action requires approval regardless of autonomy, and runs are capped at
  `trial_max_runs` (default 50).
- `active`: normal operation.

#### Scenario: Trial forces approvals
- **WHEN** an `autonomous` agent attempts a write during `trial`
- **THEN** the action requires approval

#### Scenario: Trial run cap
- **WHEN** the org has completed `trial_max_runs` runs in `trial`
- **THEN** new runs are rejected until an approver promotes the org to `active`

### Requirement: Paused and retired stop new work
In `paused`, no new runs SHALL start. Running runs finish, queued runs and external queue messages stay on the broker, and
schedule fires follow `catch_up`. In `retired`, no runs SHALL start, and run history and knowledge SHALL be read-only.

#### Scenario: Paused holds queue
- **WHEN** a webhook arrives while the org is `paused`
- **THEN** the run is created in `queued`, not started, and the endpoint responds 202

#### Scenario: Retired rejects work
- **WHEN** a user sends a chat message to a `retired` org
- **THEN** the request is rejected with a message that the org is retired

### Requirement: Allowed lifecycle transitions
Only these lifecycle transitions SHALL be allowed:
- `draft` → `trial`
- `trial` → `active` or `paused`
- `active` ⇄ `paused`
- any state except `retired` → `retired`

Manual transitions SHALL be made by an approver, through the API or dashboard, with a reason. Automatic transitions SHALL be
limited to `active`/`trial` → `paused` for budget exhaustion or a failure-rate breach.

#### Scenario: Illegal transition
- **WHEN** an operator requests `retired` → `active`
- **THEN** the request is rejected and the state is unchanged

#### Scenario: Trial promotion
- **WHEN** an approver promotes `trial` → `active` with a reason
- **THEN** the state becomes `active`, and a lifecycle-change notification records who promoted it and why

### Requirement: Failure-rate circuit breaker
When more than `operations.lifecycle.max_failure_rate` of runs fail within the last
`operations.lifecycle.failure_window` runs, the org SHALL auto-pause with reason `failure_rate`. The defaults are 0.5 and 20.

#### Scenario: Breaker trips
- **WHEN** 11 of the last 20 runs failed
- **THEN** the org transitions to `paused` with reason `failure_rate`

### Requirement: Individual agents and units can be disabled
An approver SHALL be able to disable or enable a single agent or unit at runtime without changing the spec. A disabled agent
or unit SHALL reject new runs and delegations and SHALL skip its triggers. Disabling a unit disables everything nested in it.

#### Scenario: Disabled agent skipped
- **WHEN** agent `outreach` is disabled and its schedule fires
- **THEN** no run is created and the skip is logged

#### Scenario: Disabled unit cascades
- **WHEN** unit `sales` is disabled
- **THEN** work addressed to `sales` or to any agent nested in it is rejected

### Requirement: Lifecycle is observable
The node SHALL expose these lifecycle endpoints:
- `GET /api/v1/lifecycle`: returns the current state, reason and transition history;
- `POST /api/v1/lifecycle`: requests a transition.

Each transition SHALL publish a `lifecycle.changed` event.

#### Scenario: History returned
- **WHEN** a client reads the lifecycle after two transitions
- **THEN** both transitions are listed with actor, reason and timestamp
