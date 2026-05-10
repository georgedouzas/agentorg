"""Generic charter loader — reads sections + parameters from app/config.yaml,
substitutes user state from the org_state DB table, returns the rendered context block.
"""

import re
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from investment_team.db.engine import get_engine

_CONFIG_PATH = Path(__file__).parent.parent / "app" / "config.yaml"
_CONFIG = yaml.safe_load(_CONFIG_PATH.read_text())
_CHARTER = _CONFIG.get("charter", {})


def _currency(amount: float) -> str:
    return f"${amount:,.0f}"


def _pct(val: float) -> str:
    v = val * 100
    return f"{v:.0f}" if v == int(v) else f"{v:g}"


_FORMAT_FNS = {"currency": _currency, "pct": _pct}


def _eval_expr(expr: str, vars: dict[str, Any]) -> Any:
    """Safely evaluate a derived expression: 'currency(initial_value * cash_reserve_pct)' etc."""
    # Match 'fn(arg_expr)' where arg_expr is a simple arithmetic over var names + numbers
    m = re.fullmatch(r"\s*(\w+)\((.+)\)\s*", expr)
    if not m:
        msg = f"Bad expr: {expr!r}"
        raise ValueError(msg)
    fn_name, body = m.group(1), m.group(2)
    if fn_name not in _FORMAT_FNS:
        msg = f"Unknown format fn: {fn_name!r}"
        raise ValueError(msg)
    # Evaluate body in a restricted namespace (only vars + arithmetic)
    value = eval(body, {"__builtins__": {}}, vars)  # noqa: S307
    return _FORMAT_FNS[fn_name](value)


def _defaults() -> dict[str, Any]:
    """Return charter parameters with their defaults."""
    return {p["name"]: p["default"] for p in _CHARTER.get("parameters", [])}


def _load_user_parameters(user_id: str = "default") -> dict[str, Any]:
    """Read parameters from org_state, falling back to defaults."""
    base = _defaults()
    try:
        with get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT parameters FROM org_state WHERE user_id = :uid"),
                {"uid": user_id},
            ).first()
        if row and row.parameters:
            return {**base, **row.parameters}
    except SQLAlchemyError:
        pass
    return base


def _build_vars(params: dict[str, Any]) -> dict[str, Any]:
    """Apply derived expressions on top of raw parameters."""
    rendered: dict[str, Any] = dict(params)
    for d in _CHARTER.get("derived", []):
        rendered[d["name"]] = _eval_expr(d["expr"], rendered)
    return rendered


def load_context(user_id: str = "default") -> str:
    """Render all charter sections with current parameters, separated by ---."""
    sections = _CHARTER.get("sections", [])
    if not sections:
        return ""
    rendered_vars = _build_vars(_load_user_parameters(user_id))
    blocks = []
    for s in sections:
        blocks.append(f"# {s['title']}\n\n{s['body'].format_map(rendered_vars)}")
    return "\n\n---\n\n".join(blocks)


COMMITTEE_CONTEXT = load_context()
