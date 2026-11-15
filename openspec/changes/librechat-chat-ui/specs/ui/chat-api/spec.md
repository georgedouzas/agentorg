# Spec Delta

## Purpose

Lets any OpenAI-compatible chat client talk to a rendered org's agents and units, while every message still runs
through the org's operations runtime.

## ADDED Requirements

### Requirement: The node lists its chat targets as models
Every rendered node SHALL serve `GET /v1/models`, which returns one model entry per enabled agent and per unit. The model id
SHALL be the agent or unit id. Disabled agents and units SHALL NOT be listed.

#### Scenario: Models listed
- **WHEN** a client calls `GET /v1/models` on an org with agents `triage` and `responder` in a unit `desk`
- **THEN** the response lists the ids `triage`, `responder` and `desk` in the OpenAI list format

#### Scenario: Disabled agent hidden
- **WHEN** `responder` has been disabled through the API and a client lists models
- **THEN** `responder` is not in the list

### Requirement: Chat completions start runs through the runtime
`POST /v1/chat/completions` SHALL start a run of the target named by `model`, with the last user message as the run's
input and trigger kind `manual`, exactly like a chat started from the dashboard. The run SHALL go through the same
admission, policy, budget and lifecycle checks, and SHALL be recorded in the run history. An unknown `model` SHALL return 404 in the
OpenAI error format.

#### Scenario: Chat run recorded
- **WHEN** a client sends a chat completion to `triage`
- **THEN** a run of `triage` with trigger kind `manual` appears in `GET /api/v1/runs`, and its output is the reply

#### Scenario: Retired org refuses
- **WHEN** the org is retired and a client sends a chat completion
- **THEN** the reply is a refusal message naming the retired state, and no run is queued

### Requirement: Replies stream in the OpenAI format
With `stream: true`, the node SHALL reply with server-sent `chat.completion.chunk` events ending in `data: [DONE]`.
Without it, the node SHALL wait for the run to end and return one `chat.completion`. The reply SHALL report the run's
token usage. Each response SHALL carry the run id in an `X-Agentorg-Run-Id` header.

#### Scenario: Streaming reply
- **WHEN** a client sends a streaming chat completion
- **THEN** it receives text deltas as the agent produces them, then a final chunk with `finish_reason: stop`, then
  `[DONE]`

### Requirement: Run activity is visible as text
While streaming, the node SHALL send the run's tool calls and delegations as short, distinguishable text lines. When the
run is held for approval, the node SHALL send a message naming the held action with a link to the matching item in the
operations console and the `/approve` and `/reject` commands, keep the stream open while the run waits, and continue streaming once the approval is decided. A
run that fails SHALL end the stream with a message stating the failure reason.

#### Scenario: Approval hold
- **WHEN** an agent's outbound action is held for approval during a streamed chat
- **THEN** the client receives a message with a link to the Inbox item, and after the action is approved in the
  console, the rest of the reply streams to the same client

#### Scenario: Rejection
- **WHEN** the held action is rejected with a comment
- **THEN** the stream continues with the agent's reply to the rejection

### Requirement: Conversations map to agent sessions
The node SHALL resume the same agent session for every message of one client conversation, so an agent keeps its
context without the client resending it. The conversation SHALL be identified by the `X-Agentorg-Conversation-Id` header
when present. Without the header, the node SHALL derive a stable key from the target and the conversation's earlier
messages. A conversation SHALL NOT resume a session that belongs to another user or another target.

#### Scenario: Follow-up keeps context
- **WHEN** a user sends two messages in one conversation with the same conversation id
- **THEN** the second run resumes the first run's agent session

#### Scenario: Conversation follows a handoff
- **WHEN** `triage` hands the conversation off to `responder` and the user sends another message
- **THEN** the next run is a run of `responder` in the same conversation, as in the dashboard chat

#### Scenario: Same id, other user
- **WHEN** a request reuses a conversation id with a different user id
- **THEN** a new session is started

### Requirement: The chat API is authenticated and attributed
The chat API SHALL require a bearer key equal to the node's `CHAT_API_KEY` and SHALL return 401 otherwise. When
`CHAT_API_KEY` is not set, as in tests without it, the chat API SHALL be disabled and return 404. Runs SHALL be attributed to the user named by
the `X-Agentorg-User-Id` header, or to `default` without it.

#### Scenario: Missing key
- **WHEN** a client calls the chat API without the bearer key
- **THEN** the response is 401 and no run starts

#### Scenario: User attribution
- **WHEN** a chat completion carries `X-Agentorg-User-Id: dana`
- **THEN** the run's user is `dana`

### Requirement: Chat commands cover what LibreChat lacks
A user message starting with `/` SHALL be answered by the node as a command, without starting a run and without
changing the conversation's agent session. The commands SHALL be:
- `/approve <id> [comment]` and `/reject <id> <comment>`;
- `/runs`, `/run <id>` and `/inbox`;
- `/status`, `/pause <reason>` and `/resume`;
- `/help`, which lists them.

An unknown command SHALL reply with the `/help` text.

#### Scenario: Status without a run
- **WHEN** a user sends `/status`
- **THEN** the reply states the lifecycle state, broker health and pending approvals, and no run is created

#### Scenario: Unknown command
- **WHEN** a user sends `/frobnicate`
- **THEN** the reply lists the available commands

### Requirement: Approvals can be decided in chat by approvers
`/approve` and `/reject` SHALL decide a pending approval only when the user's email, from `X-Agentorg-User-Email`, is
one of the approval's approvers, or when the approval lists no approvers and the email is the org admin's. A rejection
SHALL require a comment. Every decision SHALL be recorded with the user's email as the actor, exactly like a decision
made in the operations console. The approval-hold message SHALL name the `/approve` and `/reject` commands next to the
console link.

#### Scenario: Approver approves in chat
- **WHEN** an approver sends `/approve ap1` while run `r1` waits on `ap1`
- **THEN** the approval is recorded as approved by that approver, and `r1` continues

#### Scenario: Not an approver
- **WHEN** a user who is not an approver sends `/approve ap1`
- **THEN** the reply says they cannot decide it, and the approval stays pending

#### Scenario: Rejection needs a comment
- **WHEN** an approver sends `/reject ap1` without a comment
- **THEN** the reply asks for a comment, and the approval stays pending

### Requirement: Only org approvers pause and resume from chat
`/pause` and `/resume` SHALL be allowed only for the org approvers, or the admin when the org lists none. `/pause`
SHALL move the org to `paused` with the given reason, and `/resume` SHALL return it to `active`.

#### Scenario: Approver pauses
- **WHEN** an org approver sends `/pause maintenance`
- **THEN** the org is paused with that reason, recorded with the approver's email

#### Scenario: Other user refused
- **WHEN** a user who is not an org approver sends `/pause`
- **THEN** the reply says only the org approvers can pause it, and the lifecycle is unchanged
