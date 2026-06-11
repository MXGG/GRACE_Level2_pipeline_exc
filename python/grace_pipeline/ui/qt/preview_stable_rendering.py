"""Stable preview rendering for longitude-normalized global grids.

This renderer is installed last.  It avoids the common CSR Mascon/Level-3
longitude mismatch where data are stored on a 0..360 grid while coastlines and
annotations are drawn in -180..180 coordinates.
"""

from __future__ import annotations

import contextlib
import time
import warnings
from pathlib import Path
from types import MethodType

import numpy as np

from grace_pipeline.ui.plotting.boundaries import plot_line, split_dateline
from grace_pipeline.ui.plotting.projections import (
    apply_proj_scale,
    get_conic_parallels,
    get_proj_center,
    normalize_lon_for_plot,
    parse_float,
    scale_projection,
    wrap_delta_lon,
)
from grace_pipeline.ui.qt import preview_enhancements as pe
from grace_pipeline.ui.qt.preview_title_status import restore_preview_header

_GRID_COLOR = "#6f8fa3"
_COAST_COLOR = "#1f3547"


def _safe_disconnect(signal) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with contextlib.suppress(Exception):
            signal.disconnect()


def _show_grid(page) -> bool:
    if hasattr(page, "chk_show_graticule"):
        return page.chk_show_graticule.isChecked()
    return bool(getattr(page, "chk_layer_grid", None) and page.chk_layer_grid.isChecked())


def _show_colorbar(page) -> bool:
    if hasattr(page, "chk_show_colorbar"):
        return page.chk_show_colorbar.isChecked()
    return True


def _show_coastlines(page) -> bool:
    return bool(getattr(page, "chk_layer_coastlines", None) is None or page.chk_layer_coastlines.isChecked())


def _is_3d_label(page) -> bool:
    return page.cmb_projection.currentText().strip() == "3D Globe (Surface)"


def _normalize_grid_longitudes(lon: np.ndarray, grid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return longitude as -180..180 and reorder the first grid axis."""

    lon = np.asarray(lon, dtype=float).squeeze()
    grid = np.asarray(grid, dtype=float)
    lon_plot = normalize_lon_for_plot(lon)
    order = np.argsort(lon_plot)
    lon_sorted = lon_plot[order]
    if grid.shape[0] == lon.size:
        grid_sorted = grid[order, :]
    elif grid.ndim >= 2 and grid.shape[1] == lon.size:
        grid_sorted = grid[:, order].T
    else:
        grid_sorted = grid
    return lon_sorted, grid_sorted


def _frame_context(controller):
    page = controller.window.page_preview
    path, idx, frame, grid, lon, lat = pe._grid_context(controller)
    grid, lon, lat, bbox = pe._apply_bbox(controller, grid, lon, lat)
    lon_plot, grid = _normalize_grid_longitudes(lon, grid)
    lat = np.asarray(lat, dtype=float).squeeze()
    return path, idx, frame, grid, lon_plot, lat, bbox


def _project(controller, proj: str, lon, lat, *, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0):
    if proj == "PlateCarree":
        return np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
    x, y = controller._project(proj, lon, lat, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
    x = apply_proj_scale(x, getattr(controller, "_proj_scale", None), getattr(controller, "_proj_x0", None))
    return x, y


def _line(ax, x, y, *, color, linewidth, alpha=1.0, linestyle="-", zorder=20):
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


def _label(ax, x, y, text, *, ha="center", va="center") -> None:
    if not (np.isfinite(x) and np.isfinite(y)):
        return
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    dx = abs(xmax - xmin)
    dy = abs(ymax - ymin)
    if not (min(xmin, xmax) - 0.05 * dx <= x <= max(xmin, xmax) + 0.05 * dx):
        return
    if not (min(ymin, ymax) - 0.05 * dy <= y <= max(ymin, ymax) + 0.05 * dy):
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
        zorder=35,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.55, "pad": 0.8},
    )


def _draw_graticule(controller, proj, lon0, lat0, lat1, lat2) -> None:
    page = controller.window.page_preview
    if not _show_grid(page):
        return
    ax = controller._ax
    for lat_line in np.arange(-60, 61, 30):
        lons = np.linspace(-180, 180, 721)
        lats = np.full_like(lons, lat_line, dtype=float)
        x, y = _project(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        _line(ax, x, y, color=_GRID_COLOR, linewidth=0.58, alpha=0.86, linestyle="--", zorder=25)
    for lon_line in np.arange(-180, 181, 60):
        lats = np.linspace(-88, 88, 721)
        lons = np.full_like(lats, lon_line, dtype=float)
        x, y = _project(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        _line(ax, x, y, color=_GRID_COLOR, linewidth=0.58, alpha=0.86, linestyle="--", zorder=25)

    label_lat = -82.0
    for lon_line in np.arange(-120, 181, 60):
        x, y = _project(
            controller,
            proj,
            np.asarray([lon_line], dtype=float),
            np.asarray([label_lat], dtype=float),
            lon0=lon0,
            lat0=lat0,
            lat1=lat1,
            lat2=lat2,
        )
        text = f"{abs(int(lon_line))}°{'W' if lon_line < 0 else ('E' if lon_line > 0 else '')}"
        _label(ax, float(x[0]), float(y[0]), text, va="top")

    label_lon = -174.0
    for lat_line in np.arange(-60, 61, 30):
        x, y = _project(
            controller,
            proj,
            np.asarray([label_lon], dtype=float),
            np.asarray([lat_line], dtype=float),
            lon0=lon0,
            lat0=lat0,
            lat1=lat1,
            lat2=lat2,
        )
        text = f"{abs(int(lat_line))}°{'S' if lat_line < 0 else ('N' if lat_line > 0 else '')}"
        _label(ax, float(x[0]), float(y[0]), text, ha="right")


def _draw_coastlines(controller, proj, lon0, lat0, lat1, lat2) -> None:
    page = controller.window.page_preview
    if not _show_coastlines(page):
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
                if seg.shape[0] < 2:
                    continue
                for lons, lats in split_dateline(seg[:, 0], seg[:, 1], wrap_delta_lon, lon0=lon0):
                    x, y = _project(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                    _line(controller._ax, x, y, color=_COAST_COLOR, linewidth=0.44, alpha=0.92, zorder=32)
    except Exception:
        return


def _color_limits(page, grid_plot):
    cmin = parse_float(page.edit_cmin.text())
    cmax = parse_float(page.edit_cmax.text())
    return cmin, cmax


def _render_normalized_2d(controller) -> None:
    page = controller.window.page_preview
    start = time.perf_counter()
    path, idx, frame, grid, lon, lat, _bbox = _frame_context(controller)
    proj = pe._projection_key(controller, page.cmb_projection.currentText().strip())

    lon2d, lat2d = np.meshgrid(lon, lat)
    grid_plot = grid.T if grid.shape == (lon.size, lat.size) else grid
    lon0, lat0 = get_proj_center(lon, lat)
    lat1, lat2 = get_conic_parallels(float(np.nanmin(lat)), float(np.nanmax(lat)))

    if proj == "PlateCarree":
        x, y = lon2d, lat2d
        controller._proj_scale = None
        controller._proj_x0 = None
    else:
        x_raw, y_raw = controller._project(proj, lon2d, lat2d, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        x, y, controller._proj_scale, controller._proj_x0 = scale_projection(x_raw, y_raw, target_ratio=2.0)

    cmin, cmax = _color_limits(page, grid_plot)
    cmap = page.cmb_cmap.currentText().strip() or "RdBu_r"

    controller._figure.clear()
    ax = controller._figure.add_subplot(111)
    controller._ax = ax
    finite_xy = np.isfinite(x) & np.isfinite(y) & np.isfinite(grid_plot)
    im = None
    if np.all(np.isfinite(x)) and np.all(np.isfinite(y)):
        im = ax.pcolormesh(x, y, grid_plot, shading="auto", cmap=cmap, vmin=cmin, vmax=cmax, zorder=2)
    elif np.any(finite_xy):
        im = ax.scatter(x[finite_xy], y[finite_xy], c=grid_plot[finite_xy], s=9, marker="s", linewidths=0, cmap=cmap, vmin=cmin, vmax=cmax, zorder=2)

    ax.set_axis_off()
    finite = np.isfinite(x) & np.isfinite(y)
    if np.any(finite):
        xmin, xmax = float(np.nanmin(x[finite])), float(np.nanmax(x[finite]))
        ymin, ymax = float(np.nanmin(y[finite])), float(np.nanmax(y[finite]))
        xr = max(1e-9, xmax - xmin)
        yr = max(1e-9, ymax - ymin)
        ax.set_xlim(xmin - 0.045 * xr, xmax + 0.045 * xr)
        ax.set_ylim(ymin - 0.07 * yr, ymax + 0.07 * yr)
        controller._preview_full_view = (xmin - 0.045 * xr, xmax + 0.045 * xr, ymin - 0.07 * yr, ymax + 0.07 * yr)

    _draw_graticule(controller, proj, lon0, lat0, lat1, lat2)
    _draw_coastlines(controller, proj, lon0, lat0, lat1, lat2)

    if im is not None and _show_colorbar(page):
        cbar = controller._figure.colorbar(im, ax=ax, shrink=0.78, pad=0.02)
        cbar.set_label(page.cmb_data_var.currentText().strip() or "value", fontsize=9)
        cbar.ax.tick_params(labelsize=8)

    # Larger default map view.  Leave room for a visible color scale only when it is enabled.
    if _show_colorbar(page):
        ax.set_position([0.035, 0.06, 0.80, 0.86])
        for cax in [item for item in controller._figure.axes if item is not ax]:
            cax.set_position([0.865, 0.18, 0.022, 0.64])
    else:
        ax.set_position([0.035, 0.06, 0.92, 0.86])

    controller._preview_pick_state = {
        "x": np.asarray(x, dtype=float),
        "y": np.asarray(y, dtype=float),
        "lon": np.asarray(lon2d, dtype=float),
        "lat": np.asarray(lat2d, dtype=float),
        "grid": np.asarray(grid_plot, dtype=float),
    }

    active_var_name = frame.get("meta", {}).get("active_var", page.cmb_data_var.currentText().strip() or "value")
    page.lbl_dataset.setText(f"{Path(path).name} | {active_var_name}")
    finite_grid = np.isfinite(grid)
    page.lbl_grid_value.setText(f"{float(np.nanmean(grid[finite_grid])):.3f}" if np.any(finite_grid) else "NaN")
    page.lbl_engine_latency.setText(f"{(time.perf_counter() - start) * 1000.0:.1f} ms")
    restore_preview_header(controller.window)
    controller._canvas.draw_idle()


def _strip_colorbar_units(controller) -> None:
    fig = getattr(controller, "_figure", None)
    ax = getattr(controller, "_ax", None)
    if fig is None or ax is None:
        return
    label = controller.window.page_preview.cmb_data_var.currentText().strip() or "value"
    for cax in [item for item in fig.axes if item is not ax]:
        with contextlib.suppress(Exception):
            cax.set_ylabel(label, fontsize=9)


def install_preview_stable_rendering(window) -> None:
    """Install the final rendering hook after all preview UI polish hooks."""

    if getattr(window, "_preview_stable_rendering_installed", False):
        return
    controller = window.controller
    page = window.page_preview
    previous_render = controller.on_render_preview

    def render(self):
        if _is_3d_label(page):
            result = previous_render()
            _strip_colorbar_units(self)
            restore_preview_header(window)
            return result
        try:
            if not pe._handle_cpt_combo(self):
                return None
            _render_normalized_2d(self)
            return None
        except Exception as exc:
            self._show_error("Preview", str(exc))
            return None

    controller.on_render_preview = MethodType(render, controller)
    _safe_disconnect(page.btn_plot.clicked)
    page.btn_plot.clicked.connect(controller.on_render_preview)
    for signal in (
        getattr(page, "chk_show_graticule", None),
        getattr(page, "chk_show_colorbar", None),
        getattr(page, "chk_layer_coastlines", None),
        getattr(page, "chk_layer_grid", None),
    ):
        if signal is not None:
            with contextlib.suppress(Exception):
                signal.toggled.connect(lambda *_args, _controller=controller: _controller.on_render_preview())
    window._preview_stable_rendering_installed = True
