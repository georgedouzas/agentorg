"""Browser UI that wraps the master interview agent."""

from ._preview import PreviewManager, PreviewSnapshot
from ._server import build_app

__all__ = ['PreviewManager', 'PreviewSnapshot', 'build_app']
