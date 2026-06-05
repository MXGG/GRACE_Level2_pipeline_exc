"""Global run-monitor wiring for the Qt shell.

This module keeps run monitoring in the top application bar instead of exposing a
separate Run Monitor page. It is deliberately written as a small wiring layer so
existing controller signals and page widgets remain compatible during the Qt
architecture cleanup.
"""

from __future__ import annotations

import time
from types import MethodType

from PySide6.QtWidgets import QLabel, QPushButton, QHBoxLayout, QWidget


_CONFIGURED_ATTR = "_global_run_monitor_configured"


def _add_label(layout, text: str, object_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setMinimumWidth(96)
    label.setWordWrap(False)
    layout.addWidget(label, 0)
    return label


def _format_eta(start_ts: float, pct: float) -> str:
    try:
        pct = float(pct)
    except Exception:
        return "ETA: --"
    if pct >= 100.0:
        return "ETA: complete"
    if pct <= 0.0 or not start_ts:
        return "ETA: calculating"
    elapsed = max(0.0, time.time() - float(start_ts))
    remaining = elapsed * max(0.0, 100.0 - pct) / max(pct, 1.0e-6)
    if remaining < 60.0:
        return f"ETA: {int(round(remaining))} s"
    minutes = int(remaining // 60)
    seconds = int(round(remaining % 60))
    if minutes < 60:
        return f"ETA: {minutes} min {seconds:02d} s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"ETA: {hours} h {minutes:02d} min"


def configure_global_run_monitor(window) -> None:
    """Move run control/monitoring to the global top bar.

    Safe to call multiple times. The function is used both by the normal GUI
    bootstrap and GUI tests that instantiate ``MainWindow`` directly.
    """
    if bool(getattr(window, _CONFIGURED_ATTR, False)):
        return
    setattr(window, _CONFIGURED_ATTR, True)

    progress_layout = window.top_progress_wrap.layout()
    if progress_layout is None:
        progress_layout = QHBoxLayout(window.top_progress_wrap)

    window.top_progress_task = _add_label(progress_layout, "Task: idle", "TopProgressDetail")
    window.top_progress_subtask = _add_label(progress_layout, "Subtask: idle", "TopProgressDetail")
    window.top_progress_eta = _add_label(progress_layout, "ETA: --", "TopProgressDetail")

    window.btn_top_pause = QPushButton("Pause")
    window.btn_top_pause.setObjectName("GhostButton")
    window.btn_top_pause.setMinimumHeight(30)
    window.btn_top_pause.setEnabled(False)
    progress_layout.addWidget(window.btn_top_pause, 0)

    window.btn_top_stop = QPushButton("Stop")
    window.btn_top_stop.setObjectName("DangerGhostButton")
    window.btn_top_stop.setMinimumHeight(30)
    window.btn_top_stop.setEnabled(False)
    progress_layout.addWidget(window.btn_top_stop, 0)

    # Keep Dashboard as an overview page. Its start/pause/stop controls are no
    # longer user-facing; run entry now lives beside the filter settings.
    for name in ("btn_run_full", "btn_pause_run", "btn_stop_run"):
        button = getattr(window.page_dashboard, name, None)
        if button is not None:
            button.setVisible(False)
            button.setEnabled(False)

    if not hasattr(window.page_processing, "btn_run_filters"):
        run_row = QWidget()
        run_layout = QHBoxLayout(run_row)
        run_layout.setContentsMargins(0, 10, 0, 0)
        run_layout.setSpacing(8)
        window.page_processing.btn_run_filters = QPushButton("Run Filters")
        window.page_processing.btn_run_filters.setObjectName("PrimaryButton")
        window.page_processing.btn_run_filters.setMinimumHeight(38)
        run_layout.addStretch(1)
        run_layout.addWidget(window.page_processing.btn_run_filters, 0)
        window.page_processing.card_filters.body.addWidget(run_row)

    window.btn_run = window.page_processing.btn_run_filters
    window.btn_pause = window.btn_top_pause
    window.btn_stop = window.btn_top_stop
    controller = getattr(window, "controller", None)
    if controller is not None:
        try:
            window.page_processing.btn_run_filters.clicked.connect(controller.on_run_pipeline)
        except Exception:
            pass
        try:
            window.btn_top_pause.clicked.connect(controller.on_pause_active)
        except Exception:
            pass
        try:
            window.btn_top_stop.clicked.connect(controller.on_stop_active)
        except Exception:
            pass

    original_set_active_page = window.set_active_page
    original_set_run_active = window.set_run_active
    original_set_run_progress = window.set_run_progress

    def set_active_page(self, key: str):
        if key == "monitor":
            key = "dashboard"
        return original_set_active_page(key)

    def _set_run_button_state(self, active: bool):
        run_button = getattr(self, "btn_run", None)
        if run_button is not None:
            run_button.setEnabled(not active)
        for btn in (getattr(self, "btn_top_pause", None), getattr(self, "btn_top_stop", None)):
            if btn is not None:
                btn.setEnabled(active)
        pause_button = getattr(self, "btn_top_pause", None)
        if pause_button is not None and not active:
            pause_button.setText("Pause")

    def set_pause_action_paused(self, paused: bool):
        text = "Resume" if paused else "Pause"
        pause_button = getattr(self, "btn_top_pause", None)
        if pause_button is not None:
            pause_button.setText(text)
        monitor_pause = getattr(getattr(self, "page_monitor", None), "btn_pause_run", None)
        if monitor_pause is not None:
            monitor_pause.setText(text)

    def set_run_active(self, active: bool, text: str = "", indeterminate: bool = False):
        if active:
            self._global_run_started_at = time.time()
        original_set_run_active(active, text=text, indeterminate=indeterminate)
        self._set_run_button_state(active)
        if active:
            self.top_progress_wrap.setVisible(True)
            if text:
                self.top_progress_task.setText(f"Task: {text}")
            self.top_progress_subtask.setText("Subtask: preparing")
            self.top_progress_eta.setText("ETA: calculating")
        elif text == "Idle":
            self.top_progress_task.setText("Task: idle")
            self.top_progress_subtask.setText("Subtask: idle")
            self.top_progress_eta.setText("ETA: --")

    def set_run_progress(self, pct: float, detail: str = "", stage: str = "", subtask: str = "", eta: str = ""):
        original_set_run_progress(pct, detail=detail, stage=stage)
        task_text = stage or self.top_progress_label.text() or "Running"
        subtask_text = subtask or detail or "working"
        self.top_progress_task.setText(f"Task: {task_text}")
        self.top_progress_subtask.setText(f"Subtask: {subtask_text}")
        self.top_progress_eta.setText(eta or _format_eta(getattr(self, "_global_run_started_at", 0.0), pct))

    window.set_active_page = MethodType(set_active_page, window)
    window._set_run_button_state = MethodType(_set_run_button_state, window)
    window.set_pause_action_paused = MethodType(set_pause_action_paused, window)
    window.set_run_active = MethodType(set_run_active, window)
    window.set_run_progress = MethodType(set_run_progress, window)
    window._set_run_button_state(False)
    window.refresh_translations()
