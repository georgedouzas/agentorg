# Spec Delta

## Purpose

Runs the master interview, and chats with the live preview's agents, in LibreChat, the same chat app every rendered org
uses.

## ADDED Requirements

### Requirement: The master serves the interview as a chat model
The master server SHALL serve `GET /v1/models` with one model, `agentorg`, and `POST /v1/chat/completions` in the same
OpenAI format and with the same bearer authentication as rendered nodes. Each user message SHALL go to the agent of the
current interview stage, and its reply, tool activity and stage changes SHALL stream back as text. The interview SHALL
keep one draft per master process, whatever conversation the message comes from.

#### Scenario: Interview turn
- **WHEN** a user in the Discover stage sends a description of their group
- **THEN** the Discover agent answers, its tool calls appear as lines in the reply, and the draft is updated

#### Scenario: Stage change visible
- **WHEN** the stage agent advances the interview after the user confirms
- **THEN** the reply ends with a line naming the new stage

### Requirement: Interview commands answer from the draft
A user message to `agentorg` starting with `/` SHALL be answered from the interview state without calling a stage
agent. `/stage` SHALL report the current stage, the stages done and the current blockers. `/spec` SHALL return the
current `spec.py` source. `/preview` SHALL report the live preview's status and its operations console link. `/help`
SHALL list the commands.

#### Scenario: Stage report
- **WHEN** a user sends `/stage` during Configure
- **THEN** the reply names Configure, marks Discover done and lists Configure's blockers

### Requirement: Interview commands change the draft only when safe
`/next` SHALL advance to the next stage only when the current stage has no blockers, and otherwise list them.
`/reset` SHALL start a new draft only when followed by `confirm`.

#### Scenario: Blocked advance
- **WHEN** a user sends `/next` while the Configure stage still lacks a budget
- **THEN** the reply lists the missing budget, and the stage does not change

#### Scenario: Reset needs confirmation
- **WHEN** a user sends `/reset` without `confirm`
- **THEN** the reply explains how to confirm, and the draft is unchanged

### Requirement: The agentorg command starts LibreChat
`agentorg ui` SHALL start the master server and a local LibreChat stack (LibreChat, MongoDB and Meilisearch) from a
compose file shipped with agentorg, using the same pinned LibreChat image as rendered orgs. The command SHALL generate
the chat key and LibreChat secrets on first use, keep them in the agentorg data directory, open LibreChat in the browser,
and stop the stack when it exits. Without a running Docker daemon it SHALL exit with a message that Docker is required.

#### Scenario: First start
- **WHEN** a user runs `agentorg ui` with Docker running
- **THEN** LibreChat opens with the `agentorg` model selected, and the master's chat API answers it

#### Scenario: No Docker
- **WHEN** a user runs `agentorg ui` without a Docker daemon
- **THEN** the command exits before starting anything, naming Docker as the requirement

### Requirement: The live preview's agents are chat models
The master's LibreChat configuration SHALL include a second endpoint for the live preview node's chat API, with its
model list read from the node, so agents and units added during the interview appear without restarting LibreChat.
The preview node SHALL run with a chat key and SHALL serve chat commands like any rendered node.

#### Scenario: New agent appears
- **WHEN** the Build stage adds an agent `triage` and the preview reloads
- **THEN** `triage` appears in LibreChat under the preview endpoint, and a message to it runs in the preview

### Requirement: The master UI is the preview page
The master server's web page SHALL show the live preview and the interview's stage progress, and SHALL link to
LibreChat. It SHALL NOT contain a chat.

#### Scenario: No second chat
- **WHEN** a user opens the master server's page
- **THEN** it shows the preview and stage progress with a link to LibreChat, and no message box
