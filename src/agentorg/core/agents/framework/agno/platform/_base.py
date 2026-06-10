"""Aggregation of the six built-in platform agents into the `PLATFORM_AGENTS` tuple."""

from ._backend_engineer import agent as backend_engineer
from ._frontend_engineer import agent as frontend_engineer
from ._knowledge_engineer import agent as knowledge_engineer
from ._platform_engineer import agent as platform_engineer
from ._qa_engineer import agent as qa_engineer
from ._security_engineer import agent as security_engineer

PLATFORM_AGENTS = (
    platform_engineer,
    security_engineer,
    backend_engineer,
    frontend_engineer,
    knowledge_engineer,
    qa_engineer,
)
PLATFORM_AGENT_IDS: frozenset[str] = frozenset(a.id for a in PLATFORM_AGENTS if a.id)
