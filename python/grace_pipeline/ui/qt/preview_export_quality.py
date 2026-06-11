"""High-quality preview figure export.

The earlier exporter appended a long metadata caption to the figure and then used
``bbox_inches='tight'``.  For long CSR Mascon file names this made the exported
image much wider than the map itself, leaving large blank margins and reducing
the apparent map sharpness.  This exporter keeps metadata out of the canvas,
exports the map/colorbar area only, and uses pixel-size presets instead of
asking the user to solve the DPI problem manually.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from types import MethodType

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from grace_pipeline.infra.config import get_root_dir
from grace_pipeline.ui.qt.preview_title_status import restore_preview_header

ROOT_DIR = get_root_dir().resolve()


def _is_zh(window) -> bool:
    return getattr(getattr(window, "ui_preferences", None), "language", "en") == "zh"


def _tr(window, en: str, zh: str) -> str:
    return zh if _is_zh(window) else en


def _safe_disconnect(signal) -> None:
    with contextlib.suppress(Exception):
        signal.disconnect()


def _data_axes(controller):
    fig = getattr(controller, "_figure", None)
    ax = getattr(controller, "_ax", None)
    if fig is None or ax is None or not fig.axes:
        return None, None, []
    return fig, ax, [item for item in fig.axes if item is not ax]


def _apply_export_layout(controller, *, show_colorbar: bool) -> None:
    fig, ax, caxes = _data_axes(controller)
    if fig is None or ax is None:
        return
    is_3d = getattr(ax, "name", "") == "3d" or hasattr(ax, "get_zlim3d")
    if is_3d:
        ax.set_position([0.025, 0.025, 0.82 if show_colorbar else 0.95, 0.94])
        with contextlib.suppress(Exception):
            ax.set_xlim(-1.10, 1.10)
            ax.set_ylim(-1.10, 1.10)
            ax.set_zlim(-1.10, 1.10)
            ax.set_box_aspect((1, 1, 1))
    else:
        ax.set_position([0.020, 0.035, 0.84 if show_colorbar else 0.96, 0.93])
    for cax in caxes:
        cax.set_visible(show_colorbar)
        if show_colorbar:
            cax.set_position([0.885, 0.17, 0.020, 0.70])
            with contextlib.suppress(Exception):
                # Export label uses variable name only.  Units are intentionally
                # not written because GRACE/CSR products may use cm, mm, EWH,
                # or product-specific water-thickness conventions.
                cax.set_ylabel(controller.window.page_preview.cmb_data_var.currentText().strip() or "value", fontsize=9)
                cax.tick_params(labelsize=8)
    with contextlib.suppress(Exception):
        ax.set_title("")


def _export_dialog(controller):
    window = controller.window
    dialog = QDialog(window)
    dialog.setWindowTitle(_tr(window, "Export Figure", "导出图像"))
    dialog.setModal(True)
    dialog.resize(760, 300)
    layout = QVBoxLayout(dialog)
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setSpacing(10)

    default_path = ROOT_DIR / "output" / "local" / "preview.png"
    row_path = QWidget()
    row_layout = QHBoxLayout(row_path)
    row_layout.setContentsMargins(0, 0, 0, 0)
    path_edit = QLineEdit(str(default_path))
    browse_btn = QPushButton(_tr(window, "Browse", "浏览"))
    row_layout.addWidget(path_edit, 1)
    row_layout.addWidget(browse_btn)
    form.addRow(_tr(window, "Output file", "输出文件"), row_path)

    fmt_combo = QComboBox()
    fmt_combo.addItems(["png", "tif", "pdf", "svg"])
    form.addRow(_tr(window, "Format", "格式"), fmt_combo)

    dpi_combo = QComboBox()
    dpi_combo.addItems(["300", "450", "600"])
    dpi_combo.setCurrentText("300")
    form.addRow("DPI", dpi_combo)

    width_spin = QSpinBox()
    width_spin.setRange(1600, 16000)
    width_spin.setSingleStep(200)
    width_spin.setValue(4800)
    height_spin = QSpinBox()
    height_spin.setRange(1000, 10000)
    height_spin.setSingleStep(200)
    height_spin.setValue(2800)
    size_row = QWidget()
    size_layout = QHBoxLayout(size_row)
    size_layout.setContentsMargins(0, 0, 0, 0)
    size_layout.addWidget(width_spin)
    size_layout.addWidget(QLabel("×"))
    size_layout.addWidget(height_spin)
    size_layout.addWidget(QLabel("px"))
    size_layout.addStretch(1)
    form.addRow(_tr(window, "Canvas size", "画布尺寸"), size_row)

    note = QLabel(_tr(window, "Recommended: keep 300–450 DPI and increase canvas pixels for sharper raster output.", "建议：保持 300–450 DPI，通过提高画布像素改善栅格图清晰度。"))
    note.setWordWrap(True)
    form.addRow("", note)
    layout.addLayout(form)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.button(QDialogButtonBox.Ok).setText(_tr(window, "Export", "导出"))
    buttons.button(QDialogButtonBox.Cancel).setText(_tr(window, "Cancel", "取消"))
    layout.addWidget(buttons)

    def choose_path():
        path, _ = QFileDialog.getSaveFileName(
            dialog,
            _tr(window, "Export Figure", "导出图像"),
            path_edit.text().strip() or str(default_path),
            "PNG (*.png);;TIFF (*.tif);;PDF (*.pdf);;SVG (*.svg)",
        )
        if path:
            path_edit.setText(path)

    browse_btn.clicked.connect(choose_path)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    if dialog.exec() != QDialog.Accepted:
        return None
    return {
        "path": Path(path_edit.text().strip() or str(default_path)),
        "fmt": fmt_combo.currentText().strip().lower() or "png",
        "dpi": int(dpi_combo.currentText()),
        "width_px": int(width_spin.value()),
        "height_px": int(height_spin.value()),
    }


def _high_quality_export(self) -> None:
    fig, ax, _caxes = _data_axes(self)
    if fig is None or ax is None:
        self._show_info(_tr(self.window, "Export Figure", "导出图像"), _tr(self.window, "Render a preview before exporting.", "请先渲染预览图。"))
        return
    options = _export_dialog(self)
    if options is None:
        return

    out_path = options["path"]
    fmt = options["fmt"]
    if out_path.suffix.lower() != f".{fmt}":
        out_path = out_path.with_suffix(f".{fmt}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    dpi = int(options["dpi"])
    width_px = int(options["width_px"])
    height_px = int(options["height_px"])
    old_size = tuple(fig.get_size_inches())
    old_dpi = float(fig.dpi)
    old_positions = {item: item.get_position().frozen() for item in fig.axes}
    old_visible = {item: item.get_visible() for item in fig.axes}

    try:
        fig.set_dpi(dpi)
        fig.set_size_inches(width_px / dpi, height_px / dpi, forward=True)
        page = self.window.page_preview
        show_colorbar = bool(getattr(page, "chk_show_colorbar", None) is None or page.chk_show_colorbar.isChecked())
        _apply_export_layout(self, show_colorbar=show_colorbar)
        fig.savefig(
            str(out_path),
            dpi=dpi,
            format=fmt,
            bbox_inches="tight",
            pad_inches=0.02,
            facecolor="white",
            metadata={"Software": "GRACE Level-2 Pipeline"} if fmt in {"png", "pdf", "svg"} else None,
        )
        self._show_info(_tr(self.window, "Export Figure", "导出图像"), _tr(self.window, "Saved to:", "已保存至：") + f"\n{out_path}")
        self.on_log(f"[PREVIEW] Figure exported: {out_path} ({fmt}, {width_px}x{height_px}, {dpi} dpi)", "stdout")
    finally:
        for item, pos in old_positions.items():
            with contextlib.suppress(Exception):
                item.set_position(pos)
        for item, visible in old_visible.items():
            with contextlib.suppress(Exception):
                item.set_visible(visible)
        fig.set_dpi(old_dpi)
        fig.set_size_inches(old_size[0], old_size[1], forward=True)
        restore_preview_header(self.window)
        self._canvas.draw_idle()


def install_preview_export_quality(window) -> None:
    if getattr(window, "_preview_export_quality_installed", False):
        return
    controller = window.controller
    page = window.page_preview
    controller.on_export_figure = MethodType(_high_quality_export, controller)
    _safe_disconnect(page.btn_export_figure.clicked)
    page.btn_export_figure.clicked.connect(controller.on_export_figure)
    window._preview_export_quality_installed = True
