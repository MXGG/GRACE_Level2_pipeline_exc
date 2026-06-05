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

    from grace_pipeline.ui.qt.main_window import MainWindow
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

    window = MainWindow(load_persisted=True)
    window.show()

    if owns_app:
        return app.exec()
    return window
