"""Seed Spec used at the start of the interview."""

from agentorg.core.spec import (
    AI,
    UI,
    AppUI,
    EmptyState,
    EnvVars,
    Infra,
    Knowledge,
    Org,
    Principles,
    Runtime,
    Spec,
)

PLACEHOLDER = 'TODO'
PLACEHOLDER_NAME = 'My Org'
PLACEHOLDER_SLUG = 'my-org'
PLACEHOLDER_PACKAGE = 'my_org'
PLACEHOLDER_EMAIL = 'author@example.com'
PLACEHOLDER_ICON = 'robot'
PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {PLACEHOLDER, PLACEHOLDER_NAME, PLACEHOLDER_SLUG, PLACEHOLDER_PACKAGE, PLACEHOLDER_EMAIL, PLACEHOLDER_ICON},
)


def default_spec() -> Spec:
    """Build a validated `Spec` whose required string fields all carry recognisable placeholders."""
    return Spec(
        org=Org(
            name=PLACEHOLDER_NAME,
            slug=PLACEHOLDER_SLUG,
            package_name=PLACEHOLDER_PACKAGE,
            description=PLACEHOLDER,
            repository=PLACEHOLDER,
            author_name=PLACEHOLDER,
            author_email=PLACEHOLDER_EMAIL,
            visibility='private',
        ),
        runtime=Runtime(
            infra=Infra(
                packaging='none',
                database='sqlite',
                vector_db='chromadb',
                embedder='google:gemini-embedding-001',
                api='none',
                frontend='none',
                auth='none',
            ),
            env_vars=EnvVars(required=[], optional=[]),
            setup=[],
        ),
        ai=AI(agents=[], teams=[], workflows=[]),
        parameters=[],
        knowledge=Knowledge(principles=Principles(sections=[]), types=[]),
        ui=UI(
            app=AppUI(name=PLACEHOLDER_NAME, icon=PLACEHOLDER_ICON, description=PLACEHOLDER),
            empty_state=EmptyState(icon=PLACEHOLDER_ICON, title=PLACEHOLDER, body=PLACEHOLDER),
            knowledge_empty=PLACEHOLDER,
            agent_groups=[],
            workflow_groups=[],
            featured_agents=[],
            agent_icons={},
            overview=[],
            agent_configs={},
            chat_quick_prompts={},
        ),
    )
