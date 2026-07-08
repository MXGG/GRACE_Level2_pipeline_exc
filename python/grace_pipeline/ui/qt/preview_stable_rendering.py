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
import matplotlib.ticker as mticker

from grace_pipeline.infra.stack.loader import load_stack_slice_any
from grace_pipeline.ui.plotting.boundaries import draw_boundaries, plot_line, read_boundary_file, split_dateline
from grace_pipeline.ui.plotting.projections import (
    apply_proj_scale,
    get_conic_parallels,
    get_proj_center,
    normalize_lon_for_plot,
    parse_float,
    scale_projection,
    split_plot_lon_segments,
    wrap_delta_lon,
)
from grace_pipeline.ui.qt import preview_enhancements as pe
from grace_pipeline.ui.qt.preview_view_polish import _draw_graticule_frame, _graticule_options, _projection_accepts_rectangular_frame
from grace_pipeline.ui.qt.projection_registry import (
    is_global_extent,
    projection_default_extent,
    projection_name_to_key,
    projection_renderer,
    projection_spec,
    projection_supports_global_extent,
)
from grace_pipeline.ui.qt.preview_title_status import restore_preview_header

_GRID_COLOR = "#6f8fa3"
_COAST_COLOR = "#1f3547"
_RECTANGULAR_CARTOPY_KEYS = {"plate_carree", "mercator", "miller", "lambert_cylindrical"}


def _safe_disconnect(signal) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with contextlib.suppress(Exception):
            signal.disconnect()


def _show_layer(controller, layer_type: str, *, path: str | None = None, fallback: bool = True) -> bool:
    with contextlib.suppress(Exception):
        if hasattr(controller, "_preview_layer_visible"):
            return bool(controller._preview_layer_visible(layer_type, path=path))
    return bool(fallback)


def _visible_layers(controller, *layer_types: str):
    with contextlib.suppress(Exception):
        if hasattr(controller, "_preview_layers_by_type"):
            return controller._preview_layers_by_type(*layer_types, visible_only=True)
    return []


def _show_grid(controller) -> bool:
    page = controller.window.page_preview
    fallback = bool(getattr(page, "chk_layer_grid", None) and page.chk_layer_grid.isChecked())
    return _show_layer(controller, "graticule", fallback=fallback)


def _show_colorbar(controller) -> bool:
    page = controller.window.page_preview
    fallback = bool(getattr(page, "chk_show_colorbar", None) is None or page.chk_show_colorbar.isChecked())
    return _show_layer(controller, "colorbar", fallback=fallback)


def _show_coastlines(controller) -> bool:
    page = controller.window.page_preview
    fallback = bool(getattr(page, "chk_layer_coastlines", None) is None or page.chk_layer_coastlines.isChecked())
    return _show_layer(controller, "coastline", fallback=fallback)


def _show_base_raster(controller) -> bool:
    with contextlib.suppress(Exception):
        controller._ensure_preview_layers()
        return any(layer.type == "raster" and layer.path is None and layer.visible for layer in controller.preview_layers)
    page = controller.window.page_preview
    return bool(getattr(page, "chk_layer_data", None) is None or page.chk_layer_data.isChecked())


def _is_3d_label(page) -> bool:
    return projection_renderer(page.cmb_projection.currentText().strip()) == "matplotlib_3d"


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


def _label(ax, x, y, text, *, ha="center", va="center", fontsize=7, fontfamily=None) -> None:
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
        fontsize=fontsize,
        fontfamily=fontfamily,
        color="#405766",
        ha=ha,
        va=va,
        clip_on=True,
        zorder=35,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.55, "pad": 0.8},
    )


def _draw_graticule(controller, proj, lon0, lat0, lat1, lat2, zorder=25) -> None:
    if not _show_grid(controller):
        return
    ax = controller._ax
    opts = _graticule_options(controller)
    lat_lines = np.arange(-90 + opts["lat_interval"], 90, opts["lat_interval"])
    lon_lines = np.arange(-180, 180 + 0.1, opts["lon_interval"])
    for lat_line in lat_lines:
        lons = np.linspace(-180, 180, 721)
        lats = np.full_like(lons, lat_line, dtype=float)
        x, y = _project(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        _line(ax, x, y, color=opts["color"], linewidth=opts["linewidth"], alpha=0.86, linestyle=opts["linestyle"], zorder=zorder)
    for lon_line in lon_lines:
        lats = np.linspace(-88, 88, 721)
        lons = np.full_like(lats, lon_line, dtype=float)
        x, y = _project(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        _line(ax, x, y, color=opts["color"], linewidth=opts["linewidth"], alpha=0.86, linestyle=opts["linestyle"], zorder=zorder)

    if not opts["show_labels"]:
        if _projection_accepts_rectangular_frame(proj):
            _draw_graticule_frame(ax, opts)
        return

    label_lat = -82.0
    for lon_line in np.arange(-180 + opts["lon_interval"], 180 + 0.1, opts["lon_interval"]):
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
        _label(ax, float(x[0]), float(y[0]), text, va="top", fontsize=opts["font_size"], fontfamily=opts["font_family"])

    label_lon = -174.0
    for lat_line in lat_lines:
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
        _label(ax, float(x[0]), float(y[0]), text, ha="right", fontsize=opts["font_size"], fontfamily=opts["font_family"])
    if _projection_accepts_rectangular_frame(proj):
        _draw_graticule_frame(ax, opts)


def _draw_coastlines(controller, proj, lon0, lat0, lat1, lat2, zorder=32) -> None:
    if not _show_coastlines(controller):
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
                    _line(controller._ax, x, y, color=_COAST_COLOR, linewidth=0.44, alpha=0.92, zorder=zorder)
    except Exception:
        return


def _draw_boundary_layer(controller, layer, proj, lon0, lat0, lat1, lat2, bbox, zorder=40) -> None:
    path = str(getattr(layer, "path", "") or "")
    if not path or Path(path).suffix.lower() not in {".shp", ".bln", ".txt"}:
        return
    if not Path(path).exists():
        return
    with contextlib.suppress(Exception):
        boundaries = read_boundary_file(path)
        draw_boundaries(
            controller._ax,
            boundaries,
            proj=proj,
            lon0=lon0,
            lat0=lat0,
            lat1=lat1,
            lat2=lat2,
            bbox=bbox,
            normalize_lon_for_plot_cb=lambda arr: normalize_lon_for_plot(arr, lon_mode="-180_180"),
            split_dateline_cb=lambda lons, lats, lon0=0.0: split_dateline(lons, lats, wrap_delta_lon, lon0=lon0),
            split_plot_lon_segments_cb=lambda lons, lats, plate_carree=False: split_plot_lon_segments(
                lons,
                lats,
                split_dateline,
                lon0=lon0,
                plate_carree=plate_carree,
                lon_mode="-180_180",
            ),
            apply_proj_scale_cb=lambda xx: apply_proj_scale(xx, getattr(controller, "_proj_scale", None), getattr(controller, "_proj_x0", None)),
            plot_line_cb=lambda ax, x, y, **kwargs: plot_line(ax, x, y, **{**kwargs, "zorder": zorder}),
            projector_cb=controller._project,
        )


def _draw_boundary_layers(controller, proj, lon0, lat0, lat1, lat2, bbox) -> None:
    for layer in _visible_layers(controller, "boundary", "shapefile"):
        _draw_boundary_layer(controller, layer, proj, lon0, lat0, lat1, lat2, bbox)


def _draw_imported_raster_layer(controller, layer, idx, proj, lon0, lat0, lat1, lat2, cmap, cmin, cmax):
    page = controller.window.page_preview
    path = str(getattr(layer, "path", "") or "")
    if not path:
        return None
    if Path(path).suffix.lower() not in {".nc", ".nc4", ".cdf", ".h5", ".hdf5", ".hdf", ".mat"}:
        return None
    if not Path(path).exists():
        return None
    with contextlib.suppress(Exception):
        grid, lon, lat, _t_val, _meta = load_stack_slice_any(
            path,
            time_index=idx,
            active_var=page.cmb_data_var.currentText().strip() or None,
        )
        if grid is None or lon is None or lat is None:
            return None
        grid = np.asarray(grid, dtype=float)
        lon = np.asarray(lon, dtype=float).squeeze()
        lat = np.asarray(lat, dtype=float).squeeze()
        if grid.shape[0] != lon.size and grid.ndim >= 2 and grid.shape[1] == lon.size:
            grid = grid.T
        lon, grid = _normalize_grid_longitudes(lon, grid)
        lon2d, lat2d = np.meshgrid(lon, lat)
        grid_plot = grid.T if grid.shape == (lon.size, lat.size) else np.squeeze(grid)
        x, y = _project(controller, proj, lon2d, lat2d, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        alpha = float(getattr(layer, "opacity", 0.72) or 0.72)
        return controller._ax.pcolormesh(
            x,
            y,
            grid_plot,
            shading="auto",
            cmap=cmap,
            vmin=cmin,
            vmax=cmax,
            alpha=max(0.05, min(1.0, alpha)),
            zorder=int(getattr(layer, "zorder", 5) or 5),
        )
    return None


def _draw_imported_raster_layers(controller, idx, proj, lon0, lat0, lat1, lat2, cmap, cmin, cmax):
    first_im = None
    for layer in _visible_layers(controller, "raster"):
        if not getattr(layer, "path", None):
            continue
        im = _draw_imported_raster_layer(controller, layer, idx, proj, lon0, lat0, lat1, lat2, cmap, cmin, cmax)
        if first_im is None and im is not None:
            first_im = im
    return first_im


def _color_limits(page, grid_plot):
    cmin = parse_float(page.edit_cmin.text())
    cmax = parse_float(page.edit_cmax.text())
    return cmin, cmax


def _render_manual_2d(controller) -> None:
    page = controller.window.page_preview
    with contextlib.suppress(Exception):
        controller._ensure_preview_layers()
        controller._sync_preview_legacy_layer_controls()
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
    im = None
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

    layer_queue = []
    with contextlib.suppress(Exception):
        layer_queue = controller._preview_sorted_layers(visible_only=True)
    if not layer_queue:
        layer_queue = []

    for layer in layer_queue:
        layer_type = getattr(layer, "type", "")
        if layer_type == "raster" and not getattr(layer, "path", None):
            finite_xy = np.isfinite(x) & np.isfinite(y) & np.isfinite(grid_plot)
            if np.all(np.isfinite(x)) and np.all(np.isfinite(y)):
                im = ax.pcolormesh(
                    x,
                    y,
                    grid_plot,
                    shading="auto",
                    cmap=cmap,
                    vmin=cmin,
                    vmax=cmax,
                    zorder=int(getattr(layer, "zorder", 2) or 2),
                )
            elif np.any(finite_xy):
                im = ax.scatter(
                    x[finite_xy],
                    y[finite_xy],
                    c=grid_plot[finite_xy],
                    s=9,
                    marker="s",
                    linewidths=0,
                    cmap=cmap,
                    vmin=cmin,
                    vmax=cmax,
                    zorder=int(getattr(layer, "zorder", 2) or 2),
                )
        elif layer_type == "raster":
            overlay_im = _draw_imported_raster_layer(controller, layer, idx, proj, lon0, lat0, lat1, lat2, cmap, cmin, cmax)
            if im is None and overlay_im is not None:
                im = overlay_im
        elif layer_type == "coastline":
            _draw_coastlines(controller, proj, lon0, lat0, lat1, lat2, zorder=int(getattr(layer, "zorder", 32) or 32))
        elif layer_type == "graticule":
            _draw_graticule(controller, proj, lon0, lat0, lat1, lat2, zorder=int(getattr(layer, "zorder", 25) or 25))
        elif layer_type in {"boundary", "shapefile"}:
            _draw_boundary_layer(controller, layer, proj, lon0, lat0, lat1, lat2, _bbox, zorder=int(getattr(layer, "zorder", 40) or 40))

    if not layer_queue and _show_base_raster(controller):
        finite_xy = np.isfinite(x) & np.isfinite(y) & np.isfinite(grid_plot)
        if np.all(np.isfinite(x)) and np.all(np.isfinite(y)):
            im = ax.pcolormesh(x, y, grid_plot, shading="auto", cmap=cmap, vmin=cmin, vmax=cmax, zorder=2)
        elif np.any(finite_xy):
            im = ax.scatter(x[finite_xy], y[finite_xy], c=grid_plot[finite_xy], s=9, marker="s", linewidths=0, cmap=cmap, vmin=cmin, vmax=cmax, zorder=2)
        _draw_coastlines(controller, proj, lon0, lat0, lat1, lat2)
        _draw_graticule(controller, proj, lon0, lat0, lat1, lat2)
        _draw_boundary_layers(controller, proj, lon0, lat0, lat1, lat2, _bbox)

    if im is not None and _show_colorbar(controller):
        cbar = controller._figure.colorbar(im, ax=ax, shrink=0.78, pad=0.02)
        cbar.set_label(page.cmb_data_var.currentText().strip() or "value", fontsize=9)
        cbar.ax.tick_params(labelsize=8)

    # Larger default map view.  Leave room for a visible color scale only when it is enabled.
    if _show_colorbar(controller):
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


def _cartopy_crs_module():
    try:
        import cartopy.crs as ccrs

        return ccrs
    except Exception:
        return None


def _build_cartopy_crs(label: str, params: dict):
    ccrs = _cartopy_crs_module()
    if ccrs is None:
        return None
    spec = projection_spec(label)
    class_name = spec.get("crs_class")
    if not class_name:
        return None
    cls = getattr(ccrs, str(class_name), None)
    if cls is None:
        raise RuntimeError(f"Cartopy CRS class is not available: {class_name}")
    kwargs = {}
    for key in spec.get("crs_params", []):
        if key not in params:
            continue
        value = params[key]
        if key == "standard_parallels" and isinstance(value, (list, tuple)):
            value = tuple(float(item) for item in value[:2])
        kwargs[key] = value
    if class_name == "UTM":
        return cls(zone=int(kwargs.get("zone", 49)), southern_hemisphere=bool(kwargs.get("southern_hemisphere", False)))
    try:
        return cls(**kwargs)
    except TypeError:
        allowed = {"central_longitude", "central_latitude", "standard_parallels"}
        return cls(**{key: value for key, value in kwargs.items() if key in allowed})


def _polish_cartopy_frame(ax, label: str) -> None:
    """Avoid a Matplotlib rectangular frame around curved Cartopy projections."""

    key = projection_name_to_key(label)
    if key in _RECTANGULAR_CARTOPY_KEYS:
        return
    for name, spine in ax.spines.items():
        with contextlib.suppress(Exception):
            spine.set_visible(False)
    with contextlib.suppress(Exception):
        ax.set_frame_on(False)
    with contextlib.suppress(Exception):
        ax.patch.set_edgecolor("none")
        ax.patch.set_linewidth(0.0)
    with contextlib.suppress(Exception):
        ax.tick_params(left=False, right=False, bottom=False, top=False)


def _extent_from_page(controller) -> list[float]:
    page = controller.window.page_preview
    return [
        controller._safe_float(page.edit_region_lon_min.text(), -180.0),
        controller._safe_float(page.edit_region_lon_max.text(), 180.0),
        controller._safe_float(page.edit_region_lat_min.text(), -90.0),
        controller._safe_float(page.edit_region_lat_max.text(), 90.0),
    ]


def _resolve_projection_extent(controller, label: str, params: dict, bbox) -> tuple[list[float] | None, str | None]:
    spec = projection_spec(label)
    has_extent_param = "extent" in spec.get("view_params", [])
    if has_extent_param and isinstance(params.get("extent"), (list, tuple)) and len(params["extent"]) == 4:
        extent = [float(v) for v in params["extent"]]
    elif bbox is not None:
        extent = [float(v) for v in bbox]
    else:
        extent = _extent_from_page(controller)

    if not has_extent_param and spec.get("recommended_scope") == "global":
        return None, None

    if not projection_supports_global_extent(label) and is_global_extent(extent):
        default_extent = projection_default_extent(label)
        msg = (
            f"{spec.get('name', label)} is not recommended for global extent; "
            f"using default {default_extent}."
        )
        return default_extent, msg
    return extent, None


def _crop_grid_to_extent(grid, lon, lat, extent):
    if extent is None:
        return grid, lon, lat
    lon_min, lon_max, lat_min, lat_max = [float(v) for v in extent]
    lon_eval = normalize_lon_for_plot(lon, lon_mode="-180_180")
    if lon_min <= lon_max:
        lon_mask = (lon_eval >= lon_min) & (lon_eval <= lon_max)
    else:
        lon_mask = (lon_eval >= lon_min) | (lon_eval <= lon_max)
    lat_mask = (lat >= min(lat_min, lat_max)) & (lat <= max(lat_min, lat_max))
    if np.any(lon_mask) and np.any(lat_mask):
        return grid[np.ix_(lon_mask, lat_mask)], lon[lon_mask], lat[lat_mask]
    return grid, lon, lat


def _draw_cartopy_coastlines(controller, ax, data_crs, *, zorder: int) -> None:
    if not _show_coastlines(controller):
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
                    ax.plot(seg[:, 0], seg[:, 1], transform=data_crs, color=_COAST_COLOR, linewidth=0.44, alpha=0.92, zorder=zorder)
    except Exception as exc:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] Coastline layer failed: {exc}", "stderr")


def _draw_cartopy_graticule(controller, ax, data_crs, *, zorder: int) -> None:
    if not _show_grid(controller):
        return
    try:
        opts = _graticule_options(controller)
        gl = ax.gridlines(
            crs=data_crs,
            draw_labels=bool(opts["show_labels"]),
            linewidth=opts["linewidth"],
            color=opts["color"],
            alpha=0.76,
            linestyle=opts["linestyle"],
            zorder=zorder,
        )
        gl.xlocator = mticker.FixedLocator(np.arange(-180, 180 + 0.1, opts["lon_interval"]))
        gl.ylocator = mticker.FixedLocator(np.arange(-90, 90 + 0.1, opts["lat_interval"]))
        gl.top_labels = False
        gl.right_labels = False
        label_style = {"size": opts["font_size"], "color": "#405766"}
        if opts.get("font_family"):
            label_style["family"] = opts["font_family"]
        gl.xlabel_style = dict(label_style)
        gl.ylabel_style = dict(label_style)
    except Exception as exc:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] Graticule layer failed: {exc}", "stderr")


def _draw_cartopy_boundary_layer(controller, ax, data_crs, layer, *, zorder: int) -> None:
    path = str(getattr(layer, "path", "") or "")
    if not path or Path(path).suffix.lower() not in {".shp", ".bln", ".txt"} or not Path(path).exists():
        return
    try:
        boundaries = read_boundary_file(path)
        for boundary in boundaries:
            lons = np.asarray(getattr(boundary, "lon", []), dtype=float)
            lats = np.asarray(getattr(boundary, "lat", []), dtype=float)
            if lons.size >= 2 and lats.size >= 2:
                ax.plot(lons, lats, transform=data_crs, color="#b00020", linewidth=0.8, alpha=0.85, zorder=zorder)
    except Exception as exc:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] Boundary layer failed: {path}: {exc}", "stderr")


def _draw_cartopy_imported_raster(controller, ax, data_crs, layer, idx, cmap, cmin, cmax):
    page = controller.window.page_preview
    path = str(getattr(layer, "path", "") or "")
    if not path or Path(path).suffix.lower() not in {".nc", ".nc4", ".cdf", ".h5", ".hdf5", ".hdf", ".mat"} or not Path(path).exists():
        return None
    try:
        grid, lon, lat, _t_val, _meta = load_stack_slice_any(path, time_index=idx, active_var=page.cmb_data_var.currentText().strip() or None)
        if grid is None or lon is None or lat is None:
            return None
        grid = np.asarray(grid, dtype=float)
        lon = np.asarray(lon, dtype=float).squeeze()
        lat = np.asarray(lat, dtype=float).squeeze()
        if grid.shape[0] != lon.size and grid.ndim >= 2 and grid.shape[1] == lon.size:
            grid = grid.T
        lon, grid = _normalize_grid_longitudes(lon, grid)
        lon2d, lat2d = np.meshgrid(lon, lat)
        grid_plot = grid.T if grid.shape == (lon.size, lat.size) else np.squeeze(grid)
        return ax.pcolormesh(
            lon2d,
            lat2d,
            grid_plot,
            transform=data_crs,
            shading="auto",
            cmap=cmap,
            vmin=cmin,
            vmax=cmax,
            alpha=max(0.05, min(1.0, float(getattr(layer, "opacity", 0.72) or 0.72))),
            zorder=int(getattr(layer, "zorder", 5) or 5),
        )
    except Exception as exc:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] Raster overlay failed: {path}: {exc}", "stderr")
    return None


def _show_projection_error(controller, message: str) -> None:
    controller._figure.clear()
    ax = controller._figure.add_subplot(111)
    controller._ax = ax
    ax.set_axis_off()
    ax.text(
        0.5,
        0.52,
        "当前投影绘制失败，请检查投影参数或范围设置。",
        ha="center",
        va="center",
        fontsize=12,
        color="#b00020",
        transform=ax.transAxes,
    )
    ax.text(0.5, 0.44, message, ha="center", va="center", fontsize=9, color="#405766", transform=ax.transAxes, wrap=True)
    controller._canvas.draw_idle()


def _render_cartopy_2d(controller) -> None:
    page = controller.window.page_preview
    ccrs = _cartopy_crs_module()
    if ccrs is None:
        with contextlib.suppress(Exception):
            controller.on_log("[PREVIEW] Cartopy is not installed; using legacy 2D projection fallback.", "stderr")
        _render_manual_2d(controller)
        return

    with contextlib.suppress(Exception):
        controller._ensure_preview_layers()
        controller._sync_preview_legacy_layer_controls()
    start = time.perf_counter()
    label = page.cmb_projection.currentText().strip() or "Robinson"
    params = pe._projection_params(page, label)
    spec = projection_spec(label)
    path, idx, frame, grid, lon, lat, bbox = _frame_context(controller)
    extent, warning = _resolve_projection_extent(controller, label, params, bbox)
    if warning:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] {warning}", "stderr")
    if extent is not None and not spec.get("supports_global_extent", True):
        grid, lon, lat = _crop_grid_to_extent(grid, lon, lat, extent)
    if lon.size < 2 or lat.size < 2:
        raise RuntimeError("Selected extent does not contain enough grid cells.")

    lon2d, lat2d = np.meshgrid(lon, lat)
    grid_plot = grid.T if grid.shape == (lon.size, lat.size) else grid
    cmin, cmax = _color_limits(page, grid_plot)
    cmap = page.cmb_cmap.currentText().strip() or "RdBu_r"

    target_crs = _build_cartopy_crs(label, params)
    if target_crs is None:
        raise RuntimeError(f"Unsupported projection renderer: {label}")
    data_crs = ccrs.PlateCarree()

    controller._figure.clear()
    ax = controller._figure.add_subplot(111, projection=target_crs)
    controller._ax = ax
    _polish_cartopy_frame(ax, label)
    im = None
    layer_queue = []
    with contextlib.suppress(Exception):
        layer_queue = controller._preview_sorted_layers(visible_only=True)

    for layer in layer_queue:
        layer_type = getattr(layer, "type", "")
        zorder = int(getattr(layer, "zorder", 10) or 10)
        if layer_type == "raster" and not getattr(layer, "path", None):
            im = ax.pcolormesh(lon2d, lat2d, grid_plot, transform=data_crs, shading="auto", cmap=cmap, vmin=cmin, vmax=cmax, zorder=zorder)
        elif layer_type == "raster":
            overlay_im = _draw_cartopy_imported_raster(controller, ax, data_crs, layer, idx, cmap, cmin, cmax)
            if im is None and overlay_im is not None:
                im = overlay_im
        elif layer_type == "coastline":
            _draw_cartopy_coastlines(controller, ax, data_crs, zorder=zorder)
        elif layer_type == "graticule":
            _draw_cartopy_graticule(controller, ax, data_crs, zorder=zorder)
        elif layer_type in {"boundary", "shapefile"}:
            _draw_cartopy_boundary_layer(controller, ax, data_crs, layer, zorder=zorder)

    if not layer_queue and _show_base_raster(controller):
        im = ax.pcolormesh(lon2d, lat2d, grid_plot, transform=data_crs, shading="auto", cmap=cmap, vmin=cmin, vmax=cmax, zorder=2)
        _draw_cartopy_coastlines(controller, ax, data_crs, zorder=20)
        _draw_cartopy_graticule(controller, ax, data_crs, zorder=30)

    try:
        if extent is None:
            ax.set_global()
        else:
            ax.set_extent(extent, crs=data_crs)
    except Exception as exc:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] Extent failed for {label}: {extent}: {exc}", "stderr")

    if im is not None and _show_colorbar(controller):
        cbar = controller._figure.colorbar(im, ax=ax, shrink=0.78, pad=0.02)
        cbar.set_label(page.cmb_data_var.currentText().strip() or "value", fontsize=9)
        cbar.ax.tick_params(labelsize=8)

    ax.set_title("")
    _polish_cartopy_frame(ax, label)
    if _show_colorbar(controller):
        ax.set_position([0.035, 0.06, 0.80, 0.86])
        for cax in [item for item in controller._figure.axes if item is not ax]:
            cax.set_position([0.865, 0.18, 0.022, 0.64])
    else:
        ax.set_position([0.035, 0.06, 0.92, 0.86])

    controller._preview_pick_state = {
        "x": np.asarray(lon2d, dtype=float),
        "y": np.asarray(lat2d, dtype=float),
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
    with contextlib.suppress(Exception):
        controller._sync_preview_toolbar_mode()
    controller._canvas.draw_idle()


def _render_normalized_2d(controller) -> None:
    _render_cartopy_2d(controller)


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
            result = pe._render_3d_globe(self)
            _strip_colorbar_units(self)
            restore_preview_header(window)
            return result
        try:
            if not pe._handle_cpt_combo(self):
                return None
            _render_normalized_2d(self)
            return None
        except Exception as exc:
            label = page.cmb_projection.currentText().strip() or "Robinson"
            params = {}
            extent = None
            with contextlib.suppress(Exception):
                params = pe._projection_params(page, label)
                extent = params.get("extent") or _extent_from_page(self)
            projection_key = projection_name_to_key(label)
            with contextlib.suppress(Exception):
                self.on_log(
                    f"[PREVIEW] Projection render failed: key={projection_key}; params={params}; extent={extent}; error={exc}",
                    "stderr",
                )
            _show_projection_error(self, str(exc))
            self._show_error("Preview", f"当前投影绘制失败，请检查投影参数或范围设置。\n\n{exc}")
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
