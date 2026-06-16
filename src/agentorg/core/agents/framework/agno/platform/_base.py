"""Aggregation of the six built-in platform agents into the `PLATFORM_AGENTS` tuple."""

from .backend_engineer import agent as backend_engineer
from .frontend_engineer import agent as frontend_engineer
from .knowledge_engineer import agent as knowledge_engineer
from .platform_engineer import agent as platform_engineer
from .qa_engineer import agent as qa_engineer
from .security_engineer import agent as security_engineer

PLATFORM_AGENTS = (
    platform_engineer,
    security_engineer,
    backend_engineer,
    frontend_engineer,
    knowledge_engineer,
    qa_engineer,
)
PLATFORM_AGENT_IDS: frozenset[str] = frozenset(a.id for a in PLATFORM_AGENTS if a.id)
