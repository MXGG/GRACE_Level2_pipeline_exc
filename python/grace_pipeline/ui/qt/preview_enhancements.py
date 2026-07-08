"""Preview-page rendering, projection, colormap, unit, and export refinements."""

from __future__ import annotations

import contextlib
import re
import warnings
from pathlib import Path
from types import MethodType

import numpy as np
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
from grace_pipeline.ui.qt.qt_safe import is_deleted_qt_object_error, qt_object_is_alive
from grace_pipeline.ui.plotting.boundaries import plot_line, read_boundary_file, split_dateline
from grace_pipeline.ui.plotting.overlays import draw_coastlines
from grace_pipeline.ui.plotting.projections import (
    apply_proj_scale,
    get_conic_parallels,
    get_proj_center,
    infer_plot_lon_mode,
    normalize_lon_for_plot,
    parse_float,
    scale_projection,
    split_plot_lon_segments,
    wrap_delta_lon,
)
from grace_pipeline.ui.qt.projection_registry import (
    PARAM_DEFS,
    PROJECTION_DISPLAY_NAMES,
    projection_defaults,
    projection_default_extent,
    projection_engine_name,
    projection_key_to_name,
    projection_name_to_key,
    projection_renderer,
    projection_spec,
    visible_projection_params,
)

ROOT_DIR = get_root_dir().resolve()
PROJECTION_CHOICES = PROJECTION_DISPLAY_NAMES
FALLBACK_RENDER_PROJECTIONS = {
    "Orthographic",
    "AzimuthalEquidistant",
    "LambertAzimuthalEqualArea",
    "Stereographic",
    "LambertConformal",
    "AlbersEqualArea",
    "TransverseMercator",
    "UTM",
}
BASE_CMAPS = [
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
]
DEBUG_3D_COASTLINE = True


def _is_zh(window) -> bool:
    return getattr(getattr(window, "ui_preferences", None), "language", "en") == "zh"


def _tr(window, en: str, zh: str) -> str:
    return zh if _is_zh(window) else en


def _safe_disconnect(signal) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with contextlib.suppress(Exception):
            signal.disconnect()


def _set_combo_items(combo, values, current=None) -> None:
    old = current or combo.currentText()
    combo.blockSignals(True)
    combo.clear()
    for value in values:
        combo.addItem(value, value)
    idx = combo.findText(old)
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


def _load_cpt_colormap(path: str) -> str:
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
    colors = [((zi - zmin) / scale, (r / 255.0, g / 255.0, b / 255.0)) for zi, r, g, b in rows]
    name = "cpt_" + re.sub(r"[^0-9A-Za-z_]+", "_", p.stem.lower())[:40]
    cmap = LinearSegmentedColormap.from_list(name, colors, N=256)
    with contextlib.suppress(Exception):
        mpl.colormaps.unregister(name)
    mpl.colormaps.register(cmap, name=name)
    return name


def _import_cpt_label(window) -> str:
    return _tr(window, "Import CPT...", "导入 CPT...")


def _is_import_cpt_text(text: str) -> bool:
    return str(text or "").strip().lower() in {"import cpt...", "导入 cpt..."}


def _handle_cpt_combo(controller) -> bool:
    page = controller.window.page_preview
    if not _is_import_cpt_text(page.cmb_cmap.currentText()):
        page._last_valid_cmap = page.cmb_cmap.currentText().strip() or "RdBu_r"
        return True
    path, _ = QFileDialog.getOpenFileName(
        controller.window,
        _tr(controller.window, "Import CPT colormap", "导入 CPT 色带"),
        str(ROOT_DIR),
        "GMT CPT (*.cpt);;All files (*.*)",
    )
    if not path:
        fallback = getattr(page, "_last_valid_cmap", "RdBu_r")
        page.cmb_cmap.blockSignals(True)
        page.cmb_cmap.setCurrentText(fallback)
        page.cmb_cmap.blockSignals(False)
        return False
    cmap_name = _load_cpt_colormap(path)
    if page.cmb_cmap.findText(cmap_name) < 0:
        page.cmb_cmap.insertItem(max(0, page.cmb_cmap.count() - 1), cmap_name, cmap_name)
    page.cmb_cmap.blockSignals(True)
    page.cmb_cmap.setCurrentText(cmap_name)
    page.cmb_cmap.blockSignals(False)
    page._last_valid_cmap = cmap_name
    page._custom_cpt_path = path
    return True


def _unit_from_meta(meta: dict | None, var_name: str) -> str:
    meta = meta or {}
    for key in ("units", "unit", "data_units", "ewh_unit", "value_unit"):
        value = meta.get(key)
        if value:
            return str(value)
    var_units = meta.get("var_units") or meta.get("variable_units")
    if isinstance(var_units, dict):
        value = var_units.get(var_name) or var_units.get(str(var_name).lower())
        if value:
            return str(value)
    return "mm"


def _current_unit(controller) -> str:
    page = controller.window.page_preview
    var_name = page.cmb_data_var.currentText().strip() or "ewh"
    meta = {}
    with contextlib.suppress(Exception):
        info = controller.host._stack_info_cache or {}
        if info.get("path") == page.edit_dataset_source.text().strip():
            meta = info.get("meta", {}) or {}
    if not meta:
        with contextlib.suppress(Exception):
            meta = (controller.host._stack_cache or {}).get("meta", {}) or {}
    return _unit_from_meta(meta, var_name)


def _apply_preview_labels(window) -> None:
    page = window.page_preview
    replacements = {
        "Load Stack Info": _tr(window, "Read Data", "读取数据"),
        "Read Dataset": _tr(window, "Read Data", "读取数据"),
        "读取栈信息": "读取数据",
        "Stack Status": _tr(window, "Data Status", "数据状态"),
        "栈状态": "数据状态",
        "Dataset Source": _tr(window, "Data Source", "数据源"),
        "Data Source": _tr(window, "Data Source", "数据源"),
        "Data Variable": _tr(window, "Plot Variable", "绘图变量"),
        "Plot Variable": _tr(window, "Plot Variable", "绘图变量"),
        "Time Index": _tr(window, "Time Slice", "时间索引/切片"),
        "Time Slice": _tr(window, "Time Slice", "时间索引/切片"),
        "Projection": _tr(window, "Projection", "投影方式"),
        "Projection Settings": _tr(window, "Projection Settings", "投影设置"),
        "Projection Parameters": _tr(window, "Projection Parameters", "投影参数"),
        "Central longitude": _tr(window, "Central longitude", "中心经度"),
        "中心经度": _tr(window, "Central longitude", "中心经度"),
        "Central latitude": _tr(window, "Central latitude", "中心纬度"),
        "中心纬度": _tr(window, "Central latitude", "中心纬度"),
        "Standard parallels": _tr(window, "Standard parallels", "标准纬线"),
        "Lat 1": _tr(window, "Lat 1", "纬线 1"),
        "Lat 2": _tr(window, "Lat 2", "纬线 2"),
        "Extent": _tr(window, "Extent", "显示范围"),
        "Azimuth": _tr(window, "Azimuth", "方位角"),
        "方位角": _tr(window, "Azimuth", "方位角"),
        "Elevation": _tr(window, "Elevation", "俯仰角"),
        "俯仰角": _tr(window, "Elevation", "俯仰角"),
        "Zoom": _tr(window, "Zoom", "缩放"),
        "缩放": _tr(window, "Zoom", "缩放"),
        "Color Scale": _tr(window, "Color Scale Settings", "色带设置"),
        "色标尺": _tr(window, "Color Scale Settings", "色带设置"),
        "Enable Spatial Grid": _tr(window, "Enable Spatial Grid", "启用空间网格配置"),
        "Spatial Extent": _tr(window, "Spatial Extent", "空间范围"),
        "Spatial Grid Configuration": _tr(window, "Spatial Grid Configuration", "空间网格配置"),
        "Colormap": _tr(window, "Colormap", "色带"),
        "Minimum": _tr(window, "Minimum", "最小值"),
        "Maximum": _tr(window, "Maximum", "最大值"),
        "Color Min": _tr(window, "Minimum", "最小值"),
        "Color Max": _tr(window, "Maximum", "最大值"),
        "Use Detected Extent": _tr(window, "Use Data Extent", "使用数据范围"),
        "Use Data Extent": _tr(window, "Use Data Extent", "使用数据覆盖范围"),
        "Lon Min": _tr(window, "Lon Min", "最小经度"),
        "Lon Max": _tr(window, "Lon Max", "最大经度"),
        "Lat Min": _tr(window, "Lat Min", "最小纬度"),
        "Lat Max": _tr(window, "Lat Max", "最大纬度"),
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
        if label.text() in replacements:
            label.setText(replacements[label.text()])
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
        page.canvas_preview_title.setText("")
        page.canvas_preview_title.setVisible(False)
    with contextlib.suppress(Exception):
        if page.lbl_stack_info.text().strip() in {"Stack not loaded.", "栈未读取。", "未读取。"}:
            page.lbl_stack_info.setText(_tr(window, "Not loaded", "未读取"))
    with contextlib.suppress(Exception):
        if "cm" in page.lbl_grid_value.text() and page.lbl_dataset.text().startswith("GRACE Level-2"):
            page.lbl_grid_value.setText("—")
    with contextlib.suppress(Exception):
        _sync_projection_parameter_panel(window)
    with contextlib.suppress(Exception):
        last_idx = page.cmb_cmap.count() - 1
        if last_idx >= 0:
            label = _import_cpt_label(window)
            page.cmb_cmap.setItemText(last_idx, label)
            page.cmb_cmap.setItemData(last_idx, label)


def _patch_refresh_translations(window) -> None:
    if getattr(window, "_preview_refresh_patch", False):
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
    window._preview_refresh_patch = True


def _projection_key(controller, label: str) -> str:
    try:
        return controller._projection_key(label)
    except Exception:
        return projection_engine_name(label)


def _safe_param_float(text: str, default: float) -> float:
    with contextlib.suppress(Exception):
        return float(str(text).strip())
    return float(default)


def _projection_params(page, projection_label: str) -> dict:
    params = projection_defaults(projection_label)
    widgets = getattr(page, "projection_param_widgets", {})
    for key, value in list(params.items()):
        widget_info = widgets.get(key)
        if not widget_info:
            continue
        with contextlib.suppress(Exception):
            if isinstance(widget_info, tuple):
                _field, edit = widget_info
                params[key] = _safe_param_float(edit.text(), float(value))
                continue
            kind = str(widget_info.get("type") or "float")
            if kind in {"float", "int"}:
                edit = widget_info.get("edit")
                if edit is not None:
                    parsed = _safe_param_float(edit.text(), float(value))
                    params[key] = int(round(parsed)) if kind == "int" else parsed
            elif kind == "float_pair":
                edits = list(widget_info.get("edits") or [])
                default = list(value) if isinstance(value, (list, tuple)) else [0.0, 0.0]
                if len(edits) >= 2:
                    params[key] = [
                        _safe_param_float(edits[0].text(), float(default[0])),
                        _safe_param_float(edits[1].text(), float(default[1])),
                    ]
            elif kind == "extent":
                edits = list(widget_info.get("edits") or [])
                default = list(value) if isinstance(value, (list, tuple)) and len(value) == 4 else projection_default_extent(projection_label)
                if len(edits) >= 4:
                    params[key] = [
                        _safe_param_float(edits[0].text(), float(default[0])),
                        _safe_param_float(edits[1].text(), float(default[1])),
                        _safe_param_float(edits[2].text(), float(default[2])),
                        _safe_param_float(edits[3].text(), float(default[3])),
                    ]
    return params


def _sync_projection_parameter_panel(window) -> None:
    page = window.page_preview
    panel = getattr(page, "projection_params_panel", None)
    widgets = getattr(page, "projection_param_widgets", {})
    if panel is None or not widgets:
        return
    label = page.cmb_projection.currentText().strip() or "Robinson"
    current_key = projection_name_to_key(label)
    previous_key = getattr(panel, "_last_projection_key", None)
    projection_changed = previous_key != current_key
    panel._last_projection_key = current_key
    params = visible_projection_params(label)
    spec = projection_spec(label)
    defaults = projection_defaults(label)
    has_visible = False
    for key, widget_info in widgets.items():
        if isinstance(widget_info, tuple):
            field, edit = widget_info
            edits = [edit]
            kind = "float"
        else:
            field = widget_info.get("field")
            edits = list(widget_info.get("edits") or [])
            edit = widget_info.get("edit")
            if edit is not None:
                edits = [edit]
            kind = str(widget_info.get("type") or "float")
        if field is None:
            continue
        visible = key in params
        field.setVisible(visible)
        if visible:
            has_visible = True
            with contextlib.suppress(Exception):
                default_value = defaults.get(key, PARAM_DEFS.get(key, {}).get("default", ""))
                if kind == "extent":
                    values = list(default_value if isinstance(default_value, (list, tuple)) else projection_default_extent(label))
                    for edit_item, value in zip(edits, values):
                        if projection_changed or not edit_item.text().strip():
                            edit_item.setText(str(value))
                elif kind == "float_pair":
                    values = list(default_value if isinstance(default_value, (list, tuple)) else [25.0, 45.0])
                    for edit_item, value in zip(edits, values):
                        if projection_changed or not edit_item.text().strip():
                            edit_item.setText(str(value))
                elif edits and (projection_changed or not edits[0].text().strip()):
                    edits[0].setText(str(default_value))
    with contextlib.suppress(Exception):
        panel.setVisible(has_visible)
    with contextlib.suppress(Exception):
        panel.content.setVisible(has_visible and panel.toggle.isChecked())
    panel.setToolTip(f"{spec.get('group', '')} | {spec.get('renderer', 'cartopy')}")


def _project(controller, proj, lon, lat, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0):
    return controller._project(proj, lon, lat, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)


def _draw_segmented_line(ax, x, y, *, color, linewidth, alpha=1.0, linestyle="-", zorder=8):
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    if x.size < 2 or y.size < 2:
        return
    mask = np.isfinite(x) & np.isfinite(y)
    if not np.any(mask):
        return
    x2 = x.copy()
    y2 = y.copy()
    x2[~mask] = np.nan
    y2[~mask] = np.nan
    plot_line(ax, x2, y2, color=color, linewidth=linewidth, alpha=alpha, linestyle=linestyle, zorder=zorder)


def _float_ui_option(page, attr: str, default: float, *, min_value: float | None = None, max_value: float | None = None) -> float:
    value = default
    widget = getattr(page, attr, None)
    with contextlib.suppress(Exception):
        value = float(widget.text())
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


def _combo_value(widget, default: str) -> str:
    if widget is None:
        return default
    with contextlib.suppress(Exception):
        data = widget.currentData()
        if data is not None:
            return str(data)
    with contextlib.suppress(Exception):
        return str(widget.currentText())
    return default


def _graticule_ui_options(controller) -> dict:
    page = controller.window.page_preview
    style_widget = getattr(page, "cmb_graticule_style", None)
    font_widget = getattr(page, "cmb_graticule_font", None)
    style_key = _combo_value(style_widget, "Dashed").strip().lower()
    if style_key in {"none", "no line", "无线条", "off", "关闭"}:
        linestyle = "none"
    else:
        linestyle = "-" if style_key in {"solid", "实线"} else (":" if style_key in {"dotted", "点线"} else "--")
    color_widget = getattr(page, "edit_graticule_color", None)
    labels_widget = getattr(page, "chk_graticule_labels", None)
    font_family = _combo_value(font_widget, "Default").strip()
    return {
        "lon_interval": _float_ui_option(page, "edit_graticule_lon_interval", 60.0, min_value=5.0, max_value=180.0),
        "lat_interval": _float_ui_option(page, "edit_graticule_lat_interval", 30.0, min_value=5.0, max_value=90.0),
        "linewidth": _float_ui_option(page, "edit_graticule_line_width", 0.55, min_value=0.1, max_value=3.0),
        "tick_length": _float_ui_option(page, "edit_graticule_tick_length", 4.0, min_value=0.0, max_value=20.0),
        "tick_width": _float_ui_option(page, "edit_graticule_tick_width", 0.8, min_value=0.1, max_value=4.0),
        "font_size": _float_ui_option(page, "edit_graticule_font_size", 7.0, min_value=5.0, max_value=18.0),
        "font_family": None if font_family.lower() == "default" else font_family,
        "linestyle": linestyle,
        "color": color_widget.text().strip() if color_widget is not None and color_widget.text().strip() else "#8aa4b4",
        "show_labels": bool(labels_widget is None or labels_widget.isChecked()),
    }


def _draw_enhanced_graticule(controller, *, proj, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0) -> None:
    ax = controller._ax
    if ax is None:
        return
    opts = _graticule_ui_options(controller)
    line_visible = opts["linestyle"] not in {"none", "None", ""} and opts["linewidth"] > 0
    if proj == "PlateCarree":
        with contextlib.suppress(Exception):
            ax.set_xticks(np.arange(-180, 180 + 0.1, opts["lon_interval"]))
            ax.set_yticks(np.arange(-90, 90 + 0.1, opts["lat_interval"]))
            if line_visible:
                ax.grid(True, color=opts["color"], linewidth=opts["linewidth"], linestyle=opts["linestyle"], alpha=0.78, zorder=7)
            else:
                ax.grid(False)
        return
    if not line_visible:
        return
    for lat in np.arange(-90 + opts["lat_interval"], 90, opts["lat_interval"]):
        lons = np.linspace(-180, 180, 721)
        lats = np.full_like(lons, lat, dtype=float)
        x, y = _project(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        x = apply_proj_scale(x, getattr(controller, "_proj_scale", None), getattr(controller, "_proj_x0", None))
        _draw_segmented_line(ax, x, y, color=opts["color"], linewidth=opts["linewidth"], alpha=0.72, linestyle=opts["linestyle"], zorder=7)
    for lon in np.arange(-180, 180 + 0.1, opts["lon_interval"]):
        lats = np.linspace(-88, 88, 721)
        lons = np.full_like(lats, lon, dtype=float)
        x, y = _project(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        x = apply_proj_scale(x, getattr(controller, "_proj_scale", None), getattr(controller, "_proj_x0", None))
        _draw_segmented_line(ax, x, y, color=opts["color"], linewidth=opts["linewidth"], alpha=0.72, linestyle=opts["linestyle"], zorder=7)


def _draw_enhanced_coastlines(controller, *, proj, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0, bbox=None) -> None:
    ax = controller._ax
    coast_path = ""
    with contextlib.suppress(Exception):
        coast_path = controller._resolve_coastline_path()
    if not ax or not coast_path:
        return
    try:
        import os
        import shapefile

        shp_path = coast_path
        if os.path.isdir(shp_path):
            for filename in os.listdir(shp_path):
                if filename.lower().endswith(".shp"):
                    shp_path = os.path.join(shp_path, filename)
                    break
        reader = shapefile.Reader(shp_path)
        for shape in reader.shapes():
            points = shape.points
            parts = list(shape.parts) + [len(points)]
            for i in range(len(parts) - 1):
                seg = np.asarray(points[parts[i] : parts[i + 1]], dtype=float)
                if seg.ndim != 2 or seg.shape[0] < 2:
                    continue
                lons = seg[:, 0]
                lats = seg[:, 1]
                for lons_seg, lats_seg in split_dateline(lons, lats, wrap_delta_lon, lon0=lon0):
                    if proj == "PlateCarree":
                        x = normalize_lon_for_plot(lons_seg)
                        y = lats_seg
                    else:
                        x, y = _project(controller, proj, lons_seg, lats_seg, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                        x = apply_proj_scale(x, getattr(controller, "_proj_scale", None), getattr(controller, "_proj_x0", None))
                    _draw_segmented_line(ax, x, y, color="#263f4d", linewidth=0.36, alpha=0.88, zorder=9)
    except Exception:
        with contextlib.suppress(Exception):
            draw_coastlines(
                ax,
                coast_path=coast_path,
                proj=proj,
                lon0=lon0,
                lat0=lat0,
                lat1=lat1,
                lat2=lat2,
                bbox=bbox,
                normalize_lon_for_plot_cb=normalize_lon_for_plot,
                split_dateline_cb=lambda lons, lats, lon0=0.0: split_dateline(lons, lats, wrap_delta_lon, lon0=lon0),
                split_plot_lon_segments_cb=lambda lons, lats, plate_carree=False: split_plot_lon_segments(lons, lats, split_dateline, lon0=lon0, plate_carree=plate_carree),
                apply_proj_scale_cb=lambda x: apply_proj_scale(x, getattr(controller, "_proj_scale", None), getattr(controller, "_proj_x0", None)),
                plot_line_cb=plot_line,
                projector_cb=controller._project,
            )


def _grid_context(controller):
    page = controller.window.page_preview
    path = page.edit_dataset_source.text().strip()
    active_var = page.cmb_data_var.currentText().strip() or None
    idx = int(page.slider_time_index.value())
    frame = controller.host.get_stack_frame(path, idx, active_var=active_var)
    grid = np.asarray(frame["grid"], dtype=float)
    lon = np.asarray(frame["lon"], dtype=float).squeeze()
    lat = np.asarray(frame["lat"], dtype=float).squeeze()
    if grid.shape[0] != lon.size and grid.shape[1] == lon.size:
        grid = grid.T
    return path, idx, frame, grid, lon, lat


def _apply_bbox(controller, grid, lon, lat):
    page = controller.window.page_preview
    if page.chk_auto_region.isChecked():
        bbox = (float(np.nanmin(lon)), float(np.nanmax(lon)), float(np.nanmin(lat)), float(np.nanmax(lat)))
        page.edit_region_lon_min.setText(f"{bbox[0]:.6g}")
        page.edit_region_lon_max.setText(f"{bbox[1]:.6g}")
        page.edit_region_lat_min.setText(f"{bbox[2]:.6g}")
        page.edit_region_lat_max.setText(f"{bbox[3]:.6g}")
    else:
        bbox = (
            controller._safe_float(page.edit_region_lon_min.text(), -180.0),
            controller._safe_float(page.edit_region_lon_max.text(), 180.0),
            controller._safe_float(page.edit_region_lat_min.text(), -90.0),
            controller._safe_float(page.edit_region_lat_max.text(), 90.0),
        )
    lon_min, lon_max, lat_min, lat_max = bbox
    lat_min, lat_max = min(lat_min, lat_max), max(lat_min, lat_max)
    raw_span = lon_max - lon_min
    if raw_span < 0.0:
        raw_span += 360.0
    full_lon = abs(raw_span) >= 359.0
    lon_mode = "0_360" if lon_min >= 0.0 and (lon_max > 180.0 or lon_min > lon_max) else "-180_180"
    lon_eval = normalize_lon_for_plot(lon, lon_mode=lon_mode)
    if lon_mode == "0_360":
        lon_min_eval = lon_min % 360.0
        lon_max_eval = lon_max % 360.0
        if abs(lon_max - 360.0) < 1.0e-9:
            lon_max_eval = 360.0
    else:
        lon_min_eval = float(normalize_lon_for_plot([lon_min], lon_mode="-180_180")[0])
        lon_max_eval = float(normalize_lon_for_plot([lon_max], lon_mode="-180_180")[0])
        if abs(lon_max - 180.0) < 1.0e-9:
            lon_max_eval = 180.0
    if full_lon:
        lon_mask = np.ones_like(lon, dtype=bool)
    elif lon_mode == "0_360" and abs(lon_max_eval - 360.0) < 1.0e-9:
        lon_mask = lon_eval >= lon_min_eval
    elif lon_min_eval <= lon_max_eval:
        lon_mask = (lon_eval >= lon_min_eval) & (lon_eval <= lon_max_eval)
    else:
        lon_mask = (lon_eval >= lon_min_eval) | (lon_eval <= lon_max_eval)
    lat_mask = (lat >= lat_min) & (lat <= lat_max)
    if np.any(lon_mask) and np.any(lat_mask):
        lon = normalize_lon_for_plot(lon[lon_mask], lon_mode="-180_180")
        lat = lat[lat_mask]
        grid = grid[np.ix_(lon_mask, lat_mask)]
        order = np.argsort(lon)
        lon = lon[order]
        grid = grid[order, :]
    return grid, lon, lat, bbox


def _color_limits(page, grid):
    cmin = parse_float(page.edit_cmin.text())
    cmax = parse_float(page.edit_cmax.text())
    return cmin, cmax


def is_3d_axes(ax) -> bool:
    return bool(getattr(ax, "name", "") == "3d" or hasattr(ax, "get_zlim3d"))


def apply_3d_globe_view(controller, *, zoom: float | None = None, draw: bool = True) -> None:
    ax = getattr(controller, "_ax", None)
    if ax is None or not is_3d_axes(ax):
        return
    params = dict(getattr(controller, "_preview_globe_params", {}) or {})
    params.update(dict(getattr(controller, "_preview_globe_control_params", {}) or {}))
    if zoom is not None:
        params["zoom"] = max(0.1, min(5.0, float(zoom)))
    else:
        params["zoom"] = max(0.1, min(5.0, float(params.get("zoom", 1.0))))
    projection_mode = str(params.get("projection_mode", "orthographic")).lower()
    with contextlib.suppress(Exception):
        if projection_mode.startswith("pers"):
            try:
                ax.set_proj_type("persp", focal_length=max(0.2, float(params.get("focal_length", 1.0))))
            except TypeError:
                ax.set_proj_type("persp")
        else:
            ax.set_proj_type("ortho")
    with contextlib.suppress(Exception):
        try:
            ax.view_init(
                elev=float(params.get("elevation", 25.0)),
                azim=float(params.get("azimuth", -60.0)),
                roll=float(params.get("roll", 0.0)),
            )
        except TypeError:
            ax.view_init(elev=float(params.get("elevation", 25.0)), azim=float(params.get("azimuth", -60.0)))
    lim = 1.05 / float(params["zoom"])
    ax.set_xlim3d(-lim, lim)
    ax.set_ylim3d(-lim, lim)
    ax.set_zlim3d(-lim, lim)
    ax.set_box_aspect([1, 1, 1])
    ax.set_axis_off()
    with contextlib.suppress(Exception):
        # Keep the 3D drawing region square inside wide canvases so the globe
        # is not visually stretched by the surrounding widget geometry.
        has_colorbar = any(item is not ax for item in ax.figure.axes)
        ax.set_position([0.07, 0.09, 0.76 if has_colorbar else 0.84, 0.76 if has_colorbar else 0.84])
    controller._preview_globe_params = params
    controller._preview_globe_zoom = float(params["zoom"])
    with contextlib.suppress(Exception):
        controller._sync_preview_3d_controls_from_params(params)
    if draw:
        with contextlib.suppress(Exception):
            controller._canvas.draw_idle()


def _preview_layer_visible(controller, layer_type: str, *, fallback: bool = True) -> bool:
    with contextlib.suppress(Exception):
        if hasattr(controller, "_preview_layer_visible"):
            return bool(controller._preview_layer_visible(layer_type))
    return bool(fallback)


def _preview_layers_by_type(controller, *layer_types: str):
    with contextlib.suppress(Exception):
        if hasattr(controller, "_preview_layers_by_type"):
            return controller._preview_layers_by_type(*layer_types, visible_only=True)
    return []


def _update_preview_status(controller, path, idx, frame, grid, elapsed_ms: float) -> None:
    page = controller.window.page_preview
    active_var_name = frame.get("meta", {}).get("active_var", page.cmb_data_var.currentText().strip() or "ewh")
    page.lbl_dataset.setText(f"{Path(path).name} | {active_var_name}")
    finite = np.isfinite(grid)
    if np.any(finite):
        page.lbl_grid_value.setText(f"{float(np.nanmean(grid[finite])):.3f}")
    else:
        page.lbl_grid_value.setText("NaN")
    page.lbl_engine_latency.setText(f"{elapsed_ms:.1f} ms")
    page.canvas_preview_title.setText("")
    page.canvas_preview_title.setVisible(False)


def _render_2d_fallback(controller) -> None:
    import time

    start = time.perf_counter()
    page = controller.window.page_preview
    label = page.cmb_projection.currentText().strip()
    proj = _projection_key(controller, label)
    path, idx, frame, grid, lon, lat = _grid_context(controller)
    grid, lon, lat, bbox = _apply_bbox(controller, grid, lon, lat)
    lon_sort = wrap_delta_lon(lon, 0.0)
    order = np.argsort(lon_sort)
    lon = lon[order]
    grid = grid[order, :]
    lon2d, lat2d = np.meshgrid(lon, lat)
    grid_plot = grid.T if grid.shape == (lon.size, lat.size) else grid
    lon0, lat0 = get_proj_center(lon, lat)
    lat1, lat2 = get_conic_parallels(float(np.nanmin(lat)), float(np.nanmax(lat)))
    x, y = _project(controller, proj, lon2d, lat2d, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
    x, y, controller._proj_scale, controller._proj_x0 = scale_projection(x, y, target_ratio=2.0)
    cmin, cmax = _color_limits(page, grid_plot)
    cmap = page.cmb_cmap.currentText().strip() or "RdBu_r"
    controller._figure.clear()
    controller._ax = controller._figure.add_subplot(111)
    ax = controller._ax
    im = None
    finite_xy = np.isfinite(x) & np.isfinite(y) & np.isfinite(grid_plot)
    if np.all(np.isfinite(x)) and np.all(np.isfinite(y)):
        im = ax.pcolormesh(x, y, grid_plot, shading="auto", cmap=cmap, vmin=cmin, vmax=cmax, zorder=2)
    elif np.any(finite_xy):
        im = ax.scatter(x[finite_xy], y[finite_xy], c=grid_plot[finite_xy], s=9, marker="s", linewidths=0, cmap=cmap, vmin=cmin, vmax=cmax, zorder=2)
    ax.set_axis_off()
    spatial_grid_enabled = bool(getattr(page, "chk_enable_spatial_grid", None) is None or page.chk_enable_spatial_grid.isChecked())
    if spatial_grid_enabled and _preview_layer_visible(controller, "graticule", fallback=getattr(page, "chk_layer_grid", None) is None or page.chk_layer_grid.isChecked()):
        _draw_enhanced_graticule(controller, proj=proj, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
    _draw_enhanced_coastlines(controller, proj=proj, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
    if im is not None and _preview_layer_visible(controller, "colorbar", fallback=getattr(page, "chk_show_colorbar", None) is None or page.chk_show_colorbar.isChecked()):
        controller._figure.colorbar(im, ax=ax, shrink=0.82, pad=0.02)
    finite = np.isfinite(x) & np.isfinite(y)
    if np.any(finite):
        xmin, xmax = float(np.nanmin(x[finite])), float(np.nanmax(x[finite]))
        ymin, ymax = float(np.nanmin(y[finite])), float(np.nanmax(y[finite]))
        xr, yr = max(1e-9, xmax - xmin), max(1e-9, ymax - ymin)
        controller._preview_full_view = (xmin - 0.05 * xr, xmax + 0.05 * xr, ymin - 0.08 * yr, ymax + 0.08 * yr)
        ax.set_xlim(controller._preview_full_view[0], controller._preview_full_view[1])
        ax.set_ylim(controller._preview_full_view[2], controller._preview_full_view[3])
    controller._preview_pick_state = {"x": np.asarray(x, dtype=float), "y": np.asarray(y, dtype=float), "lon": np.asarray(lon2d, dtype=float), "lat": np.asarray(lat2d, dtype=float), "grid": np.asarray(grid_plot, dtype=float)}
    _polish_rendered_figure(controller, export=False)
    _update_preview_status(controller, path, idx, frame, grid, (time.perf_counter() - start) * 1000.0)
    controller._canvas.draw_idle()


def _render_3d_globe(controller) -> None:
    import time
    import matplotlib as mpl
    import matplotlib.pyplot as plt

    start = time.perf_counter()
    page = controller.window.page_preview
    with contextlib.suppress(Exception):
        controller.on_log("[PREVIEW] 3D Globe render start", "stdout")
    params = _projection_params(page, "3D Globe")
    params.update(dict(getattr(controller, "_preview_globe_control_params", {}) or {}))
    params["radius"] = 1.0
    params["shading"] = False
    params["background_alpha"] = 1.0
    relief = max(0.0, min(0.05, float(params.get("relief_exaggeration", params.get("vertical_exaggeration", 0.0)) or 0.0)))
    params["relief_exaggeration"] = relief
    path, idx, frame, grid, lon, lat = _grid_context(controller)
    grid, lon, lat, _bbox = _apply_bbox(controller, grid, lon, lat)
    lon, grid = _normalize_and_roll_longitude(lon, grid, center=float(params.get("central_longitude", 0.0)))
    lon_step = max(1, int(np.ceil(lon.size / 180)))
    lat_step = max(1, int(np.ceil(lat.size / 90)))
    lon_s = lon[::lon_step]
    lat_s = lat[::lat_step]
    grid_s = grid[::lon_step, ::lat_step]
    lon2d, lat2d = np.meshgrid(lon_s, lat_s)
    grid_plot = grid_s.T if grid_s.shape == (lon_s.size, lat_s.size) else grid_s
    finite = grid_plot[np.isfinite(grid_plot)]
    cmin = parse_float(page.edit_cmin.text())
    cmax = parse_float(page.edit_cmax.text())
    if finite.size and (cmin is None or cmax is None):
        q = float(np.nanpercentile(np.abs(finite), 98.0))
        if q <= 0:
            q = float(np.nanmax(np.abs(finite)) or 1.0)
        cmin = -q if cmin is None else cmin
        cmax = q if cmax is None else cmax
    if cmin is None or cmax is None:
        cmin, cmax = -1.0, 1.0
    norm = mpl.colors.Normalize(vmin=cmin, vmax=cmax)
    cmap = mpl.colormaps[page.cmb_cmap.currentText().strip() or "RdBu_r"]
    fill_value = float(np.nanmean(finite)) if finite.size else 0.0
    grid_for_surface = np.nan_to_num(grid_plot, nan=fill_value)
    radius_grid = 1.0
    if relief > 0:
        max_abs = float(np.nanmax(np.abs(finite))) if finite.size else 0.0
        if max_abs > 0:
            radius_grid = 1.0 + relief * np.clip(grid_for_surface / max_abs, -1.0, 1.0)
    x, y, z = _lonlat_to_globe_xyz(lon2d, lat2d, params=params, surface=True, radius=radius_grid)
    facecolors = cmap(norm(np.nan_to_num(grid_plot, nan=fill_value)))
    controller._figure.clear()
    ax = controller._figure.add_subplot(111, projection="3d")
    controller._ax = ax
    ax.clear()
    ax.plot_surface(
        x,
        y,
        z,
        facecolors=facecolors,
        rstride=1,
        cstride=1,
        linewidth=0,
        antialiased=False,
        shade=False,
        alpha=1.0,
    )
    coastline_visible = _preview_layer_visible(controller, "coastline", fallback=getattr(page, "chk_layer_coastlines", None) is None or page.chk_layer_coastlines.isChecked())
    with contextlib.suppress(Exception):
        controller.on_log(f"[PREVIEW] 3D coastline visible = {bool(coastline_visible)}", "stdout")
    if coastline_visible:
        with contextlib.suppress(Exception):
            controller.on_log("[PREVIEW] calling _draw_3d_coastlines", "stdout")
        coastline_segments = _draw_3d_coastlines(controller, ax, params=params)
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] 3D coastline drawn segments = {coastline_segments}", "stdout")
    spatial_grid_enabled = bool(getattr(page, "chk_enable_spatial_grid", None) is None or page.chk_enable_spatial_grid.isChecked())
    if spatial_grid_enabled and _preview_layer_visible(controller, "graticule", fallback=getattr(page, "chk_layer_grid", None) is None or page.chk_layer_grid.isChecked()):
        _draw_3d_graticule(ax, params=params, options=_graticule_ui_options(controller))
    _draw_3d_boundary_layers(controller, ax, params=params)
    controller._preview_globe_params = params
    mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    mappable.set_array([])
    if _preview_layer_visible(controller, "colorbar", fallback=getattr(page, "chk_show_colorbar", None) is None or page.chk_show_colorbar.isChecked()):
        controller._figure.colorbar(mappable, ax=ax, shrink=0.68, pad=0.03)
    _polish_rendered_figure(controller, export=False)
    apply_3d_globe_view(controller)
    _update_preview_status(controller, path, idx, frame, grid, (time.perf_counter() - start) * 1000.0)
    controller._preview_pick_state = None
    with contextlib.suppress(Exception):
        controller._sync_preview_toolbar_mode()
    controller._canvas.draw_idle()


def _normalize_and_roll_longitude(lon, grid, *, center: float = 0.0):
    lon = np.asarray(lon, dtype=float).squeeze()
    grid = np.asarray(grid, dtype=float)
    lon_centered = ((lon - center + 180.0) % 360.0) - 180.0 + center
    order = np.argsort(lon_centered)
    if grid.shape[0] == lon.size:
        grid = grid[order, :]
    elif grid.ndim >= 2 and grid.shape[1] == lon.size:
        grid = grid[:, order].T
    return lon_centered[order], grid


def _lonlat_to_globe_xyz(lons, lats, *, params: dict, surface: bool = False, radius: float | None = None):
    if radius is None:
        radius = float(params.get("radius", 1.0))
        if not surface:
            radius *= 1.004
    central_lon = float(params.get("central_longitude", 0.0))
    central_lat = float(params.get("central_latitude", 0.0))
    lon_rad = np.deg2rad(np.asarray(lons, dtype=float) - central_lon)
    lat_rad = np.deg2rad(np.asarray(lats, dtype=float))
    x = radius * np.cos(lat_rad) * np.cos(lon_rad)
    y = radius * np.cos(lat_rad) * np.sin(lon_rad)
    z = radius * np.sin(lat_rad)
    if central_lat:
        angle = np.deg2rad(-central_lat)
        x_rot = x * np.cos(angle) + z * np.sin(angle)
        z_rot = -x * np.sin(angle) + z * np.cos(angle)
        x, z = x_rot, z_rot
    return x, y, z


def _surface_radius_max(params: dict) -> float:
    relief = max(0.0, min(0.05, float(params.get("relief_exaggeration", 0.0) or 0.0)))
    return 1.0 + relief


def _line_radius(params: dict, offset: float) -> float:
    return _surface_radius_max(params) + float(offset)


def _draw_3d_graticule(ax, *, params: dict, options: dict | None = None) -> None:
    options = options or {
        "lon_interval": 60.0,
        "lat_interval": 30.0,
        "linewidth": 0.48,
        "linestyle": "--",
        "color": "#8aa4b4",
    }
    if options.get("linestyle") in {"none", "None", ""} or float(options.get("linewidth", 0.0) or 0.0) <= 0.0:
        return
    radius = _line_radius(params, 0.010)
    for lat in np.arange(-90 + options["lat_interval"], 90, options["lat_interval"]):
        lons = np.linspace(-180, 180, 361)
        lats = np.full_like(lons, lat, dtype=float)
        _plot_3d_lonlat(
            ax,
            lons,
            lats,
            params=params,
            radius=radius,
            color=options["color"],
            linewidth=options["linewidth"],
            alpha=0.72,
            linestyle=options["linestyle"],
        )
    for lon in np.arange(-180, 180 + 0.1, options["lon_interval"]):
        lats = np.linspace(-90, 90, 241)
        lons = np.full_like(lats, lon, dtype=float)
        _plot_3d_lonlat(
            ax,
            lons,
            lats,
            params=params,
            radius=radius,
            color=options["color"],
            linewidth=options["linewidth"],
            alpha=0.72,
            linestyle=options["linestyle"],
        )


def _draw_3d_coastlines(controller, ax, *, params: dict) -> int:
    drawn = 0
    radius = _line_radius(params, 0.030 if DEBUG_3D_COASTLINE else 0.012)
    color = "#000000" if DEBUG_3D_COASTLINE else "#1f2933"
    linewidth = 1.2 if DEBUG_3D_COASTLINE else 0.55
    alpha = 1.0 if DEBUG_3D_COASTLINE else 0.85
    stats: list[dict[str, int]] = []
    try:
        for lons, lats in get_coastline_geometries():
            drawn += _plot_3d_lonlat_segments(
                ax,
                lons,
                lats,
                params=params,
                radius=radius,
                color=color,
                linewidth=linewidth,
                alpha=alpha,
                linestyle="-",
                stats=stats,
            )
    except Exception as exc:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] 3D coastline Natural Earth geometry failed: {exc}", "stderr")

    _log_3d_segment_stats(controller, "Natural Earth coastline", stats)
    if drawn > 0:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] 3D coastline rendered from Cartopy/Natural Earth: {drawn} segments", "stdout")
        return drawn

    # Keep the project-local coastline source only as a supplementary path.
    # The primary 3D source above mirrors the Cartopy/Natural Earth source used
    # by 2D GeoAxes coastlines.
    coast_path = ""
    with contextlib.suppress(Exception):
        coast_path = controller._resolve_coastline_path()
    if not coast_path:
        with contextlib.suppress(Exception):
            controller.on_log("[PREVIEW] 3D coastline rendered 0 segments from Cartopy/Natural Earth.", "stderr")
        return drawn
    try:
        import os
        import shapefile

        shp_path = coast_path
        if os.path.isdir(shp_path):
            for filename in os.listdir(shp_path):
                if filename.lower().endswith(".shp"):
                    shp_path = os.path.join(shp_path, filename)
                    break
        reader = shapefile.Reader(shp_path)
        for shape in reader.shapes():
            pts = np.asarray(shape.points, dtype=float)
            if pts.ndim != 2 or pts.shape[0] < 2:
                continue
            parts = list(shape.parts) + [len(pts)]
            for i in range(len(parts) - 1):
                seg = pts[parts[i] : parts[i + 1]]
                if seg.shape[0] >= 2:
                    drawn += _plot_3d_lonlat_segments(
                        ax,
                        seg[:, 0],
                        seg[:, 1],
                        params=params,
                        radius=radius,
                        color=color,
                        linewidth=linewidth,
                        alpha=alpha,
                        linestyle="-",
                        stats=stats,
                    )
        _log_3d_segment_stats(controller, "local coastline", stats)
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] 3D coastline rendered from local source: {drawn} segments", "stdout")
    except Exception as exc:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] 3D coastline layer failed: {exc}", "stderr")
    return drawn


def get_coastline_geometries(resolution: str = "110m"):
    """Yield lon/lat coastline line segments from Cartopy Natural Earth data."""
    import cartopy.feature as cfeature

    feature = cfeature.NaturalEarthFeature(
        category="physical",
        name="coastline",
        scale=resolution,
        facecolor="none",
    )
    for geom in feature.geometries():
        yield from _iter_geometry_lonlat_lines(geom)


def _iter_geometry_lonlat_lines(geom):
    geom_type = getattr(geom, "geom_type", "")
    if geom_type == "LineString":
        coords = np.asarray(getattr(geom, "coords", []), dtype=float)
        if coords.ndim == 2 and coords.shape[0] >= 2:
            yield coords[:, 0], coords[:, 1]
        return
    if geom_type == "MultiLineString":
        for line in getattr(geom, "geoms", []):
            yield from _iter_geometry_lonlat_lines(line)
        return
    if geom_type == "Polygon":
        exterior = getattr(geom, "exterior", None)
        coords = np.asarray(getattr(exterior, "coords", []), dtype=float)
        if coords.ndim == 2 and coords.shape[0] >= 2:
            yield coords[:, 0], coords[:, 1]
        return
    if geom_type == "MultiPolygon":
        for polygon in getattr(geom, "geoms", []):
            yield from _iter_geometry_lonlat_lines(polygon)


def _draw_3d_boundary_layers(controller, ax, *, params: dict) -> None:
    radius = _line_radius(params, 0.014)
    for layer in _preview_layers_by_type(controller, "boundary", "shapefile"):
        path = str(getattr(layer, "path", "") or "")
        if not path or Path(path).suffix.lower() not in {".shp", ".bln", ".txt"}:
            with contextlib.suppress(Exception):
                controller.on_log(f"[PREVIEW] 3D layer skipped: unsupported boundary layer {getattr(layer, 'name', path)}", "stderr")
            continue
        if not Path(path).exists():
            continue
        try:
            boundaries = read_boundary_file(path)
            for boundary in boundaries:
                lons = np.asarray(getattr(boundary, "lon", []), dtype=float)
                lats = np.asarray(getattr(boundary, "lat", []), dtype=float)
                if lons.size >= 2 and lats.size >= 2:
                    _plot_3d_lonlat_segments(ax, lons, lats, params=params, radius=radius, color="#b00020", linewidth=0.72, alpha=0.88, linestyle="-")
        except Exception as exc:
            with contextlib.suppress(Exception):
                controller.on_log(f"[PREVIEW] 3D boundary layer failed: {path}: {exc}", "stderr")


def _plot_3d_lonlat(ax, lons, lats, *, params: dict, radius: float = 1.004, color, linewidth, alpha=1.0, linestyle="-") -> None:
    x, y, z = _lonlat_to_globe_xyz(lons, lats, params=params, radius=radius)
    ax.plot3D(x, y, z, color=color, linewidth=linewidth, alpha=alpha, linestyle=linestyle)


def _plot_3d_lonlat_segments(ax, lons, lats, *, params: dict, radius: float, color, linewidth: float, alpha: float, linestyle: str = "-", stats: list[dict[str, int]] | None = None) -> int:
    raw_lons = np.asarray(lons, dtype=float)
    raw_lats = np.asarray(lats, dtype=float)
    input_points = int(min(raw_lons.size, raw_lats.size))
    lons = normalize_lon_for_plot(raw_lons, lon_mode="-180_180")
    lats = raw_lats
    if lons.size < 2 or lats.size < 2:
        if stats is not None:
            stats.append({"input_points": input_points, "finite_points": 0, "split_segments": 0, "plot_count": 0})
        return 0
    finite = np.isfinite(lons) & np.isfinite(lats)
    if not np.any(finite):
        if stats is not None:
            stats.append({"input_points": input_points, "finite_points": 0, "split_segments": 0, "plot_count": 0})
        return 0
    lons = lons[finite]
    lats = lats[finite]
    split_segments = list(split_dateline(lons, lats, wrap_delta_lon, threshold=180.0, lon0=float(params.get("central_longitude", 0.0))))
    drawn = 0
    for seg_lons, seg_lats in split_segments:
        if len(seg_lons) < 2:
            continue
        _plot_3d_lonlat(ax, seg_lons, seg_lats, params=params, radius=radius, color=color, linewidth=linewidth, alpha=alpha, linestyle=linestyle)
        drawn += 1
    if stats is not None:
        stats.append(
            {
                "input_points": input_points,
                "finite_points": int(lons.size),
                "split_segments": int(len(split_segments)),
                "plot_count": int(drawn),
            }
        )
    return drawn


def _log_3d_segment_stats(controller, label: str, stats: list[dict[str, int]]) -> None:
    if not stats:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] 3D {label} stats: no input segments", "stderr")
        return
    totals = {
        "input_points": sum(item.get("input_points", 0) for item in stats),
        "finite_points": sum(item.get("finite_points", 0) for item in stats),
        "split_segments": sum(item.get("split_segments", 0) for item in stats),
        "plot_count": sum(item.get("plot_count", 0) for item in stats),
    }
    with contextlib.suppress(Exception):
        controller.on_log(
            "[PREVIEW] 3D "
            f"{label} stats: input_points={totals['input_points']} "
            f"finite_points={totals['finite_points']} "
            f"split_segments={totals['split_segments']} "
            f"plot3D_calls={totals['plot_count']}",
            "stdout",
        )


def _post_polish_overlay(controller) -> None:
    page = controller.window.page_preview
    label = page.cmb_projection.currentText().strip()
    if projection_renderer(label) == "matplotlib_3d":
        return
    proj = _projection_key(controller, label)
    try:
        _path, _idx, _frame, grid, lon, lat = _grid_context(controller)
        grid, lon, lat, bbox = _apply_bbox(controller, grid, lon, lat)
        lon0, lat0 = get_proj_center(lon, lat)
        lat1, lat2 = get_conic_parallels(float(np.nanmin(lat)), float(np.nanmax(lat)))
    except Exception:
        lon0, lat0, lat1, lat2, bbox = 0.0, 0.0, 30.0, 60.0, None
    _draw_enhanced_graticule(controller, proj=proj, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
    _draw_enhanced_coastlines(controller, proj=proj, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)


def _polish_rendered_figure(controller, *, export: bool = False) -> None:
    fig = getattr(controller, "_figure", None)
    ax = getattr(controller, "_ax", None)
    page = controller.window.page_preview
    if fig is None or ax is None:
        return
    var_name = page.cmb_data_var.currentText().strip() or "value"
    unit = _current_unit(controller)
    cb_label = f"{var_name} ({unit})" if unit else var_name
    with contextlib.suppress(Exception):
        ax.set_title("")
    with contextlib.suppress(Exception):
        page.canvas_preview_title.setText("")
        page.canvas_preview_title.setVisible(False)
    with contextlib.suppress(Exception):
        for line in ax.lines:
            color = str(line.get_color()).lower()
            if color in {"#1f3547", "#1f3547ff", "#263f4d"}:
                line.set_linewidth(0.30 if export else 0.42)
                line.set_alpha(0.88)
            elif "cccccc" in color or "9fb6c5" in color or "gray" in color or "grey" in color:
                line.set_linewidth(0.26 if export else 0.38)
                line.set_alpha(0.72)
        ax.tick_params(labelsize=8 if not export else 9)
    for cax in list(fig.axes):
        if cax is ax:
            continue
        with contextlib.suppress(Exception):
            cax.set_ylabel(cb_label, fontsize=9 if not export else 10)
            cax.tick_params(labelsize=8 if not export else 9)
    with contextlib.suppress(Exception):
        fig.subplots_adjust(left=0.04, right=0.94, top=0.96, bottom=0.05)


def _enhanced_render(self) -> None:
    try:
        if not _handle_cpt_combo(self):
            return
        label = self.window.page_preview.cmb_projection.currentText().strip()
        renderer = projection_renderer(label)
        proj = _projection_key(self, label)
        if renderer == "matplotlib_3d":
            _render_3d_globe(self)
        elif proj in FALLBACK_RENDER_PROJECTIONS:
            _render_2d_fallback(self)
        else:
            self._preview_original_render()
            _post_polish_overlay(self)
            _polish_rendered_figure(self, export=False)
            self._canvas.draw_idle()
        _apply_preview_labels(self.window)
    except Exception as exc:
        self._show_error(_tr(self.window, "Preview", "预览"), str(exc))


def _enhanced_load_stack_info(self) -> None:
    page = self.window.page_preview
    path = page.edit_dataset_source.text().strip()
    if not path:
        self._show_warning(_tr(self.window, "Preview", "预览"), _tr(self.window, "Please select a data file first.", "请先选择数据文件。"))
        return
    try:
        info = self.host.load_stack_info(path)
        shape = tuple(info.get("shape") or ())
        meta = info.get("meta", {}) or {}
        active_var = str(meta.get("active_var") or "ewh").strip() or "ewh"
        var_names = [str(name).strip() for name in meta.get("data_var_names", []) if str(name).strip()] or [active_var]
        current = page.cmb_data_var.currentText().strip()
        page.cmb_data_var.blockSignals(True)
        page.cmb_data_var.clear()
        page.cmb_data_var.addItems(var_names)
        target_var = active_var if active_var in var_names else (current if current in var_names else var_names[0])
        page.cmb_data_var.setCurrentText(target_var)
        page.cmb_data_var.blockSignals(False)
        nt = int(shape[2]) if len(shape) >= 3 else 1
        page.slider_time_index.blockSignals(True)
        page.slider_time_index.setRange(0, max(0, nt - 1))
        page.slider_time_index.setValue(0)
        page.slider_time_index.blockSignals(False)
        self._sync_preview_time_label(0)
        if _is_zh(self.window):
            page.lbl_stack_info.setText(f"尺寸 {shape[0]} × {shape[1]} × {nt}")
        else:
            page.lbl_stack_info.setText(f"Size {shape[0]} × {shape[1]} × {nt}")
        self._apply_preview_bbox_from_info(info)
        _apply_preview_labels(self.window)
        self.on_log(f"[PREVIEW] Data loaded: {path}", "stdout")
    except Exception as exc:
        page.lbl_stack_info.setText((_tr(self.window, "Load failed", "读取失败")) + f": {exc}")
        self._show_error(_tr(self.window, "Preview", "预览"), str(exc))


def _enhanced_var_changed(self) -> None:
    _apply_preview_labels(self.window)


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
        row_layout = QHBoxLayout(row_path)
        row_layout.setContentsMargins(0, 0, 0, 0)
        path_edit = QLineEdit(str(default_path))
        browse_btn = QPushButton(_tr(self.window, "Browse", "浏览"))
        row_layout.addWidget(path_edit, 1)
        row_layout.addWidget(browse_btn)
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
        size_layout = QHBoxLayout(size_row)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.addWidget(width_spin)
        size_layout.addWidget(QLabel("×"))
        size_layout.addWidget(height_spin)
        size_layout.addWidget(QLabel("px"))
        size_layout.addStretch(1)
        form.addRow(_tr(self.window, "Canvas size", "画布尺寸"), size_row)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(_tr(self.window, "Export", "导出"))
        buttons.button(QDialogButtonBox.Cancel).setText(_tr(self.window, "Cancel", "取消"))
        layout.addWidget(buttons)

        def choose_path():
            path, _ = QFileDialog.getSaveFileName(dialog, _tr(self.window, "Export Figure", "导出图像"), path_edit.text().strip() or str(default_path), "PNG (*.png);;TIFF (*.tif);;PDF (*.pdf);;SVG (*.svg)")
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
        added = []
        try:
            self._figure.set_dpi(dpi)
            self._figure.set_size_inches(width_px / dpi, height_px / dpi, forward=True)
            _polish_rendered_figure(self, export=True)
            dataset = self.window.page_preview.lbl_dataset.text().strip()
            time_text = self._preview_time_text(int(self.window.page_preview.slider_time_index.value()))
            variable = self.window.page_preview.cmb_data_var.currentText().strip() or "ewh"
            caption = f"{dataset}    Variable: {variable}" + (f"    Time: {time_text}" if time_text else "")
            added.append(self._figure.text(0.04, 0.018, caption, fontsize=8, color="#34495e"))
            self._figure.savefig(str(out_path), dpi=dpi, format=fmt, bbox_inches="tight", pad_inches=0.05, facecolor="white")
            self._show_info(_tr(self.window, "Export Figure", "导出图像"), _tr(self.window, "Saved to:", "已保存至：") + f"\n{out_path}")
            self.on_log(f"[PREVIEW] Figure exported: {out_path} ({fmt}, {width_px}x{height_px}, {dpi} dpi)", "stdout")
        finally:
            for item in added:
                with contextlib.suppress(Exception):
                    item.remove()
            self._figure.set_dpi(old_dpi)
            self._figure.set_size_inches(old_size[0], old_size[1], forward=True)
            _polish_rendered_figure(self, export=False)
            self._canvas.draw_idle()
    except Exception as exc:
        self._show_error(_tr(self.window, "Export Figure", "导出图像"), str(exc))


def _on_cmap_changed(controller) -> None:
    _handle_cpt_combo(controller)


def install_preview_enhancements(window) -> None:
    _register_default_colormaps()
    page = window.page_preview
    controller = window.controller
    cpt_item = _import_cpt_label(window)
    _set_combo_items(page.cmb_projection, PROJECTION_CHOICES, current=projection_key_to_name(page.cmb_projection.currentText() or "Robinson"))
    _set_combo_items(page.cmb_cmap, BASE_CMAPS + [cpt_item], current="RdBu_r")
    page._last_valid_cmap = "RdBu_r"
    page.chk_layer_coastlines.setChecked(True)
    page.chk_layer_grid.setChecked(True)
    page.lbl_grid_value.setText("—")

    if not hasattr(controller, "_preview_original_render"):
        controller._preview_original_render = controller.on_render_preview
    if not hasattr(controller, "_preview_original_export"):
        controller._preview_original_export = controller.on_export_figure
    if not hasattr(controller, "_preview_original_load_stack_info"):
        controller._preview_original_load_stack_info = controller.on_load_stack_info
    if not hasattr(controller, "_preview_original_var_changed"):
        controller._preview_original_var_changed = controller.on_preview_var_changed

    controller.on_render_preview = MethodType(_enhanced_render, controller)
    controller.on_export_figure = MethodType(_enhanced_export, controller)
    controller.on_load_stack_info = MethodType(_enhanced_load_stack_info, controller)
    controller.on_preview_var_changed = MethodType(_enhanced_var_changed, controller)

    for button, handler in ((page.btn_plot, controller.on_render_preview), (page.btn_export_figure, controller.on_export_figure), (page.btn_load_stack, controller.on_load_stack_info)):
        _safe_disconnect(button.clicked)
        button.clicked.connect(handler)
    _safe_disconnect(page.cmb_data_var.currentIndexChanged)
    page.cmb_data_var.currentIndexChanged.connect(lambda _idx=0: controller.on_preview_var_changed())
    _safe_disconnect(page.cmb_cmap.currentIndexChanged)
    page.cmb_cmap.currentIndexChanged.connect(lambda _idx=0: _on_cmap_changed(controller))
    _safe_disconnect(page.cmb_projection.currentIndexChanged)
    page.cmb_projection.currentIndexChanged.connect(lambda _idx=0: _sync_projection_parameter_panel(window))
    _sync_projection_parameter_panel(window)
    _patch_refresh_translations(window)
    _apply_preview_labels(window)
