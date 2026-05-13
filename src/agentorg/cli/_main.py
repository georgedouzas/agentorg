"""User-facing CLI."""

from pathlib import Path

import click

from agentorg.core import render


@click.group()
@click.version_option(package_name='agentorg')
def cli() -> None:
    """Agentorg: Generate runnable multi-agent organisations from a Python `spec.py`."""


@cli.command(name='render')
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
def render_project(spec_path: Path | None, output: Path) -> None:
    """Render a project from a `spec.py` file (defaults to `./spec.py`)."""
    target = spec_path or Path.cwd() / 'spec.py'
    if not target.exists():
        msg = f'No spec at {target}'
        raise click.ClickException(msg)
    render(target, output)
    click.echo(f'Rendered into {output}')


if __name__ == '__main__':
    cli()
