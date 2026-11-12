# Spec Delta

## Purpose

Defines how a single agent's behaviour is declared in `spec.py`: who it is, what it may do, which tools and context it has, and
the limits it runs under. Every field is a closed choice or a validated reference so the master agent and humans author the
same thing.

## ADDED Requirements

### Requirement: Agents are declared as typed definitions
`Spec.ai.agents` SHALL accept only agent definitions. Each has a unique `id` (lowercase kebab-case), a display `name`, and a
one-sentence `role`. Arbitrary runnables and framework objects SHALL be rejected at spec validation time.

#### Scenario: Framework object rejected
- **WHEN** a `spec.py` passes an object that is not an agent definition in `ai.agents`
- **THEN** loading the spec fails with a validation error naming the offending entry

#### Scenario: Duplicate ids rejected
- **WHEN** two agents, or an agent and a unit, share the same `id`
- **THEN** spec validation fails naming the duplicated id

### Requirement: Persona shapes the agent's voice and judgement
Each agent SHALL carry a persona with these fields:
- `tone`: one of `direct`, `warm`, `formal`, `playful`
- `verbosity`: one of `terse`, `balanced`, `thorough`
- `instructions`: free-form text
- `in_scope`: list of topics
- `out_of_scope`: list of topic-to-referral pairs

The persona SHALL be compiled into the agent's system prompt together with the org principles.

#### Scenario: Out-of-scope referral
- **WHEN** an agent declares `out_of_scope` with topic "billing" referred to agent `finance`
- **THEN** the compiled system prompt instructs the agent to decline billing requests and name `finance`

#### Scenario: Referral to unknown agent rejected
- **WHEN** an `out_of_scope` entry refers to an id that is not a declared agent or unit
- **THEN** spec validation fails

### Requirement: Model is selected from Claude tiers
Each agent SHALL declare `model` as one of `opus`, `sonnet` or `haiku`, defaulting to `sonnet`. Provider-prefixed model
strings SHALL be rejected.

#### Scenario: Default model
- **WHEN** an agent omits `model`
- **THEN** it runs on the `sonnet` tier

#### Scenario: Non-Claude model rejected
- **WHEN** an agent declares `model='google:gemini-2.5-flash'`
- **THEN** spec validation fails

### Requirement: Autonomy level bounds what an agent may do unattended
Each agent SHALL declare `autonomy`, defaulting to `propose`. The four levels are:
- `read_only`: read and research only
- `propose`: side-effecting actions require human approval
- `act`: side effects are allowed except governed action classes
- `autonomous`: side effects are allowed without approval within the agent workspace

#### Scenario: Read-only agent cannot write
- **WHEN** a `read_only` agent attempts a file write, shell command or write-tagged tool
- **THEN** the action is denied and the denial is returned to the agent as the tool result

#### Scenario: Propose agent pauses for approval
- **WHEN** a `propose` agent calls a write-tagged tool
- **THEN** the run enters `awaiting_approval` instead of executing the tool

### Requirement: Built-in harness tools are an explicit allowlist
Each agent SHALL declare `builtin_tools` as a subset of these tools:
- `read`, `write`, `edit`, `glob`, `grep`
- `bash`
- `web_search`, `web_fetch`
- `todo`

If `builtin_tools` is omitted, the default SHALL be derived from `autonomy`. Granting `write`, `edit` or `bash` to a
`read_only` agent SHALL be rejected.

#### Scenario: Default tools for read_only
- **WHEN** a `read_only` agent omits `builtin_tools`
- **THEN** it receives exactly `read`, `glob`, `grep`, `web_search`, `web_fetch`, `todo`

#### Scenario: Contradictory grant rejected
- **WHEN** a `read_only` agent declares `builtin_tools=['bash']`
- **THEN** spec validation fails

### Requirement: Custom tools are Python callables with declared side effects
Each agent MAY list custom tools as typed Python callables. Each tool SHALL be marked `read` or `write`, defaulting to
`write`. The tool's input schema SHALL be derived from its signature and its description from its docstring.

#### Scenario: Unmarked tool treated as write
- **WHEN** a custom tool has no side-effect marker
- **THEN** it is governed as a `write` tool for autonomy and approval purposes

### Requirement: MCP servers are declared per agent with tool filtering
Each agent MAY list MCP servers. Each server declares:
- `name`
- `transport`: one of `stdio`, `http`, `sse`
- connection details: `command`/`args` or `url`
- `env`: environment-variable names, never literal secrets
- optionally `allowed_tools`, `read_tools` and `outbound_tools`

MCP tools not listed in `read_tools` SHALL be treated as write tools.

#### Scenario: Secret referenced by env var
- **WHEN** an MCP server needs an API token
- **THEN** the spec references the env var name, and the name must be declared in `runtime.env_vars`, or validation fails

#### Scenario: Tool filtering
- **WHEN** a server declares `allowed_tools=['search_issues']`
- **THEN** the agent cannot call any other tool from that server

### Requirement: Skills are referenced by name
Each agent MAY list skills by name. Every name SHALL resolve to a custom skill emitted into the project or a pinned external
skill reference. The listed skills SHALL be the only skills available to the agent.

#### Scenario: Unknown skill rejected
- **WHEN** an agent lists a skill that resolves to neither a project skill nor a pinned reference
- **THEN** spec validation fails

### Requirement: Workspace mode controls file persistence
Each agent SHALL declare `workspace`, defaulting to `ephemeral`:
- `ephemeral`: a fresh directory per run, deleted afterwards
- `persistent`: one directory per agent, kept across runs
- `shared`: one directory per unit, shared by its members

#### Scenario: Ephemeral cleanup
- **WHEN** a run of an `ephemeral` agent finishes
- **THEN** its working directory no longer exists

### Requirement: Memory mode controls conversational continuity
Each agent SHALL declare `memory`, defaulting to `session`:
- `none`: every run starts fresh
- `session`: runs with the same session id resume the conversation
- `user`: the `session` behaviour, plus per-user notes persisted in the user's actor scope

#### Scenario: Session resume
- **WHEN** a `session` agent receives a second message with the same session id
- **THEN** it has the prior exchange in context

### Requirement: Per-run limits are enforced
Each agent SHALL declare these limits:
- `max_turns`: default 30
- `max_run_usd`: default from `operations.budget.per_run_usd`
- `timeout_s`: default 600

A run exceeding any limit SHALL stop with a status naming the limit hit.

#### Scenario: Turn cap
- **WHEN** an agent reaches `max_turns` without finishing
- **THEN** the run ends with failure reason `max_turns`

### Requirement: Output contract
Each agent SHALL declare `output` as `text` (default) or `json` with a JSON schema. It MAY also name a `knowledge_type` into
which successful outputs are written. A `json` output that fails schema validation SHALL fail the run.

#### Scenario: Report persisted as knowledge
- **WHEN** an agent with `output.knowledge_type='report'` completes a run
- **THEN** a knowledge unit of type `report` exists containing the output

#### Scenario: Unknown knowledge type rejected
- **WHEN** `output.knowledge_type` is not declared in `knowledge.types`
- **THEN** spec validation fails
