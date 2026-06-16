"""CLI command for the interactive master-agent interview that produces a spec.py."""

import asyncio
from pathlib import Path

import click

from agentorg.master import (
    DEFAULT_DRAFT_PATH,
    build_master_agent,
    finalize_spec,
    load_draft,
    reset_state,
    save_draft,
)


@click.command()
@click.option(
    '--output',
    default='spec.py',
    type=click.Path(file_okay=True, dir_okay=False, path_type=Path),
    help='Where to write the final spec.py.',
)
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
def new(output: Path, resume: bool, draft: Path) -> None:
    """Interview the user to assemble an agentorg spec.py."""
    if resume and draft.exists():
        load_draft(draft)
        click.echo(f'Resumed draft from {draft}.')
    else:
        reset_state()
    agent = build_master_agent()
    asyncio.run(_chat_loop(agent, output=output, draft=draft))


async def _chat_loop(agent: object, *, output: Path, draft: Path) -> None:
    click.echo("I'll help you build an agentorg spec. Type your answers; Ctrl-D or 'quit' to exit.")
    while True:
        try:
            message = click.prompt('You', prompt_suffix='> ', default='', show_default=False)
        except (EOFError, click.Abort):
            click.echo()
            break
        if message.strip().lower() in {'quit', 'exit'}:
            break
        if not message.strip():
            continue
        result = await agent.arun(message)  # type: ignore[attr-defined]
        click.echo(f'Master> {result.content}')
        save_draft(draft)
        if 'Wrote ' in (result.content or ''):
            finalize_spec(output)
            click.echo(f'Final spec written to {output}.')
            break
