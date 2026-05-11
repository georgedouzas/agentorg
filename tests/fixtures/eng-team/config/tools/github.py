"""GitHub tools — open PRs, list issues, fetch commit history via the gh CLI."""

import subprocess


def list_open_prs() -> list[dict]:
    """Return a list of open pull requests for the current repo."""
    result = subprocess.run(  # noqa: S603, S607
        ["gh", "pr", "list", "--state", "open", "--json", "number,title,author"],
        capture_output=True,
        text=True,
        check=False,
    )
    import json

    return json.loads(result.stdout) if result.returncode == 0 else []


def open_pr(title: str, body: str) -> str:
    """Open a pull request from the current branch."""
    result = subprocess.run(  # noqa: S603, S607
        ["gh", "pr", "create", "--title", title, "--body", body],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()
