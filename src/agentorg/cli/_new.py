"""CLI command for the interactive master-agent interview that produces a spec.py."""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

import click

from agentorg.master import (
    DEFAULT_DRAFT_PATH,
    build_master_agent,
    load_draft,
    reset_state,
    save_draft,
)


def _make_autosave(draft: Path) -> Callable[[], Awaitable[None]]:
    """Build an async post-hook that snapshots the working spec to `draft` after each turn."""

    async def autosave() -> None:
        save_draft(draft)

    return autosave


@click.command()
@click.option(
    '--resume/--no-resume',
    default=False,
    help='Resume from the saved draft at ~/.agentorg/draft.json instead of starting fresh.',
)
@click.option(
    '--draft',
    default=str(DEFAULT_DRAFT_PATH),
    type=click.Path(path_type=Path),
    help='Path used for autosave of the in-progress draft.',
)
def new(resume: bool, draft: Path) -> None:
    """Interview the user to assemble an agentorg spec.py."""
    if resume and draft.exists():
        load_draft(draft)
        click.echo(f'Resumed draft from {draft}.')
    else:
        reset_state()

    agent = build_master_agent()
    agent.post_hooks = [_make_autosave(draft)]
    asyncio.run(agent.acli_app(user='You', emoji=':robot:', markdown=True))
