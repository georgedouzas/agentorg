"""CLI command for the browser-based master agent UI."""

import webbrowser
from pathlib import Path
from threading import Timer

import click

from agentorg.master import (
    DEFAULT_DRAFT_PATH,
    load_draft,
    reset_state,
)
from agentorg.master.ui._server import serve


@click.command()
@click.option(
    '--host',
    default='127.0.0.1',
    show_default=True,
    help='Bind address. Defaults to localhost only.',
)
@click.option(
    '--port',
    default=8765,
    show_default=True,
    type=int,
    help='Bind port.',
)
@click.option(
    '--resume/--no-resume',
    default=False,
    help='Resume from the saved draft instead of starting fresh.',
)
@click.option(
    '--draft',
    default=str(DEFAULT_DRAFT_PATH),
    type=click.Path(path_type=Path),
    help='Path used for autosave of the in-progress draft.',
)
@click.option(
    '--open-browser/--no-open-browser',
    default=True,
    help='Open the default browser to the UI on startup.',
)
def ui(host: str, port: int, resume: bool, draft: Path, open_browser: bool) -> None:
    """Run the browser-based master interview UI."""
    if resume and draft.exists():
        load_draft(draft)
        click.echo(f'Resumed draft from {draft}.')
    else:
        reset_state()

    url = f'http://{host}:{port}/'
    click.echo(f'AgentOrg UI: {url}  (Ctrl-C to stop)')
    if open_browser:
        Timer(0.8, lambda: webbrowser.open(url)).start()
    serve(host=host, port=port, draft_path=draft)
