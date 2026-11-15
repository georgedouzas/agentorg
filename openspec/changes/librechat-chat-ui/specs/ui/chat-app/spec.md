# Spec Delta

## Purpose

Makes LibreChat, configured and not forked, the chat app of every rendered org, while the generated dashboard is the
operations console.

## ADDED Requirements

### Requirement: Every org ships LibreChat as its chat app
Every rendered org SHALL contain a `librechat.yaml` and SHALL declare `CHAT_API_KEY` as a required variable. There SHALL
be no option to render an org without LibreChat. The README SHALL explain how LibreChat runs for the org's packaging,
and Railway orgs SHALL list a setup step that deploys LibreChat with the same `CHAT_API_KEY`.

#### Scenario: Local org
- **WHEN** an org with `packaging='none'` is rendered
- **THEN** it contains `librechat.yaml`, and its README explains how to run LibreChat against the local API

#### Scenario: Railway org
- **WHEN** an org with `api='railway'` is rendered
- **THEN** its setup checklist contains a LibreChat deployment step that is complete once `CHAT_API_KEY` is set

### Requirement: LibreChat offers exactly the org's agents and units
The rendered `librechat.yaml` SHALL contain one custom endpoint pointing at the node's chat API, authenticated with
`CHAT_API_KEY`. It SHALL list one model spec per agent and unit, named, iconed and described from the spec's UI
settings, with the first featured agent as the default. Re-rendering SHALL update the model specs.

#### Scenario: Agents become model specs
- **WHEN** a spec with agents `triage` and `responder` is rendered
- **THEN** LibreChat's model picker offers exactly those agents and the org's units, under their display names

### Requirement: LibreChat cannot bypass the runtime
The rendered `librechat.yaml` SHALL turn off model selection outside the model specs, presets, LibreChat agents, MCP,
file search, code execution and web search, and SHALL hide LibreChat's built-in model endpoints.

#### Scenario: No bypass
- **WHEN** a user opens the rendered LibreChat
- **THEN** no option lets them create a LibreChat agent, attach an MCP server or pick a model that is not one of the
  org's agents or units

### Requirement: LibreChat carries the org's identity and users
The rendered configuration SHALL use the org's app name and empty-state text for branding, link to the operations
console, and send the LibreChat user id, user email and conversation id to the chat API as `X-Agentorg-User-Id`,
`X-Agentorg-User-Email` and `X-Agentorg-Conversation-Id`.

#### Scenario: Runs attributed to LibreChat users
- **WHEN** two LibreChat users chat with the same agent
- **THEN** their runs carry different user ids and neither resumes the other's session

### Requirement: The compose stack runs LibreChat beside the org
With docker packaging, the rendered `compose.yaml` SHALL add LibreChat, MongoDB and Meilisearch services. The LibreChat
image SHALL be the official image pinned to an exact version. LibreChat SHALL reach the node on the compose network,
and the node and LibreChat SHALL read `CHAT_API_KEY` from the same variable. The rendered `example.env` SHALL list every
variable LibreChat needs, with secrets left empty.

#### Scenario: Stack boots
- **WHEN** `docker compose up` runs in a rendered project with its required variables set
- **THEN** LibreChat answers on its published port, and a message sent to an agent there produces a run visible in
  the operations console

### Requirement: The dashboard is the operations console
The rendered dashboard SHALL have no chat panel or agent chat views, and the node SHALL have no dashboard chat stream
route. The dashboard SHALL keep the runs, Inbox, lifecycle, knowledge, parameters, settings and unit views, SHALL open
LibreChat when an agent is selected, and SHALL link to LibreChat. Links from chat messages to Inbox items SHALL open the
matching item.

#### Scenario: Approval deep link
- **WHEN** a user follows the approval link from a LibreChat message
- **THEN** the operations console opens with that approval shown, and approving it lets the chat continue

#### Scenario: Agent opens LibreChat
- **WHEN** a user selects an agent in the dashboard's sidebar
- **THEN** LibreChat opens instead of a chat panel
