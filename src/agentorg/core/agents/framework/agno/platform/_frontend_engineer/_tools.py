"""Frontend Engineer tools that introspect UI configuration."""

import json
from typing import Any

from agentorg.core.agents.tools._tags import tags


@tags('platform', 'frontend')
def read_ui_config(ui: dict[str, Any] | None = None) -> str:
    """Return the spec's `ui` section as pretty-printed JSON.

    Arguments:
        ui: The spec's `ui` dict, or None to use an empty config.

    Returns:
        json: The UI config as pretty-printed JSON.
    """
    return json.dumps(ui or {}, indent=2)


@tags('platform', 'frontend')
def list_overview_widgets(ui: dict[str, Any] | None = None) -> str:
    """List every overview-tab widget id and kind.

    Arguments:
        ui: The spec's `ui` dict, or None to use an empty config.

    Returns:
        listing: Each widget's id and kind, one per line.
    """
    widgets = ((ui or {}).get('overview') or {}).get('widgets') or []
    if not widgets:
        return 'No overview widgets configured.'
    return 'Overview widgets:\n' + '\n'.join(f"  - {w.get('id', '?'):24s} kind={w.get('kind', '?')}" for w in widgets)
