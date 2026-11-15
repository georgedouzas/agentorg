"""CLI command for the browser-based master agent UI."""

import webbrowser
from pathlib import Path
from threading import Timer

import click

from ..master import (
    DEFAULT_DRAFT_PATH,
    load_draft,
    reset_state,
)
from ..master.ui import LibreChatStack, docker_available
from ..master.ui._server import serve


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
@click.option(
    '--preview/--no-preview',
    default=True,
    help=(
        'Boot the live preview subprocesses (rendered org API + Vite dev server) '
        'alongside the master UI. Disable for CI/headless smoke runs that do not '
        'have uv or npm available.'
    ),
)
@click.option(
    '--chat/--no-chat',
    default=True,
    help='Start LibreChat (needs Docker), where the interview and the preview agents are chatted with.',
)
@click.option(
    '--librechat-dir',
    default=str(Path.home() / '.agentorg' / 'librechat'),
    type=click.Path(path_type=Path),
    help='Where the LibreChat stack keeps its configuration and secrets.',
)
def ui(
    *,
    host: str,
    port: int,
    resume: bool,
    draft: Path,
    open_browser: bool,
    preview: bool,
    chat: bool,
    librechat_dir: Path,
) -> None:
    """Run the master interview: LibreChat for the conversation, a browser page for the live preview."""
    if chat and not docker_available():
        msg = 'Docker is required: the interview runs in LibreChat, which needs MongoDB and Meilisearch containers.'
        raise click.ClickException(msg)
    if resume and draft.exists():
        load_draft(draft)
        click.echo(f'Resumed draft from {draft}.')
    else:
        reset_state()

    url = f'http://{host}:{port}/'
    click.echo(f'AgentOrg UI: {url}  (Ctrl-C to stop)')
    if not chat:
        if open_browser:
            Timer(0.8, lambda: webbrowser.open(url)).start()
        serve(host=host, port=port, draft_path=draft, preview_enabled=preview)
        return
    stack = LibreChatStack(librechat_dir)
    stack.prepare(master_port=port, preview_port=port + 1)
    click.echo('Starting LibreChat...')
    stack.up()
    click.echo(f'Chat: {stack.url}  (pick the AgentOrg model)')
    if open_browser:
        Timer(3.0, lambda: webbrowser.open(stack.url)).start()
    try:
        serve(
            host=host,
            port=port,
            draft_path=draft,
            preview_enabled=preview,
            chat_api_key=stack.chat_api_key,
            chat_url=stack.url,
        )
    finally:
        stack.down()
