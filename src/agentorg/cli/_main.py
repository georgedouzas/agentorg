"""The agentorg command group and subcommand wiring."""

import click

from ._new import new
from ._render import render


@click.group()
@click.version_option(package_name='agentorg')
def main() -> None:
    """Agentorg: Generate runnable multi-agent organisations."""

main.add_command(new)
main.add_command(render)
