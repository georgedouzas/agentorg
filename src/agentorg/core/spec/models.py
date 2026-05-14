"""The top-level `Spec` model — the single Python value a user constructs in `spec.py`.

`Spec` is five domain models: `org`, `runtime`, `ai`, `knowledge`, `ui`. Each lives in its own `_*.py` module. `org` /
`runtime` / `knowledge` / `ui` accept plain dict literals (Pydantic coerces them); `ai` holds agno-native objects.
"""

from pydantic import BaseModel, ConfigDict

from agentorg.core.spec._ai import AI
from agentorg.core.spec._knowledge import Knowledge
from agentorg.core.spec._org import Org
from agentorg.core.spec._runtime import Runtime
from agentorg.core.spec._ui import UI


class Spec(BaseModel):
    """The whole org spec — a single Python value the user constructs in `spec.py`."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    org: Org
    runtime: Runtime
    ai: AI
    knowledge: Knowledge
    ui: UI
