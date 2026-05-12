"""Shared agent infrastructure: knowledge bases, instruction composer, agent-config map."""

from os import getenv
from pathlib import Path

import yaml

from org.db import create_knowledge

# Shared knowledge bases — instantiated once
team_knowledge = create_knowledge("Team Knowledge", "team_knowledge")
team_learnings = create_knowledge("Team Learnings", "team_learnings")

# Exa MCP URL for web search
EXA_API_KEY = getenv("EXA_API_KEY", "")
EXA_MCP_URL = f"https://mcp.exa.ai/mcp?exaApiKey={EXA_API_KEY}&tools=web_search_exa"

# Per-agent config (loaded once from app/config.yaml)
_CONFIG_PATH = Path(__file__).parent.parent.parent / "app" / "config.yaml"
AGENT_CONFIGS: dict[str, dict] = yaml.safe_load(_CONFIG_PATH.read_text()).get("agents", {})


def get_instructions(agent_id: str) -> str:
    """Compose the runtime LLM prompt for an agent from its structured fields.

    The agent's `agentorg.json` definition holds typed fields — `role`, `in_scope`,
    `out_of_scope`, `workflow`, `output_format`, `count_rule`, `save_rule`. This
    function stitches them into a coherent system prompt the LLM consumes. The
    same fields are exposed to the UI's Description tab so the user sees a clean
    structured view rather than the raw prompt.
    """
    from org.org import COMMITTEE_CONTEXT  # noqa: PLC0415

    cfg = AGENT_CONFIGS.get(agent_id, {})
    name = cfg.get("name", agent_id)
    parts: list[str] = [
        f"You are the {name}.",
        "",
        "## Committee Rules (ALWAYS FOLLOW)",
        "",
        COMMITTEE_CONTEXT,
        "",
    ]

    if cfg.get("role"):
        parts += ["## Role", "", cfg["role"], ""]

    if cfg.get("in_scope"):
        parts += ["## In scope"]
        parts += [f"- {x}" for x in cfg["in_scope"]]
        parts.append("")

    if cfg.get("out_of_scope"):
        parts += ["## Out of scope — decline and refer"]
        for item in cfg["out_of_scope"]:
            parts.append(f"- {item.get('topic', '')} → **{item.get('refer_to', '')}**")
        parts += [
            "",
            "If asked anything outside your scope (including topics unrelated to this team's"
            " domain), decline firmly and point to the right person.",
            "",
        ]

    if cfg.get("count_rule"):
        cr = cfg["count_rule"]
        parts += ["## How many results to return"]
        for r in cr.get("rules", []):
            parts.append(f"- **{r.get('phrase', '')}** → {r.get('count', '')}")
        if cr.get("default") is not None:
            parts.append(f"- (otherwise) → {cr['default']}")
        parts.append("")

    if cfg.get("workflow"):
        parts += ["## Workflow"]
        parts += [f"{i+1}. {step}" for i, step in enumerate(cfg["workflow"])]
        parts.append("")

    if cfg.get("output_format"):
        parts += ["## Output format"]
        of = cfg["output_format"]
        if of.get("kind") == "markdown_table":
            parts.append(f"Markdown table with columns: {' | '.join(of.get('columns', []))}.")
        if of.get("sections"):
            parts.append("Use these sections (in order): " + ", ".join(of["sections"]) + ".")
        if of.get("trailer"):
            parts.append(of["trailer"])
        parts.append("")

    if cfg.get("save_rule"):
        sr = cfg["save_rule"]
        parts += [
            "## Auto-save the report",
            "",
            f"Your final action is to call `{sr.get('tool', 'write_agent_report')}`. "
            "The tool's response IS the user's confirmation; do not write any other text after the call.",
            "",
            "**Argument rules (strict):**",
            f"- `name`: {sr.get('name_pattern', '')}",
            f"- `title`: {sr.get('title_pattern', '')}",
            "- `content`: the full markdown analysis you just produced.",
            "- `metadata`: optional tags dict (tickers, sector, etc.).",
        ]
        if sr.get("note"):
            parts += ["", sr["note"]]

    return "\n".join(parts)
