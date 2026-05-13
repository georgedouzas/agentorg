"""Setup-status tool — reports which setup steps are done and which are missing."""

import os
from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path(__file__).parent.parent.parent / "app" / "config.yaml"


def _steps() -> list[dict[str, Any]]:
    return yaml.safe_load(_CONFIG_PATH.read_text()).get("setup", {}).get("steps", [])


def get_setup_status() -> str:
    """Return the current setup checklist with completion status.

    Env-var steps are auto-detected (complete iff every listed var is set & non-empty).
    CLI/manual steps cannot be verified from inside the running app — they are reported
    as 'unknown' and the user must confirm completion verbally.

    Returns:
        Formatted status of every required setup step.
    """
    lines: list[str] = []
    for s in _steps():
        if "vars" in s:
            missing = [v for v in s["vars"] if not os.getenv(v)]
            status = "✅ done" if not missing else f"❌ missing {', '.join(missing)}"
        else:
            status = "⚪ unverified (CLI/manual)"
        lines.append(f"- {s['title']} — {status}")
        if s.get("command"):
            lines.append(f"    command: {s['command']}")
        if s.get("manual_fallback"):
            lines.append(f"    fallback: {s['manual_fallback']}")
    return "\n".join(lines) if lines else "No setup steps configured."
