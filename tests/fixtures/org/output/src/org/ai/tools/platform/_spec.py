"""Shared helpers for platform tools — read config.yaml, locate the rendered project root."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_PACKAGE_ROOT = Path(__file__).parent.parent.parent.parent
_CONFIG_PATH = _PACKAGE_ROOT / "org" / "app" / "config.yaml"


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    """Return the parsed `app/config.yaml` (cached for the process lifetime)."""
    return yaml.safe_load(_CONFIG_PATH.read_text())


def project_root() -> Path:
    """Return the rendered project's filesystem root (one level above `src/`)."""
    return _PACKAGE_ROOT.parent.parent
