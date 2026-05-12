"""Security-engineer tools — secret scanning + env var inventory."""

import os
import re

from ._spec import load_config, project_root

# Pattern catches obvious hardcoded creds: AWS keys, GH tokens, common API key prefixes.
_SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key
    re.compile(r"ghp_[A-Za-z0-9]{36}"),  # GitHub personal access token
    re.compile(r"sk-[A-Za-z0-9]{32,}"),  # OpenAI-style API key
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),  # Google API key
    re.compile(r"xoxb-[0-9A-Za-z\-]{20,}"),  # Slack bot token
]


def scan_secrets() -> str:
    """Scan every `.py` file under `src/<package>/ai/tools/` for likely hardcoded secrets."""
    tools_dir = project_root() / "src"
    hits: list[str] = []
    for path in tools_dir.rglob("*.py"):
        text = path.read_text()
        for pattern in _SECRET_PATTERNS:
            for match in pattern.finditer(text):
                rel = path.relative_to(project_root())
                line = text[: match.start()].count("\n") + 1
                hits.append(f"  {rel}:{line}  matches /{pattern.pattern}/")
    if not hits:
        return "No likely secrets found in tool modules."
    return "Likely hardcoded secrets:\n" + "\n".join(hits)


def list_required_env_vars() -> str:
    """List the env vars declared as required in the spec, with their current set/unset status."""
    cfg = load_config()
    setup = cfg.get("setup") or {}
    required: list[str] = []
    for step in setup.get("steps") or []:
        for var in step.get("vars", []) or []:
            required.append(var)
    if not required:
        return "No required env vars declared."
    lines = [f"  {v:24s} [{'set' if os.getenv(v) else 'MISSING'}]" for v in required]
    return "Required env vars:\n" + "\n".join(lines)
