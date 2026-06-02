"""GUI public interface.

The PySide6 desktop shell is now the preferred entrypoint.
Legacy Tk widgets remain lazily importable for compatibility during migration.
"""

__all__ = [
    "GracePipelineGUI",
    "ScrollableFrame",
    "TextRedirector",
    "start_gui",
    "start_tk_gui",
]


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
    try:
        from grace_pipeline.ui.qt import start_gui as _start_qt_gui
    except ModuleNotFoundError as exc:
        if getattr(exc, "name", "") and exc.name.startswith("PySide6"):
            return start_tk_gui(*args, **kwargs)
        raise

    return _start_qt_gui(*args, **kwargs)
