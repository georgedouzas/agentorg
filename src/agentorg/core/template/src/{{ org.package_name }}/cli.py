"""CLI proxy functions for development tasks."""

import subprocess  # nosec: B404
import sys
from functools import partial


def _run(session: str) -> None:
    """Run nox session."""
    args = ['nox', '--default-venv-backend', 'uv', '--error-on-external-run', '-R', '-s', session]
    if sys.argv[1:]:
        args.extend(['--', *sys.argv[1:]])
    subprocess.run(args, check=False)  # noqa: S603  # nosec: B603


formatting = partial(_run, 'formatting')
checks = partial(_run, 'checks')
tests = partial(_run, 'tests')
docs = partial(_run, 'docs')
changelog = partial(_run, 'changelog')
build = partial(_run, 'build')
deploy = partial(_run, 'deploy')
clean = partial(_run, 'clean')
