"""CLI commands for rendering projects."""

from pathlib import Path

import click

from agentorg.core import render as _render


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
def render(spec_path: Path | None, output: Path) -> None:
    """Render a project from a specification file."""
    target = spec_path or Path.cwd() / 'spec.py'
    if not target.exists():
        msg = f'No spec at {target}'
        raise click.ClickException(msg)
    _render(target, output)
    click.echo(f'Rendered into {output}')
