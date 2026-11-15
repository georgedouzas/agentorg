# Spec Delta

## Purpose

Makes every unit of work a durable, inspectable run with one status machine, bounded concurrency and explicit failure
handling. Operators can see what the org did, what it is doing and what went wrong.

## ADDED Requirements

### Requirement: Every piece of work is a run
Each invocation of an agent or unit SHALL create a run record. The record holds:
- `id`, `target` and trigger kind/id;
- the parent run, when it was created by delegation, a pipeline step or a council member;
- the session id, user id and status;
- start and end timestamps;
- the output, the failure reason, the cost and the token usage.

Runs SHALL persist across node restarts.

#### Scenario: Run survives restart
- **WHEN** the node restarts after a run succeeded
- **THEN** the run is still listed with its output and cost

### Requirement: Run status machine
A run SHALL be in exactly one of these states:
- `queued`
- `running`
- `awaiting_approval`
- `succeeded`
- `failed`
- `cancelled`

Allowed transitions:
- `queued` → `running` or `cancelled`
- `running` → `awaiting_approval`, `succeeded`, `failed` or `cancelled`
- `awaiting_approval` → `running` or `cancelled`

Terminal states SHALL NOT change.

#### Scenario: Approval resumes run
- **WHEN** an `awaiting_approval` run's pending action is approved
- **THEN** the run returns to `running` and the action executes

#### Scenario: Terminal state immutable
- **WHEN** a cancel request arrives for a `succeeded` run
- **THEN** the request is rejected and the run stays `succeeded`

### Requirement: Queued work is carried by a mandatory message broker
The org SHALL use the RabbitMQ broker at `AMQP_URL` for queued runs, retries, dead-lettered runs and org events. Outside
preview mode, the node SHALL refuse to start when `AMQP_URL` is unset or unreachable. Queued runs SHALL survive restarts of
both the node and the broker.

#### Scenario: Missing broker fails fast
- **WHEN** the node starts outside preview mode without `AMQP_URL`
- **THEN** startup fails with an error naming `AMQP_URL`

#### Scenario: Queued run survives broker restart
- **WHEN** the broker restarts while a run is `queued`
- **THEN** the run starts after the broker is back, and it starts exactly once

#### Scenario: Health reports broker
- **WHEN** the broker connection is lost
- **THEN** the node's health endpoint reports the broker as unavailable

### Requirement: Several workers share the queue
More than one node process for the same org MAY consume runs. Each run SHALL execute on exactly one worker. Schedule triggers
SHALL fire exactly once per due time, whatever the number of workers.

#### Scenario: Two workers, one execution
- **WHEN** two workers are running and one run is enqueued
- **THEN** exactly one worker executes it

#### Scenario: Single schedule fire
- **WHEN** two workers are running and an hourly schedule comes due
- **THEN** exactly one run is created

### Requirement: Preview mode bypasses the broker
In preview mode, the node SHALL start without `AMQP_URL`. Manual runs SHALL execute directly, without being queued.

#### Scenario: Preview without broker
- **WHEN** the master's live preview boots a rendered org with no broker available
- **THEN** a chat message to an agent runs and streams its reply

### Requirement: Interrupted runs are failed explicitly
A run that was `running` on a worker that stopped SHALL be marked `failed` with reason `interrupted` by the next worker to
start. It SHALL then follow the retry policy.

#### Scenario: Worker crash
- **WHEN** a worker dies mid-run and another worker starts
- **THEN** the run is `failed` with reason `interrupted` and a retry is enqueued if retries remain

### Requirement: Concurrency is capped org-wide and per agent
The runtime SHALL enforce two concurrency caps:
- `operations.runs.max_concurrent` (default 4) per worker process;
- each agent's `replicas` (default 1), across all workers.

Runs beyond either cap SHALL wait in `queued`. Queued runs start in priority order and FIFO within a priority:
`manual` > `webhook` and `queue` > `event` > `schedule`.

#### Scenario: Manual jumps the queue
- **WHEN** a scheduled run and a manual run for the same agent are both queued
- **THEN** the manual run starts first

### Requirement: Failed runs retry by policy
`operations.runs.retries` (default 1) SHALL bound automatic retries of a failed run. Retries use exponential backoff starting
at 30 seconds. Runs that failed on a limit (`max_turns`, `max_run_usd`, `timeout`) or a denial SHALL NOT be retried.
A delegated run SHALL NOT be retried or dead-lettered on its own: the run that delegated it waits on it and handles its
failure. A unit run whose member failed SHALL fail with the member's reason.

#### Scenario: Transient error retried
- **WHEN** a run fails with an API overload error and `retries=1`
- **THEN** one retry run is created linked to the original

#### Scenario: Budget failure not retried
- **WHEN** a run fails with reason `max_run_usd`
- **THEN** no retry is created

#### Scenario: Delegated failure left to the parent
- **WHEN** a delegated run fails with an API overload error
- **THEN** no retry of it is created, and the run that delegated it receives the failure

#### Scenario: Unit fails with its member's reason
- **WHEN** the only member of a `solo` unit fails with reason `max_turns`
- **THEN** the unit run fails with reason `max_turns` and is not retried

#### Scenario: Retry delayed
- **WHEN** a run fails and a retry is due after 30 seconds
- **THEN** the retry run does not start before 30 seconds have passed

### Requirement: Failure policy after retries are exhausted
A run that exhausts its retries SHALL be dead-lettered. `operations.runs.on_failure` SHALL be one of:
- `notify`: the default; emit a notification;
- `escalate`: create a human inbox item;
- `handoff`: start a run of a named fallback agent with the failure context.

#### Scenario: Escalate to human
- **WHEN** a run exhausts retries under `on_failure='escalate'`
- **THEN** an inbox item linking the run appears in the dashboard

### Requirement: Runs can be cancelled
An operator SHALL be able to cancel a `queued`, `running` or `awaiting_approval` run. Cancelling stops the run and its
descendant delegated runs.

#### Scenario: Cascade cancel
- **WHEN** a run that delegated to another agent is cancelled
- **THEN** the delegated run is also `cancelled`

### Requirement: Run history is queryable
The node SHALL expose `GET /api/v1/runs`, filterable by target, status, trigger kind and time range. It SHALL also expose
`GET /api/v1/runs/{id}`, which returns the run, its child runs and its event transcript. Run records SHALL be retained for
`operations.runs.retention_days`, which defaults to 90.

#### Scenario: Filter failed runs
- **WHEN** a client requests runs with `status=failed`
- **THEN** only failed runs are returned, newest first
