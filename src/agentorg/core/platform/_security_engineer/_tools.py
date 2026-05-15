"""Security Engineer tools for secret scanning and required env var inventory."""

import os
import re
from pathlib import Path

_SECRET_PATTERNS = [
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'ghp_[A-Za-z0-9]{36}'),
    re.compile(r'sk-[A-Za-z0-9]{32,}'),
    re.compile(r'AIza[0-9A-Za-z_\-]{35}'),
    re.compile(r'xoxb-[0-9A-Za-z\-]{20,}'),
]


def scan_secrets(scan_dir: str = 'src') -> str:
    """Scan every `.py` file under `scan_dir` for likely hardcoded secrets."""
    root = Path(scan_dir)
    if not root.exists():
        return f'No directory at {scan_dir}.'
    hits: list[str] = []
    for path in root.rglob('*.py'):
        text = path.read_text(encoding='utf-8', errors='replace')
        for pattern in _SECRET_PATTERNS:
            for match in pattern.finditer(text):
                line = text[: match.start()].count('\n') + 1
                hits.append(f'  {path}:{line}  /{pattern.pattern}/')
    return 'No likely secrets found.' if not hits else 'Likely hardcoded secrets:\n' + '\n'.join(hits)


def list_required_env_vars(required: list[str] | None = None) -> str:
    """List the spec's required env vars + their set/unset status."""
    required = required or []
    if not required:
        return 'No required env vars declared.'
    lines = [f'  {v:24s} [{"set" if os.getenv(v) else "MISSING"}]' for v in required]
    return 'Required env vars:\n' + '\n'.join(lines)
