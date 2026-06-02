"""Legacy GUI compatibility shim.

Canonical GUI implementation now lives in ``grace_pipeline.ui.app``.
"""

from grace_pipeline.ui.app import GracePipelineGUI, ScrollableFrame, TextRedirector, start_gui

__all__ = ["GracePipelineGUI", "ScrollableFrame", "TextRedirector", "start_gui"]
