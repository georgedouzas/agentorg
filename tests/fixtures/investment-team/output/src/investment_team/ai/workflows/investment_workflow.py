"""Investment workflow built from app/config.yaml — steps, HITL config, agents."""

from pathlib import Path
from typing import Any

import yaml
from agno.workflow import OnReject, Parallel, Step, Workflow

from investment_team.ai.agents.committee_chair import committee_chair
from investment_team.ai.agents.financial_analyst import financial_analyst
from investment_team.ai.agents.knowledge_agent import knowledge_agent
from investment_team.ai.agents.market_analyst import market_analyst
from investment_team.ai.agents.memo_writer import memo_writer
from investment_team.ai.agents.portfolio_agent import portfolio_agent
from investment_team.ai.agents.research_analyst import research_analyst
from investment_team.ai.agents.risk_officer import risk_officer
from investment_team.ai.agents.stock_screener import stock_screener
from investment_team.ai.agents.technical_analyst import technical_analyst

_CONFIG = yaml.safe_load((Path(__file__).parent.parent.parent / "app" / "config.yaml").read_text())

_AGENTS = {
    "stock-screener":    stock_screener,
    "research-analyst":  research_analyst,
    "market-analyst":    market_analyst,
    "financial-analyst": financial_analyst,
    "technical-analyst": technical_analyst,
    "risk-officer":      risk_officer,
    "knowledge-agent":   knowledge_agent,
    "memo-writer":       memo_writer,
    "committee-chair":   committee_chair,
    "portfolio-agent":   portfolio_agent,
}


def _on_reject(value: str | None) -> OnReject | None:
    return OnReject.cancel if value == "cancel" else None


def _build_step(cfg: dict[str, Any]) -> Step | Parallel:
    if "parallel" in cfg:
        sub_steps = [Step(name=s["name"], agent=_AGENTS[s["agent"]]) for s in cfg["parallel"]]
        return Parallel(*sub_steps, name=cfg["name"])

    kwargs: dict[str, Any] = {"name": cfg["name"], "agent": _AGENTS[cfg["agent"]]}
    hitl = cfg.get("hitl") or {}
    htype = hitl.get("type")
    if htype == "output_review":
        kwargs["requires_output_review"] = True
        kwargs["output_review_message"] = hitl["message"]
    elif htype == "user_input":
        kwargs["requires_user_input"] = True
        kwargs["user_input_message"] = hitl["message"]
        if "schema" in hitl:
            kwargs["user_input_schema"] = hitl["schema"]
    elif htype == "confirmation":
        kwargs["requires_confirmation"] = True
        kwargs["confirmation_message"] = hitl["message"]
    if hitl.get("on_reject") and _on_reject(hitl["on_reject"]):
        kwargs["on_reject"] = _on_reject(hitl["on_reject"])
    return Step(**kwargs)


_WF_CFG = next(w for w in _CONFIG["workflows"] if w["id"] == "investment-workflow")

investment_workflow = Workflow(
    id=_WF_CFG["id"],
    name=_WF_CFG["name"],
    steps=[_build_step(s) for s in _WF_CFG["steps"]],
)
