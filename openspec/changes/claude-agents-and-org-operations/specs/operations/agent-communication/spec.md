# Spec Delta

## Purpose

Defines the only ways agents interact: four audited primitives and shared knowledge. Who may use a primitive towards whom is
decided by the org structure (see `operations/org-structure`), never by agents themselves.

## ADDED Requirements

### Requirement: Four communication primitives
Agents SHALL interact only through four primitives:
- `delegate(target, task)`: a synchronous sub-run whose output returns to the caller;
- `handoff(target, note)`: transfers the current conversation and ends the caller's turn;
- `publish(event, payload)`: emits a `custom.*` event on the org bus;
- `escalate(reason, context)`: raises the issue up the unit tree.

Shared knowledge SHALL be the only shared state.

#### Scenario: Delegation returns output
- **WHEN** hub lead `lead` delegates "summarise ticket 42" to member `support`
- **THEN** a child run of `support` is created, and its output is returned to `lead` as the tool result

#### Scenario: Handoff transfers ownership
- **WHEN** pool member `triage` hands off a chat to pool member `billing`
- **THEN** the user's next message in that session is routed to `billing`, with the handoff note in its context

### Requirement: Primitives are offered only where permitted
Each agent SHALL receive only the primitives its position in the unit tree permits. A call to a target outside the
permitted set SHALL be denied with a message naming the allowed targets.

#### Scenario: Non-lead has no delegate
- **WHEN** an agent that leads no hub runs
- **THEN** its tool list does not contain `delegate`

### Requirement: Delegation chains are bounded and acyclic
A delegation chain SHALL NOT exceed the depth of the unit tree. An agent SHALL NOT delegate to a target already in its own
chain.

#### Scenario: Re-entrant delegation denied
- **WHEN** a chain reaches an agent that tries to delegate back to an agent already in the chain
- **THEN** the call is denied

### Requirement: Escalation reaches humans at the root
Escalating SHALL end the agent's turn and pass the reason and context to its escalation target. An escalation reaching the
root unit SHALL create a human inbox item and tell the user that a human was notified.

#### Scenario: Escalation visible
- **WHEN** an escalation reaches the root
- **THEN** an inbox item with the reason, the escalation path and a link to the run appears in the dashboard
