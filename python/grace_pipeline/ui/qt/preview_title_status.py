"""Restore the preview canvas header after preview rendering patches.

The Matplotlib axes title is intentionally kept empty for clean exported figures.
This module restores the Qt-side canvas header above the figure, so the user
still sees the current projection, time slice and dataset state in the preview
panel itself.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from types import MethodType


def _is_zh(window) -> bool:
    return getattr(getattr(window, "ui_preferences", None), "language", "en") == "zh"


def _projection_title(window) -> str:
    page = window.page_preview
    projection = page.cmb_projection.currentText().strip() or "Map"
    if _is_zh(window):
        if projection == "3D Globe (Surface)":
            return "三维球面"
        if projection.endswith("(Global)"):
            projection = projection.replace("(Global)", "").strip()
        return f"{projection} 投影"
    if projection == "3D Globe (Surface)":
        return "3D Globe"
    return projection


def _time_text(window) -> str:
    controller = getattr(window, "controller", None)
    page = window.page_preview
    idx = int(page.slider_time_index.value())
    with contextlib.suppress(Exception):
        label = controller._preview_time_text(idx)
        if label:
            return str(label)
    text = page.lbl_time_index.text().strip()
    if "|" in text:
        return text.rsplit("|", 1)[-1].strip()
    return ""


def _dataset_text(window) -> str:
    page = window.page_preview
    dataset = page.lbl_dataset.text().strip()
    if dataset and dataset not in {"-", "—", "Dataset", "数据集"}:
        return dataset
    path = page.edit_dataset_source.text().strip()
    if path:
        return Path(path).name
    return ""


def restore_preview_header(window) -> None:
    page = window.page_preview
    parts = [_projection_title(window)]
    time_label = _time_text(window)
    dataset = _dataset_text(window)
    if time_label:
        parts.append(time_label)
    if dataset:
        parts.append(dataset)
    text = " | ".join(part for part in parts if part)
    with contextlib.suppress(Exception):
        page.canvas_preview_title.setText(text)
        page.canvas_preview_title.setVisible(True)
        page.canvas_preview_title.setToolTip(text)


def install_preview_title_status(window) -> None:
    """Keep the Qt-side preview header visible and synchronized."""
    if getattr(window, "_preview_title_status_installed", False):
        return

    controller = window.controller
    page = window.page_preview

    original_render = controller.on_render_preview

    def render_with_header(self):
        result = original_render()
        restore_preview_header(window)
        return result

    controller.on_render_preview = MethodType(render_with_header, controller)
    with contextlib.suppress(Exception):
        page.btn_plot.clicked.disconnect()
    with contextlib.suppress(Exception):
        page.btn_plot.clicked.connect(controller.on_render_preview)

    original_refresh = window.refresh_translations

    def refresh_with_header(self):
        result = original_refresh()
        restore_preview_header(self)
        return result

    window.refresh_translations = MethodType(refresh_with_header, window)

    for signal in (
        page.cmb_projection.currentIndexChanged,
        page.cmb_data_var.currentIndexChanged,
        page.slider_time_index.valueChanged,
    ):
        with contextlib.suppress(Exception):
            signal.connect(lambda *_args, _window=window: restore_preview_header(_window))

    restore_preview_header(window)
    window._preview_title_status_installed = True
