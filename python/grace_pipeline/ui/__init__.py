"""Canonical UI entrypoints."""

__all__ = ["GracePipelineGUI", "ScrollableFrame", "TextRedirector", "start_gui", "start_tk_gui"]


def __getattr__(name):
    if name in {"GracePipelineGUI", "ScrollableFrame", "TextRedirector"}:
        from grace_pipeline.ui.app import GracePipelineGUI, ScrollableFrame, TextRedirector

        legacy = {
            "GracePipelineGUI": GracePipelineGUI,
            "ScrollableFrame": ScrollableFrame,
            "TextRedirector": TextRedirector,
        }
        return legacy[name]
    raise AttributeError(name)


def start_tk_gui(*args, **kwargs):
    from grace_pipeline.ui.app import start_gui as _start_tk_gui

    return _start_tk_gui(*args, **kwargs)


def start_gui(*args, **kwargs):
    from grace_pipeline.gui import start_gui as _start_gui

    return _start_gui(*args, **kwargs)
