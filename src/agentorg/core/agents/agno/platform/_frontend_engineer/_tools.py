"""Frontend Engineer tools that introspect UI configuration."""

import json
from typing import Any

from ....tools._tags import tags


@tags('platform', 'frontend')
def read_ui_config(ui: dict[str, Any] | None = None) -> str:
    """Return the spec's `ui` section as pretty-printed JSON."""
    return json.dumps(ui or {}, indent=2)


@tags('platform', 'frontend')
def list_overview_widgets(ui: dict[str, Any] | None = None) -> str:
    """List every overview-tab widget id and kind."""
    widgets = ((ui or {}).get('overview') or {}).get('widgets') or []
    if not widgets:
        return 'No overview widgets configured.'
    return 'Overview widgets:\n' + '\n'.join(f"  - {w.get('id', '?'):24s} kind={w.get('kind', '?')}" for w in widgets)
