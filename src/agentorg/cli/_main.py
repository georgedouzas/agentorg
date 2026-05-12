"""User-facing CLI."""

from pathlib import Path

import click

from agentorg.core import render


@click.group()
@click.version_option(package_name='agentorg')
def cli() -> None:
    """Agentorg: Generate runnable multi-agent organisations from a single agentorg.json spec."""


@cli.command(name='render')
@click.argument(
    'config',
    type=click.Path(exists=True, dir_okay=True, file_okay=False, path_type=Path),
)
@click.option(
    '--output',
    default='output',
    type=click.Path(file_okay=False, path_type=Path),
    help='Output directory.',
)
def render_project(config: Path, output: Path) -> None:
    """Render a project from a spec directory into output directory."""
    render(config, output)
    click.echo(f'Rendered into {output}')


if __name__ == '__main__':
    cli()
