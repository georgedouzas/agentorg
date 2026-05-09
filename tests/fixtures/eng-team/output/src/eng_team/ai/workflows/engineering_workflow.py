"""Engineering workflow built from app/config.yaml — steps, HITL config, agents."""

from pathlib import Path
from typing import Any

import yaml
from agno.workflow import OnReject, Parallel, Step, Workflow

from eng_team.ai.agents.architect import architect
from eng_team.ai.agents.backend_engineer import backend_engineer
from eng_team.ai.agents.frontend_engineer import frontend_engineer
from eng_team.ai.agents.product_manager import product_manager
from eng_team.ai.agents.qa_engineer import qa_engineer
from eng_team.ai.agents.tech_lead import tech_lead

_CONFIG = yaml.safe_load((Path(__file__).parent.parent.parent / "app" / "config.yaml").read_text())

_AGENTS = {
    "product-manager":    product_manager,
    "architect":          architect,
    "backend-engineer":   backend_engineer,
    "frontend-engineer":  frontend_engineer,
    "qa-engineer":        qa_engineer,
    "tech-lead":          tech_lead,
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


_WF_CFG = next(w for w in _CONFIG["workflows"] if w["id"] == "engineering-workflow")

engineering_workflow = Workflow(
    id=_WF_CFG["id"],
    name=_WF_CFG["name"],
    steps=[_build_step(s) for s in _WF_CFG["steps"]],
)
