"""Proxies for the project's nox-based development tasks.

These are wired up as console scripts in `pyproject.toml` so contributors can run `uv run formatting`, `uv run tests`,
etc. They are not part of the user-facing CLI.
"""

import subprocess
import sys
from functools import partial


def _run(session: str) -> None:
    """Run a nox session with any extra args forwarded."""
    args = ['nox', '--default-venv-backend', 'uv', '--error-on-external-run', '-R', '-s', session]
    if sys.argv[1:]:
        args.extend(['--', *sys.argv[1:]])
    subprocess.run(args, check=False)  # noqa: S603


formatting = partial(_run, 'formatting')
checks = partial(_run, 'checks')
tests = partial(_run, 'tests')
docs = partial(_run, 'docs')
changelog = partial(_run, 'changelog')
release = partial(_run, 'release')
clean = partial(_run, 'clean')
