"""Runtime UI refinements for the PySide6 desktop shell."""
from __future__ import annotations

_PATCHED = False


def install_runtime_patches() -> None:
    global _PATCHED
    if _PATCHED:
        return
    # Kept as a compatibility hook for older entrypoints. Theme, language,
    # settings, download confirmation, and tray behavior now live in the main
    # PySide6 modules so source and packaged builds follow the same path.
    _PATCHED = True


def apply_window_refinements(window, app=None) -> None:
    return None
