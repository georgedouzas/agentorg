"""Shared template that composes an agent's instructions from a standard set of sections."""

from collections.abc import Iterable

# Default "When to act" bullets every agent inherits unless the spec overrides them.
DEFAULT_WHEN_TO_ACT: tuple[str, ...] = (
    'Greetings or unclear messages: reply briefly and ask for a concrete request.',
    'Requests outside your scope (see below): decline and refer to the named agent.',
    'Concrete in-scope requests: run the workflow.',
)


# One-line descriptions rendered under each section heading, before its bullets.
SECTION_INTROS: dict[str, str] = {
    'role': 'What this agent does.',
    'when_to_act': 'When this agent engages versus stays quiet.',
    'style': 'Tone and format rules for every response.',
    'in_scope': 'Topics this agent owns.',
    'out_of_scope': 'Topics this agent declines, and the peer to refer to.',
    'workflow': 'Steps this agent follows for an in-scope request.',
    'principles': 'Org-wide rules every agent follows, drawn from the principles.',
}


def _section(heading: str, intro: str, bullets: Iterable[str]) -> list[str]:
    return [f'## {heading}', f'_{intro}_', '', *bullets, '']


def compose(
    *,
    role: str,
    when_to_act: Iterable[str],
    style: Iterable[str],
    in_scope: Iterable[str],
    out_of_scope: Iterable[tuple[str, str]],
    workflow: Iterable[str],
) -> str:
    """Compose an agent's instructions from the standard six-section template.

    Every section is mandatory: `Role`, `When to act`, `Style`, `In scope`, `Out of scope`, `Workflow`.
    Each section opens with a one-line description; lists are bulleted (no enumeration).
    The runtime appends a final `Principles` section with the org's principles at boot.
    """
    parts: list[str] = []
    parts += _section('Role', SECTION_INTROS['role'], [role.strip()])
    parts += _section('When to act', SECTION_INTROS['when_to_act'], [f'- {x}' for x in when_to_act])
    parts += _section('Style', SECTION_INTROS['style'], [f'- {x}' for x in style])
    parts += _section('In scope', SECTION_INTROS['in_scope'], [f'- {x}' for x in in_scope])
    parts += _section('Out of scope', SECTION_INTROS['out_of_scope'], [f'- {t} → **{r}**' for t, r in out_of_scope])
    parts += _section('Workflow', SECTION_INTROS['workflow'], [f'- {x}' for x in workflow])
    return '\n'.join(parts).rstrip() + '\n'


def append_principles(instructions: str, principles: str) -> str:
    """Append the org's principles to an agent's instructions under a `## Principles` heading."""
    base = (instructions or '').rstrip()
    body = (principles or '').strip()
    if not body:
        return base
    return f'{base}\n\n## Principles\n_{SECTION_INTROS["principles"]}_\n\n{body}\n'
