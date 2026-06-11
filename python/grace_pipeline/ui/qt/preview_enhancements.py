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
from grace_pipeline.ui.plotting.boundaries import plot_line, read_boundary_file, split_dateline
from grace_pipeline.ui.plotting.overlays import draw_boundaries, draw_coastlines
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

ROOT_DIR = get_root_dir().resolve()
PROJECTION_CHOICES = [
    "Robinson (Global)",
    "Plate Carree",
    "Mercator",
    "Mollweide",
    "Equal Earth",
    "Winkel Tripel",
    "Eckert IV",
    "Sinusoidal",
    "Miller",
    "Orthographic",
    "Azimuthal Equidistant",
    "Stereographic",
    "Lambert Conformal",
    "Albers Equal Area",
    "3D Globe (Surface)",
]
FALLBACK_RENDER_PROJECTIONS = {
    "Orthographic",
    "Azimuthal Equidistant",
    "Stereographic",
    "Lambert Conformal",
    "Albers Equal Area",
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
        "Data Variable": _tr(window, "Variable", "数据变量"),
        "Time Index": _tr(window, "Time", "时间"),
        "Projection": _tr(window, "Projection", "投影方式"),
        "Colormap": _tr(window, "Colormap", "色带"),
        "Color Min": _tr(window, "Minimum", "色标最小值"),
        "Color Max": _tr(window, "Maximum", "色标最大值"),
        "Use Detected Extent": _tr(window, "Use Data Extent", "使用数据范围"),
        "Render Preview": _tr(window, "Render", "渲染预览"),
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
        if label.text() in replacements:
            label.setText(replacements[label.text()])
    for widget in page.findChildren(QWidget):
        if hasattr(widget, "text") and hasattr(widget, "setText"):
            with contextlib.suppress(Exception):
                text = widget.text()
                if text in replacements:
                    widget.setText(replacements[text])
    with contextlib.suppress(Exception):
        page.btn_load_stack.setText(_tr(window, "Read Data", "读取数据"))
        page.btn_plot.setText(_tr(window, "Render", "渲染预览"))
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
        result = original()
        _apply_preview_labels(self)
        return result

    window.refresh_translations = MethodType(patched_refresh_translations, window)
    window._preview_refresh_patch = True


def _projection_key(controller, label: str) -> str:
    try:
        return controller._projection_key(label)
    except Exception:
        mapping = {
            "Robinson (Global)": "Robinson",
            "Plate Carree": "PlateCarree",
            "Mercator": "Mercator",
            "Mollweide": "Mollweide",
            "Equal Earth": "EqualEarth",
            "Winkel Tripel": "WinkelTripel",
            "Eckert IV": "EckertIV",
            "Sinusoidal": "Sinusoidal",
            "Miller": "Miller",
            "Orthographic": "Orthographic",
            "Azimuthal Equidistant": "AzimuthalEquidistant",
            "Stereographic": "Stereographic",
            "Lambert Conformal": "LambertConformal",
            "Albers Equal Area": "AlbersEqualArea",
        }
        return mapping.get(label, "Robinson")


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


def _draw_enhanced_graticule(controller, *, proj, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0) -> None:
    ax = controller._ax
    if ax is None:
        return
    if proj == "PlateCarree":
        with contextlib.suppress(Exception):
            ax.set_xticks(np.arange(-180, 181, 60))
            ax.set_yticks(np.arange(-90, 91, 30))
            ax.grid(True, color="#9fb6c5", linewidth=0.55, linestyle="--", alpha=0.78, zorder=7)
        return
    for lat in np.arange(-60, 61, 30):
        lons = np.linspace(-180, 180, 721)
        lats = np.full_like(lons, lat, dtype=float)
        x, y = _project(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        x = apply_proj_scale(x, getattr(controller, "_proj_scale", None), getattr(controller, "_proj_x0", None))
        _draw_segmented_line(ax, x, y, color="#9fb6c5", linewidth=0.48, alpha=0.72, linestyle="--", zorder=7)
    for lon in np.arange(-180, 181, 60):
        lats = np.linspace(-88, 88, 721)
        lons = np.full_like(lats, lon, dtype=float)
        x, y = _project(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        x = apply_proj_scale(x, getattr(controller, "_proj_scale", None), getattr(controller, "_proj_x0", None))
        _draw_segmented_line(ax, x, y, color="#9fb6c5", linewidth=0.48, alpha=0.72, linestyle="--", zorder=7)


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
    bbox = None
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
    lon_eval = normalize_lon_for_plot(lon, lon_mode=infer_plot_lon_mode(lon))
    full_lon = abs(lon_max - lon_min) >= 359.0
    if full_lon:
        lon_mask = np.ones_like(lon, dtype=bool)
    elif lon_min <= lon_max:
        lon_mask = (lon_eval >= lon_min) & (lon_eval <= lon_max)
    else:
        lon_mask = (lon_eval >= lon_min) | (lon_eval <= lon_max)
    lat_mask = (lat >= lat_min) & (lat <= lat_max)
    if np.any(lon_mask) and np.any(lat_mask):
        lon = lon[lon_mask]
        lat = lat[lat_mask]
        grid = grid[np.ix_(lon_mask, lat_mask)]
    return grid, lon, lat, bbox


def _color_limits(page, grid):
    cmin = parse_float(page.edit_cmin.text())
    cmax = parse_float(page.edit_cmax.text())
    return cmin, cmax


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
    _draw_enhanced_graticule(controller, proj=proj, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
    _draw_enhanced_coastlines(controller, proj=proj, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
    if im is not None:
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
    path, idx, frame, grid, lon, lat = _grid_context(controller)
    grid, lon, lat, _bbox = _apply_bbox(controller, grid, lon, lat)
    # Downsample for responsive 3-D rendering.
    lon_step = max(1, int(np.ceil(lon.size / 180)))
    lat_step = max(1, int(np.ceil(lat.size / 90)))
    lon_s = lon[::lon_step]
    lat_s = lat[::lat_step]
    grid_s = grid[::lon_step, ::lat_step]
    lon2d, lat2d = np.meshgrid(lon_s, lat_s)
    grid_plot = grid_s.T if grid_s.shape == (lon_s.size, lat_s.size) else grid_s
    finite = grid_plot[np.isfinite(grid_plot)]
    if finite.size:
        cmin = parse_float(page.edit_cmin.text())
        cmax = parse_float(page.edit_cmax.text())
        if cmin is None or cmax is None:
            q = float(np.nanpercentile(np.abs(finite), 98.0))
            if q <= 0:
                q = float(np.nanmax(np.abs(finite)) or 1.0)
            cmin = -q if cmin is None else cmin
            cmax = q if cmax is None else cmax
    else:
        cmin, cmax = -1.0, 1.0
    norm = mpl.colors.Normalize(vmin=cmin, vmax=cmax)
    cmap = mpl.colormaps[page.cmb_cmap.currentText().strip() or "RdBu_r"]
    amp = np.zeros_like(grid_plot, dtype=float)
    if cmax != cmin:
        amp = np.clip((grid_plot - cmin) / (cmax - cmin) - 0.5, -0.5, 0.5)
    radius = 1.0 + 0.08 * np.nan_to_num(amp, nan=0.0)
    lon_rad = np.deg2rad(lon2d)
    lat_rad = np.deg2rad(lat2d)
    x = radius * np.cos(lat_rad) * np.cos(lon_rad)
    y = radius * np.cos(lat_rad) * np.sin(lon_rad)
    z = radius * np.sin(lat_rad)
    facecolors = cmap(norm(np.nan_to_num(grid_plot, nan=np.nanmean(finite) if finite.size else 0.0)))
    controller._figure.clear()
    ax = controller._figure.add_subplot(111, projection="3d")
    controller._ax = ax
    ax.plot_surface(x, y, z, facecolors=facecolors, rstride=1, cstride=1, linewidth=0, antialiased=False, shade=False, alpha=0.98)
    _draw_3d_graticule(controller, ax)
    _draw_3d_coastlines(controller, ax)
    ax.set_axis_off()
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=24, azim=-65)
    mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    mappable.set_array([])
    controller._figure.colorbar(mappable, ax=ax, shrink=0.68, pad=0.03)
    _polish_rendered_figure(controller, export=False)
    _update_preview_status(controller, path, idx, frame, grid, (time.perf_counter() - start) * 1000.0)
    controller._preview_pick_state = None
    controller._canvas.draw_idle()


def _draw_3d_graticule(controller, ax) -> None:
    for lat in np.arange(-60, 61, 30):
        lons = np.linspace(-180, 180, 361)
        lats = np.full_like(lons, lat, dtype=float)
        _plot_3d_lonlat(ax, lons, lats, color="#9fb6c5", linewidth=0.45, alpha=0.65, linestyle="--")
    for lon in np.arange(-180, 181, 60):
        lats = np.linspace(-85, 85, 241)
        lons = np.full_like(lats, lon, dtype=float)
        _plot_3d_lonlat(ax, lons, lats, color="#9fb6c5", linewidth=0.45, alpha=0.65, linestyle="--")


def _draw_3d_coastlines(controller, ax) -> None:
    coast_path = ""
    with contextlib.suppress(Exception):
        coast_path = controller._resolve_coastline_path()
    if not coast_path:
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
            pts = np.asarray(shape.points, dtype=float)
            if pts.ndim != 2 or pts.shape[0] < 2:
                continue
            parts = list(shape.parts) + [len(pts)]
            for i in range(len(parts) - 1):
                seg = pts[parts[i] : parts[i + 1]]
                if seg.shape[0] >= 2:
                    _plot_3d_lonlat(ax, seg[:, 0], seg[:, 1], color="#263f4d", linewidth=0.35, alpha=0.9)
    except Exception:
        return


def _plot_3d_lonlat(ax, lons, lats, *, color, linewidth, alpha=1.0, linestyle="-") -> None:
    lon_rad = np.deg2rad(np.asarray(lons, dtype=float))
    lat_rad = np.deg2rad(np.asarray(lats, dtype=float))
    r = 1.006
    x = r * np.cos(lat_rad) * np.cos(lon_rad)
    y = r * np.cos(lat_rad) * np.sin(lon_rad)
    z = r * np.sin(lat_rad)
    ax.plot3D(x, y, z, color=color, linewidth=linewidth, alpha=alpha, linestyle=linestyle)


def _post_polish_overlay(controller) -> None:
    page = controller.window.page_preview
    label = page.cmb_projection.currentText().strip()
    if label == "3D Globe (Surface)":
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


def _safe_original_render(controller) -> None:
    controller._preview_original_render()


def _enhanced_render(self) -> None:
    try:
        if not _handle_cpt_combo(self):
            return
        label = self.window.page_preview.cmb_projection.currentText().strip()
        if label == "3D Globe (Surface)":
            _render_3d_globe(self)
        elif label in FALLBACK_RENDER_PROJECTIONS:
            _render_2d_fallback(self)
        else:
            _safe_original_render(self)
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
        _t_years, time_labels = self.host._resolve_time(info.get("t"), nt, meta=meta)
        first_label = str(time_labels[0]) if time_labels else "-"
        last_label = str(time_labels[min(len(time_labels), nt) - 1]) if time_labels else "-"
        unit = _unit_from_meta(meta, target_var)
        if _is_zh(self.window):
            page.lbl_stack_info.setText(f"尺寸 {shape[0]} × {shape[1]} × {nt}\n变量 {target_var} | 单位 {unit}\n时间 {first_label} — {last_label}")
        else:
            page.lbl_stack_info.setText(f"Size {shape[0]} × {shape[1]} × {nt}\nVariable {target_var} | Unit {unit}\nTime {first_label} — {last_label}")
        self._apply_preview_bbox_from_info(info)
        _apply_preview_labels(self.window)
        self.on_log(f"[PREVIEW] Data loaded: {path}", "stdout")
    except Exception as exc:
        page.lbl_stack_info.setText((_tr(self.window, "Load failed", "读取失败")) + f": {exc}")
        self._show_error(_tr(self.window, "Preview", "预览"), str(exc))


def _enhanced_var_changed(self) -> None:
    page = self.window.page_preview
    active = page.cmb_data_var.currentText().strip() or "ewh"
    text = page.lbl_stack_info.text().strip()
    unit = _current_unit(self)
    lines = text.splitlines() if text else []
    if len(lines) >= 2 and (lines[1].startswith("变量") or lines[1].startswith("Variable")):
        lines[1] = f"变量 {active} | 单位 {unit}" if _is_zh(self.window) else f"Variable {active} | Unit {unit}"
        page.lbl_stack_info.setText("\n".join(lines))
    elif not text:
        page.lbl_stack_info.setText(f"变量 {active} | 单位 {unit}" if _is_zh(self.window) else f"Variable {active} | Unit {unit}")
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
    _set_combo_items(page.cmb_projection, PROJECTION_CHOICES, current="Robinson (Global)")
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
    _patch_refresh_translations(window)
    _apply_preview_labels(window)
