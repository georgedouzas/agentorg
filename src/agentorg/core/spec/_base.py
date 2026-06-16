"""The top-level `Spec` model that a user constructs in `spec.py`."""

from ._ai import AI
from ._config import SpecModel
from ._knowledge import Knowledge
from ._org import Org
from ._parameters import Parameter
from ._runtime import Runtime
from ._ui import UI


class Spec(SpecModel):
    """The whole organization specification."""

    org: Org
    runtime: Runtime
    ai: AI
    parameters: list[Parameter]
    knowledge: Knowledge
    ui: UI
