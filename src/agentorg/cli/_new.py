"""CLI command for the interactive master-agent interview that produces a spec.py."""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from agentorg.master import (
    DEFAULT_DRAFT_PATH,
    MASTER_INTRODUCTION,
    STAGE_LABELS,
    STAGES,
    advance,
    agent_for_current_stage,
    get_state,
    load_draft,
    reset_state,
    save_draft,
    stage_summary,
)


def _stage_banner(console: Console) -> None:
    """Print a one-line stage banner: `Stage 1/6 — Discover    Next: enabled`."""
    state = get_state()
    summary = stage_summary(state)
    stage = state.stage
    idx = STAGES.index(stage) + 1
    label = STAGE_LABELS[stage]
    if summary['next_enabled']:
        next_marker = Text('  Next: enabled', style='green')
    else:
        blockers = summary['next_blockers']
        why = blockers[0] if isinstance(blockers, list) and blockers else 'gathering info'
        next_marker = Text(f'  Next: {why}', style='yellow')
    line = Text.assemble(
        Text(f'  Stage {idx}/{len(STAGES)} - {label}', style='cyan bold'),
        next_marker,
    )
    console.print(line)


def _do_advance(console: Console) -> None:
    """Handle the user typing `next` - move the stage forward or report blockers."""
    state = get_state()
    ok, new_stage, blockers = advance(state)
    if ok:
        console.print(f'[green]✓[/green] Advanced to [cyan]{STAGE_LABELS[new_stage]}[/cyan].')
    else:
        console.print('[yellow]Not ready to advance:[/yellow]')
        for b in blockers:
            console.print(f'  • {b}')


async def _interview(draft: Path) -> None:
    """Run the staged interview loop: special commands `next` / `quit`, anything else -> the agent."""
    console = Console()

    while True:
        _stage_banner(console)
        try:
            message = Prompt.ask('[bold]You[/bold]')
        except (EOFError, KeyboardInterrupt):
            console.print('\n[dim]Saving draft and exiting.[/dim]')
            save_draft(draft)
            return

        cmd = message.strip().lower()
        if cmd in {'quit', 'exit', ':q'}:
            save_draft(draft)
            console.print('[dim]Saved. Bye.[/dim]')
            return
        if cmd == 'next':
            _do_advance(console)
            save_draft(draft)
            continue
        if not cmd:
            continue

        # Refetch each turn so a stage transition (via advance_to_next_stage) picks up
        # the next stage's narrowly-scoped agent immediately.
        run_output = await agent_for_current_stage().arun(message)
        content = getattr(run_output, 'content', None) or '(no reply)'
        console.print()
        console.print(Markdown(content))
        console.print()
        save_draft(draft)


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

    console = Console()
    console.print(Panel.fit(MASTER_INTRODUCTION, title='🤖 AgentOrg', border_style='cyan'))
    console.print('[dim]Type `next` to advance stages, `quit` to save and exit.[/dim]\n')

    asyncio.run(_interview(draft))
