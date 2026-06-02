"""PySide6 desktop shell for the GRACE pipeline UI."""

__all__ = [
    "start_gui",
]


def start_gui(*args, **kwargs):
    from grace_pipeline.ui.qt.app import start_gui as _start_gui

    return _start_gui(*args, **kwargs)
