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


def _set_label_text(obj, name: str, text: str) -> None:
    label = getattr(obj, name, None)
    if label is not None and hasattr(label, "setText"):
        label.setText(text)


def _append_monitor_metric(monitor, attr_name: str, text: str) -> None:
    if hasattr(monitor, attr_name):
        _set_label_text(monitor, attr_name, text)
        return
    try:
        from PySide6.QtWidgets import QLabel

        label = QLabel(text)
        label.setWordWrap(True)
        setattr(monitor, attr_name, label)
        monitor.card_status.body.addWidget(label)
    except Exception:
        return


def _enable_monitor_page(window) -> None:
    """Route the Run Monitor nav item to the real monitor page and neutralize mock text."""
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

    dashboard = getattr(window, "page_dashboard", None)
    if dashboard is not None:
        _set_label_text(dashboard, "lbl_project_name", "Unsaved configuration")
        _set_label_text(dashboard, "lbl_last_edited", "Not saved")
        _set_label_text(dashboard, "lbl_uid", "pending")
        _set_label_text(dashboard, "lbl_output_root", "Output root: not resolved")
        _set_label_text(dashboard, "lbl_data_count", "0")
        _set_label_text(dashboard, "lbl_time_span", "GFC data files | not scanned")
        _set_label_text(dashboard, "lbl_dashboard_status", "Idle")
        _set_label_text(dashboard, "lbl_dashboard_stage", "Ready to run with the current configuration.")
        _set_label_text(dashboard, "lbl_preview_artifact", "Latest Artifact: waiting for pipeline outputs.")

    monitor = getattr(window, "page_monitor", None)
    if monitor is not None:
        _set_label_text(monitor, "lbl_pipeline_status", "Idle")
        _set_label_text(monitor, "lbl_overall_progress", "0 / 0")
        _set_label_text(monitor, "lbl_current_task", "Waiting for a pipeline run.")
        _append_monitor_metric(monitor, "lbl_current_subtask", "Subtask: not started")
        _append_monitor_metric(monitor, "lbl_eta", "ETA: not available")
        _set_label_text(monitor, "lbl_run_config", "Config: not loaded")
        _set_label_text(monitor, "lbl_run_filters", "Filters: not evaluated")
        _set_label_text(monitor, "lbl_run_output", "Output Root: not resolved")
        _set_label_text(monitor, "lbl_run_timespan", "Time Span: not scanned")
        _set_label_text(monitor, "lbl_output_root", "Output Root: not resolved")
        _set_label_text(monitor, "lbl_output_local", "Local Output: not resolved")
        _set_label_text(monitor, "lbl_output_plots", "Plots: not resolved")
        _set_label_text(monitor, "lbl_last_artifact", "Latest Artifact: not generated yet.")
        log_widget = getattr(monitor, "text_live_logs", None)
        if log_widget is not None and hasattr(log_widget, "setPlainText"):
            log_widget.setPlainText("Run monitor initialized. Start a run to stream live logs.")


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
