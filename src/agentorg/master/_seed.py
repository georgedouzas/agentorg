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

# Friendly seed defaults: the rendered dashboard reads these directly, so they should
# look reasonable from turn 1 instead of literal 'TODO' / 'My Org' / 'robot' strings.
# The master agent's gates still use PLACEHOLDER_VALUES to detect "field is still at its
# seed default" - we just changed *which* string each field defaults to.
PLACEHOLDER = 'Not set yet'
PLACEHOLDER_NAME = 'Untitled org'
PLACEHOLDER_SLUG = 'untitled-org'
PLACEHOLDER_PACKAGE = 'untitled_org'
PLACEHOLDER_EMAIL = 'you@example.com'
PLACEHOLDER_ICON = '🛠'
PLACEHOLDER_DESCRIPTION = 'A new agent organisation in progress.'
PLACEHOLDER_ADMIN_NAME = 'You'
PLACEHOLDER_EMPTY_TITLE = 'Nothing here yet'
PLACEHOLDER_EMPTY_BODY = 'Your org is taking shape — keep chatting with AgentOrg.'
PLACEHOLDER_EMPTY_ICON = '✨'
PLACEHOLDER_KNOWLEDGE_EMPTY = 'No knowledge entries yet.'

# The detection set includes legacy values ('TODO', 'My Org', 'robot', ...) so drafts
# saved by older versions are still recognised as "not yet filled in".
PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {
        PLACEHOLDER,
        PLACEHOLDER_NAME,
        PLACEHOLDER_SLUG,
        PLACEHOLDER_PACKAGE,
        PLACEHOLDER_EMAIL,
        PLACEHOLDER_ICON,
        PLACEHOLDER_DESCRIPTION,
        PLACEHOLDER_ADMIN_NAME,
        PLACEHOLDER_EMPTY_TITLE,
        PLACEHOLDER_EMPTY_BODY,
        PLACEHOLDER_EMPTY_ICON,
        PLACEHOLDER_KNOWLEDGE_EMPTY,
        # Legacy seed values - keep so older saved drafts still register as unfilled.
        'TODO',
        'My Org',
        'my-org',
        'my_org',
        'author@example.com',
        'robot',
    },
)


def default_spec() -> Spec:
    """Build a validated `Spec` whose required string fields all carry recognisable placeholders."""
    return Spec(
        org=Org(
            name=PLACEHOLDER_NAME,
            slug=PLACEHOLDER_SLUG,
            package_name=PLACEHOLDER_PACKAGE,
            description=PLACEHOLDER_DESCRIPTION,
            repository=PLACEHOLDER,
            admin_name=PLACEHOLDER_ADMIN_NAME,
            admin_email=PLACEHOLDER_EMAIL,
            visibility='private',
            budget='medium',
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
            app=AppUI(name=PLACEHOLDER_NAME, icon=PLACEHOLDER_ICON, description=PLACEHOLDER_DESCRIPTION),
            empty_state=EmptyState(
                icon=PLACEHOLDER_EMPTY_ICON,
                title=PLACEHOLDER_EMPTY_TITLE,
                body=PLACEHOLDER_EMPTY_BODY,
            ),
            knowledge_empty=PLACEHOLDER_KNOWLEDGE_EMPTY,
            agent_groups=[],
            workflow_groups=[],
            featured_agents=[],
            agent_icons={},
            overview=[],
            agent_configs={},
            chat_quick_prompts={},
        ),
    )
