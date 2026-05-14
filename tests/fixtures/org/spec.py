"""Spec for the `org` fixture — a tiny research team.

Two custom agents (`researcher`, `analyst`), one pipeline workflow, one coordinate team.
The six platform agents are populated automatically by `Spec`'s default factory.
"""

from agno.agent import Agent
from agno.team import Team
from agno.workflow import Step, Workflow

from agentorg.core.spec import PLATFORM_AGENTS, Org, Spec
from agentorg.core.tools.knowledge import list_knowledge, read_knowledge, write_knowledge

_MODEL = 'google:gemini-2.0-flash'


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


researcher = Agent(
    id='researcher',
    name='Researcher',
    role='Gather source material on a topic and write a structured research document.',
    model=_MODEL,
    tools=[write_research_doc, read_research_doc, list_research_docs],
    instructions=(
        'You are the Researcher.\n\n'
        '## Workflow\n'
        '1. Restate the topic in one paragraph.\n'
        '2. Gather at least the configured minimum number of sources.\n'
        '3. Draft a research doc with sections: Background, Findings, Sources.\n'
        '4. Auto-save with `write_research_doc`.\n\n'
        '## Out of scope\n'
        '- Final synthesis and recommendations → **Analyst**.\n'
    ),
)


analyst = Agent(
    id='analyst',
    name='Analyst',
    role='Synthesise existing research docs into a structured analysis report.',
    model=_MODEL,
    tools=[read_research_doc, list_research_docs, write_agent_report],
    instructions=(
        'You are the Analyst.\n\n'
        '## Workflow\n'
        '1. List the available research docs on the topic.\n'
        '2. Read the most relevant ones.\n'
        '3. Draft a report with sections: Overview, Findings, Implications, Open Questions.\n'
        '4. Auto-save with `write_agent_report`.\n\n'
        '## Out of scope\n'
        '- Primary source gathering → **Researcher**.\n'
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
                'vars': ['GOOGLE_API_KEY'],
                'command': None,
                'platform': None,
            },
        ],
    },
    agents=[*PLATFORM_AGENTS, researcher, analyst],
    teams=[research_team],
    workflows=[research_pipeline],
    charter={
        'parameters': [
            {'name': 'domain_focus', 'type': 'string', 'default': 'applied research', 'label': 'Domain Focus'},
            {'name': 'min_sources', 'type': 'int', 'default': 3, 'label': 'Min Sources per Research Doc'},
        ],
        'sections': [
            {
                'id': 'charter',
                'title': 'Charter',
                'body': (
                    '## Mission\n'
                    '- Focus area: {domain_focus}\n'
                    '- Every research doc cites at least {min_sources} sources.\n'
                    '- Reports are structured: Overview, Findings, Implications, Open Questions.'
                ),
            },
            {
                'id': 'process',
                'title': 'Process',
                'body': (
                    '1. Researcher gathers material and writes research docs.\n'
                    '2. Analyst synthesises research into a final report.\n'
                    '3. Both auto-save their outputs.'
                ),
            },
        ],
    },
    documents={
        'types': [
            {'id': 'research', 'label': 'Research Docs'},
            {'id': 'report', 'label': 'Analyst Reports'},
        ],
    },
    agent_groups=[{'label': 'Research Team', 'ids': ['researcher', 'analyst']}],
    workflow_groups=[{'label': 'Pipelines', 'ids': ['research-pipeline']}],
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
        'knowledge_empty': {
            'documents': 'No knowledge yet — run the researcher first.',
            'learnings': 'No learnings accumulated yet.',
        },
        'featured_agents': ['analyst'],
        'agent_icons': {'researcher': '📚', 'analyst': '🧪'},
    },
)
