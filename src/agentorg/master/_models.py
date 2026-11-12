"""Interview-time drafts of units, custom tools and custom skills."""

from pydantic import Field

from ..core.spec import ActionClass, Autonomy, Decision, Model, Review, Routing, SpecModel


class UnitDraft(SpecModel):
    """A unit as the interview builds it: flat, pointing at its parent, assembled into the tree on every change."""

    id: str
    name: str
    model: Model
    parent_id: str | None = None
    lead: str | None = None
    members: list[str] = Field(default_factory=list)
    routing: Routing = 'least_loaded'
    decision: Decision | None = None
    review: Review = 'none'
    step_reviews: dict[str, Review] = Field(default_factory=dict)
    step_instructions: dict[str, str] = Field(default_factory=dict)
    owners: list[str] = Field(default_factory=list)
    max_autonomy: Autonomy | None = None
    monthly_usd: float | None = None
    approval_required: list[ActionClass] = Field(default_factory=list)


class CustomTool(SpecModel):
    """A user-defined tool function emitted via `emit_custom_tool` and inlined into spec.py."""

    name: str
    source: str


class CustomSkill(SpecModel):
    """A user-defined skill emitted via `emit_custom_skill` and written to `skills/<name>/SKILL.md` next to spec.py."""

    name: str
    skill_md: str
