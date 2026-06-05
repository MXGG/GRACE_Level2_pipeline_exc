"""PySide6 application bootstrap for the first-stage desktop shell."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import MethodType


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


def _enable_monitor_page(window) -> None:
    """Route the Run Monitor nav item to the real monitor page.

    The historical shell instantiated ``RunMonitorPage`` but redirected the
    monitor key back to Dashboard. Keeping this patch in bootstrap avoids a
    large UI-file rewrite while making the monitor page reachable from the nav
    rail. It can be folded into ``MainWindow.set_active_page`` in the later full
    Qt cleanup.
    """
    from grace_pipeline.ui.qt.mock_data import PAGE_TITLES

    def set_active_page(self, key: str):
        if key not in self._pages:
            return
        self.stack.setCurrentWidget(self._pages[key])
        self.breadcrumb.setText(PAGE_TITLES.get(key, key))
        for btn_key, btn in self._nav_buttons.items():
            btn.setChecked(btn_key == key)
        self._apply_responsive_layout(force=(key == "preview"))
        self.refresh_translations()

    window.set_active_page = MethodType(set_active_page, window)


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
    _enable_monitor_page(window)
    window.show()

    if owns_app:
        return app.exec()
    return window
