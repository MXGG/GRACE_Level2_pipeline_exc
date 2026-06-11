"""PySide6 application bootstrap for the first-stage desktop shell."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_windows_fonts() -> None:
    from PySide6.QtGui import QFontDatabase

    font_candidates = [
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
    ]
    for font_path in font_candidates:
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))


def start_gui(argv: list[str] | None = None):
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from grace_pipeline.ui.qt import leakage_wizard_stable
    from grace_pipeline.ui.qt.global_monitor import configure_global_run_monitor
    from grace_pipeline.ui.qt.help_docs import bind_help_docs
    from grace_pipeline.ui.qt.main_window import MainWindow
    from grace_pipeline.ui.qt.splash import create_splash_screen
    from grace_pipeline.ui.qt.theme import app_stylesheet

    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_MAX_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")

    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(argv or sys.argv)

    app.setOrganizationName("GRACE-L2")
    app.setApplicationName("GRACE Level-2 Pipeline")

    splash = create_splash_screen()
    if splash is not None:
        splash.set_progress(12, "Loading runtime environment...")

    app.setStyleSheet(app_stylesheet("system", app=app))
    _load_windows_fonts()
    preferred_families = [
        "Segoe UI",
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "Arial",
    ]
    available = set(QFontDatabase.families())
    family = next((name for name in preferred_families if name in available), "")
    font = QFont(family, 10) if family else QFont()
    if not family:
        font.setPointSize(10)
    app.setFont(font)
    if splash is not None:
        splash.set_progress(32, "Preparing interface fonts and theme...")

    window = MainWindow(load_persisted=True)
    leakage_wizard_stable.install_leakage_wizard(window)
    bind_help_docs(window)
    if splash is not None:
        splash.set_progress(68, "Constructing processing workspace...")

    configure_global_run_monitor(window)
    if splash is not None:
        splash.set_progress(84, "Binding run monitor and workflow controls...")

    window.show()
    if splash is not None:
        splash.set_progress(100, "Ready.")
        splash.finish(window)

    if owns_app:
        return app.exec()
    return window
