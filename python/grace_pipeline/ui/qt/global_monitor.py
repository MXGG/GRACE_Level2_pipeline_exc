"""Global run-monitor and page-composition wiring for the Qt shell.

This module keeps run monitoring in the top application bar instead of exposing a
separate Run Monitor page. It also folds the minimal filter-processing path
inputs into the Processing page so the Dashboard can remain an overview page.
"""

from __future__ import annotations

import time
from types import MethodType

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QFrame, QGridLayout, QHBoxLayout, QWidget


_CONFIGURED_ATTR = "_global_run_monitor_configured"


def _format_eta(start_ts: float, pct: float) -> str:
    try:
        pct = float(pct)
    except Exception:
        return "ETA --"
    if pct >= 100.0:
        return "ETA done"
    if pct <= 0.0 or not start_ts:
        return "ETA ..."
    elapsed = max(0.0, time.time() - float(start_ts))
    remaining = elapsed * max(0.0, 100.0 - pct) / max(pct, 1.0e-6)
    if remaining < 60.0:
        return f"ETA {int(round(remaining))}s"
    minutes = int(remaining // 60)
    seconds = int(round(remaining % 60))
    if minutes < 60:
        return f"ETA {minutes}m{seconds:02d}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"ETA {hours}h{minutes:02d}m"


def _remove_widget_from_layout(widget) -> None:
    parent = widget.parentWidget()
    if parent is not None and parent.layout() is not None:
        parent.layout().removeWidget(widget)


def _set_card_title(card, title: str) -> None:
    label = card.findChild(QLabel, "CardTitle")
    if label is not None:
        label.setText(title)


def _compact_top_monitor(window) -> None:
    progress_layout = window.top_progress_wrap.layout()
    if progress_layout is None:
        progress_layout = QHBoxLayout(window.top_progress_wrap)
    progress_layout.setContentsMargins(8, 5, 8, 5)
    progress_layout.setSpacing(6)
    window.top_progress_wrap.setMinimumWidth(540)
    window.top_progress_wrap.setMaximumHeight(48)

    window.top_progress_label.setMinimumWidth(70)
    window.top_progress_label.setMaximumWidth(140)
    window.top_progress_label.setText("Idle")
    window.top_progress_detail.setMinimumWidth(54)
    window.top_progress_detail.setMaximumWidth(70)
    window.top_progress_percent.setMinimumWidth(34)
    window.top_progress_percent.setMaximumWidth(42)
    window.top_progress_bar.setMinimumWidth(120)
    window.top_progress_bar.setMaximumWidth(190)

    window.top_progress_task = QLabel("Task idle | Subtask idle | ETA --")
    window.top_progress_task.setObjectName("TopProgressDetail")
    window.top_progress_task.setMinimumWidth(190)
    window.top_progress_task.setMaximumWidth(320)
    window.top_progress_task.setWordWrap(False)
    progress_layout.addWidget(window.top_progress_task, 1)

    window.top_progress_subtask = window.top_progress_task
    window.top_progress_eta = window.top_progress_task

    window.btn_top_pause = QPushButton("Resume")
    window.btn_top_pause.setObjectName("GhostButton")
    window.btn_top_pause.setMinimumHeight(28)
    window.btn_top_pause.setMaximumWidth(68)
    window.btn_top_pause.setEnabled(False)
    progress_layout.addWidget(window.btn_top_pause, 0)

    window.btn_top_stop = QPushButton("Stop")
    window.btn_top_stop.setObjectName("DangerGhostButton")
    window.btn_top_stop.setMinimumHeight(28)
    window.btn_top_stop.setMaximumWidth(58)
    window.btn_top_stop.setEnabled(False)
    progress_layout.addWidget(window.btn_top_stop, 0)


def _compose_dashboard(window) -> None:
    page = window.page_dashboard
    page.card_commands.hide()
    try:
        grid = page.body.itemAt(1).widget().layout()
        grid.removeWidget(page.card_commands)
        grid.removeWidget(page.card_active_run)
        grid.removeWidget(page.card_data_availability)
        grid.removeWidget(page.card_output_root)
        grid.removeWidget(page.card_output_preview)
        grid.addWidget(page.card_active_run, 1, 0)
        grid.addWidget(page.card_data_availability, 1, 1)
        grid.addWidget(page.card_output_root, 2, 0)
        grid.addWidget(page.card_output_preview, 2, 1)
        page.card_output_preview.setSizePolicy(page.card_output_root.sizePolicy())
    except Exception:
        pass


def _move_filter_paths_to_processing(window) -> None:
    data_page = window.page_data_paths
    proc = window.page_processing

    proc.add_header = getattr(proc, "add_header", None)
    _set_card_title(data_page.card_input_dirs, "Filter Input Paths")
    _set_card_title(data_page.card_output_dirs, "Filter Output Paths")
    _set_card_title(data_page.card_reference_paths, "Auxiliary Filter Files")

    # Keep only filter-pipeline paths visible. Boundary shapefiles and Mascon
    # reference products belong to later leakage/basin workflows, not to the
    # basic filtering entrypoint.
    for widget in (
        getattr(data_page, "edit_boundary_path", None), getattr(data_page, "btn_boundary_browse", None), getattr(data_page, "badge_boundary_path", None),
        getattr(data_page, "edit_mascon_root", None), getattr(data_page, "btn_mascon_root_browse", None), getattr(data_page, "badge_mascon_root", None),
        getattr(data_page, "edit_mascon_reference", None), getattr(data_page, "btn_mascon_reference_browse", None), getattr(data_page, "badge_mascon_reference", None),
        getattr(data_page, "edit_mascon_gad", None), getattr(data_page, "btn_mascon_gad_browse", None), getattr(data_page, "badge_mascon_gad", None),
        getattr(data_page, "edit_mascon_gia", None), getattr(data_page, "btn_mascon_gia_browse", None), getattr(data_page, "badge_mascon_gia", None),
    ):
        if widget is not None:
            widget.hide()

    # Hide whole reference rows by traversing the row widgets that contain the
    # hidden inputs. The underlying widgets remain alive for config compatibility.
    for edit in (
        getattr(data_page, "edit_boundary_path", None),
        getattr(data_page, "edit_mascon_root", None),
        getattr(data_page, "edit_mascon_reference", None),
        getattr(data_page, "edit_mascon_gad", None),
        getattr(data_page, "edit_mascon_gia", None),
    ):
        if edit is not None:
            row = edit.parentWidget()
            while row is not None and row.parentWidget() is not data_page.card_reference_paths:
                if row.parentWidget() is data_page.card_reference_paths:
                    break
                row = row.parentWidget()
            if row is not None:
                row.hide()

    # Remove the legacy toggle button from the merged page; low-degree/DDK/GIA
    # paths should be visible directly and vertically.
    if hasattr(data_page, "btn_toggle_reference_roots"):
        data_page.btn_toggle_reference_roots.hide()
    if hasattr(data_page, "reference_roots_panel"):
        data_page.reference_roots_panel.show()

    # Put filter path cards above the scientific parameter cards.
    try:
        _remove_widget_from_layout(data_page.card_input_dirs)
        _remove_widget_from_layout(data_page.card_output_dirs)
        _remove_widget_from_layout(data_page.card_reference_paths)
        proc.body.insertWidget(1, data_page.card_input_dirs)
        proc.body.insertWidget(2, data_page.card_output_dirs)
        proc.body.insertWidget(3, data_page.card_reference_paths)
    except Exception:
        pass

    if not hasattr(proc, "btn_run_filters"):
        run_row = QWidget()
        run_layout = QHBoxLayout(run_row)
        run_layout.setContentsMargins(0, 10, 0, 0)
        run_layout.setSpacing(8)
        proc.btn_run_filters = QPushButton("Run Filters")
        proc.btn_run_filters.setObjectName("PrimaryButton")
        proc.btn_run_filters.setMinimumHeight(38)
        run_layout.addStretch(1)
        run_layout.addWidget(proc.btn_run_filters, 0)
        proc.card_filters.body.addWidget(run_row)


def configure_global_run_monitor(window) -> None:
    """Move run control/monitoring to the global top bar and compose pages."""
    if bool(getattr(window, _CONFIGURED_ATTR, False)):
        return
    setattr(window, _CONFIGURED_ATTR, True)

    _compact_top_monitor(window)
    _compose_dashboard(window)
    _move_filter_paths_to_processing(window)

    # Keep Dashboard as an overview page. Its start/pause/stop controls are no
    # longer user-facing; run entry now lives beside the filter settings.
    for name in ("btn_run_full", "btn_pause_run", "btn_stop_run"):
        button = getattr(window.page_dashboard, name, None)
        if button is not None:
            button.setVisible(False)
            button.setEnabled(False)

    window.btn_run = window.page_processing.btn_run_filters
    window.btn_pause = window.btn_top_pause
    window.btn_stop = window.btn_top_stop
    controller = getattr(window, "controller", None)
    if controller is not None:
        for signal, slot in (
            (window.page_processing.btn_run_filters.clicked, controller.on_run_pipeline),
            (window.btn_top_pause.clicked, controller.on_pause_active),
            (window.btn_top_stop.clicked, controller.on_stop_active),
        ):
            try:
                signal.connect(slot)
            except Exception:
                pass

    original_set_active_page = window.set_active_page
    original_set_run_active = window.set_run_active
    original_set_run_progress = window.set_run_progress

    def set_active_page(self, key: str):
        if key in {"monitor", "data_paths"}:
            key = "processing"
        return original_set_active_page(key)

    def _set_run_button_state(self, active: bool):
        run_button = getattr(self, "btn_run", None)
        if run_button is not None:
            run_button.setEnabled(not active)
        pause_button = getattr(self, "btn_top_pause", None)
        stop_button = getattr(self, "btn_top_stop", None)
        if pause_button is not None:
            pause_button.setEnabled(active)
            if not active:
                pause_button.setText("Resume")
        if stop_button is not None:
            stop_button.setEnabled(active)

    def set_pause_action_paused(self, paused: bool):
        text = "Resume" if paused else "Pause"
        pause_button = getattr(self, "btn_top_pause", None)
        if pause_button is not None:
            pause_button.setText(text)
        monitor_pause = getattr(getattr(self, "page_monitor", None), "btn_pause_run", None)
        if monitor_pause is not None:
            monitor_pause.setText(text)

    def _set_monitor_text(self, task: str, subtask: str = "", pct: float | None = None, eta: str = ""):
        task = str(task or "Idle").replace("Task:", "").strip()
        subtask = str(subtask or "").replace("Subtask:", "").strip()
        eta_text = eta or (_format_eta(getattr(self, "_global_run_started_at", 0.0), pct) if pct is not None else "ETA --")
        compact = f"Task: {task}"
        if subtask:
            compact += f" | Subtask: {subtask}"
        compact += f" | {eta_text}"
        self.top_progress_task.setText(compact)
        self.top_progress_task.setToolTip(compact)

    def set_run_active(self, active: bool, text: str = "", indeterminate: bool = False):
        if active:
            self._global_run_started_at = time.time()
        original_set_run_active(active, text=text, indeterminate=indeterminate)
        self._set_run_button_state(active)
        if active:
            self.top_progress_wrap.setVisible(True)
            self._set_monitor_text(text or "Preparing", "preparing", -1.0)
        elif text == "Idle":
            self._set_monitor_text("Idle", "", None, "ETA --")

    def set_run_progress(self, pct: float, detail: str = "", stage: str = "", subtask: str = "", eta: str = ""):
        original_set_run_progress(pct, detail=detail, stage=stage)
        task_text = stage or self.top_progress_label.text() or "Running"
        subtask_text = subtask or detail or "working"
        self._set_monitor_text(task_text, subtask_text, pct, eta)

    window.set_active_page = MethodType(set_active_page, window)
    window._set_run_button_state = MethodType(_set_run_button_state, window)
    window.set_pause_action_paused = MethodType(set_pause_action_paused, window)
    window._set_monitor_text = MethodType(_set_monitor_text, window)
    window.set_run_active = MethodType(set_run_active, window)
    window.set_run_progress = MethodType(set_run_progress, window)
    window._set_run_button_state(False)
    window.refresh_translations()
