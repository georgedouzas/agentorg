# Spec Delta

## Purpose

Keeps humans in control of consequential actions and spending. Approvals are tied to declared action classes, and budgets
are expressed in USD with defined alerting and exhaustion behaviour.

## ADDED Requirements

### Requirement: Governed action classes
`operations.governance.approval_required` SHALL be a subset of these action classes:
- `external_write`: write-class custom or MCP tools;
- `outbound_message`: tools tagged as sending email, chat or SMS;
- `code_execution`: `bash`;
- `knowledge_publish`: knowledge writes;
- `spend`: a single run projected over `spend_threshold_usd`.

The default is `['external_write', 'outbound_message']`.

#### Scenario: Outbound message held
- **WHEN** an `act`-autonomy agent calls a tool tagged `outbound_message`, and that class is governed
- **THEN** the run moves to `awaiting_approval` with the tool name and arguments shown to the approver

### Requirement: Autonomy and governance combine conservatively
An action SHALL require approval when either of these holds:
- its class is governed;
- the agent's autonomy is `propose` and the action is a write.

`autonomous` agents SHALL bypass approval only for classes that are not governed.

#### Scenario: Autonomous still governed
- **WHEN** an `autonomous` agent attempts an `outbound_message`, and that class is governed
- **THEN** approval is required

### Requirement: Approvals have approvers, timeouts and outcomes
`operations.governance` SHALL declare:
- `approvers`: emails, defaulting to the org admin;
- `approval_timeout_h`: default 24;
- `on_timeout`: `reject`, which is the default, or `approve`.

An approver SHALL be able to approve, reject with a comment, or approve with edited arguments.

#### Scenario: Timeout rejects
- **WHEN** an approval is not decided within `approval_timeout_h` and `on_timeout='reject'`
- **THEN** the action is denied, the agent receives the denial, and an `approval.decided` event is published

#### Scenario: Edited approval
- **WHEN** an approver edits an email draft's body and approves
- **THEN** the tool executes with the edited arguments

### Requirement: Budget in USD
`operations.budget` SHALL declare:
- `monthly_usd`: required;
- `per_run_usd`: default 2.0;
- `alert_at`: a fraction of `monthly_usd`, default 0.8;
- `on_exhausted`: `pause`, which is the default, or `notify_only`.

Spend SHALL be the sum of run costs in the current calendar month, in UTC.

#### Scenario: Alert threshold
- **WHEN** month-to-date spend crosses `alert_at * monthly_usd`
- **THEN** a `budget.alert` event is published once for that month and a notification is sent

#### Scenario: Exhausted budget pauses org
- **WHEN** spend reaches `monthly_usd` and `on_exhausted='pause'`
- **THEN** the org transitions to `paused` with reason `budget`

### Requirement: Notifications go to declared channels
`operations.notifications.channels` SHALL be a subset of `dashboard`, `email`, `webhook` and `amqp`. Notifications SHALL fire for
these events:
- an approval request;
- an escalation;
- a run failure after retries;
- a budget alert;
- a lifecycle change.

`dashboard` is always on.

#### Scenario: Webhook channel
- **WHEN** `webhook` is a channel with `url_env='OPS_WEBHOOK_URL'` and an escalation occurs
- **THEN** a JSON POST describing the escalation is sent to that URL

#### Scenario: AMQP channel
- **WHEN** `amqp` is a channel with `exchange='ops'` and a run fails after retries
- **THEN** a persistent JSON message with routing key `run.failed` is published to the `ops` exchange

### Requirement: Every governance decision is audited
Approval requests, decisions, timeouts, budget alerts and denials SHALL be recorded with actor, time and run id. They SHALL
be visible in the run transcript.

#### Scenario: Decision in transcript
- **WHEN** an approver rejects an action
- **THEN** the run transcript shows the rejection, the approver email and the comment
