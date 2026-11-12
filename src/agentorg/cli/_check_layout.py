"""CLI command for checking the test layout."""

from pathlib import Path

import click

from ..core.quality import find_layout_violations


@click.command(name='check-layout')
@click.argument('project_root', default='.', type=click.Path(exists=True, file_okay=False, path_type=Path))
def check_layout(project_root: Path) -> None:
    """Check that the test tree mirrors the source tree."""
    violations = find_layout_violations(project_root)
    for violation in violations:
        click.echo(violation, err=True)
    if violations:
        msg = f'{len(violations)} test layout violation(s); add the missing tests or declare exemptions.'
        raise click.ClickException(msg)
    click.echo('Test layout OK')
