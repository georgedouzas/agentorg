# Spec Delta

## Purpose

Constrains how agents work together. Agents interact through three audited primitives (delegate, handoff, publish), within
a declared topology, and through declared teams and workflows. Free-form agent chatter is not possible.

## ADDED Requirements

### Requirement: Three communication primitives
Agents SHALL communicate only through three primitives:
- `delegate(agent_id, task)`: a synchronous sub-run whose output returns to the caller;
- `handoff(agent_id, note)`: transfers the current conversation to another agent and ends the caller's turn;
- `publish(event, payload)`: emits a `custom.*` event on the org bus.

Shared knowledge SHALL be the only shared state.

#### Scenario: Delegation returns output
- **WHEN** agent `lead` delegates "summarise ticket 42" to `support`
- **THEN** a child run of `support` is created and its output is returned to `lead` as the tool result

#### Scenario: Handoff transfers ownership
- **WHEN** agent `triage` hands off a chat to `billing`
- **THEN** the user's next message in that session is routed to `billing`, with the handoff note in its context

### Requirement: Topology bounds who may delegate or hand off
`operations.communication.topology` SHALL be one of three values:
- `hub`: only the declared `coordinator` agent may delegate or hand off;
- `hierarchy`: the default; an agent may delegate to agents whose `reports_to` is itself, and hand off to its peers and
  manager;
- `mesh`: any agent may reach any other.

Calls outside the topology SHALL be denied.

#### Scenario: Hierarchy denial
- **WHEN** under `hierarchy`, agent `writer` tries to delegate to its manager `editor`
- **THEN** the call is denied with a message naming the allowed targets

#### Scenario: Hub requires coordinator
- **WHEN** `topology='hub'` and no `coordinator` is declared
- **THEN** spec validation fails

### Requirement: Reporting lines are acyclic
Each agent MAY declare `reports_to`, naming another agent. The resulting graph SHALL be acyclic.

#### Scenario: Cycle rejected
- **WHEN** `a.reports_to='b'` and `b.reports_to='a'`
- **THEN** spec validation fails

### Requirement: Delegation depth is bounded
A chain of delegations SHALL NOT exceed `operations.communication.max_delegation_depth`, which defaults to 3. An agent SHALL
NOT delegate to an agent already in its own delegation chain.

#### Scenario: Re-entrant delegation denied
- **WHEN** `a` delegates to `b` and `b` tries to delegate back to `a`
- **THEN** the call is denied

### Requirement: Teams route through a lead
A team SHALL declare:
- `id` and `name`;
- `lead`: an agent id;
- `members`: agent ids that exclude the lead.

Invoking a team SHALL start a run of its lead. Within the team, the lead may delegate to members regardless of the org
topology.

#### Scenario: Team invocation
- **WHEN** a user messages team `research`
- **THEN** a run of the team's lead is created, and the lead can delegate to any member

### Requirement: Workflows run fixed agent steps
A workflow SHALL declare `id`, `name` and an ordered list of steps. Each step has:
- an `agent`;
- an `instruction`;
- `review`, a boolean that defaults to false.

Each step receives the previous step's output. A `review` step SHALL pause the workflow in `awaiting_approval` with the
step output until a human approves, edits or rejects it.

#### Scenario: Review gate
- **WHEN** the `draft` step of a content workflow has `review=true` and completes
- **THEN** the workflow run is `awaiting_approval` and the next step has not started

#### Scenario: Rejected review
- **WHEN** a reviewer rejects a step's output with a comment
- **THEN** the step re-runs once with the comment appended, and a second rejection fails the workflow run

### Requirement: Humans can be escalated to
Every agent SHALL have an `escalate(reason, context)` tool. It SHALL create a human inbox item and end the agent's turn,
telling the user that a human was notified.

#### Scenario: Escalation visible
- **WHEN** an agent escalates
- **THEN** an inbox item with the reason and a link to the run appears in the dashboard
