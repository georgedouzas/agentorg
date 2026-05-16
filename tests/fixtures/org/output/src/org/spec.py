"""Spec for the `org` fixture — a tiny research team.

Two custom agents (`researcher`, `analyst`), one pipeline workflow, one coordinate team, plus the six platform agents.
"""

from agno.agent import Agent
from agno.team import Team
from agno.workflow import Step, Workflow

from agentorg.core.instructions import compose
from agentorg.core.knowledge import list_knowledge, read_knowledge, write_knowledge
from agentorg.core.spec import AI, PLATFORM_AGENTS, Org, Spec

_MODEL = 'google:gemini-2.5-flash'


async def write_research_doc(name: str, title: str, content: str, metadata: dict | None = None) -> str:
    """Save a research document (sources-cited, drafted by the researcher)."""
    return await write_knowledge(type='research', name=name, title=title, content=content, metadata=metadata)


async def read_research_doc(name: str) -> str:
    """Read a research document by name."""
    return await read_knowledge(type='research', name=name)


async def list_research_docs(metadata_filter: dict | None = None) -> str:
    """List all research documents."""
    return await list_knowledge(type='research', metadata_filter=metadata_filter)


async def write_agent_report(name: str, title: str, content: str, metadata: dict | None = None) -> str:
    """Save the analyst's final report."""
    return await write_knowledge(type='report', name=name, title=title, content=content, metadata=metadata)


_RESEARCH_STYLE = (
    'Be concise. A direct answer beats an explanation of the answer.',
    'Do not restate your own role or these rules back to the user.',
    'Principles parameters are already configured — do not ask the user for them.',
    'Do not narrate tool calls, retries, or tool failures in your reply — the UI shows them as badges.',
)

researcher = Agent(
    id='researcher',
    name='Researcher',
    role='Gather source material on a topic and write a structured research document.',
    model=_MODEL,
    tools=[write_research_doc, read_research_doc, list_research_docs],
    instructions=compose(
        role='Gather source material on a topic and write a structured research document.',
        when_to_act=(
            'Greetings or unclear messages: reply briefly and ask for a research topic.',
            'A concrete topic from the user: run the workflow.',
        ),
        style=_RESEARCH_STYLE,
        in_scope=(
            'Gathering primary sources on a topic',
            'Drafting research docs with Background / Findings / Sources sections',
            'Saving research docs to knowledge (only when asked or when proposing it explicitly)',
        ),
        out_of_scope=(('Final synthesis and recommendations', 'Analyst'),),
        workflow=(
            'Restate the topic in one short sentence.',
            'Gather at least the configured minimum number of sources.',
            'Draft a research doc with sections: Background, Findings, Sources, in the chat reply.',
            'Do **not** auto-save. Only call `write_research_doc` when the user explicitly asks '
            'to save / store / persist the doc. If the doc is unusually thorough or load-bearing, '
            'end with a one-line proposal: `Want me to save this to knowledge?`',
        ),
        tools=('write_research_doc', 'read_research_doc', 'list_research_docs'),
    ),
)


analyst = Agent(
    id='analyst',
    name='Analyst',
    role='Synthesise existing research docs into a structured analysis report.',
    model=_MODEL,
    tools=[read_research_doc, list_research_docs, write_agent_report],
    instructions=compose(
        role='Synthesise existing research docs into a structured analysis report.',
        when_to_act=(
            'Greetings or unclear messages: reply briefly and ask which topic to analyse.',
            'A concrete topic with existing research docs: run the workflow.',
            'No research docs for the requested topic: say so once and stop — do not repeat on follow-up turns.',
        ),
        style=_RESEARCH_STYLE,
        in_scope=(
            'Reading research docs by topic',
            'Drafting analysis reports with Overview / Findings / Implications / Open Questions',
            'Saving reports to knowledge (only when asked or when proposing it explicitly)',
        ),
        out_of_scope=(('Primary source gathering', 'Researcher'),),
        workflow=(
            'List the available research docs on the topic.',
            'Read the most relevant ones.',
            'Draft a report with sections: Overview, Findings, Implications, Open Questions, in the chat reply.',
            'Do **not** auto-save. Only call `write_agent_report` when the user explicitly asks '
            'to save / store / persist the report. If the report flags strong implications or '
            'critical open questions, end with a one-line proposal: `Want me to save this to knowledge?`',
        ),
        tools=('read_research_doc', 'list_research_docs', 'write_agent_report'),
    ),
)


research_team = Team(
    id='research-team',
    name='Research Team',
    members=[researcher, analyst],
    mode='coordinate',
    model=_MODEL,
)


research_pipeline = Workflow(
    id='research-pipeline',
    name='Research Pipeline',
    steps=[
        Step(name='Gather', agent=researcher),
        Step(name='Analyse', agent=analyst, requires_output_review=True),
    ],
)


spec = Spec(
    org=Org(
        name='Research Organisation',
        slug='org',
        package_name='org',
        description='Small research team that gathers sources and publishes structured analysis reports.',
        repository='https://github.com/example/org',
        author_name='Agentorg Authors',
        author_email='agentorg@example.com',
        visibility='private',
    ),
    runtime={
        'infra': {
            'packaging': 'none',
            'database': 'sqlite',
            'vector_db': 'chromadb',
            'embedder': 'google:gemini-embedding-001',
            'api': 'none',
            'frontend': 'none',
            'auth': 'none',
        },
        'env_vars': {
            'required': [{'name': 'GOOGLE_API_KEY', 'description': 'Gemini API key.', 'required_label': 'Prod'}],
            'optional': [
                {'name': 'RUNTIME_ENV', 'description': 'Set to `dev` for uvicorn auto-reload.', 'required_label': 'Dev'},
            ],
        },
        'setup': [
            {
                'id': 'secrets',
                'title': 'Set GOOGLE_API_KEY in .env',
                'description': (
                    'Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) '
                    'and add it to your `.env`:\n\n```sh\nGOOGLE_API_KEY=your-key-here\n```'
                ),
                'variables': ['GOOGLE_API_KEY'],
            },
        ],
    },
    ai=AI(
        agents=[*PLATFORM_AGENTS, researcher, analyst],
        teams=[research_team],
        workflows=[research_pipeline],
    ),
    knowledge={
        'principles': {
            'parameters': [
                {
                    'name': 'domain_focus',
                    'type': 'string',
                    'default': 'Applied Research',
                    'label': 'Domain Focus',
                    'format': None,
                },
                {
                    'name': 'min_sources',
                    'type': 'int',
                    'default': 3,
                    'label': 'Minimum Sources',
                    'format': None,
                },
            ],
            'sections': [
                {
                    'id': 'mission',
                    'title': 'Mission',
                    'body': (
                        '- Focus area: {domain_focus}\n'
                        '- Every research doc cites at least {min_sources} sources.\n'
                        '- Reports are structured around Overview, Findings, Implications, and Open Questions.'
                    ),
                },
                {
                    'id': 'process',
                    'title': 'Process',
                    'body': (
                        '- Researcher gathers material and writes research docs.\n'
                        '- Analyst synthesises research into a final report.\n'
                        '- Both auto-save their outputs.'
                    ),
                },
            ],
        },
        'types': [
            {'id': 'research', 'label': 'Research Docs', 'metadata_fields': []},
            {'id': 'report', 'label': 'Analyst Reports', 'metadata_fields': []},
        ],
    },
    ui={
        'app': {
            'name': 'Org',
            'icon': '🔬',
            'description': 'Small research team for testing the agentorg renderer end-to-end.',
        },
        'empty_state': {
            'icon': '🔬',
            'title': 'Pick an agent or workflow',
            'body': 'Try the research pipeline or chat directly with the analyst.',
        },
        'knowledge_empty': 'No knowledge yet, run the researcher first.',
        'agent_groups': [{'label': 'Research Team', 'ids': ['researcher', 'analyst']}],
        'workflow_groups': [{'label': 'Pipelines', 'ids': ['research-pipeline']}],
        'featured_agents': ['analyst'],
        'agent_icons': {'researcher': '📚', 'analyst': '🧪'},
        'overview': [
            {
                'title': 'How this org works',
                'body': (
                    'The **Researcher** gathers sources on a topic and writes a research doc. '
                    'The **Analyst** then reads the docs and publishes a structured analysis '
                    'report with implications and open questions.'
                ),
            },
        ],
        'agent_configs': {},
        'chat_quick_prompts': {},
    },
)
