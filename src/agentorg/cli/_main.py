"""User-facing CLI."""

import click

from ._render import render


@click.group()
@click.version_option(package_name='agentorg')
def main() -> None:
    """Agentorg: Generate runnable multi-agent organisations."""

main.add_command(render)
