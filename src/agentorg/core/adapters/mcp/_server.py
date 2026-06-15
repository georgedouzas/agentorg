"""Stdio MCP server that re-exposes an agentorg node's skills as MCP tools."""

import asyncio
import json
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


async def _discover_skills(client: httpx.AsyncClient, node_url: str) -> list[dict[str, Any]]:
    """Fetch the node's `GET /skills` listing and normalise it into a flat skill list."""
    resp = await client.get(f'{node_url.rstrip("/")}/skills')
    resp.raise_for_status()
    payload = resp.json()
    skills = payload.get('skills', payload) if isinstance(payload, dict) else payload
    return list(skills) if isinstance(skills, list) else []


def _tool_for(skill: dict[str, Any]) -> Tool:
    """Project an AgentField skill descriptor into the MCP `Tool` shape."""
    sid = skill.get('id') or skill.get('name') or 'unknown'
    description_parts: list[str] = []
    if skill.get('description'):
        description_parts.append(str(skill['description']))
    tags = skill.get('tags') or []
    if tags:
        description_parts.append(f'(tags: {", ".join(tags)})')
    return Tool(
        name=sid,
        description=' '.join(description_parts) or f'agentorg skill `{sid}`',
        inputSchema=skill.get('input_schema') or {'type': 'object', 'properties': {}, 'additionalProperties': True},
    )


async def _serve(node_url: str) -> None:
    server: Server = Server(name='agentorg', instructions=f'Skills proxied from {node_url}')

    async with httpx.AsyncClient(timeout=30.0) as client:
        skills = await _discover_skills(client, node_url)
        skill_index = {(s.get('id') or s.get('name')): s for s in skills if (s.get('id') or s.get('name'))}

        @server.list_tools()
        async def _list() -> list[Tool]:
            return [_tool_for(s) for s in skill_index.values()]

        @server.call_tool()
        async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            if name not in skill_index:
                msg = f'unknown skill {name!r}'
                raise ValueError(msg)
            resp = await client.post(
                f'{node_url.rstrip("/")}/skills/{name}',
                json=arguments or {},
                headers={'Content-Type': 'application/json'},
            )
            resp.raise_for_status()
            body = resp.text
            try:
                parsed = resp.json()
                body = parsed if isinstance(parsed, str) else json.dumps(parsed, indent=2)
            except (ValueError, json.JSONDecodeError):
                pass
            return [TextContent(type='text', text=body)]

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    """CLI entry point — reads `AGENTORG_NODE` (default http://localhost:8000) and serves over stdio."""
    node_url = os.environ.get('AGENTORG_NODE', 'http://localhost:8000')
    asyncio.run(_serve(node_url))
