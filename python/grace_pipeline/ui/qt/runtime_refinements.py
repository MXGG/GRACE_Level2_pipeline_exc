"""Runtime UI refinements for the PySide6 desktop shell."""

from __future__ import annotations

_PATCHED = False


def install_runtime_patches() -> None:
    """Install late-bound GUI patches before MainWindow is constructed."""
    global _PATCHED
    if _PATCHED:
        return
    from grace_pipeline.ui.qt import runtime_terms_min, runtime_theme_simple, runtime_settings_min, runtime_download_patch
    runtime_terms_min.install()
    runtime_theme_simple.install()
    runtime_settings_min.install()
    runtime_download_patch.install()
    _PATCHED = True


def apply_window_refinements(window, app=None) -> None:
    """Apply page-level and window-level refinements after the controller exists."""
    from grace_pipeline.ui.qt import runtime_layout_only, runtime_tray_only
    runtime_layout_only.apply(window)
    runtime_tray_only.apply(window, app)
    with __import__("contextlib").suppress(Exception):
        window.refresh_translations()
