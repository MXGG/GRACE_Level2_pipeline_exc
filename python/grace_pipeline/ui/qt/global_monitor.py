"""Global run-monitor and page-composition wiring for the Qt shell.

This module keeps run monitoring in the top application bar instead of exposing a
separate Run Monitor page. It also folds the minimal filter-processing path
inputs into the Processing page so the Dashboard can remain an overview page.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from types import MethodType

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QHBoxLayout, QWidget

from grace_pipeline.ui.qt.path_defaults import DEFAULT_DATA_PATHS


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


def _clear_layout(layout) -> None:
    while layout is not None and layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)
        if widget is not None:
            widget.setParent(None)


def _set_card_title(card, title: str) -> None:
    label = card.findChild(QLabel, "CardTitle")
    if label is not None:
        label.setText(title)


def _hide_field_row_for_widget(widget) -> None:
    row = widget.parentWidget() if widget is not None else None
    while row is not None and row.objectName() != "FieldRow":
        row = row.parentWidget()
    if row is not None:
        row.hide()


def _retitle_processing_page(window) -> None:
    try:
        from grace_pipeline.ui.qt.i18n import TRANSLATIONS

        zh = TRANSLATIONS.setdefault("zh", {})
        zh["Filter Processing"] = "滤波处理"
        zh["Processing Setup"] = "滤波处理"
        zh["Configure input/output paths, time coverage, grid geometry, inversion setup, and filters."] = "配置输入输出路径、时间范围、网格、反演和滤波方法。"
        zh["Filter Input Paths"] = "滤波输入路径"
        zh["Filter Output Paths"] = "滤波输出路径"
        zh["Auxiliary Filter Files"] = "辅助滤波文件"
        zh["Maximum Degree / Order"] = "最大阶次"
    except Exception:
        pass

    for label in window.page_processing.findChildren(QLabel):
        if label.text() in {"Processing Setup", "处理设置"}:
            label.setText("Filter Processing")
        elif label.text() == "Configure time coverage, grid geometry, inversion setup, and filters.":
            label.setText("Configure input/output paths, time coverage, grid geometry, inversion setup, and filters.")


def _compact_top_monitor(window) -> None:
    progress_layout = window.top_progress_wrap.layout()
    if progress_layout is None:
        progress_layout = QHBoxLayout(window.top_progress_wrap)
    progress_layout.setContentsMargins(8, 5, 8, 5)
    progress_layout.setSpacing(6)
    window.top_progress_wrap.setMinimumWidth(690)
    window.top_progress_wrap.setMaximumWidth(820)
    window.top_progress_wrap.setMaximumHeight(48)
    window.top_progress_wrap.setToolTip("Click to expand or collapse run progress details.")

    window.top_progress_label.setMinimumWidth(80)
    window.top_progress_label.setMaximumWidth(160)
    window.top_progress_label.setText("Idle")
    window.top_progress_detail.setMinimumWidth(76)
    window.top_progress_detail.setMaximumWidth(100)
    window.top_progress_percent.setMinimumWidth(44)
    window.top_progress_percent.setMaximumWidth(52)
    window.top_progress_bar.setMinimumWidth(190)
    window.top_progress_bar.setMaximumWidth(340)

    window.top_progress_task = QLabel("Task idle | Subtask idle | ETA --")
    window.top_progress_task.setObjectName("TopProgressDetail")
    window.top_progress_task.setMinimumWidth(260)
    window.top_progress_task.setMaximumWidth(520)
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

    def toggle_progress_width(_event):
        expanded = not bool(getattr(window, "_top_progress_expanded", False))
        window._top_progress_expanded = expanded
        window.top_progress_wrap.setMaximumWidth(1040 if expanded else 820)
        window.top_progress_bar.setMaximumWidth(450 if expanded else 340)
        window.top_progress_task.setMaximumWidth(760 if expanded else 520)

    window.top_progress_wrap.mousePressEvent = toggle_progress_width


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


def _install_degree_input(window) -> None:
    page = window.page_processing
    if hasattr(page, "edit_degree_order"):
        return
    _hide_field_row_for_widget(getattr(page, "slider_degree_order", None))
    page.edit_degree_order = QLineEdit(str(getattr(page.slider_degree_order, "value", lambda: 60)()))
    page.edit_degree_order.setPlaceholderText("60")
    page.edit_degree_order.setMaximumWidth(160)

    def sync_degree_from_edit() -> None:
        try:
            value = int(float(page.edit_degree_order.text().strip() or "60"))
        except Exception:
            value = 60
        value = max(0, min(240, value))
        page.edit_degree_order.setText(str(value))
        page.slider_degree_order.setValue(value)

    page.edit_degree_order.editingFinished.connect(sync_degree_from_edit)
    try:
        from grace_pipeline.ui.qt.pages import _make_field_row

        page.card_inversion.body.insertWidget(0, _make_field_row("Maximum Degree / Order", page.edit_degree_order))
    except Exception:
        page.card_inversion.body.insertWidget(0, page.edit_degree_order)


def _move_filter_paths_to_processing(window) -> None:
    data_page = window.page_data_paths
    proc = window.page_processing
    _set_card_title(data_page.card_input_dirs, "Filter Input Paths")
    _set_card_title(data_page.card_output_dirs, "Filter Output Paths")
    _set_card_title(data_page.card_reference_paths, "Auxiliary Filter Files")

    try:
        from grace_pipeline.ui.qt.pages import _make_edit_browse_widget, _make_field_row

        _clear_layout(data_page.card_reference_paths.body)
        _hide_field_row_for_widget(data_page.edit_ddk_data_dir)
        data_page.card_reference_paths.body.addWidget(
            _make_field_row(
                "DDK Data Directory",
                _make_edit_browse_widget(data_page.edit_ddk_data_dir, data_page.btn_ddk_browse),
                data_page.badge_ddk_data,
                label_width=220,
            )
        )
        data_page.card_reference_paths.body.addWidget(
            _make_field_row(
                "C20 Replacement File",
                _make_edit_browse_widget(data_page.edit_low_degree_path, data_page.btn_low_degree_browse),
                data_page.badge_low_degree,
                label_width=220,
            )
        )
        data_page.card_reference_paths.body.addWidget(
            _make_field_row(
                "Degree-1 File",
                _make_edit_browse_widget(data_page.edit_degree1_path, data_page.btn_degree1_browse),
                data_page.badge_degree1,
                label_width=220,
            )
        )
        data_page.card_reference_paths.body.addWidget(
            _make_field_row(
                "GIA Model Path",
                _make_edit_browse_widget(data_page.edit_gia_path, data_page.btn_gia_browse),
                data_page.badge_gia,
                label_width=220,
            )
        )
    except Exception:
        pass

    # Mascon and boundary inputs are still present as hidden compatibility
    # widgets for leakage/basin config loading, but not shown in basic filtering.
    for widget in (
        getattr(data_page, "edit_boundary_path", None), getattr(data_page, "btn_boundary_browse", None), getattr(data_page, "badge_boundary_path", None),
        getattr(data_page, "edit_boundary_root", None), getattr(data_page, "btn_boundary_root_browse", None), getattr(data_page, "badge_boundary_root", None),
        getattr(data_page, "edit_mascon_root", None), getattr(data_page, "btn_mascon_root_browse", None), getattr(data_page, "badge_mascon_root", None),
        getattr(data_page, "edit_mascon_reference", None), getattr(data_page, "btn_mascon_reference_browse", None), getattr(data_page, "badge_mascon_reference", None),
        getattr(data_page, "edit_mascon_gad", None), getattr(data_page, "btn_mascon_gad_browse", None), getattr(data_page, "badge_mascon_gad", None),
        getattr(data_page, "edit_mascon_gia", None), getattr(data_page, "btn_mascon_gia_browse", None), getattr(data_page, "badge_mascon_gia", None),
        getattr(data_page, "btn_toggle_reference_roots", None), getattr(data_page, "reference_roots_panel", None),
    ):
        if widget is not None:
            widget.hide()

    try:
        _remove_widget_from_layout(data_page.card_input_dirs)
        _remove_widget_from_layout(data_page.card_output_dirs)
        _remove_widget_from_layout(data_page.card_reference_paths)
        proc.body.insertWidget(1, data_page.card_input_dirs)
        proc.body.insertWidget(2, data_page.card_output_dirs)
        proc.body.insertWidget(3, data_page.card_reference_paths)
    except Exception:
        pass

    _install_degree_input(window)

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


def _patch_download_controls(window, controller) -> None:
    if controller is None:
        return
    controller.host._scope_events.setdefault("download", {"pause": threading.Event(), "stop": threading.Event()})

    def on_download_gfc_range(self) -> None:
        page = self.window.page_data_paths
        download_dir = self._native_path(page.edit_download_dir.text(), base_dir=Path(__file__).resolve().parents[4])
        if not download_dir:
            self._show_warning("下载数据", "请先设置下载文件夹。")
            return
        start_ym, end_ym = self._gfc_download_range()
        center = self._configured_gfc_center()
        product_type = self._download_product_type()
        if product_type == "MASCON_NC" and center not in {"CSR", "JPL", "GSFC"}:
            self._show_warning("下载 Mascon", "Mascon NC 下载目前支持 CSR、JPL 和 GSFC。")
            return
        if not self._ensure_earthdata_auth_for_download(product_type, center):
            return
        low_degree_dir = self._low_degree_dir()
        page.lbl_gfc_download_status.setText(f"正在下载 {center} {product_type}：{start_ym} 到 {end_ym}...")
        pause_event, stop_event = self.host._get_scope_events("download")

        def check_pause_stop() -> None:
            while pause_event.is_set():
                if stop_event.is_set():
                    raise RuntimeError("Download stopped by user.")
                time.sleep(0.2)
            if stop_event.is_set():
                raise RuntimeError("Download stopped by user.")

        def progress(text: str) -> None:
            check_pause_stop()
            self.signals.log.emit(f"[GFC] {text}", "stdout")

        def progress_pct(pct: float, text: str) -> None:
            check_pause_stop()
            self.signals.progress.emit("download", pct, text)

        def task() -> None:
            from grace_pipeline.services.gfc_download import download_gfc_range, download_mascon_nc

            check_pause_stop()
            if product_type == "MASCON_NC":
                result = download_mascon_nc(
                    out_dir=download_dir,
                    source=center,
                    start_ym=start_ym,
                    end_ym=end_ym,
                    resolution=self._configured_mascon_resolution(),
                    progress=progress,
                    progress_pct=progress_pct,
                )
            else:
                result = download_gfc_range(
                    gfc_dir=download_dir,
                    start_ym=start_ym,
                    end_ym=end_ym,
                    center=center,
                    low_degree_dir=low_degree_dir,
                    progress=progress,
                    progress_pct=progress_pct,
                )
            check_pause_stop()
            self.signals.gfc_download_done.emit(result)

        self._run_in_thread("download", task, "DOWNLOADING DATA")

    controller.on_download_gfc_range = MethodType(on_download_gfc_range, controller)
    with_context = getattr(window.page_data_paths.btn_download_gfc_range.clicked, "disconnect", None)
    try:
        if with_context is not None:
            window.page_data_paths.btn_download_gfc_range.clicked.disconnect()
    except Exception:
        pass
    window.page_data_paths.btn_download_gfc_range.clicked.connect(controller.on_download_gfc_range)


def configure_global_run_monitor(window) -> None:
    """Move run control/monitoring to the global top bar and compose pages."""
    if bool(getattr(window, _CONFIGURED_ATTR, False)):
        return
    setattr(window, _CONFIGURED_ATTR, True)

    _retitle_processing_page(window)
    _compact_top_monitor(window)
    _compose_dashboard(window)
    _move_filter_paths_to_processing(window)

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
        _patch_download_controls(window, controller)
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
    _retitle_processing_page(window)
