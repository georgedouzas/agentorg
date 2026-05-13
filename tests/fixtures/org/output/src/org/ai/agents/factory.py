"""Agent factory — builds every agent from the spec.

`default` agent architecture: a single `agno.Agent` per spec entry, with
instructions composed from structured fields, real-callable tools, and shared knowledge +
(optional) learning wired in.
"""

from agno.agent import Agent as AgnoAgent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.google import Gemini

from agentorg.core.schema import Agent, Spec
from agentorg.core.tools._engine import create_knowledge, get_postgres_db

_TEAM_KNOWLEDGE = create_knowledge('Team Knowledge', 'team_knowledge')
_TEAM_LEARNINGS = create_knowledge('Team Learnings', 'team_learnings')


def _build_learning(agent_spec: Agent) -> LearningMachine | None:
    if not agent_spec.learning:
        return None
    return LearningMachine(
        knowledge=_TEAM_LEARNINGS,
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC, namespace='global'),
    )


def _compose_instructions(agent_spec: Agent, charter_text: str) -> str:
    parts: list[str] = [
        f'You are the {agent_spec.name}.',
        '',
        '## Committee Rules (ALWAYS FOLLOW)',
        '',
        charter_text,
        '',
    ]
    if agent_spec.role:
        parts += ['## Role', '', agent_spec.role, '']
    if agent_spec.in_scope:
        parts += ['## In scope']
        parts += [f'- {x}' for x in agent_spec.in_scope]
        parts.append('')
    if agent_spec.out_of_scope:
        parts += ['## Out of scope — decline and refer']
        for item in agent_spec.out_of_scope:
            parts.append(f'- {item.topic} → **{item.refer_to}**')
        parts += ['', 'If asked anything outside your scope, decline firmly and point to the right person.', '']
    if agent_spec.count_rule:
        cr = agent_spec.count_rule
        parts += ['## How many results to return']
        for rule in cr.rules:
            parts.append(f'- **{rule.phrase}** → {rule.count}')
        if cr.default is not None:
            parts.append(f'- (otherwise) → {cr.default}')
        parts.append('')
    if agent_spec.workflow:
        parts += ['## Workflow']
        parts += [f'{i + 1}. {step}' for i, step in enumerate(agent_spec.workflow)]
        parts.append('')
    if agent_spec.output_format:
        of = agent_spec.output_format
        parts += ['## Output format']
        if of.kind == 'markdown_table' and of.columns:
            parts.append(f'Markdown table with columns: {" | ".join(of.columns)}.')
        if of.sections:
            parts.append('Use these sections (in order): ' + ', '.join(of.sections) + '.')
        if of.trailer:
            parts.append(of.trailer)
        parts.append('')
    if agent_spec.save_rule:
        sr = agent_spec.save_rule
        parts += [
            '## Auto-save the report',
            '',
            f'Your final action is to call `{sr.tool}`. The tool response IS the confirmation; '
            'do not write anything after the call.',
            '',
            '**Argument rules (strict):**',
            f'- `name`: {sr.name_pattern}',
            f'- `title`: {sr.title_pattern}',
            '- `content`: the full markdown analysis you just produced.',
            '- `metadata`: optional tags dict.',
        ]
        if sr.note:
            parts += ['', sr.note]
    return '\n'.join(parts)


def build_agents(spec: Spec, charter_text: str = '') -> dict[str, AgnoAgent]:
    """Return ``{agent_id: agno.Agent}`` for every agent declared in the spec."""
    db = get_postgres_db()
    agents: dict[str, AgnoAgent] = {}
    for agent_spec in spec.generated.agents:
        agents[agent_spec.id] = AgnoAgent(
            id=agent_spec.id,
            name=agent_spec.name,
            model=Gemini(id=agent_spec.model),
            db=db,
            instructions=_compose_instructions(agent_spec, charter_text),
            tools=list(agent_spec.tools),
            knowledge=_TEAM_KNOWLEDGE,
            search_knowledge=True,
            learning=_build_learning(agent_spec),
            add_datetime_to_context=True,
            add_history_to_context=True,
            num_history_runs=5,
            markdown=True,
            enable_agentic_memory=True,
        )
    return agents
