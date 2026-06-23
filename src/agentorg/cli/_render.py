"""CLI commands for rendering projects."""

from pathlib import Path

import click

from agentorg.core import render as _render

_TEMPLATES = ['full', 'frontend', 'backend', 'ai']


@click.command()
@click.argument(
    'spec_path',
    required=False,
    type=click.Path(exists=True, dir_okay=False, file_okay=True, path_type=Path),
)
@click.option(
    '--output',
    default='output',
    type=click.Path(file_okay=False, path_type=Path),
    help='Output directory.',
)
@click.option(
    '--template',
    default='full',
    type=click.Choice(_TEMPLATES),
    show_default=True,
    help=(
        'Which shipped template to render. `full` is the complete project; '
        '`frontend` / `backend` / `ai` are partials that emit a runnable, testable '
        'mini-project scoped to one layer.'
    ),
)
def render(spec_path: Path | None, output: Path, template: str) -> None:
    """Render a project from a specification file."""
    target = spec_path or Path.cwd() / 'spec.py'
    if not target.exists():
        msg = f'No spec at {target}'
        raise click.ClickException(msg)
    _render(target, output, template=template)
    click.echo(f'Rendered ({template}) into {output}')
