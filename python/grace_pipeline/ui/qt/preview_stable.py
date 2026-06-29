"""Stable wrapper for preview-page refinements.

The first preview enhancement pass patches rendering and export, but several
labels are reset later by the global translation refresh.  This wrapper applies
post-refresh text normalisation, hides the in-canvas title, and keeps the CPT
pseudo item from leaving stale UI state.
"""

from __future__ import annotations

import contextlib
import warnings
from types import MethodType

from PySide6.QtWidgets import QLabel, QWidget

from grace_pipeline.ui.qt import preview_enhancements as base
from grace_pipeline.ui.qt.qt_safe import is_deleted_qt_object_error, qt_object_is_alive


def _is_zh(window) -> bool:
    return getattr(getattr(window, "ui_preferences", None), "language", "en") == "zh"


def _tr(window, en: str, zh: str) -> str:
    return zh if _is_zh(window) else en


def _safe_disconnect(signal) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with contextlib.suppress(Exception):
            signal.disconnect()


def _apply_preview_labels(window) -> None:
    page = window.page_preview
    zh = _is_zh(window)
    replacements = {
        "Load Stack Info": _tr(window, "Read Data", "读取数据"),
        "Read Dataset": _tr(window, "Read Data", "读取数据"),
        "读取栈信息": "读取数据",
        "Preview Controls": _tr(window, "Preview Controls", "预览控制"),
        "Dataset Source": _tr(window, "Data Source", "数据源"),
        "Stack Status": _tr(window, "Data Status", "数据状态"),
        "Data Status": _tr(window, "Data Status", "数据状态"),
        "栈状态": "数据状态",
        "Data Variable": _tr(window, "Variable", "数据变量"),
        "Time Index": _tr(window, "Time", "时间"),
        "Projection": _tr(window, "Projection", "投影方式"),
        "Colormap": _tr(window, "Colormap", "色带"),
        "Color Min": _tr(window, "Minimum", "色标最小值"),
        "Color Max": _tr(window, "Maximum", "色标最大值"),
        "Use Detected Extent": _tr(window, "Use Data Extent", "使用数据范围"),
        "Render Preview": _tr(window, "Render Preview", "渲染预览"),
        "Export Figure": _tr(window, "Export", "导出图像"),
        "Hide Controls": _tr(window, "Hide Controls", "隐藏控制"),
        "Hide Status": _tr(window, "Hide Status", "隐藏状态"),
        "Tools": _tr(window, "Tools", "工具"),
        "Map Status": _tr(window, "Map Status", "地图状态"),
        "Dataset": _tr(window, "Dataset", "数据集"),
        "Cursor": _tr(window, "Cursor", "光标"),
        "Value": _tr(window, "Value", "数值"),
        "Latency": _tr(window, "Latency", "延迟"),
    }
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

    with contextlib.suppress(Exception):
        page.btn_load_stack.setText(_tr(window, "Read Data", "读取数据"))
        page.btn_plot._tr_base_text = "Render Preview"
        page.btn_plot.setText(_tr(window, "Render Preview", "渲染预览"))
        if not page.btn_plot.text().strip():
            page.btn_plot.setText(_tr(window, "Render Preview", "渲染预览"))
        page.btn_export_figure.setText(_tr(window, "Export", "导出图像"))
        page.btn_toggle_tools.setText(_tr(window, "Tools", "工具"))

    # Keep the figure window clean: the card/page already provides context.
    with contextlib.suppress(Exception):
        page.canvas_preview_title.setText("")
        page.canvas_preview_title.setVisible(False)

    # Reset construction-time placeholder text that otherwise leaks into Chinese UI.
    with contextlib.suppress(Exception):
        if page.lbl_stack_info.text().strip() in {"Stack not loaded.", "栈未读取。", "未读取。"}:
            page.lbl_stack_info.setText(_tr(window, "Not loaded", "未读取"))
    with contextlib.suppress(Exception):
        if "cm" in page.lbl_grid_value.text() and page.lbl_dataset.text().startswith("GRACE Level-2"):
            page.lbl_grid_value.setText("—")

    # The CPT importer is an action item, not a persistent colormap name.
    with contextlib.suppress(Exception):
        last_text = _tr(window, "Import CPT...", "导入 CPT...")
        last_index = page.cmb_cmap.count() - 1
        if last_index >= 0:
            page.cmb_cmap.setItemText(last_index, last_text)
            page.cmb_cmap.setItemData(last_index, last_text)


def _patch_refresh_translations(window) -> None:
    if getattr(window, "_preview_stable_refresh_patched", False):
        return
    original = window.refresh_translations

    def patched_refresh_translations(self):
        try:
            result = original()
            _apply_preview_labels(self)
        except RuntimeError as exc:
            if not is_deleted_qt_object_error(exc):
                raise
            result = None
        return result

    window.refresh_translations = MethodType(patched_refresh_translations, window)
    window._preview_stable_refresh_patched = True


def _polish_after_render(controller) -> None:
    with contextlib.suppress(Exception):
        ax = getattr(controller, "_ax", None)
        if ax is not None:
            ax.set_title("")
    with contextlib.suppress(Exception):
        controller.window.page_preview.canvas_preview_title.setText("")
        controller.window.page_preview.canvas_preview_title.setVisible(False)
    with contextlib.suppress(Exception):
        base._polish_rendered_figure(controller, export=False)
        controller._canvas.draw_idle()
    _apply_preview_labels(controller.window)


def _install_wrapped_handlers(window) -> None:
    controller = window.controller
    page = window.page_preview

    base_render = controller.on_render_preview
    base_load = controller.on_load_stack_info
    base_export = controller.on_export_figure

    def render_handler():
        base_render()
        _polish_after_render(controller)

    def load_handler():
        base_load()
        _apply_preview_labels(window)

    def export_handler():
        _polish_after_render(controller)
        base_export()
        _apply_preview_labels(window)

    controller.on_render_preview = render_handler
    controller.on_load_stack_info = load_handler
    controller.on_export_figure = export_handler

    _safe_disconnect(page.btn_plot.clicked)
    page.btn_plot.clicked.connect(controller.on_render_preview)
    _safe_disconnect(page.btn_load_stack.clicked)
    page.btn_load_stack.clicked.connect(controller.on_load_stack_info)
    _safe_disconnect(page.btn_export_figure.clicked)
    page.btn_export_figure.clicked.connect(controller.on_export_figure)


def install_preview_enhancements(window) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        base.install_preview_enhancements(window)
    _patch_refresh_translations(window)
    _install_wrapped_handlers(window)
    _apply_preview_labels(window)
