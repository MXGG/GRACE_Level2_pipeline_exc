"""Preview map rendering and export refinements for the Qt GUI."""

from __future__ import annotations

import contextlib
import re
import time
from pathlib import Path
from types import MethodType

import numpy as np
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

from grace_pipeline.infra.config import get_root_dir


ROOT_DIR = get_root_dir().resolve()
ROBUST_PROJECTIONS = [
    "Robinson (Global)",
    "Plate Carree",
    "Mercator",
    "Mollweide",
    "Equal Earth",
    "Winkel Tripel",
    "Eckert IV",
]
DEFAULT_CMAPS = [
    "RdBu_r",
    "coolwarm",
    "seismic",
    "BrBG",
    "PiYG",
    "viridis",
    "cividis",
    "turbo",
    "matlab_jet",
    "grace_bwr",
    "Import CPT...",
]


def _is_zh(window) -> bool:
    return getattr(getattr(window, "ui_preferences", None), "language", "en") == "zh"


def _tr(window, en: str, zh: str) -> str:
    return zh if _is_zh(window) else en


def _set_combo_items(combo, values, current=None) -> None:
    if combo is None:
        return
    old = current or combo.currentText()
    combo.blockSignals(True)
    combo.clear()
    for value in values:
        combo.addItem(value, value)
    target = old if old in values else (current or values[0])
    idx = combo.findText(target)
    combo.setCurrentIndex(max(0, idx))
    combo.blockSignals(False)


def _register_default_colormaps() -> None:
    with contextlib.suppress(Exception):
        import matplotlib as mpl
        from matplotlib.colors import LinearSegmentedColormap

        names = set(mpl.colormaps)
        if "matlab_jet" not in names:
            mpl.colormaps.register(mpl.colormaps["jet"], name="matlab_jet")
        if "grace_bwr" not in names:
            cmap = LinearSegmentedColormap.from_list(
                "grace_bwr",
                ["#08306b", "#2171b5", "#6baed6", "#f7fbff", "#fdd0a2", "#f16913", "#7f0000"],
                N=256,
            )
            mpl.colormaps.register(cmap, name="grace_bwr")


def _load_cpt_colormap(path: str):
    import matplotlib as mpl
    from matplotlib.colors import LinearSegmentedColormap

    p = Path(path)
    rows = []
    for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line[0].upper() in {"B", "F", "N"}:
            continue
        parts = re.split(r"\s+", line)
        if len(parts) < 8:
            continue
        try:
            z1, r1, g1, b1, z2, r2, g2, b2 = [float(x) for x in parts[:8]]
        except Exception:
            continue
        rows.append((z1, r1, g1, b1))
        rows.append((z2, r2, g2, b2))
    if not rows:
        raise ValueError("No RGB control points were found in the CPT file.")
    rows = sorted(rows, key=lambda item: item[0])
    z = np.asarray([r[0] for r in rows], dtype=float)
    zmin = float(np.nanmin(z))
    zmax = float(np.nanmax(z))
    scale = max(1.0e-12, zmax - zmin)
    colors = []
    for zi, r, g, b in rows:
        colors.append(((zi - zmin) / scale, (r / 255.0, g / 255.0, b / 255.0)))
    name = "cpt_" + re.sub(r"[^0-9A-Za-z_]+", "_", p.stem.lower())[:40]
    cmap = LinearSegmentedColormap.from_list(name, colors, N=256)
    with contextlib.suppress(Exception):
        mpl.colormaps.unregister(name)
    mpl.colormaps.register(cmap, name=name)
    return name


def _resolve_colormap(controller) -> bool:
    page = controller.window.page_preview
    current = page.cmb_cmap.currentText().strip()
    if current != "Import CPT...":
        return True
    path, _ = QFileDialog.getOpenFileName(
        controller.window,
        _tr(controller.window, "Import CPT colormap", "导入 CPT 色带"),
        str(ROOT_DIR),
        "GMT CPT (*.cpt);;All files (*.*)",
    )
    if not path:
        idx = page.cmb_cmap.findText("RdBu_r")
        if idx >= 0:
            page.cmb_cmap.setCurrentIndex(idx)
        return False
    cmap_name = _load_cpt_colormap(path)
    if page.cmb_cmap.findText(cmap_name) < 0:
        insert_at = max(0, page.cmb_cmap.count() - 1)
        page.cmb_cmap.insertItem(insert_at, cmap_name, cmap_name)
    page.cmb_cmap.setCurrentText(cmap_name)
    page._custom_cpt_path = path
    return True


def _unit_for_variable(var_name: str) -> str:
    var = str(var_name or "").lower()
    if var in {"ewh", "tws", "twsa", "water", "mass"} or "ewh" in var or "tws" in var:
        return "cm"
    return ""


def _polish_rendered_figure(controller, *, export: bool = False) -> None:
    fig = getattr(controller, "_figure", None)
    ax = getattr(controller, "_ax", None)
    page = controller.window.page_preview
    if fig is None or ax is None:
        return
    var_name = page.cmb_data_var.currentText().strip() or "value"
    unit = _unit_for_variable(var_name)
    cb_label = f"{var_name} ({unit})" if unit else var_name

    # Main axes line and grid weight. This keeps coastlines readable on screen but
    # prevents overly heavy coastlines in high-DPI exports.
    with contextlib.suppress(Exception):
        for line in ax.lines:
            color = str(line.get_color()).lower()
            if color in {"#1f3547", "#1f3547ff"}:
                line.set_linewidth(0.35 if export else 0.45)
                line.set_alpha(0.88)
            elif "cccccc" in color or "gray" in color or "grey" in color:
                line.set_linewidth(0.28 if export else 0.35)
                line.set_alpha(0.58)
        ax.tick_params(labelsize=8 if not export else 9)

    with contextlib.suppress(Exception):
        title = page.canvas_preview_title.text().strip()
        if title:
            ax.set_title(title, fontsize=10 if not export else 12, fontweight="bold", pad=8)

    # Colorbar axes are every axis except the active map axis.
    for cax in list(fig.axes):
        if cax is ax:
            continue
        with contextlib.suppress(Exception):
            cax.set_ylabel(cb_label, fontsize=9 if not export else 10)
            cax.tick_params(labelsize=8 if not export else 9)

    with contextlib.suppress(Exception):
        fig.subplots_adjust(left=0.04, right=0.94, top=0.92, bottom=0.06)


def _replace_preview_text(window) -> None:
    page = window.page_preview
    if _is_zh(window):
        replacements = {
            "Preview Controls": "预览控制",
            "Dataset Source": "数据源",
            "Load Stack Info": "读取数据",
            "Stack Status": "数据状态",
            "Data Variable": "数据变量",
            "Time Index": "时间索引",
            "Projection": "投影方式",
            "Colormap": "色带",
            "Color Min": "色标最小值",
            "Color Max": "色标最大值",
            "Use Detected Extent": "使用数据范围",
            "Render Preview": "渲染预览",
            "Export Figure": "导出图像",
            "Hide Controls": "隐藏控制",
            "Hide Status": "隐藏状态",
            "Tools": "工具",
            "Map Status": "地图状态",
            "Dataset": "数据集",
            "Cursor": "光标",
            "Value": "数值",
            "Latency": "延迟",
        }
    else:
        replacements = {
            "Load Stack Info": "Read Dataset",
            "Stack Status": "Data Status",
        }
    for label in page.findChildren(QLabel):
        if label.text() in replacements:
            label.setText(replacements[label.text()])
    for widget in page.findChildren(QWidget):
        if hasattr(widget, "text") and hasattr(widget, "setText"):
            with contextlib.suppress(Exception):
                text = widget.text()
                if text in replacements:
                    widget.setText(replacements[text])


def _safe_original_render(controller) -> None:
    page = controller.window.page_preview
    # The previous free-form projection list includes several projections that
    # can create non-finite x/y arrays in pcolormesh. Restrict the UI to stable
    # projections and fall back to Robinson when a stale value remains.
    if page.cmb_projection.currentText().strip() not in ROBUST_PROJECTIONS:
        page.cmb_projection.setCurrentText("Robinson (Global)")
    controller._preview_original_render()


def _enhanced_render(self) -> None:
    try:
        if not _resolve_colormap(self):
            return
        _safe_original_render(self)
        _polish_rendered_figure(self, export=False)
        self._canvas.draw_idle()
    except Exception as exc:
        self._show_error(_tr(self.window, "Preview", "预览"), str(exc))


def _enhanced_export(self) -> None:
    try:
        if getattr(self, "_figure", None) is None or not self._figure.axes:
            self._show_info(_tr(self.window, "Export Figure", "导出图像"), _tr(self.window, "Render a preview before exporting.", "请先渲染预览图。"))
            return
        dialog = QDialog(self.window)
        dialog.setWindowTitle(_tr(self.window, "Export Figure", "导出图像"))
        dialog.setModal(True)
        dialog.resize(720, 260)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        default_path = ROOT_DIR / "output" / "local" / "preview.png"
        row_path = QWidget()
        row_path_layout = QHBoxLayout(row_path)
        row_path_layout.setContentsMargins(0, 0, 0, 0)
        row_path_layout.setSpacing(8)
        path_edit = QLineEdit(str(default_path))
        browse_btn = QPushButton(_tr(self.window, "Browse", "浏览"))
        browse_btn.setObjectName("GhostButton")
        row_path_layout.addWidget(path_edit, 1)
        row_path_layout.addWidget(browse_btn)
        form.addRow(_tr(self.window, "Output file", "输出文件"), row_path)

        fmt_combo = QComboBox()
        fmt_combo.addItems(["png", "tif", "pdf", "svg"])
        form.addRow(_tr(self.window, "Format", "格式"), fmt_combo)

        dpi_combo = QComboBox()
        dpi_combo.addItems(["300", "450", "600"])
        dpi_combo.setCurrentText("450")
        form.addRow("DPI", dpi_combo)

        width_spin = QSpinBox()
        width_spin.setRange(1200, 12000)
        width_spin.setValue(3000)
        height_spin = QSpinBox()
        height_spin.setRange(800, 8000)
        height_spin.setValue(1800)
        size_row = QWidget()
        size_row_layout = QHBoxLayout(size_row)
        size_row_layout.setContentsMargins(0, 0, 0, 0)
        size_row_layout.setSpacing(8)
        size_row_layout.addWidget(width_spin)
        size_row_layout.addWidget(QLabel("x"))
        size_row_layout.addWidget(height_spin)
        size_row_layout.addWidget(QLabel("px"))
        size_row_layout.addStretch(1)
        form.addRow(_tr(self.window, "Canvas size", "画布尺寸"), size_row)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(_tr(self.window, "Export", "导出"))
        buttons.button(QDialogButtonBox.Cancel).setText(_tr(self.window, "Cancel", "取消"))
        layout.addWidget(buttons)

        def choose_path():
            path, _ = QFileDialog.getSaveFileName(
                dialog,
                _tr(self.window, "Export Figure", "导出图像"),
                path_edit.text().strip() or str(default_path),
                "PNG (*.png);;TIFF (*.tif);;PDF (*.pdf);;SVG (*.svg)",
            )
            if path:
                path_edit.setText(path)

        browse_btn.clicked.connect(choose_path)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.Accepted:
            return

        out_path = Path(path_edit.text().strip() or str(default_path))
        fmt = fmt_combo.currentText().strip().lower() or "png"
        if out_path.suffix.lower() != f".{fmt}":
            out_path = out_path.with_suffix(f".{fmt}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        dpi = int(dpi_combo.currentText())
        width_px = int(width_spin.value())
        height_px = int(height_spin.value())
        old_size = tuple(self._figure.get_size_inches())
        old_dpi = float(self._figure.dpi)
        old_texts = []
        try:
            self._figure.set_dpi(dpi)
            self._figure.set_size_inches(width_px / dpi, height_px / dpi, forward=True)
            _polish_rendered_figure(self, export=True)
            dataset = self.window.page_preview.lbl_dataset.text().strip()
            cursor = self.window.page_preview.lbl_cursor_position.text().strip()
            value = self.window.page_preview.lbl_grid_value.text().strip()
            caption = f"{dataset}    Cursor: {cursor}    Value: {value}"
            txt = self._figure.text(0.04, 0.018, caption, fontsize=8, color="#34495e")
            old_texts.append(txt)
            self._figure.savefig(str(out_path), dpi=dpi, format=fmt, bbox_inches="tight", pad_inches=0.05, facecolor="white")
            self._show_info(_tr(self.window, "Export Figure", "导出图像"), _tr(self.window, "Saved to:", "已保存至：") + f"\n{out_path}")
            self.on_log(f"[PREVIEW] Figure exported: {out_path} ({fmt}, {width_px}x{height_px}, {dpi} dpi)", "stdout")
        finally:
            for txt in old_texts:
                with contextlib.suppress(Exception):
                    txt.remove()
            self._figure.set_dpi(old_dpi)
            self._figure.set_size_inches(old_size[0], old_size[1], forward=True)
            _polish_rendered_figure(self, export=False)
            self._canvas.draw_idle()
    except Exception as exc:
        self._show_error(_tr(self.window, "Export Figure", "导出图像"), str(exc))


def install_preview_enhancements(window) -> None:
    """Patch preview controls, colour maps, rendering labels, and export defaults."""

    _register_default_colormaps()
    page = window.page_preview
    controller = window.controller

    _set_combo_items(page.cmb_projection, ROBUST_PROJECTIONS, current="Robinson (Global)")
    _set_combo_items(page.cmb_cmap, DEFAULT_CMAPS, current="RdBu_r")
    page.chk_layer_coastlines.setChecked(True)
    page.chk_layer_grid.setChecked(True)
    _replace_preview_text(window)

    if not hasattr(controller, "_preview_original_render"):
        controller._preview_original_render = controller.on_render_preview
    if not hasattr(controller, "_preview_original_export"):
        controller._preview_original_export = controller.on_export_figure
    controller.on_render_preview = MethodType(_enhanced_render, controller)
    controller.on_export_figure = MethodType(_enhanced_export, controller)

    with contextlib.suppress(Exception):
        page.btn_plot.clicked.disconnect()
    page.btn_plot.clicked.connect(controller.on_render_preview)
    with contextlib.suppress(Exception):
        page.btn_export_figure.clicked.disconnect()
    page.btn_export_figure.clicked.connect(controller.on_export_figure)
    with contextlib.suppress(Exception):
        page.cmb_cmap.currentIndexChanged.disconnect()
    page.cmb_cmap.currentIndexChanged.connect(lambda _idx=0: None)
