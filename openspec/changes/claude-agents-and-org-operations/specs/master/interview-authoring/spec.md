# Spec Delta

## Purpose

Lets the master agent author agent definitions and organization operations through its staged interview, running on the same
Claude agent harness as rendered orgs. Each stage keeps its own narrow tool slice.

## ADDED Requirements

### Requirement: Stage agents run on the Claude agent harness
Each interview stage SHALL be a Claude agent whose only tools are that stage's slice. No built-in file or shell tools SHALL
be available. Stage tools SHALL mutate the working spec, and every turn SHALL rewrite `spec.py`.

#### Scenario: No shell in interview
- **WHEN** the Build stage agent is running
- **THEN** it cannot call `bash`, `write` or `edit`

### Requirement: Configure stage owns budget and lifecycle defaults
The Configure stage SHALL own these tools, and no other stage SHALL hold them:
- tools that set `operations.budget`;
- tools that set the initial lifecycle state and trial limits;
- tools that set the approvers.

Advancing past Configure SHALL require `budget.monthly_usd` to be set.

#### Scenario: Budget blocker
- **WHEN** the user asks to advance from Configure with no monthly budget set
- **THEN** advancement is refused with a blocker naming the budget

### Requirement: Build stage owns agents, units and triggers
The Build stage SHALL own these tools:
- add, update and remove for agents, including persona, model, autonomy, built-in tools, custom tools, MCP servers, skills,
  workspace, memory, limits and output;
- add, update and remove for units, including the model, lead, members, routing, decision rule, review policy and replicas;
- move an agent or unit to another parent unit;
- add, update and remove for triggers.

Each tool SHALL return validation errors to the agent as text, not raise them.

#### Scenario: Invalid trigger reported
- **WHEN** the Build agent adds a schedule trigger with an invalid cron
- **THEN** the tool returns an error message and the spec is unchanged

#### Scenario: Discover lacks build tools
- **WHEN** the Discover stage agent is running
- **THEN** it has no agent or trigger tools

### Requirement: Refine stage owns governance and notifications
The Refine stage SHALL own the tools that set the governed action classes, the approval timeout behaviour and the
notification channels. These are in addition to its existing knowledge, parameter and UI tools.

#### Scenario: Governance set in Refine
- **WHEN** the user asks during Refine to require approval for code execution
- **THEN** `code_execution` is added to the governed classes

### Requirement: Sandbox runs exercise the real harness
The Build stage's sandbox tool SHALL run a declared agent on the Claude agent harness with preview-mode restrictions. It
SHALL return each prompt's output, tool calls and cost.

#### Scenario: Sandbox cost reported
- **WHEN** the Build agent sandboxes an agent with two test prompts
- **THEN** the result lists both outputs and the cost of each run

### Requirement: Written spec uses the declarative model
The spec writer SHALL emit `spec.py` that builds agents, units and operations from the agentorg spec models only.
It SHALL import no agent framework.

#### Scenario: No framework imports
- **WHEN** a finished interview writes `spec.py`
- **THEN** the file's imports reference only `agentorg` spec models and the project's custom tool modules
