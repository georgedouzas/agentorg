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
    'config',
    type=click.Path(exists=True, dir_okay=True, file_okay=False, path_type=Path),
)
@click.option(
    '--out',
    default='out',
    type=click.Path(file_okay=False, path_type=Path),
    help='Output directory (default: ./out).',
)
def render(config: Path, out: Path) -> None:
    """Render a project from a spec directory into OUT.

    CONFIG is a directory containing `agentorg.json` and optionally a `tools/` directory.
    """
    _render(config, out)
    click.echo(f'Rendered into {out}')


if __name__ == '__main__':
    cli()
