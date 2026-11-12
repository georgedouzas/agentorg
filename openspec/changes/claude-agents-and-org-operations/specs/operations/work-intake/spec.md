# Spec Delta

## Purpose

Defines every way work enters the organization: humans, schedules, internal events, external webhooks and external message
queues. Each trigger creates a run against a named target with a defined prompt and well-specified behaviour on overlap and
missed fires.

## ADDED Requirements

### Requirement: Triggers are a closed set of kinds
`operations.triggers` SHALL accept exactly five kinds: `manual`, `schedule`, `event`, `webhook` and `queue`. Each trigger has:
- a unique `id`;
- a `target`, which is an agent or unit id;
- a `prompt` template.

Every agent and unit SHALL be manually triggerable without declaring a manual trigger.

#### Scenario: Unknown target rejected
- **WHEN** a trigger targets an id that is not a declared agent or unit
- **THEN** spec validation fails

#### Scenario: Implicit manual trigger
- **WHEN** no trigger is declared for agent `analyst`
- **THEN** a user can still start a run of `analyst` from chat or the API

### Requirement: Schedule triggers run on cron
A `schedule` trigger SHALL declare a 5-field `cron` expression and an IANA `timezone` (default `UTC`). It SHALL create one
run per due fire time while the org lifecycle permits scheduled work.

#### Scenario: Weekly report
- **WHEN** a trigger has `cron='0 8 * * MON'` and `timezone='Europe/Athens'`
- **THEN** a run is created at 08:00 Athens time each Monday

#### Scenario: Invalid cron rejected
- **WHEN** `cron` is not a valid 5-field expression
- **THEN** spec validation fails

### Requirement: Schedule overlap policy
A `schedule` trigger SHALL declare `overlap`, defaulting to `skip`. It decides what happens when the previous run from the same
trigger is still queued or running:
- `skip` drops the new fire;
- `queue` enqueues it;
- `allow` starts it concurrently.

#### Scenario: Skip overlapping fire
- **WHEN** an hourly trigger with `overlap='skip'` fires while its previous run is still running
- **THEN** no new run is created and the skipped fire is logged

### Requirement: Schedule catch-up policy
A `schedule` trigger SHALL declare `catch_up` as `skip` (default) or `run_once`. The policy governs fires missed while the
node was down or the org was paused. `run_once` SHALL create a single run for all missed fires, not one per missed fire.

#### Scenario: Run once after downtime
- **WHEN** a daily trigger with `catch_up='run_once'` misses three fires during downtime
- **THEN** exactly one run is created when the node starts

### Requirement: Event triggers subscribe to the org bus
An `event` trigger SHALL declare an event `name` and an optional `filter` of payload-field equalities. These event names
are built in:
- `knowledge.created` and `knowledge.updated`, with a `type` field;
- `run.succeeded` and `run.failed`, with `target` and `trigger` fields;
- `approval.decided`;
- `budget.alert`;
- `lifecycle.changed`.

Agent-published custom events SHALL use names prefixed `custom.`.

#### Scenario: React to new report
- **WHEN** a trigger subscribes to `knowledge.created` with filter `type='report'` and a report unit is written
- **THEN** a run of the trigger's target is created with the event payload available to the prompt template

#### Scenario: Filter mismatch ignored
- **WHEN** a `knowledge.created` event with `type='note'` is published
- **THEN** the report-filtered trigger creates no run

### Requirement: Event cascades are bounded
A run created by an event SHALL record its causal chain. An event trigger SHALL NOT fire when doing so would exceed
`operations.communication.max_chain_depth`, which defaults to 5.

#### Scenario: Loop broken
- **WHEN** two agents each publish an event that triggers the other
- **THEN** no run beyond the configured depth is created and a warning naming both triggers is recorded in the activity log

### Requirement: Webhook triggers accept authenticated external calls
A `webhook` trigger SHALL expose `POST /api/v1/hooks/{trigger_id}`. It SHALL verify an HMAC-SHA256 signature of the body
using the secret in the env var named by `secret_env`. Unsigned or mis-signed requests SHALL be rejected with 401 and SHALL
create no run.

#### Scenario: Valid webhook
- **WHEN** a correctly signed POST arrives at a webhook trigger's path
- **THEN** the endpoint responds 202 with the created run id

#### Scenario: Bad signature
- **WHEN** the signature does not match
- **THEN** the endpoint responds 401 and no run exists

#### Scenario: Broker unavailable
- **WHEN** a correctly signed POST arrives while the broker is unreachable
- **THEN** the endpoint responds 503, no run exists, and the sender's retry later succeeds

### Requirement: Webhook deliveries are deduplicated
When a webhook request carries an `Idempotency-Key` header, any repeat key within 24 hours SHALL return the original run id
without creating a new run.

#### Scenario: Retry from sender
- **WHEN** the sender retries a delivery with the same `Idempotency-Key`
- **THEN** the response contains the original run id and only one run exists

### Requirement: Queue triggers consume external AMQP queues
A `queue` trigger SHALL declare a `queue` name and an optional payload `filter`. It MAY declare `url_env`, naming the env var
of a different broker; the default is the org broker. Each message SHALL create one run. The message SHALL be acknowledged
only after its run record exists.

#### Scenario: ERP order message
- **WHEN** an external system publishes an order message to the queue a `queue` trigger consumes
- **THEN** a run of the trigger's target is created with the message available to the prompt template

#### Scenario: Message not lost on crash
- **WHEN** the node dies after receiving a queue message but before creating its run
- **THEN** the broker redelivers the message and exactly one run is created

#### Scenario: Unparseable message dead-lettered
- **WHEN** a message body is not valid JSON
- **THEN** no run is created and the message is rejected without requeue

### Requirement: Prompt templates render trigger context
A trigger `prompt` SHALL be rendered with these variables:
- `{now}`
- `{trigger_id}`
- `{event}`: the event payload, as JSON
- `{body}`: the webhook body, as JSON
- `{message}`: the queue message body, as JSON
- the org parameters

A template referencing an unknown variable SHALL fail spec validation.

#### Scenario: Unknown variable rejected
- **WHEN** a prompt contains `{customer_name}`, and no parameter of that name exists
- **THEN** spec validation fails
