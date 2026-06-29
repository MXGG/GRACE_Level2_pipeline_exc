"""Compact visual polish for the Qt desktop pages.

This module removes explanatory prose from high-frequency workflow pages and
keeps the UI closer to a compact desktop application rather than an embedded
manual.  Detailed explanations remain available through the Help dialog.
"""

from __future__ import annotations

import contextlib

from PySide6.QtWidgets import QLabel, QWidget

from grace_pipeline.ui.qt.pages import _make_field_row
from grace_pipeline.ui.qt.qt_safe import qt_object_is_alive


def _is_zh(window) -> bool:
    return getattr(getattr(window, "ui_preferences", None), "language", "en") == "zh"


def _tr(window, en: str, zh: str) -> str:
    return zh if _is_zh(window) else en


def _hide(widget) -> None:
    if widget is not None:
        with contextlib.suppress(RuntimeError):
            widget.setVisible(False)


def _hide_long_explanatory_labels(page, *, min_len: int = 38) -> None:
    """Hide prose-like labels while preserving field values and short statuses."""

    keep_object_names = {"CardTitle", "PageTitle", "LabelCaps", "MonoText", "StatusBadge"}
    for label in page.findChildren(QLabel):
        if not qt_object_is_alive(label):
            continue
        text = (label.text() or "").strip()
        if not text:
            continue
        if label.objectName() in keep_object_names:
            continue
        if "\\" in text or ":\\" in text:
            continue
        if len(text) >= min_len or label.objectName() == "PageSubtitle":
            _hide(label)


def _hide_page_subtitles(window) -> None:
    for page in getattr(window, "_pages", {}).values():
        for label in page.findChildren(QLabel):
            if not qt_object_is_alive(label):
                continue
            if label.objectName() == "PageSubtitle":
                _hide(label)


def _compact_dashboard(window) -> None:
    page = getattr(window, "page_dashboard", None)
    if page is None:
        return

    # Remove dashboard shortcut buttons. The same actions remain available from
    # the navigation rail or the top toolbar, so this avoids duplicated controls.
    for attr in (
        "btn_open_data_paths",
        "btn_validate_paths",
        "btn_open_processing",
        "btn_load_config",
        "btn_save_config",
        "btn_run_full",
        "btn_pause_run",
        "btn_stop_run",
        "btn_console_run",
        "btn_open_preview",
    ):
        _hide(getattr(page, attr, None))

    for attr in ("lbl_output_hint", "lbl_time_span"):
        _hide(getattr(page, attr, None))

    # Remove redundant project subtitle left by the generic header builder.
    _hide_long_explanatory_labels(page, min_len=32)


def _compact_processing_page(window) -> None:
    page = getattr(window, "page_processing", None)
    if page is None:
        return

    # Merge the detected time range into the inversion card and hide the separate
    # time-range card to reduce one full card from the processing page.
    if getattr(page, "card_time_range", None) is not None and not getattr(page, "_compact_time_merged", False):
        with contextlib.suppress(Exception):
            page.lbl_detected_time_range.setParent(None)
            page.card_inversion.body.insertWidget(
                0,
                _make_field_row(_tr(window, "Time range", "时间范围"), page.lbl_detected_time_range),
            )
        _hide(page.card_time_range)
        page._compact_time_merged = True

    for attr in (
        "lbl_time_range_note",
        "lbl_correction_note",
        "lbl_grid_note",
        "lbl_sh_tool_note",
        "lbl_sh_tool_status",
    ):
        _hide(getattr(page, attr, None))

    _hide_long_explanatory_labels(page, min_len=54)


def _compact_leakage_page(window) -> None:
    page = getattr(window, "page_leakage", None)
    if page is None:
        return

    # Keep the three method cards and required inputs, but move detailed method
    # text to Help. Status labels remain visible only after users read data.
    for attr in (
        "lbl_lrc_method_hint",
        "lbl_lrc_output_hint",
        "lbl_preview_status",
        "lbl_lrc_reference_info",
        "lbl_lrc_filter_hint",
    ):
        _hide(getattr(page, attr, None))

    # Avoid mixed English/Chinese in visible official-gain labels under Chinese UI.
    if _is_zh(window):
        with contextlib.suppress(Exception):
            page.rb_lrc_official_gain.setText("官方尺度/增益因子")
        with contextlib.suppress(Exception):
            page.edit_reference_input.setPlaceholderText("官方尺度/增益因子网格")
        with contextlib.suppress(Exception):
            page.lbl_lrc_reference_label.setText("尺度/增益因子网格")

    _hide_long_explanatory_labels(page, min_len=46)


def _compact_basin_page(window) -> None:
    page = getattr(window, "page_basin", None)
    if page is None:
        return

    # Basin analysis currently contains dense descriptions below option groups.
    # Hide prose labels and keep controls/tables/results visible.
    _hide_long_explanatory_labels(page, min_len=42)


def _compact_other_pages(window) -> None:
    for name in ("page_data_paths", "page_preview"):
        page = getattr(window, name, None)
        if page is not None:
            _hide_long_explanatory_labels(page, min_len=60)


def _localize_visible_top_controls(window) -> None:
    if not _is_zh(window):
        return
    replacements = {
        "Load Config": "加载配置",
        "Save Config": "保存配置",
        "Run Filters": "运行滤波",
        "Preview Results": "预览结果",
        "Console": "控制台",
        "Pause": "暂停",
        "Stop": "停止",
        "Dashboard": "总览",
        "Processing Setup": "滤波处理",
    }
    for page in getattr(window, "_pages", {}).values():
        for label in page.findChildren(QLabel):
            if not qt_object_is_alive(label):
                continue
            text = label.text()
            if text in replacements:
                label.setText(replacements[text])
        for widget in page.findChildren(QWidget):
            if not qt_object_is_alive(widget):
                continue
            if hasattr(widget, "text") and hasattr(widget, "setText"):
                with contextlib.suppress(Exception):
                    text = widget.text()
                    if text in replacements:
                        widget.setText(replacements[text])


def install_compact_polish(window) -> None:
    """Apply compact page presentation after all page extensions are installed."""

    _hide_page_subtitles(window)
    _compact_dashboard(window)
    _compact_processing_page(window)
    _compact_leakage_page(window)
    _compact_basin_page(window)
    _compact_other_pages(window)
    _localize_visible_top_controls(window)
