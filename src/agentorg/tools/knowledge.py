"""Generic knowledge CRUD — write / read / list / search / delete knowledge units.

A knowledge unit is anything an agent produces: text artifacts (research, memo, report), structured data (charts, stats,
tables), or a refresh recipe (provider + args + schedule) that the scheduler periodically re-evaluates.

All units live in the ``knowledge`` table. Static rows have a NULL provider; live rows populate ``provider`` / ``args``
/ ``schedule`` and the scheduler keeps ``data`` / ``last_computed`` fresh. Spec wrappers in each org's ``config/tools/``
import these directly via ``from agentorg.tools.knowledge import write_knowledge``.
"""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import text

from ._engine import get_engine, get_team_knowledge


def write_knowledge(
    type: str,  # noqa: A002
    name: str,
    content: str | None = None,
    title: str | None = None,
    data: dict[str, Any] | list[Any] | None = None,
    display: dict[str, Any] | None = None,
    provider: str | None = None,
    args: dict[str, Any] | None = None,
    schedule: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Write or update a knowledge unit.

    Args:
        type: Knowledge type (e.g. ``'research'``, ``'memo'``, ``'report'``, ``'chart'``).
        name: Unique name within the type.
        content: Markdown text (for documents). Optional.
        title: Display title. Falls back to the H1 in ``content`` when absent.
        data: Structured data (for charts / tables / stats). Optional.
        display: UI hints — ``{chart_type, columns, featured, ...}``. Optional.
        provider: Refresh-provider name from the registry (e.g. ``'yfinance.history'``).
        args: Provider arguments.
        schedule: Refresh cadence — ``'on_request'`` / ``'every:5m'`` / ``'cron:...'``.
        metadata: Free-form structured metadata.

    Returns:
        Confirmation message.
    """
    md_json = json.dumps(metadata or {})
    data_json = json.dumps(data) if data is not None else None
    display_json = json.dumps(display) if display is not None else None
    args_json = json.dumps(args) if args is not None else None

    with get_engine().begin() as conn:
        conn.execute(
            text("""
                INSERT INTO knowledge (
                    type, name, title, content, data, display,
                    provider, args, schedule, metadata, updated_at
                )
                VALUES (
                    :type, :name, :title, :content,
                    CAST(:data AS JSONB), CAST(:display AS JSONB),
                    :provider, CAST(:args AS JSONB), :schedule,
                    CAST(:metadata AS JSONB), NOW()
                )
                ON CONFLICT (type, name) DO UPDATE
                    SET title      = EXCLUDED.title,
                        content    = EXCLUDED.content,
                        data       = EXCLUDED.data,
                        display    = EXCLUDED.display,
                        provider   = EXCLUDED.provider,
                        args       = EXCLUDED.args,
                        schedule   = EXCLUDED.schedule,
                        metadata   = EXCLUDED.metadata,
                        updated_at = NOW()
            """),
            {
                "type": type,
                "name": name,
                "title": title,
                "content": content,
                "data": data_json,
                "display": display_json,
                "provider": provider,
                "args": args_json,
                "schedule": schedule,
                "metadata": md_json,
            },
        )

    # If textual content is provided, also index into PgVector for semantic search.
    if content:
        team_knowledge = get_team_knowledge("Team Knowledge", "team_knowledge")
        tmp_dir = tempfile.mkdtemp()
        try:
            (Path(tmp_dir) / f"{name}.md").write_text(content, encoding="utf-8")
            team_knowledge.insert(name=f"{type}-{name}", path=tmp_dir, skip_if_exists=False)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return f"Saved {type} '{name}' to knowledge."


def read_knowledge(type: str, name: str) -> str:  # noqa: A002
    """Read a knowledge unit by type and name.

    Returns content (markdown) or stringified data.
    """
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT content, data FROM knowledge WHERE type = :t AND name = :n"),
            {"t": type, "n": name},
        ).first()
    if row is None:
        return f"No {type} knowledge found for '{name}'."
    if row.content:
        return row.content
    if row.data is not None:
        return json.dumps(row.data, indent=2)
    return ""


def list_knowledge(type: str = "", metadata_filter: dict[str, Any] | None = None) -> str:  # noqa: A002
    """List knowledge units, optionally filtered by type and / or metadata."""
    sql = "SELECT type, name, title, metadata, updated_at FROM knowledge"
    conds: list[str] = []
    params: dict[str, Any] = {}
    if type:
        conds.append("type = :t")
        params["t"] = type
    if metadata_filter:
        conds.append("metadata @> CAST(:m AS JSONB)")
        params["m"] = json.dumps(metadata_filter)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY type, name"

    with get_engine().connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()

    if not rows:
        return "No knowledge units found."

    lines: list[str] = []
    current = None
    for row in rows:
        if row.type != current:
            current = row.type
            lines.append(f"{current.title()}:")
        title = row.title or row.name
        meta = f" {row.metadata}" if row.metadata else ""
        lines.append(f"  - {row.name} — {title}{meta}  (updated {row.updated_at.strftime('%Y-%m-%d')})")
    return "\n".join(lines)


def search_knowledge(query: str, types: list[str] | None = None) -> str:
    """Full-text search across knowledge content."""
    sql = "SELECT type, name, metadata, LEFT(content, 400) AS excerpt FROM knowledge WHERE content ILIKE :q"
    params: dict[str, Any] = {"q": f"%{query}%"}
    if types:
        sql += " AND type = ANY(CAST(:types AS TEXT[]))"
        params["types"] = types
    sql += " ORDER BY updated_at DESC LIMIT 10"

    with get_engine().connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()

    if not rows:
        return f"No knowledge units matching '{query}'."

    return "\n\n".join(f"**{r.type}/{r.name}**\n{r.excerpt}…" for r in rows)


def delete_knowledge(type: str, name: str) -> str:  # noqa: A002
    """Delete a knowledge unit."""
    with get_engine().begin() as conn:
        result = conn.execute(
            text("DELETE FROM knowledge WHERE type = :t AND name = :n"),
            {"t": type, "n": name},
        )
    if result.rowcount == 0:
        return f"No {type} knowledge found for '{name}'."
    return f"Deleted {type} '{name}'."
