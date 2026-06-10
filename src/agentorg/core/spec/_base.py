"""The top-level `Spec` model that a user constructs in `spec.py`."""

from pydantic import BaseModel, ConfigDict

from ._ai import AI
from ._knowledge import Knowledge
from ._org import Org
from ._parameters import Parameter
from ._runtime import Runtime
from ._ui import UI


class Spec(BaseModel):
    """The whole organization specification."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    org: Org
    runtime: Runtime
    ai: AI
    parameters: list[Parameter]
    knowledge: Knowledge
    ui: UI
