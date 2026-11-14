# Spec Delta

## Purpose

Lets an org use LibreChat, configured and not forked, as its chat app, while the generated dashboard remains the
operations console.

## ADDED Requirements

### Requirement: The chat UI is a closed choice
`runtime.infra.chat_ui` SHALL be `dashboard` or `librechat`, and SHALL default to `dashboard`. `librechat` SHALL require
`packaging='docker'` and `auth='none'`; other combinations SHALL fail validation with a message naming the conflicting
field. With `dashboard`, rendered orgs SHALL be unchanged by this change.

#### Scenario: Default unchanged
- **WHEN** a spec does not set `chat_ui`
- **THEN** the rendered project contains no LibreChat files or services, and the dashboard keeps its chat panel

#### Scenario: Invalid combination
- **WHEN** a spec sets `chat_ui='librechat'` with `packaging='none'`
- **THEN** validation fails with a message that LibreChat requires docker packaging

### Requirement: LibreChat offers exactly the org's agents and units
With `chat_ui='librechat'`, the rendered project SHALL contain a `librechat.yaml` with one custom endpoint pointing at
the node's chat API and authenticated with `CHAT_API_KEY`. It SHALL list one model spec per agent and unit, named,
iconed and described from the spec's UI settings, with the first featured agent as the default. Re-rendering SHALL
update the model specs.

#### Scenario: Agents become model specs
- **WHEN** a spec with agents `triage` and `responder` is rendered with `chat_ui='librechat'`
- **THEN** LibreChat's model picker offers exactly those agents and the org's units, under their display names

### Requirement: LibreChat cannot bypass the runtime
The rendered `librechat.yaml` SHALL turn off model selection outside the model specs, presets, LibreChat agents, MCP,
file search, code execution and web search, and SHALL hide LibreChat's built-in model endpoints.

#### Scenario: No bypass
- **WHEN** a user opens the rendered LibreChat
- **THEN** no option lets them create a LibreChat agent, attach an MCP server or pick a model that is not one of the
  org's agents or units

### Requirement: LibreChat carries the org's identity and users
The rendered configuration SHALL use the org's app name, description and empty-state text for branding, link to the
operations console, and send the LibreChat user id and conversation id to the chat API as `X-Agentorg-User-Id` and
`X-Agentorg-Conversation-Id` where the pinned LibreChat version supports it.

#### Scenario: Runs attributed to LibreChat users
- **WHEN** two LibreChat users chat with the same agent
- **THEN** their runs carry different user ids and neither resumes the other's session

### Requirement: The compose stack runs LibreChat beside the org
With `chat_ui='librechat'`, the rendered `compose.yaml` SHALL add LibreChat, MongoDB and Meilisearch services. The
LibreChat image SHALL be the official image pinned to an exact version. LibreChat SHALL reach the node on the compose
network, and the node's `CHAT_API_KEY` and LibreChat's endpoint key SHALL come from the same variable. The rendered
`example.env` SHALL list every variable LibreChat needs, with secrets left empty.

#### Scenario: Stack boots
- **WHEN** `docker compose up` runs in a rendered project with `chat_ui='librechat'` and its required variables set
- **THEN** LibreChat answers on its published port, and a message sent to an agent there produces a run visible in
  the operations console

### Requirement: The dashboard becomes the operations console
With `chat_ui='librechat'`, the rendered dashboard SHALL drop its chat panel and agent chat views. It SHALL keep the
runs, Inbox, lifecycle, knowledge, parameters, settings and unit views, and SHALL link to LibreChat. Links from chat
messages to Inbox items SHALL open the matching item.

#### Scenario: Approval deep link
- **WHEN** a user follows the approval link from a LibreChat message
- **THEN** the operations console opens with that approval shown, and approving it lets the chat continue

### Requirement: The interview and preview keep the built-in chat
The master interview SHALL offer `chat_ui` in the Configure stage and SHALL explain the extra services `librechat`
adds. The master's live preview SHALL always use the dashboard with its chat panel and SHALL NOT start LibreChat,
MongoDB or Meilisearch, whatever `chat_ui` is.

#### Scenario: Preview of a LibreChat org
- **WHEN** a user sets `chat_ui='librechat'` during the interview
- **THEN** the live preview still shows the built-in chat panel and starts no extra services
