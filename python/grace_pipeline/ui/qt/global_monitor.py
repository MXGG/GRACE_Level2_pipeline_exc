"""Global run-monitor and page-composition wiring for the Qt shell.

This module keeps run monitoring in the top application bar instead of exposing a
separate Run Monitor page. It also folds the minimal filter-processing path
inputs into the Processing page so the Dashboard can remain an overview page.
"""

from __future__ import annotations

import contextlib
import os
import re
import threading
import time
from pathlib import Path
from types import MethodType

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QHBoxLayout, QWidget


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


def _field_row_for_widget(widget):
    row = widget.parentWidget() if widget is not None else None
    while row is not None and row.objectName() != "FieldRow":
        row = row.parentWidget()
    return row


def _hide_field_row_for_widget(widget) -> None:
    row = _field_row_for_widget(widget)
    if row is not None:
        row.hide()


def _show_field_row_for_widget(widget) -> None:
    row = _field_row_for_widget(widget)
    if row is not None:
        row.show()


def _safe_hide(widget) -> None:
    if widget is None:
        return
    try:
        widget.hide()
    except RuntimeError:
        return


def _safe_show(widget) -> None:
    if widget is None:
        return
    try:
        widget.show()
    except RuntimeError:
        return


def _move_field_row_to_layout(widget, target_layout, insert_index: int | None = None) -> None:
    row = _field_row_for_widget(widget)
    if row is None:
        return
    parent = row.parentWidget()
    if parent is not None and parent.layout() is not None:
        parent.layout().removeWidget(row)
    row.show()
    if insert_index is None:
        target_layout.addWidget(row)
    else:
        target_layout.insertWidget(insert_index, row)


def _ym_from_any(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    match = re.search(r"(\d{4})\D?(\d{1,2})", raw)
    if not match:
        return ""
    year = int(match.group(1))
    month = int(match.group(2))
    if 1 <= month <= 12:
        return f"{year:04d}-{month:02d}"
    return ""


def _date_from_ym(ym: str) -> str:
    ym = _ym_from_any(ym)
    return f"{ym}-01" if ym else ""


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
        zh["Open Logs"] = "打开日志"
        zh["Run Filters"] = "运行滤波"
        zh["Load Config"] = "加载配置"
        zh["Save Config"] = "保存配置"
        zh["Validate Paths"] = "校验路径"
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
    window.top_progress_wrap.setMinimumWidth(760)
    window.top_progress_wrap.setMaximumWidth(940)
    window.top_progress_wrap.setMaximumHeight(48)
    window.top_progress_wrap.setToolTip("Click to expand or collapse run progress details.")

    window.top_progress_label.setMinimumWidth(88)
    window.top_progress_label.setMaximumWidth(170)
    window.top_progress_label.setText("Idle")
    window.top_progress_detail.setMinimumWidth(84)
    window.top_progress_detail.setMaximumWidth(118)
    window.top_progress_percent.setMinimumWidth(46)
    window.top_progress_percent.setMaximumWidth(56)
    window.top_progress_bar.setMinimumWidth(230)
    window.top_progress_bar.setMaximumWidth(430)

    window.top_progress_task = QLabel("Task idle | Subtask idle | ETA --")
    window.top_progress_task.setObjectName("TopProgressDetail")
    window.top_progress_task.setMinimumWidth(300)
    window.top_progress_task.setMaximumWidth(640)
    window.top_progress_task.setWordWrap(False)
    progress_layout.addWidget(window.top_progress_task, 1)

    window.top_progress_subtask = window.top_progress_task
    window.top_progress_eta = window.top_progress_task

    window.btn_top_pause = QPushButton("Pause")
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
        window.top_progress_wrap.setMaximumWidth(1180 if expanded else 940)
        window.top_progress_bar.setMaximumWidth(560 if expanded else 430)
        window.top_progress_task.setMaximumWidth(860 if expanded else 640)

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


def _install_processing_action_bar(window) -> None:
    proc = window.page_processing
    data_page = window.page_data_paths
    if hasattr(proc, "filter_action_bar"):
        return
    proc.filter_action_bar = QWidget()
    layout = QHBoxLayout(proc.filter_action_bar)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addStretch(1)
    data_page.btn_load_config.setText("Load Config")
    data_page.btn_save_config.setText("Save Config")
    data_page.btn_validate_paths.setText("Validate Paths")
    proc.btn_run_filters.setMinimumWidth(148)
    for button in (data_page.btn_load_config, data_page.btn_save_config, data_page.btn_validate_paths, proc.btn_run_filters):
        layout.addWidget(button, 0)
    proc.body.insertWidget(1, proc.filter_action_bar)


def _move_filter_paths_to_processing(window) -> None:
    data_page = window.page_data_paths
    proc = window.page_processing
    _set_card_title(data_page.card_input_dirs, "Filter Input Paths")
    _set_card_title(data_page.card_output_dirs, "Filter Output Paths")
    _set_card_title(data_page.card_reference_paths, "Auxiliary Filter Files")

    if not hasattr(proc, "btn_run_filters"):
        proc.btn_run_filters = QPushButton("Run Filters")
        proc.btn_run_filters.setObjectName("PrimaryButton")
        proc.btn_run_filters.setMinimumHeight(38)

    # Input card: keep the user-selected GFC directory first, then detected
    # coverage, then optional download controls.
    data_page.btn_download_dir_browse.setText("选择下载文件夹...")
    data_page.btn_download_gfc_range.setText("下载")
    _move_field_row_to_layout(data_page.edit_gfc_input_dir, data_page.card_input_dirs.body, insert_index=0)
    _move_field_row_to_layout(data_page.lbl_gfc_detected_range, data_page.card_input_dirs.body, insert_index=1)
    _move_field_row_to_layout(data_page.edit_download_dir, data_page.card_input_dirs.body, insert_index=2)

    # Output card: hide the raw logs path and expose an action button instead.
    _hide_field_row_for_widget(data_page.edit_logs_dir)
    if not hasattr(data_page, "btn_open_logs"):
        data_page.btn_open_logs = QPushButton("Open Logs")
        data_page.btn_open_logs.setObjectName("GhostButton")
        data_page.card_output_dirs.body.addWidget(data_page.btn_open_logs)
    _safe_show(data_page.btn_open_logs)

    # Auxiliary filter files. Reuse existing rows instead of recreating rows to
    # avoid deleting Qt C++ children that are still referenced by Python wrappers.
    _move_field_row_to_layout(data_page.edit_ddk_data_dir, data_page.card_reference_paths.body, insert_index=0)
    for widget in (data_page.edit_ddk_data_dir, data_page.edit_low_degree_path, data_page.edit_degree1_path, data_page.edit_gia_path):
        _show_field_row_for_widget(widget)

    for widget in (
        getattr(data_page, "edit_boundary_path", None), getattr(data_page, "edit_boundary_root", None),
        getattr(data_page, "edit_mascon_root", None), getattr(data_page, "edit_mascon_reference", None),
        getattr(data_page, "edit_mascon_gad", None), getattr(data_page, "edit_mascon_gia", None),
    ):
        _hide_field_row_for_widget(widget)
    for widget in (getattr(data_page, "btn_toggle_reference_roots", None), getattr(data_page, "reference_roots_panel", None)):
        _safe_hide(widget)

    try:
        _remove_widget_from_layout(data_page.card_input_dirs)
        _remove_widget_from_layout(data_page.card_output_dirs)
        _remove_widget_from_layout(data_page.card_reference_paths)
        proc.body.insertWidget(2, data_page.card_input_dirs)
        proc.body.insertWidget(3, data_page.card_output_dirs)
        proc.body.insertWidget(4, data_page.card_reference_paths)
    except Exception:
        pass

    _install_degree_input(window)
    _install_processing_action_bar(window)


def _patch_filter_path_scanning(controller) -> None:
    from grace_pipeline.core.time_index import TimeEntry, detect_gfc_files, extract_ym_from_gfc, summarize_time_coverage
    from grace_pipeline.ui.qt.controller import ROOT_DIR

    def detect_time_entries_for_ui(self) -> list:
        gfc_dir = self._native_path(self.window.page_data_paths.edit_gfc_input_dir.text(), base_dir=ROOT_DIR)
        if not gfc_dir or not Path(gfc_dir).exists():
            return []
        entries = []
        for file_path in detect_gfc_files(gfc_dir, getattr(self.host.cfg.time, "product_type", "GSM"), getattr(self.host.cfg.time, "file_ext", ".gfc")):
            ym = extract_ym_from_gfc(file_path)
            if ym:
                entries.append(TimeEntry.from_ym(ym, file_path))
        entries.sort(key=lambda item: item.dt)
        return entries

    def refresh_detected_time_range(self) -> None:
        page = self.window.page_processing
        entries = self._detect_time_entries_for_ui()
        if entries:
            coverage = summarize_time_coverage(entries)
            detected_text = (
                f"{coverage['available_month_count']} GFC files | "
                f"{coverage['start_ym']} -> {coverage['end_ym']} | "
                f"missing={coverage['missing_month_count']}"
            )
            detected_start = _date_from_ym(entries[0].ym)
            detected_end = _date_from_ym(entries[-1].ym)
        else:
            detected_text = "Detected from GFC files: no valid files found."
            detected_start = ""
            detected_end = ""
        page.lbl_detected_time_range.setText(detected_text)
        self.window.page_data_paths.lbl_gfc_detected_range.setText(detected_text)
        if not page.chk_manual_time_override.isChecked():
            self._set_edit_text(page.edit_start_date, detected_start, block_signals=True)
            self._set_edit_text(page.edit_end_date, detected_end, block_signals=True)
        self.refresh_dashboard()

    controller._detect_time_entries_for_ui = MethodType(detect_time_entries_for_ui, controller)
    controller._refresh_detected_time_range = MethodType(refresh_detected_time_range, controller)


def _patch_download_controls(window, controller) -> None:
    if controller is None:
        return
    from grace_pipeline.ui.qt.controller import ROOT_DIR

    controller.host._scope_events.setdefault("download", {"pause": threading.Event(), "stop": threading.Event()})

    def sync_download_source_controls(self, update_options: bool = True) -> None:
        page = self.window.page_data_paths
        product_type = self._download_product_type()
        if update_options:
            current = self._combo_value(page.cmb_gfc_center)
            values = ["CSR", "JPL", "GSFC"] if product_type == "MASCON_NC" else ["自动", "CSR", "JPL", "GFZ", "HUST", "ITSG"]
            from PySide6.QtCore import QSignalBlocker

            with QSignalBlocker(page.cmb_gfc_center):
                page.cmb_gfc_center.clear()
                for value in values:
                    page.cmb_gfc_center.addItem(value, value)
                page.cmb_gfc_center.setCurrentText(current if current in values else values[0])
        if hasattr(page, "cmb_mascon_resolution"):
            page.cmb_mascon_resolution.setVisible(product_type == "MASCON_NC")
        page.btn_download_gfc_range.setText("下载")
        page.btn_download_dir_browse.setText("选择下载文件夹...")
        center = self._configured_gfc_center()
        if product_type == "GSM" and center in {"CSR", "JPL", "GFZ"}:
            self._apply_low_degree_files_for_center(center)
            page.lbl_gfc_download_status.setText(f"{center} GSM 使用 PO.DAAC；下载前可能需要 Earthdata 登录。")
        elif product_type == "GSM" and center in {"HUST", "ITSG"}:
            page.lbl_gfc_download_status.setText(f"{center} GSM 使用 ICGEM 下载，无需 Earthdata 登录。")
        elif product_type == "MASCON_NC":
            page.lbl_gfc_download_status.setText("Mascon NC 支持 CSR、JPL、GSFC；分辨率需与机构发布产品匹配。")
        page.btn_download_gfc_range.setToolTip(page.lbl_gfc_download_status.text())

    def gfc_download_range(self) -> tuple[str, str]:
        download_page = self.window.page_data_paths
        processing_page = self.window.page_processing
        start = _ym_from_any(download_page.edit_download_start_ym.text()) or _ym_from_any(processing_page.edit_start_date.text())
        end = _ym_from_any(download_page.edit_download_end_ym.text()) or _ym_from_any(processing_page.edit_end_date.text())
        if not start or not end:
            entries = self._detect_time_entries_for_ui()
            if entries:
                start, end = entries[0].ym, entries[-1].ym
        if not start or not end:
            raise ValueError("Set a valid start/end month before downloading files.")
        processing_start = _ym_from_any(processing_page.edit_start_date.text())
        processing_end = _ym_from_any(processing_page.edit_end_date.text())
        if processing_start and start < processing_start:
            start = processing_start
        if processing_end and end > processing_end:
            end = processing_end
        if start > end:
            raise ValueError("Download date range is outside the configured processing range.")
        return start, end

    def on_download_gfc_range(self) -> None:
        page = self.window.page_data_paths
        download_dir = self._native_path(page.edit_download_dir.text(), base_dir=ROOT_DIR)
        if not download_dir:
            self._show_warning("下载数据", "请先设置下载文件夹。")
            return
        start_ym, end_ym = self._gfc_download_range()
        center = self._configured_gfc_center()
        product_type = self._download_product_type()
        if product_type == "MASCON_NC" and center not in {"CSR", "JPL", "GSFC"}:
            self._show_warning("下载数据", "Mascon NC 下载目前支持 CSR、JPL 和 GSFC。")
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

    controller._sync_download_source_controls = MethodType(sync_download_source_controls, controller)
    controller._gfc_download_range = MethodType(gfc_download_range, controller)
    controller.on_download_gfc_range = MethodType(on_download_gfc_range, controller)
    disconnect = getattr(window.page_data_paths.btn_download_gfc_range.clicked, "disconnect", None)
    try:
        if disconnect is not None:
            window.page_data_paths.btn_download_gfc_range.clicked.disconnect()
    except Exception:
        pass
    window.page_data_paths.btn_download_gfc_range.clicked.connect(controller.on_download_gfc_range)


def _patch_filter_run_validation(window, controller) -> None:
    if controller is None or bool(getattr(controller, "_filter_run_validation_patched", False)):
        return
    controller._filter_run_validation_patched = True
    original_run_pipeline = controller.on_run_pipeline

    def validate_required_filter_files(self) -> list[str]:
        page = self.window.page_processing
        paths = self.window.page_data_paths
        issues: list[str] = []

        def exists(label: str, value: str) -> None:
            text = str(value or "").strip()
            if not text:
                issues.append(f"{label}: not configured")
                return
            path = Path(self._native_path(text, base_dir=Path.cwd()))
            if not path.exists():
                issues.append(f"{label}: missing ({path})")

        if page.btn_filter_ddk.isChecked():
            exists("DDK data directory", paths.edit_ddk_data_dir.text())
        if page.chk_lowdeg_enable.isChecked():
            if page.chk_replace_c20.isChecked() or page.chk_replace_c30.isChecked():
                exists("C20/C30 replacement file", paths.edit_low_degree_path.text())
            if page.chk_replace_degree1.isChecked():
                exists("Degree-1 replacement file", paths.edit_degree1_path.text())
        if page.chk_apply_gia.isChecked():
            exists("GIA model file", paths.edit_gia_path.text())
        return issues

    def on_run_pipeline(self):
        issues = self._validate_required_filter_files()
        if issues:
            self._sync_data_path_badges()
            self._show_warning("滤波处理", "以下必要文件不存在或未配置：\n" + "\n".join(f"- {item}" for item in issues))
            self.on_log("[VALIDATION] Filter run blocked by missing files: " + "; ".join(issues), "stderr")
            return
        return original_run_pipeline()

    controller._validate_required_filter_files = MethodType(validate_required_filter_files, controller)
    controller.on_run_pipeline = MethodType(on_run_pipeline, controller)


def _patch_open_logs(window, controller) -> None:
    data_page = window.page_data_paths
    if not hasattr(data_page, "btn_open_logs"):
        return

    def open_logs() -> None:
        output_root = data_page.edit_main_output_root.text().strip()
        log_dir = data_page.edit_logs_dir.text().strip()
        if not log_dir and output_root:
            log_dir = str(Path(output_root) / "logs")
        if not log_dir:
            log_dir = str(Path.cwd() / "outputs" / "logs")
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    with contextlib.suppress(Exception):
        data_page.btn_open_logs.clicked.disconnect()
    data_page.btn_open_logs.clicked.connect(open_logs)


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
        _patch_filter_path_scanning(controller)
        _patch_download_controls(window, controller)
        _patch_filter_run_validation(window, controller)
        _patch_open_logs(window, controller)
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
            pause_button.setText("Pause" if active else "Pause")
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
            self.set_pause_action_paused(False)
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
    if controller is not None:
        with contextlib.suppress(Exception):
            controller._refresh_detected_time_range()
        with contextlib.suppress(Exception):
            controller._sync_download_source_controls()
    window.refresh_translations()
    _retitle_processing_page(window)
