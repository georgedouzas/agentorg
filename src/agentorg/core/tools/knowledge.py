"""Generic knowledge CRUD tools — write/read/list/search/delete knowledge units.

A knowledge unit is anything an agent produces: text artifacts (research, memo, report) or structured data (charts,
stats, tables). All units live in the `knowledge` table.
"""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import text

from agentorg.core.tools._engine import create_knowledge, get_engine


def write_knowledge(
    type: str,  # noqa: A002
    name: str,
    content: str | None = None,
    title: str | None = None,
    data: dict[str, Any] | list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Write or update a knowledge unit.

    Returns confirmation.
    """
    md_json = json.dumps(metadata or {})
    data_json = json.dumps(data) if data is not None else None

    with get_engine().begin() as conn:
        conn.execute(
            text("""
                INSERT INTO knowledge (type, name, title, content, data, metadata)
                VALUES (:type, :name, :title, :content, :data, :metadata)
                ON CONFLICT (type, name) DO UPDATE
                    SET title      = excluded.title,
                        content    = excluded.content,
                        data       = excluded.data,
                        metadata   = excluded.metadata,
                        updated_at = CURRENT_TIMESTAMP
            """),
            {
                'type': type,
                'name': name,
                'title': title,
                'content': content,
                'data': data_json,
                'metadata': md_json,
            },
        )

    if content:
        team_knowledge = create_knowledge('Team Knowledge', 'team_knowledge')
        tmp_dir = tempfile.mkdtemp()
        try:
            (Path(tmp_dir) / f'{name}.md').write_text(content, encoding='utf-8')
            team_knowledge.insert(name=f'{type}-{name}', path=tmp_dir, skip_if_exists=False)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return f"Saved {type} '{name}' to knowledge."


def read_knowledge(type: str, name: str) -> str:  # noqa: A002
    """Read a knowledge unit by type and name.

    Returns content (markdown) or stringified data.
    """
    with get_engine().connect() as conn:
        row = conn.execute(
            text('SELECT content, data FROM knowledge WHERE type = :t AND name = :n'),
            {'t': type, 'n': name},
        ).first()
    if row is None:
        return f"No {type} knowledge found for '{name}'."
    if row.content:
        return row.content
    if row.data is not None:
        return row.data if isinstance(row.data, str) else json.dumps(row.data, indent=2)
    return ''


def _match_metadata(stored: str | dict[str, Any] | None, filter_dict: dict[str, Any]) -> bool:
    if stored is None:
        return False
    md = json.loads(stored) if isinstance(stored, str) else stored
    return all(md.get(k) == v for k, v in filter_dict.items())


def list_knowledge(type: str = '', metadata_filter: dict[str, Any] | None = None) -> str:  # noqa: A002
    """List knowledge units, optionally filtered by type and/or metadata (subset match)."""
    sql = 'SELECT type, name, title, metadata, updated_at FROM knowledge'
    params: dict[str, Any] = {}
    if type:
        sql += ' WHERE type = :t'
        params['t'] = type
    sql += ' ORDER BY type, name'

    with get_engine().connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()

    if metadata_filter:
        rows = [r for r in rows if _match_metadata(r.metadata, metadata_filter)]
    if not rows:
        return 'No knowledge units found.'

    lines: list[str] = []
    current = None
    for row in rows:
        if row.type != current:
            current = row.type
            lines.append(f'{current.title()}:')
        title = row.title or row.name
        meta = f' {row.metadata}' if row.metadata else ''
        updated = row.updated_at if isinstance(row.updated_at, str) else row.updated_at.strftime('%Y-%m-%d')
        lines.append(f'  - {row.name} — {title}{meta}  (updated {updated})')
    return '\n'.join(lines)


def search_knowledge(query: str, types: list[str] | None = None) -> str:
    """Substring search across knowledge content (case-insensitive)."""
    sql = (
        'SELECT type, name, metadata, SUBSTR(content, 1, 400) AS excerpt'
        ' FROM knowledge WHERE LOWER(content) LIKE LOWER(:q)'
    )
    params: dict[str, Any] = {'q': f'%{query}%'}
    if types:
        placeholders = ', '.join(f':t{i}' for i in range(len(types)))
        sql += f' AND type IN ({placeholders})'
        for i, t in enumerate(types):
            params[f't{i}'] = t
    sql += ' ORDER BY updated_at DESC LIMIT 10'
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    if not rows:
        return f"No knowledge units matching '{query}'."
    return '\n\n'.join(f'**{r.type}/{r.name}**\n{r.excerpt}…' for r in rows)


def delete_knowledge(type: str, name: str) -> str:  # noqa: A002
    """Delete a knowledge unit."""
    with get_engine().begin() as conn:
        result = conn.execute(
            text('DELETE FROM knowledge WHERE type = :t AND name = :n'),
            {'t': type, 'n': name},
        )
    if result.rowcount == 0:
        return f"No {type} knowledge found for '{name}'."
    return f"Deleted {type} '{name}'."
