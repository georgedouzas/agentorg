"""Render an organization from a single `spec.py` file."""

import runpy
from importlib.resources import files
from pathlib import Path

from agentorg.core.spec import Spec

from ._engine import _copy_static, render_tree
from ._extract import jinja_context


def _load_spec(spec_path: Path) -> Spec:
    spec = runpy.run_path(str(spec_path)).get('spec')
    if not isinstance(spec, Spec):
        msg = f'spec.py must define a top-level `spec` of type Spec, got {type(spec).__name__}.'
        raise TypeError(msg)
    return spec


def _copy_user_spec(spec_path: Path, package_name: str, output_dir: Path) -> None:
    """Place the user's spec.py at `<output>/src/<package>/spec.py` for `from <pkg>.spec import spec`.

    Kept here pending the rendered-agent-code refactor that will eliminate the runtime dependency on a copied spec.py.
    Partial templates without `src/<pkg>/` (e.g. frontend) silently skip the copy.
    """
    spec_dest = output_dir / 'src' / package_name / 'spec.py'
    if not spec_dest.parent.exists():
        return
    _copy_static(spec_path, spec_dest)


def render(spec_path: Path, output_dir: Path, *, template: str = 'full') -> None:
    """Render a project from a spec file.

    Arguments:
        spec_path: Path to the user's `spec.py`.
        output_dir: Output directory, created or overwritten in place.
        template: One of the shipped templates - `full` (default), `frontend`, `backend`, or `ai`.
    """
    spec = _load_spec(spec_path)
    template_dir = Path(str(files(__package__) / 'templates' / template))
    data = jinja_context(spec)
    render_tree(template_dir, output_dir, data)
    _copy_user_spec(spec_path, spec.org.package_name, output_dir)
