"""Final visual polish for preview map views.

This layer is installed after the preview renderer and the preview header keeper.
It enlarges the rendered map within the canvas and re-applies visible
coastlines, graticules and graticule labels after every render.  The Matplotlib
axes remain title-free so exported figures do not duplicate the Qt header.
"""

from __future__ import annotations

import contextlib
import warnings
from types import MethodType

import numpy as np
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QWidget

from grace_pipeline.ui.plotting.boundaries import plot_line, split_dateline
from grace_pipeline.ui.plotting.projections import (
    apply_proj_scale,
    get_conic_parallels,
    get_proj_center,
    normalize_lon_for_plot,
    wrap_delta_lon,
)
from grace_pipeline.ui.qt import preview_enhancements as pe
from grace_pipeline.ui.qt.preview_title_status import restore_preview_header
from grace_pipeline.ui.qt.qt_safe import is_deleted_qt_object_error


_GRID_COLOR = "#6f8fa3"
_COAST_COLOR = "#1f3547"


def _safe_disconnect(signal) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with contextlib.suppress(Exception):
            signal.disconnect()


def _is_zh(window) -> bool:
    return getattr(getattr(window, "ui_preferences", None), "language", "en") == "zh"


def _tr(window, en: str, zh: str) -> str:
    return zh if _is_zh(window) else en


def _is_3d_axes(ax) -> bool:
    return getattr(ax, "name", "") == "3d" or hasattr(ax, "get_zlim3d")


def _display_grid_enabled(controller) -> bool:
    page = controller.window.page_preview
    if hasattr(page, "chk_show_graticule"):
        return page.chk_show_graticule.isChecked()
    return bool(getattr(page, "chk_layer_grid", None) and page.chk_layer_grid.isChecked())


def _display_colorbar_enabled(controller) -> bool:
    page = controller.window.page_preview
    if hasattr(page, "chk_show_colorbar"):
        return page.chk_show_colorbar.isChecked()
    return True


def _display_coastlines_enabled(controller) -> bool:
    page = controller.window.page_preview
    return bool(getattr(page, "chk_layer_coastlines", None) is None or page.chk_layer_coastlines.isChecked())


def _rerender_safely(controller) -> None:
    with contextlib.suppress(Exception):
        if getattr(controller, "_figure", None) is not None:
            controller.on_render_preview()


def _sync_display_option_labels(window) -> None:
    page = window.page_preview
    if hasattr(page, "chk_show_graticule"):
        page.chk_show_graticule.setText(_tr(window, "Show coordinate grid", "显示坐标网格"))
    if hasattr(page, "chk_show_colorbar"):
        page.chk_show_colorbar.setText(_tr(window, "Show color scale", "显示色标尺"))


def _ensure_display_option_controls(window) -> None:
    """Add the two explicit display switches requested for the preview sidebar."""

    page = window.page_preview
    if hasattr(page, "preview_display_options_row"):
        _sync_display_option_labels(window)
        return

    row = QWidget()
    row.setObjectName("InlineField")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    chk_grid = QCheckBox(_tr(window, "Show coordinate grid", "显示坐标网格"))
    chk_grid.setChecked(bool(getattr(page, "chk_layer_grid", None) and page.chk_layer_grid.isChecked()))
    chk_colorbar = QCheckBox(_tr(window, "Show color scale", "显示色标尺"))
    chk_colorbar.setChecked(True)
    layout.addWidget(chk_grid, 1)
    layout.addWidget(chk_colorbar, 1)

    page.chk_show_graticule = chk_grid
    page.chk_show_colorbar = chk_colorbar
    page.preview_display_options_row = row

    sidebar_layout = page.sidebar.layout()
    insert_at = sidebar_layout.indexOf(page.chk_auto_region)
    if insert_at < 0:
        insert_at = max(0, sidebar_layout.count() - 1)
    sidebar_layout.insertWidget(insert_at, row)

    if hasattr(page, "chk_layer_grid"):
        chk_grid.toggled.connect(page.chk_layer_grid.setChecked)
        page.chk_layer_grid.toggled.connect(chk_grid.setChecked)
    chk_grid.toggled.connect(lambda _checked, _window=window: _rerender_safely(_window.controller))
    chk_colorbar.toggled.connect(lambda _checked, _window=window: _rerender_safely(_window.controller))


def _set_large_canvas_layout(controller) -> None:
    """Use most of the canvas instead of leaving a large blank margin."""

    fig = getattr(controller, "_figure", None)
    ax = getattr(controller, "_ax", None)
    if fig is None or ax is None:
        return
    axes = list(fig.axes)
    color_axes = [item for item in axes if item is not ax]
    show_colorbar = _display_colorbar_enabled(controller)
    try:
        if _is_3d_axes(ax):
            ax.set_position([0.03, 0.03, 0.82 if show_colorbar else 0.93, 0.92])
            ax.set_xlim(-1.10, 1.10)
            ax.set_ylim(-1.10, 1.10)
            ax.set_zlim(-1.10, 1.10)
            ax.set_box_aspect((1, 1, 1))
            for cax in color_axes:
                cax.set_visible(show_colorbar)
                if show_colorbar:
                    cax.set_position([0.86, 0.18, 0.025, 0.64])
        else:
            ax.set_position([0.025, 0.055, 0.82 if show_colorbar else 0.93, 0.88])
            for cax in color_axes:
                cax.set_visible(show_colorbar)
                if show_colorbar:
                    cax.set_position([0.87, 0.17, 0.024, 0.68])
    except Exception:
        return


def _project_line(controller, proj, lon, lat, *, lon0, lat0, lat1, lat2):
    x, y = controller._project(proj, lon, lat, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
    x = apply_proj_scale(x, getattr(controller, "_proj_scale", None), getattr(controller, "_proj_x0", None))
    return x, y


def _plot_2d_line(ax, x, y, *, color=_GRID_COLOR, linewidth=0.55, alpha=0.82, linestyle="--", zorder=20):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    if not np.any(ok):
        return
    x2 = x.copy()
    y2 = y.copy()
    x2[~ok] = np.nan
    y2[~ok] = np.nan
    plot_line(ax, x2, y2, color=color, linewidth=linewidth, alpha=alpha, linestyle=linestyle, zorder=zorder)


def _text_if_finite(ax, x, y, text, *, ha="center", va="center") -> None:
    if not (np.isfinite(x) and np.isfinite(y)):
        return
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    dx = abs(xmax - xmin)
    dy = abs(ymax - ymin)
    if x < min(xmin, xmax) - 0.04 * dx or x > max(xmin, xmax) + 0.04 * dx:
        return
    if y < min(ymin, ymax) - 0.04 * dy or y > max(ymin, ymax) + 0.04 * dy:
        return
    ax.text(
        x,
        y,
        text,
        fontsize=7,
        color="#405766",
        ha=ha,
        va=va,
        clip_on=True,
        zorder=30,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.55, "pad": 0.8},
    )


def _draw_2d_graticule_and_labels(controller) -> None:
    ax = getattr(controller, "_ax", None)
    if ax is None or _is_3d_axes(ax) or not _display_grid_enabled(controller):
        return
    page = controller.window.page_preview
    proj = pe._projection_key(controller, page.cmb_projection.currentText().strip())
    try:
        _path, _idx, _frame, grid, lon, lat = pe._grid_context(controller)
        grid, lon, lat, _bbox = pe._apply_bbox(controller, grid, lon, lat)
        lon0, lat0 = get_proj_center(lon, lat)
        lat1, lat2 = get_conic_parallels(float(np.nanmin(lat)), float(np.nanmax(lat)))
    except Exception:
        lon0, lat0, lat1, lat2 = 0.0, 0.0, 30.0, 60.0

    for lat_line in np.arange(-60, 61, 30):
        lons = np.linspace(-180, 180, 721)
        lats = np.full_like(lons, lat_line, dtype=float)
        if proj == "PlateCarree":
            x = normalize_lon_for_plot(lons)
            y = lats
        else:
            x, y = _project_line(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        _plot_2d_line(ax, x, y, linewidth=0.58, alpha=0.86)

    for lon_line in np.arange(-180, 181, 60):
        lats = np.linspace(-88, 88, 721)
        lons = np.full_like(lats, lon_line, dtype=float)
        if proj == "PlateCarree":
            x = normalize_lon_for_plot(lons)
            y = lats
        else:
            x, y = _project_line(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        _plot_2d_line(ax, x, y, linewidth=0.58, alpha=0.86)

    label_lat = -82.0
    for lon_line in np.arange(-120, 181, 60):
        if proj == "PlateCarree":
            x = float(normalize_lon_for_plot(np.asarray([lon_line]))[0])
            y = label_lat
        else:
            x_arr, y_arr = _project_line(controller, proj, np.asarray([lon_line]), np.asarray([label_lat]), lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
            x, y = float(x_arr[0]), float(y_arr[0])
        label = f"{abs(int(lon_line))}°{'W' if lon_line < 0 else ('E' if lon_line > 0 else '')}"
        _text_if_finite(ax, x, y, label, va="top")

    label_lon = -174.0
    for lat_line in np.arange(-60, 61, 30):
        if proj == "PlateCarree":
            x = float(normalize_lon_for_plot(np.asarray([label_lon]))[0])
            y = float(lat_line)
        else:
            x_arr, y_arr = _project_line(controller, proj, np.asarray([label_lon]), np.asarray([lat_line]), lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
            x, y = float(x_arr[0]), float(y_arr[0])
        label = f"{abs(int(lat_line))}°{'S' if lat_line < 0 else ('N' if lat_line > 0 else '')}"
        _text_if_finite(ax, x, y, label, ha="right")


def _draw_2d_coastlines(controller) -> None:
    ax = getattr(controller, "_ax", None)
    if ax is None or _is_3d_axes(ax) or not _display_coastlines_enabled(controller):
        return
    page = controller.window.page_preview
    proj = pe._projection_key(controller, page.cmb_projection.currentText().strip())
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
        try:
            _path, _idx, _frame, grid, lon, lat = pe._grid_context(controller)
            grid, lon, lat, _bbox = pe._apply_bbox(controller, grid, lon, lat)
            lon0, lat0 = get_proj_center(lon, lat)
            lat1, lat2 = get_conic_parallels(float(np.nanmin(lat)), float(np.nanmax(lat)))
        except Exception:
            lon0, lat0, lat1, lat2 = 0.0, 0.0, 30.0, 60.0
        reader = shapefile.Reader(shp_path)
        for shape in reader.shapes():
            points = np.asarray(shape.points, dtype=float)
            if points.ndim != 2 or points.shape[0] < 2:
                continue
            parts = list(shape.parts) + [len(points)]
            for i in range(len(parts) - 1):
                seg = points[parts[i] : parts[i + 1]]
                if seg.shape[0] < 2:
                    continue
                for lons, lats in split_dateline(seg[:, 0], seg[:, 1], wrap_delta_lon, lon0=lon0):
                    if proj == "PlateCarree":
                        x = normalize_lon_for_plot(lons)
                        y = lats
                    else:
                        x, y = _project_line(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                    _plot_2d_line(ax, x, y, color=_COAST_COLOR, linewidth=0.46, alpha=0.92, linestyle="-", zorder=31)
    except Exception:
        return


def _plot_3d_lonlat(ax, lons, lats, *, radius=1.07, color=_GRID_COLOR, linewidth=0.62, alpha=0.78, linestyle="--") -> None:
    lon_rad = np.deg2rad(np.asarray(lons, dtype=float))
    lat_rad = np.deg2rad(np.asarray(lats, dtype=float))
    x = radius * np.cos(lat_rad) * np.cos(lon_rad)
    y = radius * np.cos(lat_rad) * np.sin(lon_rad)
    z = radius * np.sin(lat_rad)
    ax.plot3D(x, y, z, color=color, linewidth=linewidth, alpha=alpha, linestyle=linestyle)


def _draw_3d_graticule_and_coastlines(controller) -> None:
    ax = getattr(controller, "_ax", None)
    if ax is None or not _is_3d_axes(ax):
        return
    if _display_grid_enabled(controller):
        for lat in np.arange(-60, 61, 30):
            lons = np.linspace(-180, 180, 361)
            _plot_3d_lonlat(ax, lons, np.full_like(lons, lat), radius=1.075, linewidth=0.62, alpha=0.75, linestyle="--")
        for lon in np.arange(-180, 181, 60):
            lats = np.linspace(-85, 85, 241)
            _plot_3d_lonlat(ax, np.full_like(lats, lon), lats, radius=1.075, linewidth=0.62, alpha=0.75, linestyle="--")

    if not _display_coastlines_enabled(controller):
        return
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
                    _plot_3d_lonlat(ax, seg[:, 0], seg[:, 1], radius=1.085, color=_COAST_COLOR, linewidth=0.70, alpha=0.95, linestyle="-")
    except Exception:
        return


def _post_render_polish(controller) -> None:
    fig = getattr(controller, "_figure", None)
    ax = getattr(controller, "_ax", None)
    if fig is None or ax is None:
        return
    if _is_3d_axes(ax):
        _draw_3d_graticule_and_coastlines(controller)
    else:
        _draw_2d_graticule_and_labels(controller)
        _draw_2d_coastlines(controller)
    _set_large_canvas_layout(controller)
    with contextlib.suppress(Exception):
        for cax in [item for item in fig.axes if item is not ax]:
            cax.set_ylabel(f"{controller.window.page_preview.cmb_data_var.currentText().strip() or 'value'} ({pe._current_unit(controller)})", fontsize=9)
            cax.tick_params(labelsize=8)
    restore_preview_header(controller.window)
    controller._canvas.draw_idle()


def install_preview_view_polish(window) -> None:
    """Install final preview view polishing hooks."""
    if getattr(window, "_preview_view_polish_installed", False):
        return
    _ensure_display_option_controls(window)
    controller = window.controller
    page = window.page_preview
    original_render = controller.on_render_preview

    def render_with_view_polish(self):
        result = original_render()
        _post_render_polish(self)
        return result

    controller.on_render_preview = MethodType(render_with_view_polish, controller)
    _safe_disconnect(page.btn_plot.clicked)
    page.btn_plot.clicked.connect(controller.on_render_preview)

    original_refresh = window.refresh_translations

    def refresh_with_display_labels(self):
        try:
            result = original_refresh()
            _sync_display_option_labels(self)
        except RuntimeError as exc:
            if not is_deleted_qt_object_error(exc):
                raise
            result = None
        return result

    window.refresh_translations = MethodType(refresh_with_display_labels, window)

    for signal in (page.cmb_projection.currentIndexChanged, page.slider_time_index.valueChanged, page.cmb_data_var.currentIndexChanged):
        with contextlib.suppress(Exception):
            signal.connect(lambda *_args, _controller=controller: restore_preview_header(_controller.window))
    window._preview_view_polish_installed = True
