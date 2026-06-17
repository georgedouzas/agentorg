"""The agentorg command group and subcommand wiring."""

import click

from ._new import new
from ._render import render
from ._ui import ui


@click.group()
@click.version_option(package_name='agentorg')
def main() -> None:
    """Agentorg: Generate runnable multi-agent organisations."""

main.add_command(new)
main.add_command(render)
main.add_command(ui)
