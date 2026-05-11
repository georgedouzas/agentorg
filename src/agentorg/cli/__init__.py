"""User-facing CLI: `agentorg <subcommand>`."""

from pathlib import Path

import click

from agentorg.render import render as _render


@click.group()
@click.version_option(package_name='agentorg')
def cli() -> None:
    """Agentorg — generate runnable multi-agent organisations from a single agentorg.json spec."""


@cli.command()
@click.argument(
    'source',
    type=click.Path(exists=True, dir_okay=False, file_okay=True, path_type=Path),
)
@click.option(
    '--out',
    default='out',
    type=click.Path(file_okay=False, path_type=Path),
    help='Output directory (default: ./out).',
)
def render(source: Path, out: Path) -> None:
    """Render a project from agentorg.json into OUT.

    SOURCE is the path to agentorg.json.
    """
    _render(source, out)
    click.echo(f'Rendered into {out}')


if __name__ == '__main__':
    cli()
