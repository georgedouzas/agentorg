"""Frontend-engineer tools — introspect UI configuration."""

import json

from ._spec import load_config


def read_ui_config() -> str:
    """Return the `ui` section of `config.yaml` as pretty-printed JSON."""
    ui = load_config().get("ui") or {}
    return json.dumps(ui, indent=2)


def list_overview_widgets() -> str:
    """List every overview-tab widget id and its kind."""
    overview = (load_config().get("ui") or {}).get("overview") or {}
    widgets = overview.get("widgets") or []
    if not widgets:
        return "No overview widgets configured."
    return "Overview widgets:\n" + "\n".join(f"  - {w.get('id', '?'):24s} kind={w.get('kind', '?')}" for w in widgets)
