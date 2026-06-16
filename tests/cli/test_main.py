"""Tests for the main module."""

from click.testing import CliRunner

from agentorg.cli import main


def test_main_help_lists_the_render_subcommand():
    """`agentorg --help` mentions the `render` subcommand so users discover it."""
    runner = CliRunner()
    result = runner.invoke(main, ['--help'])
    assert result.exit_code == 0
    assert 'render' in result.output


def test_main_version_prints_a_version_string():
    """`agentorg --version` is wired and prints something containing `version`."""
    runner = CliRunner()
    result = runner.invoke(main, ['--version'])
    assert result.exit_code == 0
    assert 'version' in result.output.lower()


def test_main_with_no_args_shows_help():
    """`agentorg` with no args exits cleanly with the group help (click's default for command groups)."""
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert 'render' in result.output
