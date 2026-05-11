"""Investment-team specific providers — portfolio summary, positions, sector allocation.

These are per-org providers (live in the spec rather than agentorg infra). They read from `org_state` (parameters +
data.positions) and shape the output for the corresponding widget renderers (StatsGrid / EntityGrid / BarTable).
"""

from typing import Any

from sqlalchemy import text

from ....db import get_engine

from . import provider


def _load_state(user_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT parameters, data FROM org_state WHERE user_id = :uid"),
            {"uid": user_id},
        ).first()
    if row is None:
        return {}, {}
    return (row.parameters or {}), (row.data or {})


@provider("portfolio.summary", args={"user_id": str})
def portfolio_summary(user_id: str = "default") -> list[dict[str, Any]]:
    """Fund summary cards (Fund Value / Deployed / Available / Benchmark) for StatsGrid."""
    params, data = _load_state(user_id)
    if not params:
        return []
    positions = data.get("positions", {}) or {}
    initial = float(params.get("initial_value", 0) or 0)
    deployed = sum(float(p.get("allocation", 0) or 0) for p in positions.values())
    reserve = initial * float(params.get("cash_reserve_pct", 0) or 0)
    available = initial - deployed - reserve
    return [
        {
            "label": "Fund Value", "value": f"${initial:,.0f}",
            "sub": f"Inception {params.get('inception_date', '—')}",
        },
        {
            "label": "Deployed", "value": f"${deployed:,.0f}",
            "sub": (
                f"{deployed / initial * 100:.1f}% · {len(positions)} positions"
                if initial else "—"
            ),
        },
        {"label": "Available", "value": f"${available:,.0f}", "sub": f"Reserve: ${reserve:,.0f}"},
        {
            "label": "Benchmark", "value": params.get("benchmark", "—"),
            "sub": params.get("investment_horizon", ""),
        },
    ]


@provider("portfolio.positions", args={"user_id": str})
def portfolio_positions(user_id: str = "default") -> list[dict[str, Any]]:
    """Positions list for EntityGrid."""
    params, data = _load_state(user_id)
    positions = data.get("positions", {}) or {}
    initial = float(params.get("initial_value", 1) or 1)
    items: list[dict[str, Any]] = []
    for ticker, pos in positions.items():
        alloc = float(pos.get("allocation", 0) or 0)
        pct = alloc / initial * 100 if initial else 0
        items.append({
            "id": ticker,
            "title": ticker,
            "subtitle": pos.get("company", ""),
            "badge": pos.get("sector", ""),
            "metrics": [
                {"label": "Allocated", "value": f"${alloc:,.0f}"},
                {"label": "Weight", "value": f"{pct:.1f}%"},
                {"label": "Entry", "value": f"${pos['entry_price']:.2f}" if pos.get("entry_price") else "—"},
                {"label": "Shares", "value": str(pos.get("shares", "—"))},
            ],
            "actions": [],
        })
    return items


@provider("portfolio.sectors", args={"user_id": str})
def portfolio_sectors(user_id: str = "default") -> dict[str, Any]:
    """Sector allocation for BarTable."""
    params, data = _load_state(user_id)
    positions = data.get("positions", {}) or {}
    initial = float(params.get("initial_value", 1) or 1)
    sector_limits = {
        "Technology": float(params.get("max_sector_pct", 0.40) or 0.40),
        "Healthcare": float(params.get("healthcare_max_pct", 0.25) or 0.25),
        "Financials": float(params.get("financials_max_pct", 0.20) or 0.20),
    }
    default_limit = float(params.get("max_position_pct", 0.15) or 0.15)

    sector_map: dict[str, float] = {}
    for pos in positions.values():
        s = pos.get("sector", "Other")
        sector_map[s] = sector_map.get(s, 0) + float(pos.get("allocation", 0) or 0)

    rows = []
    for sector, alloc in sorted(sector_map.items(), key=lambda x: -x[1]):
        used_pct = alloc / initial if initial else 0
        limit = sector_limits.get(sector, default_limit)
        rows.append({
            "cells": [sector, f"${alloc:,.0f}", f"{used_pct * 100:.1f}%", f"{limit * 100:.0f}% limit"],
            "bar": {
                "value": round(used_pct / limit * 100, 1) if limit else 0,
                "max": 100,
                "warn": used_pct >= limit * 0.85,
            },
        })

    return {"headers": ["Sector", "Deployed", "Utilization", "vs Limit"], "rows": rows}
