"""High-quality preview figure export.

This exporter keeps metadata out of the exported canvas, avoids expensive tight
bounding-box recomputation, and only applies readable font sizes during export.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from types import MethodType

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressDialog,
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
    """Use the previous export layout and only enlarge colorbar fonts."""

    fig, ax, caxes = _data_axes(controller)
    if fig is None or ax is None:
        return
    is_3d = getattr(ax, "name", "") == "3d" or hasattr(ax, "get_zlim3d")
    if is_3d:
        ax.set_position([0.030, 0.045, 0.80 if show_colorbar else 0.94, 0.90])
        with contextlib.suppress(Exception):
            ax.set_xlim(-1.10, 1.10)
            ax.set_ylim(-1.10, 1.10)
            ax.set_zlim(-1.10, 1.10)
            ax.set_box_aspect((1, 1, 1))
    else:
        ax.set_position([0.025, 0.055, 0.82 if show_colorbar else 0.94, 0.88])
    for cax in caxes:
        cax.set_visible(show_colorbar)
        if show_colorbar:
            cax.set_position([0.870, 0.18, 0.022, 0.66])
            with contextlib.suppress(Exception):
                cax.set_ylabel(controller.window.page_preview.cmb_data_var.currentText().strip() or "value", fontsize=16, labelpad=10)
                cax.tick_params(labelsize=13)
    with contextlib.suppress(Exception):
        ax.set_title("")


def _snapshot_font_style(fig) -> list[tuple[object, object]]:
    snapshot: list[tuple[object, object]] = []
    for text in fig.findobj(match=lambda item: hasattr(item, "get_fontsize") and hasattr(item, "set_fontsize")):
        with contextlib.suppress(Exception):
            snapshot.append((text, text.get_fontsize()))
    return snapshot


def _apply_export_font_style(fig) -> list[tuple[object, object]]:
    """Only enlarge export fonts; do not alter linewidth, antialiasing or pixels."""

    snapshot = _snapshot_font_style(fig)
    for text in fig.findobj(match=lambda item: hasattr(item, "get_fontsize") and hasattr(item, "set_fontsize")):
        with contextlib.suppress(Exception):
            size = float(text.get_fontsize())
            if size < 10:
                text.set_fontsize(11)
            elif size < 13:
                text.set_fontsize(13)
    for ax in fig.axes:
        with contextlib.suppress(Exception):
            ax.tick_params(labelsize=12)
        with contextlib.suppress(Exception):
            ax.xaxis.label.set_fontsize(13)
            ax.yaxis.label.set_fontsize(13)
        with contextlib.suppress(Exception):
            ax.title.set_fontsize(0.1)
    return snapshot


def _restore_font_style(snapshot) -> None:
    for obj, size in snapshot:
        with contextlib.suppress(Exception):
            obj.set_fontsize(size)


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

    note = QLabel(_tr(window, "Recommended: keep 300–450 DPI and increase canvas pixels for sharper raster output. PNG export uses this pixel size directly.", "建议：保持 300–450 DPI，通过提高画布像素改善栅格图清晰度。PNG 导出会直接采用该像素尺寸。"))
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


def _progress(window, text: str) -> QProgressDialog:
    progress = QProgressDialog(text, "", 0, 0, window)
    progress.setWindowTitle(_tr(window, "Export Figure", "导出图像"))
    progress.setCancelButton(None)
    progress.setWindowModality(Qt.ApplicationModal)
    progress.setMinimumDuration(0)
    progress.show()
    QApplication.processEvents()
    return progress


def _replace_output(tmp_path: Path, out_path: Path) -> None:
    os.replace(str(tmp_path), str(out_path))


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
    font_snapshot = []
    progress = None
    tmp_path = out_path.with_name(f".{out_path.stem}.tmp{out_path.suffix}")

    try:
        progress = _progress(self.window, _tr(self.window, "Exporting figure, please wait...", "正在导出图像，请稍候..."))
        fig.set_dpi(dpi)
        fig.set_size_inches(width_px / dpi, height_px / dpi, forward=True)
        page = self.window.page_preview
        show_colorbar = bool(getattr(page, "chk_show_colorbar", None) is None or page.chk_show_colorbar.isChecked())
        _apply_export_layout(self, show_colorbar=show_colorbar)
        font_snapshot = _apply_export_font_style(fig)
        QApplication.processEvents()

        save_kwargs = {
            "fname": str(tmp_path),
            "dpi": dpi,
            "format": fmt,
            "facecolor": "white",
            "bbox_inches": None,
            "pad_inches": 0.0,
        }
        if fmt in {"png", "pdf", "svg"}:
            save_kwargs["metadata"] = {"Software": "GRACE Level-2 Pipeline"}
        fig.savefig(**save_kwargs)
        _replace_output(tmp_path, out_path)
        size_mb = out_path.stat().st_size / (1024 * 1024)
        if progress is not None:
            progress.close()
            QApplication.processEvents()
        self._show_info(
            _tr(self.window, "Export Figure", "导出图像"),
            _tr(self.window, "Export completed:", "导出完成：")
            + f"\n{out_path}\n{width_px} × {height_px} px, {dpi} DPI, {size_mb:.2f} MB",
        )
        self.on_log(f"[PREVIEW] Figure exported: {out_path} ({fmt}, {width_px}x{height_px}, {dpi} dpi, {size_mb:.2f} MB)", "stdout")
    except Exception as exc:
        if progress is not None:
            progress.close()
        with contextlib.suppress(Exception):
            tmp_path.unlink(missing_ok=True)
        self._show_error(_tr(self.window, "Export Figure", "导出图像"), str(exc))
    finally:
        _restore_font_style(font_snapshot)
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
