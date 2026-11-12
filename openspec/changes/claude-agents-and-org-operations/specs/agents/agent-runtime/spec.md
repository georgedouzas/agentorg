# Spec Delta

## Purpose

Runs declared agents on the prebuilt Claude agent harness inside the rendered org's AgentField node. Every run is
policy-taggable, streamable, cost-accounted and audited.

## ADDED Requirements

### Requirement: Each agent is exposed as a tagged reasoner
The rendered node SHALL register every declared agent as a reasoner named by its `id`. The reasoner SHALL carry the tag
`agent` and the org slug. Each unit SHALL be registered as a reasoner carrying `unit` and its model name, such as `hub`. Custom tools SHALL also be registered as node
skills, so control-plane policies and the MCP shim can address them.

#### Scenario: Policy targeting by tag
- **WHEN** an operator creates a control-plane policy for tag `agent`
- **THEN** it applies to every declared agent reasoner and to no unit reasoner

### Requirement: Agents run on the Claude agent harness
Each run SHALL execute on the Claude agent harness with the agent's model, compiled system prompt, allowed tools, MCP
servers, skills, workspace directory and limits. No settings outside the spec SHALL leak in, such as the user's global
harness configuration.

#### Scenario: Host settings isolated
- **WHEN** the machine running the node has user-level harness settings or skills
- **THEN** a run uses only the tools, skills and settings declared for that agent

### Requirement: Org principles are part of every agent prompt
The compiled system prompt SHALL include the org principles, with parameter placeholders substituted from current parameter
values.

#### Scenario: Principle parameter substitution
- **WHEN** a principle body contains `{domain_focus}` and the parameter's value is `Applied Research`
- **THEN** the agent's system prompt contains `Applied Research` and not the placeholder

### Requirement: Runs stream progress
A reasoner invocation SHALL be available as a server-sent event stream. The stream SHALL emit assistant text, tool calls with
their names, tool results, status changes and a terminal event with the output and cost.

#### Scenario: Tool call visible
- **WHEN** an agent calls `web_search` during a streamed run
- **THEN** the stream emits a tool-call event naming `web_search` before the terminal event

### Requirement: Cost and usage are recorded per run
Every run SHALL record input tokens, output tokens and USD cost reported by the harness. These SHALL count toward the org
budget.

#### Scenario: Cost recorded
- **WHEN** a run completes
- **THEN** its run record shows a non-negative `cost_usd` and token counts

### Requirement: Permission decisions follow autonomy and governance
Before every tool use, the runtime SHALL decide to allow, deny or hold the action for approval. The decision SHALL be based
on the agent's autonomy, the tool's side-effect class, the governed action classes and the org lifecycle state. Denials
SHALL be returned to the agent as tool results, not raised as errors.

#### Scenario: Denied tool does not crash the run
- **WHEN** a `read_only` agent attempts `bash`
- **THEN** the agent receives a denial message and the run continues

### Requirement: Org communication tools are available to every agent
Every agent SHALL receive the org tools its position in the unit tree permits: `delegate`, `handoff`, `publish`, `escalate` and the
knowledge tools. They SHALL appear alongside its declared tools.

#### Scenario: Knowledge tools present
- **WHEN** any agent runs
- **THEN** it can call `search_knowledge` and `read_knowledge`

### Requirement: Preview mode stays side-effect free
When the node runs in preview mode:
- knowledge writes SHALL be no-ops;
- schedule, event, webhook and queue triggers SHALL not fire;
- write-class external actions SHALL be denied with a message stating preview mode.

#### Scenario: Schedule silent in preview
- **WHEN** the live preview runs an org with a schedule trigger due now
- **THEN** no run is created
