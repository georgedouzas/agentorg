"""Spec for the `org` fixture — a tiny research team.

Two custom agents (`researcher`, `analyst`), one pipeline workflow, one coordinate team.
The six platform agents are populated automatically by `Spec`'s default factory.
"""

from agentorg.core.schema import (
    Agent,
    AppUI,
    Charter,
    CharterParameter,
    CharterSection,
    DocumentType,
    EmptyState,
    EnvVar,
    EnvVars,
    Generated,
    GroupRef,
    KnowledgeEmpty,
    Org,
    PLATFORM_AGENTS,
    SaveRule,
    ScopeRef,
    Setup,
    SetupStep,
    Spec,
    Step,
    StepRouteHitl,
    Team,
    UI,
    Workflow,
)
from agentorg.core.tools.knowledge import (
    list_knowledge,
    read_knowledge,
    write_knowledge,
)


def write_research_doc(name: str, title: str, content: str, metadata: dict | None = None) -> str:
    """Save a research document (sources-cited, drafted by the researcher)."""
    return write_knowledge(type='research', name=name, title=title, content=content, metadata=metadata)


def read_research_doc(name: str) -> str:
    """Read a research document by name."""
    return read_knowledge(type='research', name=name)


def list_research_docs(metadata_filter: dict | None = None) -> str:
    """List all research documents."""
    return list_knowledge(type='research', metadata_filter=metadata_filter)


def write_agent_report(name: str, title: str, content: str, metadata: dict | None = None) -> str:
    """Save the analyst's final report."""
    return write_knowledge(type='report', name=name, title=title, content=content, metadata=metadata)


_DOMAIN_REFS = [
    ScopeRef(topic='Final synthesis and recommendations', refer_to='Analyst'),
]


researcher = Agent(
    id='researcher',
    name='Researcher',
    role='Gather source material on a topic and write a structured research document.',
    tools=[write_research_doc, read_research_doc, list_research_docs],
    in_scope=['Topic scoping', 'Source gathering', 'Drafting research docs', 'Citing sources inline'],
    out_of_scope=_DOMAIN_REFS,
    workflow=[
        'Restate the topic in one paragraph.',
        'Gather at least the configured minimum number of sources.',
        'Draft a research doc with sections: Background, Findings, Sources.',
        'Auto-save with `write_research_doc`.',
    ],
    save_rule=SaveRule(
        tool='write_research_doc',
        name_pattern='snake_case slug for the topic — no count, no date',
        title_pattern='Title Case with spaces — no count, no date',
    ),
)


analyst = Agent(
    id='analyst',
    name='Analyst',
    role=(
        'Synthesise existing research docs into a structured analysis report with implications and '
        'open questions.'
    ),
    tools=[read_research_doc, list_research_docs, write_agent_report],
    learning=True,
    in_scope=[
        'Reading research docs',
        'Cross-referencing findings',
        'Drafting analysis reports',
        'Surfacing implications and open questions',
    ],
    out_of_scope=[ScopeRef(topic='Primary source gathering', refer_to='Researcher')],
    workflow=[
        'List the available research docs on the topic.',
        'Read the most relevant ones.',
        'Draft a report with sections: Overview, Findings, Implications, Open Questions.',
        'Auto-save with `write_agent_report`.',
    ],
    save_rule=SaveRule(
        tool='write_agent_report',
        name_pattern='snake_case slug — no count, no date',
        title_pattern='Title Case with spaces — no count, no date',
    ),
)


spec = Spec(
    infra='local',
    workflow_architecture='pipeline',
    team_architecture='coordinate',
    org=Org(
        name='Research Organisation',
        slug='org',
        package_name='org',
        domain='applied research',
        description=(
            'Small research team that gathers source material, synthesises findings, and publishes '
            'structured analysis reports.'
        ),
        repository='https://github.com/example/org',
        author_name='Agentorg Authors',
        author_email='agentorg@example.com',
        visibility='private',
    ),
    generated=Generated(
        agents=[*PLATFORM_AGENTS, researcher, analyst],
        teams=[
            Team(
                id='research-team',
                name='Research Team',
                description=(
                    'Two-agent unit that owns the full path from raw sources to a published analysis report. '
                    "The analyst coordinates: it decides what's worth synthesising and pulls in the researcher "
                    'when more primary material is needed.'
                ),
                leader='analyst',
                members=['researcher'],
            ),
        ],
        workflows=[
            Workflow(
                id='research-pipeline',
                name='Research Pipeline',
                description='Sequential pipeline: researcher gathers material, then analyst publishes a report.',
                steps=[
                    Step(name='Gather', agent='researcher'),
                    Step(
                        name='Analyse',
                        agent='analyst',
                        hitl=StepRouteHitl(type='output_review', message='Approve the analysis report?'),
                    ),
                ],
            ),
        ],
        charter=Charter(
            parameters=[
                CharterParameter(name='domain_focus', type='string', default='applied research', label='Domain Focus'),
                CharterParameter(name='min_sources', type='int', default=3, label='Min Sources per Research Doc'),
            ],
            sections=[
                CharterSection(
                    id='charter',
                    title='Charter',
                    body=(
                        '## Mission\n'
                        '- Focus area: {domain_focus}\n'
                        '- Every research doc cites at least {min_sources} sources.\n'
                        '- Reports are structured: Overview, Findings, Implications, Open Questions.'
                    ),
                ),
                CharterSection(
                    id='process',
                    title='Process',
                    body=(
                        '1. Researcher gathers material and writes research docs.\n'
                        '2. Analyst synthesises research into a final report.\n'
                        '3. Both auto-save their outputs.'
                    ),
                ),
            ],
        ),
        documents={
            'types': [
                DocumentType(id='research', label='Research Docs'),
                DocumentType(id='report', label='Analyst Reports'),
            ],
        },
        agent_groups=[GroupRef(label='Research Team', ids=['researcher', 'analyst'])],
        workflow_groups=[GroupRef(label='Pipelines', ids=['research-pipeline'])],
        ui=UI(
            app=AppUI(
                name='Org',
                icon='🔬',
                description='Small research team for testing the agentorg renderer end-to-end.',
            ),
            empty_state=EmptyState(
                icon='🔬',
                title='Pick an agent or workflow',
                body='Try the research pipeline or chat directly with the analyst.',
            ),
            knowledge_empty=KnowledgeEmpty(
                documents='No knowledge yet — run the researcher first.',
                learnings='No learnings accumulated yet.',
            ),
            featured_agents=['analyst'],
            agent_icons={'researcher': '📚', 'analyst': '🧪'},
        ),
        env_vars=EnvVars(
            required=[EnvVar(name='GOOGLE_API_KEY', description='Gemini API key.')],
            optional=[EnvVar(name='RUNTIME_ENV', description='Set to `dev` for uvicorn auto-reload.')],
        ),
    ),
    setup=Setup(steps=[SetupStep(id='secrets', title='Set GOOGLE_API_KEY in .env', vars=['GOOGLE_API_KEY'])]),
)
